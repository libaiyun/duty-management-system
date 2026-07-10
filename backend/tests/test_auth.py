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


# --- M2-P1-T3: password change / reset ---


def _login(api_client: TestClient, username: str, password: str) -> str:
    resp = api_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def test_change_password_success(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    db_session.commit()
    token = _login(api_client, "admin", "password123")

    resp = api_client.put(
        "/api/v1/auth/password",
        json={"old_password": "password123", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    assert resp.json()["message"] == "密码修改成功"


def test_change_password_wrong_old(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    db_session.commit()
    token = _login(api_client, "admin", "password123")

    resp = api_client.put(
        "/api/v1/auth/password",
        json={"old_password": "wrongpass", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "BUSINESS_RULE_FAILED"


def test_change_password_same_as_old(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    db_session.commit()
    token = _login(api_client, "admin", "password123")

    resp = api_client.put(
        "/api/v1/auth/password",
        json={"old_password": "password123", "new_password": "password123"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 422


def test_login_with_new_password_after_change(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    db_session.commit()
    token = _login(api_client, "admin", "password123")

    api_client.put(
        "/api/v1/auth/password",
        json={"old_password": "password123", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = api_client.post("/api/v1/auth/login", json={"username": "admin", "password": "newpass456"})

    assert resp.status_code == 200


def test_login_with_old_password_fails_after_change(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    db_session.commit()
    token = _login(api_client, "admin", "password123")

    api_client.put(
        "/api/v1/auth/password",
        json={"old_password": "password123", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = api_client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"})

    assert resp.status_code == 401


def test_change_password_requires_auth(api_client: TestClient) -> None:
    resp = api_client.put(
        "/api/v1/auth/password",
        json={"old_password": "password123", "new_password": "newpass456"},
    )

    assert resp.status_code == 401


def test_reset_password_success(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    target = create_user(db_session, "target", "targetpass", "用户")
    db_session.commit()
    token = _login(api_client, "admin", "password123")

    resp = api_client.post(
        "/api/v1/auth/password/reset",
        json={"user_id": target.id, "new_password": "resetpass789"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    assert resp.json()["message"] == "密码重置成功"


def test_reset_password_user_not_found(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    db_session.commit()
    token = _login(api_client, "admin", "password123")

    resp = api_client.post(
        "/api/v1/auth/password/reset",
        json={"user_id": 99999, "new_password": "resetpass789"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 404


def test_reset_password_requires_auth(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/v1/auth/password/reset",
        json={"user_id": 1, "new_password": "resetpass789"},
    )

    assert resp.status_code == 401


def test_login_with_new_password_after_reset(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    target = create_user(db_session, "target", "targetpass", "用户")
    db_session.commit()
    token = _login(api_client, "admin", "password123")

    api_client.post(
        "/api/v1/auth/password/reset",
        json={"user_id": target.id, "new_password": "resetpass789"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = api_client.post("/api/v1/auth/login", json={"username": "target", "password": "resetpass789"})

    assert resp.status_code == 200


def test_login_with_old_password_fails_after_reset(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    target = create_user(db_session, "target", "targetpass", "用户")
    db_session.commit()
    token = _login(api_client, "admin", "password123")

    api_client.post(
        "/api/v1/auth/password/reset",
        json={"user_id": target.id, "new_password": "resetpass789"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = api_client.post("/api/v1/auth/login", json={"username": "target", "password": "targetpass"})

    assert resp.status_code == 401


def test_reset_password_on_disabled_user(api_client: TestClient, db_session) -> None:
    create_user(db_session, "admin", "password123", "管理员")
    target = create_user(db_session, "target", "targetpass", "用户")
    target.status = "disabled"
    db_session.commit()
    old_hash = target.password_hash
    token = _login(api_client, "admin", "password123")

    resp = api_client.post(
        "/api/v1/auth/password/reset",
        json={"user_id": target.id, "new_password": "resetpass789"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    db_session.refresh(target)
    assert target.password_hash != old_hash

    resp = api_client.post("/api/v1/auth/login", json={"username": "target", "password": "resetpass789"})
    assert resp.status_code == 401

    target.status = "enabled"
    db_session.commit()
    resp = api_client.post("/api/v1/auth/login", json={"username": "target", "password": "resetpass789"})
    assert resp.status_code == 200
