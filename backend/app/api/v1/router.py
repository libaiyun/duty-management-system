from fastapi import APIRouter

from app.api.v1.routes import (
    approvals,
    auth,
    exports,
    health,
    holidays,
    leaves,
    org_units,
    permissions,
    persons,
    roles,
    schedules,
    shift_rules,
    shift_swaps,
    shifts,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(approvals.router, tags=["approval-tasks"])
api_router.include_router(approvals.records_router, tags=["approval-records"])
api_router.include_router(exports.router, tags=["exports"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(roles.router, tags=["roles"])
api_router.include_router(permissions.router, tags=["permissions"])
api_router.include_router(org_units.router, tags=["org-units"])
api_router.include_router(persons.router, tags=["persons"])
api_router.include_router(shifts.router, tags=["shifts"])
api_router.include_router(shift_rules.router, tags=["shift-rules"])
api_router.include_router(holidays.router, tags=["holidays"])
api_router.include_router(leaves.router, tags=["leaves"])
api_router.include_router(leaves.covers_router, tags=["cover-assignments"])
api_router.include_router(schedules.router, tags=["schedules"])
api_router.include_router(shift_swaps.router, tags=["shift-swaps"])
