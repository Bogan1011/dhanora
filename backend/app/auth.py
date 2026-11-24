import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, delete, text
from sqlalchemy.orm import Session
from app.models import User, Family, FamilyMember, AuthSession, LoginAttempt, AuditLog
from app.security import digest, verify_password, DUMMY_HASH

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
COOKIE = "__Host-dhanora_session"
SESSION_AGE = 12 * 60 * 60
WINDOW = timedelta(minutes=5)

class LoginInput(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

def now():
    return datetime.now(timezone.utc)

def check_origin(request: Request, write: bool = False):
    origin = os.environ.get("APP_ORIGIN", "http://localhost:18080")
    parsed = urlsplit(origin)
    # HTTP is permitted only for localhost via a private SSH tunnel.
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname == "localhost"):
        raise HTTPException(503, "Authentication origin is not configured securely")
    if request.headers.get("host") != parsed.netloc:
        raise HTTPException(403, "Use the configured private application address")
    if write and request.headers.get("origin") != origin:
        raise HTTPException(403, "Invalid request origin")

def consume_attempt(db: Session, email: str):
    # Transaction-scoped lock serializes rate counters across worker processes.
    db.execute(text("SELECT pg_advisory_xact_lock(62002001)"))
    current = now()
    limits = [("global", 30), (digest(email), 5)]
    rows = []
    for key, limit in limits:
        row = db.get(LoginAttempt, key)
        if row is None:
            row = LoginAttempt(key=key, window_start=current, count=0)
            db.add(row)
        if current - row.window_start >= WINDOW:
            row.window_start, row.count = current, 0
        if row.count >= limit:
            db.rollback()
            raise HTTPException(429, "Too many login attempts; try again in five minutes", headers={"Retry-After": "300"})
        rows.append(row)
    for row in rows:
        row.count += 1
    db.execute(delete(LoginAttempt).where(LoginAttempt.window_start < current - timedelta(days=1)))
    db.commit()

def current_session(request: Request, db: Session):
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 128:
        raise HTTPException(401, "Sign in required")
    session = db.get(AuthSession, digest(token))
    if not session or session.expires_at <= now():
        raise HTTPException(401, "Session expired or invalid")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Sign in required")
    return session, user

def profile(db: Session, user: User):
    memberships = db.execute(select(Family, FamilyMember.role).join(FamilyMember, Family.id == FamilyMember.family_id).where(FamilyMember.user_id == user.id)).all()
    return {"id": str(user.id), "display_name": user.display_name, "email": user.email,
            "families": [{"id": str(f.id), "name": f.name, "role": role} for f, role in memberships]}

@router.post("/login")
def login(payload: LoginInput, request: Request, response: Response):
    check_origin(request, write=True)
    email = str(payload.email).casefold()
    with Session(request.app.state.engine) as db:
        consume_attempt(db, email)
        user = db.scalar(select(User).where(User.email == email))
        valid = verify_password(payload.password, user.password_hash if user else DUMMY_HASH)
        if not user or not valid:
            db.add(AuditLog(event="login_failed", user_id=user.id if user else None))
            db.commit()
            raise HTTPException(401, "Invalid email or password")
        token = secrets.token_urlsafe(32)
        previous = request.cookies.get(COOKIE)
        if previous and len(previous) <= 128:
            db.execute(delete(AuthSession).where(AuthSession.token_hash == digest(previous), AuthSession.user_id == user.id))
        db.execute(delete(AuthSession).where(AuthSession.expires_at <= now()))
        db.add(AuthSession(token_hash=digest(token), user_id=user.id, expires_at=now() + timedelta(seconds=SESSION_AGE)))
        db.add(AuditLog(event="login_success", user_id=user.id))
        result = profile(db, user)
        db.commit()
    response.set_cookie(COOKIE, token, max_age=SESSION_AGE, httponly=True, secure=True, samesite="strict", path="/")
    response.headers["Cache-Control"] = "no-store"
    return result

@router.get("/me")
def me(request: Request, response: Response):
    check_origin(request)
    with Session(request.app.state.engine) as db:
        _, user = current_session(request, db)
        response.headers["Cache-Control"] = "no-store"
        return profile(db, user)

@router.post("/logout")
def logout(request: Request, response: Response):
    check_origin(request, write=True)
    with Session(request.app.state.engine) as db:
        token = request.cookies.get(COOKIE)
        session = db.get(AuthSession, digest(token)) if token and len(token) <= 128 else None
        if session:
            db.add(AuditLog(event="logout", user_id=session.user_id))
            db.delete(session)
            db.commit()
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
    response.headers["Cache-Control"] = "no-store"
    return {"status": "signed_out"}
