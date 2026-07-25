import importlib

from app.core.metadata import APP_NAME
from app.main import create_app
from fastapi import FastAPI


def test_create_app_returns_fastapi_instance() -> None:
    app = create_app()

    assert isinstance(app, FastAPI)
    assert app.title == APP_NAME


def test_backend_layer_packages_are_importable() -> None:
    packages = [
        "app.api",
        "app.api.deps",
        "app.api.v1",
        "app.core",
        "app.core.exception_handlers",
        "app.core.exceptions",
        "app.core.metadata",
        "app.db",
        "app.db.base",
        "app.db.session",
        "app.schemas.pagination",
        "app.schemas.response",
        "app.models",
        "app.repositories",
        "app.schemas",
        "app.services",
    ]

    for package in packages:
        assert importlib.import_module(package)
