from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db
from app.core.exceptions import NotFoundError
from app.models.person import Person
from app.models.user import SysUser
from app.schemas.person import PersonCreateRequest, PersonResponse, PersonUpdateRequest
from app.schemas.response import ApiResponse, ok
from app.services.auth import (
    create_person,
    list_persons,
    resolve_scoped_org_unit_ids,
    update_person,
)

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("", response_model=ApiResponse[list[PersonResponse]])
def get_persons(
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("person:manage:view")),
) -> ApiResponse[list[PersonResponse]]:
    scoped_ids = resolve_scoped_org_unit_ids(db, user)
    persons = list_persons(db, org_unit_ids=scoped_ids)
    return ok([PersonResponse.model_validate(p) for p in persons])


@router.post("", response_model=ApiResponse[PersonResponse])
def create_person_endpoint(
    body: PersonCreateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("person:manage:view")),
) -> ApiResponse[PersonResponse]:
    p = create_person(
        db, body.code, body.name, body.person_type,
        org_unit_id=body.org_unit_id, phone=body.phone,
        participate_schedule=body.participate_schedule,
        rotation_order=body.rotation_order, remark=body.remark,
    )
    db.commit()
    return ok(PersonResponse.model_validate(p))


@router.get("/{person_id}", response_model=ApiResponse[PersonResponse])
def get_person(
    person_id: int,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("person:manage:view")),
) -> ApiResponse[PersonResponse]:
    p = db.get(Person, person_id)
    if p is None:
        raise NotFoundError(message="人员不存在")
    return ok(PersonResponse.model_validate(p))


@router.put("/{person_id}", response_model=ApiResponse[PersonResponse])
def update_person_endpoint(
    person_id: int,
    body: PersonUpdateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("person:manage:view")),
) -> ApiResponse[PersonResponse]:
    p = update_person(
        db, person_id,
        org_unit_id=body.org_unit_id,
        name=body.name, phone=body.phone,
        participate_schedule=body.participate_schedule,
        rotation_order=body.rotation_order,
        status=body.status, remark=body.remark,
    )
    db.commit()
    return ok(PersonResponse.model_validate(p))
