"""Sync routes for triggering email sync."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_async_session
from app.models.account import MailAccount
from app.schemas.sync import SyncRequest, SyncResponse, SyncStatus

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.post("/start", response_model=SyncResponse)
async def start_sync(
    request: SyncRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Start a sync job for an account.

    This queues a Celery task to perform the actual sync.
    """
    # Verify account exists
    result = await session.execute(
        select(MailAccount).where(MailAccount.id == request.account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Queue Celery task
    try:
        from worker.tasks import sync_account_task

        task = sync_account_task.delay(request.account_id)

        logger.info(f"Queued sync task {task.id} for account {request.account_id}")

        return SyncResponse(
            task_id=task.id,
            account_id=request.account_id,
            status=SyncStatus.PENDING,
            message="Sync job queued successfully",
        )
    except Exception as e:
        logger.error(f"Failed to queue sync task: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue sync job")


@router.get("/status/{task_id}")
async def get_sync_status(task_id: str):
    """Get the status of a sync task."""
    try:
        from celery.result import AsyncResult

        result = AsyncResult(task_id)

        status_map = {
            "PENDING": SyncStatus.PENDING,
            "STARTED": SyncStatus.IN_PROGRESS,
            "SUCCESS": SyncStatus.COMPLETED,
            "FAILURE": SyncStatus.FAILED,
        }

        status = status_map.get(result.status, SyncStatus.PENDING)

        response = {
            "task_id": task_id,
            "status": status.value,
            "result": None,
            "error": None,
        }

        if result.ready():
            if result.successful():
                response["result"] = result.result
            else:
                response["error"] = str(result.result)

        return response

    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get task status")


@router.post("/all")
async def sync_all_accounts(
    session: AsyncSession = Depends(get_async_session),
):
    """Start sync for all connected accounts."""
    result = await session.execute(select(MailAccount))
    accounts = result.scalars().all()

    if not accounts:
        raise HTTPException(status_code=404, detail="No accounts configured")

    task_ids = []
    try:
        from worker.tasks import sync_account_task

        for account in accounts:
            task = sync_account_task.delay(account.id)
            task_ids.append({
                "account_id": account.id,
                "email": account.email,
                "task_id": task.id,
            })

        logger.info(f"Queued sync tasks for {len(accounts)} accounts")

        return {
            "message": f"Sync started for {len(accounts)} accounts",
            "tasks": task_ids,
        }

    except Exception as e:
        logger.error(f"Failed to queue sync tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue sync jobs")
