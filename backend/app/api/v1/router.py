from fastapi import APIRouter

from app.api.v1.routes import auth, health, org_units, permissions, roles, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(roles.router, tags=["roles"])
api_router.include_router(permissions.router, tags=["permissions"])
api_router.include_router(org_units.router, tags=["org-units"])
