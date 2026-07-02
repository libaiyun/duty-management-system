from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import Settings, load_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.metadata import APP_NAME, APP_VERSION


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
    )
    app.state.settings = settings or load_settings()
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
