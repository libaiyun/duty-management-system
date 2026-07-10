import pytest
from fastapi.testclient import TestClient

from app.services.auth import create_user

pytestmark = pytest.mark.usefixtures("create_tables")


def test_login_success(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    db_session.commit()

    resp = api_client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "OK"
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]
    assert data["data"]["token_type"] == "bearer"


def test_login_wrong_password(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    db_session.commit()

    resp = api_client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})

    assert resp.status_code == 401
    data = resp.json()
    assert data["code"] == "UNAUTHORIZED"


def test_login_nonexistent_user(api_client: TestClient) -> None:
    resp = api_client.post("/api/v1/auth/login", json={"username": "nobody", "password": "x"})

    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_login_empty_username(api_client: TestClient) -> None:
    resp = api_client.post("/api/v1/auth/login", json={"username": "", "password": "x"})

    assert resp.status_code == 400
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_refresh_token(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    db_session.commit()

    login_resp = api_client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"})
    refresh_token = login_resp.json()["data"]["refresh_token"]

    resp = api_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "OK"
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]


def test_refresh_with_access_token_fails(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    db_session.commit()

    login_resp = api_client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"})
    access_token = login_resp.json()["data"]["access_token"]

    resp = api_client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})

    assert resp.status_code == 401


def test_refresh_with_invalid_token(api_client: TestClient) -> None:
    resp = api_client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid-token"})

    assert resp.status_code == 401


def test_logout(api_client: TestClient) -> None:
    resp = api_client.post("/api/v1/auth/logout")

    assert resp.status_code == 200
    assert resp.json()["message"] == "已退出登录"


def test_me_requires_auth(api_client: TestClient) -> None:
    resp = api_client.get("/api/v1/auth/me")

    assert resp.status_code == 401


def test_me_returns_user_info(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    db_session.commit()

    login_resp = api_client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"})
    access_token = login_resp.json()["data"]["access_token"]

    resp = api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "OK"
    assert data["data"]["username"] == "admin"
    assert data["data"]["display_name"] == "管理员"
    assert data["data"]["status"] == "enabled"


def test_me_with_invalid_token(api_client: TestClient) -> None:
    resp = api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert resp.status_code == 401
