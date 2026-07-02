from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.db.session import get_db
from app.schemas.response import ApiResponse, ok


class FixtureBase(DeclarativeBase):
    pass


class FixtureRecord(FixtureBase):
    __tablename__ = "fixture_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)


def test_api_client_uses_test_settings(api_client) -> None:
    assert api_client.app.state.settings.app_env == "test"
    assert api_client.app.state.settings.database_url.startswith("sqlite:///")


def test_app_fixture_overrides_get_db(app, db_session: Session) -> None:
    FixtureBase.metadata.create_all(bind=db_session.bind)

    @app.get("/test-fixtures/db", response_model=ApiResponse[list[str]])
    def read_records(session: Session = Depends(get_db)) -> ApiResponse[list[str]]:
        session.add(FixtureRecord(name="from-override"))
        session.flush()
        names = session.scalars(select(FixtureRecord.name)).all()
        return ok(list(names))

    with TestClient(app) as client:
        response = client.get("/test-fixtures/db")

    assert response.status_code == 200
    assert response.json() == {
        "code": "OK",
        "message": "success",
        "data": ["from-override"],
    }


def test_db_session_fixture_is_transactional(db_session: Session) -> None:
    FixtureBase.metadata.create_all(bind=db_session.bind)
    db_session.add(FixtureRecord(name="transactional"))
    db_session.flush()

    names = db_session.scalars(select(FixtureRecord.name)).all()

    assert names == ["transactional"]


def test_db_session_fixture_supports_commit_inside_test(db_session: Session) -> None:
    FixtureBase.metadata.create_all(bind=db_session.bind)
    db_session.add(FixtureRecord(name="committed-in-test"))
    db_session.commit()

    names = db_session.scalars(select(FixtureRecord.name)).all()

    assert names == ["committed-in-test"]
