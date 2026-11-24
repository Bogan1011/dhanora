from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from app.main import app

def test_health():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok", "service": "dhanora"}

def test_status():
    client = TestClient(app)
    assert client.get("/api/v1/status").json()["ai"] == "disabled"

def test_ready_with_migrated_database(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=__import__("sqlalchemy").pool.StaticPool)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('0002_authentication')"))
    monkeypatch.setattr(app.state, "engine", engine, raising=False)
    try:
        assert TestClient(app).get("/ready").status_code == 200
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM alembic_version"))
        assert TestClient(app).get("/ready").status_code == 503
    finally:
        engine.dispose()
