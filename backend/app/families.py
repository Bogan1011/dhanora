"""Family-scoped membership operations. Never trust a role from the client."""
import secrets
from datetime import timedelta
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update, text
from sqlalchemy.orm import Session
from app.auth import check_origin, current_session, now, COOKIE
from app.models import User, FamilyMember, FamilyInvitation, AuditLog
from app.security import digest, hash_password

router = APIRouter(prefix="/api/v1", tags=["families"])
Role = Literal["admin", "member", "viewer"]

class InviteInput(BaseModel):
    email: EmailStr = Field(max_length=254)
    role: Role = "member"

class RoleInput(BaseModel):
    role: Role

class AcceptInput(BaseModel):
    code: str = Field(min_length=43, max_length=43)
    display_name: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, min_length=12, max_length=128)

def lock_changes(db):
    # Small private deployment: serialize all family mutations to protect role and invitation invariants.
    db.execute(text("SELECT pg_advisory_xact_lock(62002003)"))

def membership(db, family_id, user_id):
    member = db.get(FamilyMember, (family_id, user_id))
    if not member:
        raise HTTPException(404, "Family not found")
    return member

def can_manage(actor, role):
    return role != "owner" and (actor.role == "owner" or (actor.role == "admin" and role in {"member", "viewer"}))

def require_manager(actor):
    if actor.role not in {"owner", "admin"}:
        raise HTTPException(403, "Insufficient permissions")

def invite_info(inv):
    status = "accepted" if inv.accepted_at else "revoked" if inv.revoked_at else "expired" if inv.expires_at <= now() else "pending"
    return {"id": str(inv.id), "email": inv.email, "role": inv.role, "status": status, "expires_at": inv.expires_at.isoformat()}

def revoke_issued(db, family_id, user_id):
    db.execute(update(FamilyInvitation).where(FamilyInvitation.family_id == family_id, FamilyInvitation.invited_by == user_id, FamilyInvitation.accepted_at.is_(None), FamilyInvitation.revoked_at.is_(None)).values(revoked_at=now()))

@router.get("/families/{family_id}/members")
def list_members(family_id: UUID, request: Request):
    check_origin(request)
    with Session(request.app.state.engine) as db:
        _, user = current_session(request, db)
        membership(db, family_id, user.id)
        rows = db.execute(select(User, FamilyMember.role).join(FamilyMember, User.id == FamilyMember.user_id).where(FamilyMember.family_id == family_id).order_by(User.display_name)).all()
        return [{"id": str(u.id), "display_name": u.display_name, "role": role} for u, role in rows]

@router.get("/families/{family_id}/invitations")
def list_invites(family_id: UUID, request: Request):
    check_origin(request)
    with Session(request.app.state.engine) as db:
        _, user = current_session(request, db)
        actor = membership(db, family_id, user.id)
        require_manager(actor)
        rows = db.scalars(select(FamilyInvitation).where(FamilyInvitation.family_id == family_id).order_by(FamilyInvitation.created_at.desc()).limit(100))
        return [invite_info(i) for i in rows if can_manage(actor, i.role)]

@router.post("/families/{family_id}/invitations", status_code=201)
def create_invite(family_id: UUID, payload: InviteInput, request: Request):
    check_origin(request, write=True)
    with Session(request.app.state.engine) as db:
        lock_changes(db)
        _, user = current_session(request, db)
        actor = membership(db, family_id, user.id)
        if not can_manage(actor, payload.role):
            raise HTTPException(403, "Insufficient permissions")
        email = str(payload.email).casefold()
        existing = db.scalar(select(User).where(User.email == email))
        if existing and db.get(FamilyMember, (family_id, existing.id)):
            raise HTTPException(409, "Already a family member")
        pending = db.scalars(select(FamilyInvitation).where(FamilyInvitation.family_id == family_id, FamilyInvitation.email == email, FamilyInvitation.accepted_at.is_(None), FamilyInvitation.revoked_at.is_(None), FamilyInvitation.expires_at > now())).all()
        if pending:
            raise HTTPException(409, "Pending invitation already exists; revoke it first")
        code = secrets.token_urlsafe(32)
        invitation = FamilyInvitation(family_id=family_id, invited_by=user.id, email=email, role=payload.role, token_hash=digest(code), expires_at=now()+timedelta(hours=24))
        db.add(invitation)
        db.add(AuditLog(user_id=user.id, event="family_invite_created"))
        db.flush()
        result = {**invite_info(invitation), "code": code}
        db.commit()
        return result

@router.delete("/families/{family_id}/invitations/{invite_id}")
def revoke_invite(family_id: UUID, invite_id: UUID, request: Request):
    check_origin(request, write=True)
    with Session(request.app.state.engine) as db:
        lock_changes(db)
        _, user = current_session(request, db)
        actor = membership(db, family_id, user.id)
        require_manager(actor)
        inv = db.get(FamilyInvitation, invite_id)
        if not inv or inv.family_id != family_id:
            raise HTTPException(404, "Invitation not found")
        if not can_manage(actor, inv.role):
            raise HTTPException(403, "Insufficient permissions")
        if inv.accepted_at:
            raise HTTPException(409, "Invitation already accepted")
        inv.revoked_at = now()
        db.add(AuditLog(user_id=user.id, event="family_invite_revoked"))
        db.commit()
        return {"status": "revoked"}

@router.post("/invitations/accept")
def accept_invite(payload: AcceptInput, request: Request):
    check_origin(request, write=True)
    with Session(request.app.state.engine) as db:
        lock_changes(db)
        inv = db.scalar(select(FamilyInvitation).where(FamilyInvitation.token_hash == digest(payload.code)))
        if not inv or inv.accepted_at or inv.revoked_at or inv.expires_at <= now():
            raise HTTPException(400, "Invalid or expired invitation")
        issuer = db.get(FamilyMember, (inv.family_id, inv.invited_by))
        if not issuer or not can_manage(issuer, inv.role):
            raise HTTPException(400, "Invalid or expired invitation")
        user = db.scalar(select(User).where(User.email == inv.email))
        if user:
            _, signed_in = current_session(request, db)
            if signed_in.id != user.id:
                raise HTTPException(403, "Sign in as the invited account")
        else:
            if request.cookies.get(COOKIE):
                raise HTTPException(409, "Sign out before creating a new account")
            name = (payload.display_name or "").strip()
            if not name or not payload.password:
                raise HTTPException(400, "Display name and password required for new account")
            user = User(email=inv.email, display_name=name, password_hash=hash_password(payload.password))
            db.add(user)
            db.flush()
        if db.get(FamilyMember, (inv.family_id, user.id)):
            raise HTTPException(409, "Already a family member")
        db.add(FamilyMember(family_id=inv.family_id, user_id=user.id, role=inv.role))
        inv.accepted_at = now()
        db.add(AuditLog(user_id=user.id, event="family_invite_accepted"))
        db.commit()
        return {"status": "accepted"}

@router.patch("/families/{family_id}/members/{user_id}")
def change_role(family_id: UUID, user_id: UUID, payload: RoleInput, request: Request):
    check_origin(request, write=True)
    with Session(request.app.state.engine) as db:
        lock_changes(db)
        _, user = current_session(request, db)
        actor = membership(db, family_id, user.id)
        target = membership(db, family_id, user_id)
        if user.id == user_id or not can_manage(actor, target.role) or not can_manage(actor, payload.role):
            raise HTTPException(403, "Insufficient permissions")
        if target.role != payload.role:
            revoke_issued(db, family_id, target.user_id)
            target.role = payload.role
            db.add(AuditLog(user_id=user.id, event="family_role_changed"))
        db.commit()
        return {"status": "updated"}

@router.delete("/families/{family_id}/members/{user_id}")
def remove_member(family_id: UUID, user_id: UUID, request: Request):
    check_origin(request, write=True)
    with Session(request.app.state.engine) as db:
        lock_changes(db)
        _, user = current_session(request, db)
        actor = membership(db, family_id, user.id)
        target = membership(db, family_id, user_id)
        if user.id == user_id or not can_manage(actor, target.role):
            raise HTTPException(403, "Insufficient permissions")
        revoke_issued(db, family_id, target.user_id)
        db.delete(target)
        db.add(AuditLog(user_id=user.id, event="family_member_removed"))
        db.commit()
        return {"status": "removed"}
