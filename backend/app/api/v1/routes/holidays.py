from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db
from app.core.exceptions import NotFoundError
from app.schemas.holiday import (
    HolidayCreateRequest,
    HolidayImportRequest,
    HolidayImportResponse,
    HolidayResponse,
    HolidayUpdateRequest,
    SubsidyStandardResponse,
)
from app.schemas.response import ApiResponse, ok
from app.services.holiday import (
    create_holiday,
    delete_holiday,
    get_holiday,
    get_subsidy_standard,
    import_holidays,
    list_holidays,
    update_holiday,
)

router = APIRouter(prefix="/holidays", tags=["holidays"])


@router.get("", response_model=ApiResponse[list[HolidayResponse]])
def get_holidays(
    year: int | None = Query(None),
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("holiday:standard:view")),
) -> ApiResponse[list[HolidayResponse]]:
    holidays = list_holidays(db, year=year)
    return ok([HolidayResponse.model_validate(h) for h in holidays])


@router.get("/standard", response_model=ApiResponse[SubsidyStandardResponse])
def get_standard(
    _perm: None = Depends(RequirePermission("holiday:standard:view")),
) -> ApiResponse[SubsidyStandardResponse]:
    return ok(SubsidyStandardResponse(**get_subsidy_standard()))


@router.post("", response_model=ApiResponse[HolidayResponse])
def create_holiday_endpoint(
    body: HolidayCreateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("holiday:standard:view")),
) -> ApiResponse[HolidayResponse]:
    holiday = create_holiday(
        db, body.holiday_date, body.holiday_name,
        is_legal=body.is_legal, remark=body.remark,
    )
    db.commit()
    return ok(HolidayResponse.model_validate(holiday))


@router.post("/import", response_model=ApiResponse[HolidayImportResponse])
def import_holidays_endpoint(
    body: HolidayImportRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("holiday:standard:view")),
) -> ApiResponse[HolidayImportResponse]:
    created, skipped, skipped_dates = import_holidays(
        db,
        [(i.holiday_date, i.holiday_name, i.is_legal, i.remark) for i in body.items],
    )
    db.commit()
    return ok(HolidayImportResponse(
        created=created, skipped=skipped, skipped_dates=skipped_dates,
    ))


@router.get("/{holiday_id}", response_model=ApiResponse[HolidayResponse])
def get_holiday_endpoint(
    holiday_id: int,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("holiday:standard:view")),
) -> ApiResponse[HolidayResponse]:
    holiday = get_holiday(db, holiday_id)
    if holiday is None:
        raise NotFoundError(message="节假日不存在")
    return ok(HolidayResponse.model_validate(holiday))


@router.put("/{holiday_id}", response_model=ApiResponse[HolidayResponse])
def update_holiday_endpoint(
    holiday_id: int,
    body: HolidayUpdateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("holiday:standard:view")),
) -> ApiResponse[HolidayResponse]:
    holiday = update_holiday(
        db, holiday_id,
        holiday_name=body.holiday_name,
        is_legal=body.is_legal,
        status=body.status,
        remark=body.remark,
    )
    db.commit()
    return ok(HolidayResponse.model_validate(holiday))


@router.delete("/{holiday_id}", response_model=ApiResponse[None])
def delete_holiday_endpoint(
    holiday_id: int,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("holiday:standard:view")),
) -> ApiResponse[None]:
    delete_holiday(db, holiday_id)
    db.commit()
    return ok(message="删除成功")
