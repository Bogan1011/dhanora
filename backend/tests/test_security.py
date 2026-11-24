from fastapi.testclient import TestClient
from app.main import app
from app.security import hash_password, verify_password, digest

def test_argon2():
    password = "development-test-only!"
    encoded = hash_password(password)
    assert encoded.startswith("$argon2id$")
    assert verify_password(password, encoded)
    assert not verify_password("incorrect", encoded)
    assert len(digest("sample")) == 64

def test_cross_origin_blocked(monkeypatch):
    monkeypatch.setenv("APP_ORIGIN", "http://localhost:18080")
    client = TestClient(app, base_url="http://localhost:18080")
    assert client.post("/api/v1/auth/login", headers={"Origin":"https://elsewhere.invalid"}, json={"email":"test@example.com","password":"example"}).status_code == 403

def test_direct_ip_blocked(monkeypatch):
    monkeypatch.setenv("APP_ORIGIN", "http://localhost:18080")
    client = TestClient(app, base_url="http://192.0.2.1:18080")
    assert client.get("/api/v1/auth/me").status_code == 403
