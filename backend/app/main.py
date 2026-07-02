from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.metadata import APP_NAME, APP_VERSION


def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
    )
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
