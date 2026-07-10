from typing import Annotated

from fastapi import Query

from app.db.session import get_db  # noqa: F401 — re-exported for route dependencies
from app.schemas.pagination import PageParams


def get_page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)
