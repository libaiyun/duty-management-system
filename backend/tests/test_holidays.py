import pytest
from app.models.holiday import HolidayCalendar, RefundStandard
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.user import SysPermission, SysRole
from app.services.auth import create_user
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(api_client: TestClient, db_session, username: str, password: str) -> str:
    resp = api_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _create_admin(api_client: TestClient, db_session) -> tuple[int, str]:
    room = OrgUnit(code="room-1", name="测试机房", type="room")
    db_session.add(room)
    db_session.flush()
    person = Person(code="P001", name="管理员", person_type="director", org_unit_id=room.id)
    db_session.add(person)
    db_session.flush()
    user = create_user(db_session, "admin", "password123", "管理员")
    user.person_id = person.id
    permissions = [
        SysPermission(code="holiday:standard:view", name="View Holiday", type="api"),
        SysPermission(code="holiday:standard:manage", name="Manage Standard", type="api"),
        SysPermission(code="holiday:global:manage", name="Manage Holiday", type="api"),
    ]
    role = SysRole(code="admin-role", name="Admin")
    role.permissions.extend(permissions)
    db_session.add_all([*permissions, role])
    user.roles.append(role)
    db_session.commit()
    token = _login(api_client, db_session, "admin", "password123")
    return user.id, token


class TestHolidayApi:
    def test_list_empty(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/holidays", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_create_holiday(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/holidays",
            json={"holiday_date": "2026-01-01", "holiday_name": "元旦"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["holiday_name"] == "元旦"
        assert data["holiday_date"] == "2026-01-01"
        assert data["year"] == 2026
        assert data["is_legal"] is True
        assert data["status"] == "enabled"

    def test_create_non_legal_holiday(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/holidays",
            json={"holiday_date": "2026-03-08", "holiday_name": "妇女节", "is_legal": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_legal"] is False

    def test_duplicate_date(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/holidays",
            json={"holiday_date": "2026-01-01", "holiday_name": "元旦"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = api_client.post(
            "/api/v1/holidays",
            json={"holiday_date": "2026-01-01", "holiday_name": "元旦重复"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    def test_get_detail(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/holidays",
            json={"holiday_date": "2026-05-01", "holiday_name": "劳动节"},
            headers={"Authorization": f"Bearer {token}"},
        )
        holiday_id = resp.json()["data"]["id"]
        resp = api_client.get(
            f"/api/v1/holidays/{holiday_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["holiday_name"] == "劳动节"

    def test_update_holiday(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/holidays",
            json={"holiday_date": "2026-10-01", "holiday_name": "国庆"},
            headers={"Authorization": f"Bearer {token}"},
        )
        holiday_id = resp.json()["data"]["id"]
        resp = api_client.put(
            f"/api/v1/holidays/{holiday_id}",
            json={"holiday_name": "国庆节", "status": "disabled"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["holiday_name"] == "国庆节"
        assert data["status"] == "disabled"

    def test_delete_holiday(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/holidays",
            json={"holiday_date": "2026-06-01", "holiday_name": "儿童节"},
            headers={"Authorization": f"Bearer {token}"},
        )
        holiday_id = resp.json()["data"]["id"]
        resp = api_client.delete(
            f"/api/v1/holidays/{holiday_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        resp = api_client.get(
            f"/api/v1/holidays/{holiday_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 404

    def test_not_found(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get(
            "/api/v1/holidays/99999", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 404

    def test_filter_by_year(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        for d, n in [("2025-01-01", "元旦2025"), ("2026-01-01", "元旦2026")]:
            api_client.post(
                "/api/v1/holidays",
                json={"holiday_date": d, "holiday_name": n},
                headers={"Authorization": f"Bearer {token}"},
            )
        resp = api_client.get(
            "/api/v1/holidays?year=2026", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["year"] == 2026

    def test_list_sorted_by_date(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        for d, n in [("2026-05-01", "劳动节"), ("2026-01-01", "元旦"), ("2026-10-01", "国庆")]:
            api_client.post(
                "/api/v1/holidays",
                json={"holiday_date": d, "holiday_name": n},
                headers={"Authorization": f"Bearer {token}"},
            )
        resp = api_client.get("/api/v1/holidays", headers={"Authorization": f"Bearer {token}"})
        dates = [h["holiday_date"] for h in resp.json()["data"]]
        assert dates == ["2026-01-01", "2026-05-01", "2026-10-01"]

    def test_import_holidays(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/holidays/import",
            json={"items": [
                {"holiday_date": "2026-01-01", "holiday_name": "元旦"},
                {"holiday_date": "2026-05-01", "holiday_name": "劳动节"},
            ]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["created"] == 2
        assert data["skipped"] == 0

    def test_import_skips_existing_and_duplicates(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/holidays",
            json={"holiday_date": "2026-01-01", "holiday_name": "元旦"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = api_client.post(
            "/api/v1/holidays/import",
            json={"items": [
                {"holiday_date": "2026-01-01", "holiday_name": "元旦重复"},
                {"holiday_date": "2026-05-01", "holiday_name": "劳动节"},
                {"holiday_date": "2026-05-01", "holiday_name": "劳动节重复"},
            ]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["created"] == 1
        assert data["skipped"] == 2
        assert set(data["skipped_dates"]) == {"2026-01-01", "2026-05-01"}

    def test_get_standard(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get(
            "/api/v1/holidays/standard", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["early_meal"] == 10
        assert data["middle_meal"] == 10
        assert data["night_meal"] == 14
        assert data["meal_refund_night_to_middle"] == 4
        assert data["holiday_overtime"] == 150
        assert data["holiday_overtime_refund_night_to_middle"] == 56
        standard = db_session.query(RefundStandard).one()
        assert standard.org_unit_id is not None

    def test_view_permission_can_read_standard_without_manage_permission(
        self, api_client: TestClient, db_session,
    ) -> None:
        room = OrgUnit(code="readonly-standard-room", name="只读标准机房", type="room")
        db_session.add(room)
        db_session.flush()
        person = Person(
            code="READONLY-STANDARD", name="只读人员",
            person_type="maintenance", org_unit_id=room.id,
        )
        db_session.add(person)
        db_session.flush()
        user = create_user(
            db_session, "readonly-standard", "password123", "只读人员", person_id=person.id,
        )
        permission = SysPermission(
            code="holiday:standard:view", name="查看节假日与标准", type="api",
        )
        role = SysRole(code="readonly-standard-role", name="标准只读")
        role.permissions.append(permission)
        user.roles.append(role)
        db_session.add_all([permission, role])
        db_session.commit()
        token = _login(api_client, db_session, "readonly-standard", "password123")

        response = api_client.get(
            "/api/v1/holidays/standard",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    def test_update_standard(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        response = api_client.put(
            "/api/v1/holidays/standard",
            json={
                "early_meal": 11,
                "middle_meal": 12,
                "night_meal": 15,
                "meal_refund_night_to_middle": 5,
                "holiday_overtime": 160,
                "holiday_overtime_refund_night_to_middle": 60,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["data"]["night_meal"] == 15
        standard = db_session.query(RefundStandard).one()
        assert float(standard.holiday_overtime) == 160

    def test_requires_permission(self, api_client: TestClient, db_session) -> None:
        create_user(db_session, "worker", "pass", "普通用户")
        db_session.commit()
        token = _login(api_client, db_session, "worker", "pass")
        resp = api_client.get("/api/v1/holidays", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestHolidayModel:
    def test_default_values(self, db_session) -> None:
        from datetime import date

        h = HolidayCalendar(holiday_date=date(2026, 1, 1), holiday_name="元旦", year=2026)
        db_session.add(h)
        db_session.commit()
        assert h.is_legal is True
        assert h.status == "enabled"

    def test_unique_date(self, db_session) -> None:
        from datetime import date

        db_session.add(HolidayCalendar(holiday_date=date(2026, 1, 1), holiday_name="元旦", year=2026))
        db_session.commit()
        db_session.add(HolidayCalendar(holiday_date=date(2026, 1, 1), holiday_name="元旦重复", year=2026))
        with pytest.raises(Exception):
            db_session.commit()
