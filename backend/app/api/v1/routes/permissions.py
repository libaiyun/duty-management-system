from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db
from app.schemas.response import ApiResponse, ok
from app.services.auth import list_permissions

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("", response_model=ApiResponse[list[dict]])
def get_permissions(
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[list[dict]]:
    perms = list_permissions(db)
    return ok([
        {"id": p.id, "code": p.code, "name": p.name, "type": p.type,
         "group_code": p.group_code, "group_name": p.group_name}
        for p in perms
    ])
