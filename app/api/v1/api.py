# In app/api/v1/api.py
from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, payments, admin, ambassador, registration_team, public
)

api_router = APIRouter()

api_router.include_router(public.router, prefix="/public", tags=["public"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(ambassador.router, prefix="/ambassador", tags=["ambassador"])
api_router.include_router(registration_team.router, prefix="/registration-team", tags=["registration-team"])