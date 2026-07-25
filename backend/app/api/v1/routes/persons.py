from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db, resolve_current_room_id
from app.core.exceptions import NotFoundError
from app.models.person import Person
from app.models.user import SysUser
from app.schemas.person import PersonCreateRequest, PersonResponse, PersonUpdateRequest
from app.schemas.response import ApiResponse, ok
from app.services.auth import (
    create_person,
    list_persons,
    update_person,
)

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("", response_model=ApiResponse[list[PersonResponse]])
def get_persons(
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("person:manage:view")),
    participate_schedule: bool | None = Query(None),
    org_unit_id: int | None = Query(None),
    person_type: str | None = Query(None),
) -> ApiResponse[list[PersonResponse]]:
    room_id = resolve_current_room_id(request, db, user)
    persons = list_persons(
        db, org_unit_id=room_id,
        participate_schedule=participate_schedule,
        person_type=person_type,
    )
    return ok([PersonResponse.model_validate(p) for p in persons])


@router.post("", response_model=ApiResponse[PersonResponse])
def create_person_endpoint(
    request: Request,
    body: PersonCreateRequest,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("person:manage:view")),
) -> ApiResponse[PersonResponse]:
    room_id = resolve_current_room_id(request, db, user)
    p = create_person(
        db, body.code, body.name, body.person_type,
        org_unit_id=room_id, phone=body.phone,
        participate_schedule=body.participate_schedule,
        remark=body.remark,
    )
    db.commit()
    return ok(PersonResponse.model_validate(p))


@router.get("/{person_id}", response_model=ApiResponse[PersonResponse])
def get_person(
    person_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("person:manage:view")),
) -> ApiResponse[PersonResponse]:
    p = db.get(Person, person_id)
    if p is None or p.org_unit_id != resolve_current_room_id(request, db, user):
        raise NotFoundError(message="人员不存在")
    return ok(PersonResponse.model_validate(p))


@router.put("/{person_id}", response_model=ApiResponse[PersonResponse])
def update_person_endpoint(
    person_id: int,
    request: Request,
    body: PersonUpdateRequest,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("person:manage:view")),
) -> ApiResponse[PersonResponse]:
    room_id = resolve_current_room_id(request, db, user)
    person = db.get(Person, person_id)
    if person is None or person.org_unit_id != room_id:
        raise NotFoundError(message="人员不存在")
    p = update_person(
        db, person_id,
        org_unit_id=room_id,
        name=body.name, person_type=body.person_type, phone=body.phone,
        participate_schedule=body.participate_schedule,
        status=body.status, remark=body.remark,
    )
    db.commit()
    return ok(PersonResponse.model_validate(p))
