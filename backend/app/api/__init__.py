"""API routes."""
from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.accounts import router as accounts_router
from app.api.receipts import router as receipts_router
from app.api.sync import router as sync_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
api_router.include_router(receipts_router, prefix="/receipts", tags=["receipts"])
api_router.include_router(sync_router, prefix="/sync", tags=["sync"])
