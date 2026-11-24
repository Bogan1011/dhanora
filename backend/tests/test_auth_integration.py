"""Opt-in integration tests. Use a fresh, isolated PostgreSQL schema."""
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from app.db import database_url
from app.main import app
from app.models import Base, User, Family, FamilyMember, AuthSession, AuditLog
from app.security import hash_password, digest

pytestmark = pytest.mark.skipif(os.getenv("DHANORA_RUN_DB_TESTS") != "1", reason="Opt in to isolated PostgreSQL integration tests")
ORIGIN = "https://dhanora.test"
EMAIL = "owner@example.com"
PASSWORD = "test-only-password-123!"

@pytest.fixture
def db_client(monkeypatch):
    schema = "test_" + uuid.uuid4().hex
    admin_engine = create_engine(database_url())
    test_engine = None
    try:
        with admin_engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
        test_engine = create_engine(database_url(), connect_args={"options": f"-c search_path={schema}"})
        Base.metadata.create_all(test_engine)
        with Session(test_engine) as db, db.begin():
            user = User(email=EMAIL, display_name="Test owner", password_hash=hash_password(PASSWORD))
            own = Family(name="Own family")
            other = Family(name="Unrelated family")
            db.add_all([user, own, other])
            db.flush()
            db.add(FamilyMember(user_id=user.id, family_id=own.id, role="owner"))
        monkeypatch.setattr(app.state, "engine", test_engine, raising=False)
        monkeypatch.setenv("APP_ORIGIN", ORIGIN)
        yield TestClient(app, base_url=ORIGIN), test_engine
    finally:
        if test_engine is not None:
            test_engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        admin_engine.dispose()

def test_session_lifecycle_and_family_scope(db_client):
    client, engine = db_client
    assert client.get("/api/v1/auth/me").status_code == 401
    login = client.post("/api/v1/auth/login", headers={"Origin": ORIGIN}, json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200
    cookie = login.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    token = client.cookies.get("__Host-dhanora_session")
    assert token
    with Session(engine) as db:
        session = db.scalar(select(AuthSession))
        assert session.token_hash == digest(token)
        assert session.token_hash != token
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert [(f["name"], f["role"]) for f in me.json()["families"]] == [("Own family", "owner")]
    assert client.post("/api/v1/auth/logout", headers={"Origin": "https://unrelated.invalid"}).status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN}).status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    # Replaying the revoked token must fail server-side.
    client.cookies.set("__Host-dhanora_session", token, domain="dhanora.test", path="/")
    assert client.get("/api/v1/auth/me").status_code == 401
    with Session(engine) as db:
        assert db.scalar(select(AuthSession)) is None
        assert set(db.scalars(select(AuditLog.event))) == {"login_success", "logout"}

def test_invalid_credentials_and_rate_limit(db_client):
    client, _ = db_client
    for _ in range(5):
        result = client.post("/api/v1/auth/login", headers={"Origin": ORIGIN}, json={"email": EMAIL, "password": "wrong"})
        assert result.status_code == 401
    result = client.post("/api/v1/auth/login", headers={"Origin": ORIGIN}, json={"email": EMAIL, "password": PASSWORD})
    assert result.status_code == 429
    assert client.get("/api/v1/auth/me").status_code == 401
