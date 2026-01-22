"""Account management routes."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.models.account import MailAccount
from app.schemas.account import AccountResponse, AccountListResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=AccountListResponse)
async def list_accounts(
    session: AsyncSession = Depends(get_async_session),
):
    """List all connected mail accounts."""
    result = await session.execute(
        select(MailAccount).order_by(MailAccount.created_at.desc())
    )
    accounts = result.scalars().all()

    return AccountListResponse(
        accounts=[AccountResponse.model_validate(a) for a in accounts],
        total=len(accounts),
    )


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """Get a specific mail account."""
    result = await session.execute(
        select(MailAccount).where(MailAccount.id == account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return AccountResponse.model_validate(account)


@router.delete("/{account_id}")
async def delete_account(
    account_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """Disconnect and delete a mail account."""
    result = await session.execute(
        select(MailAccount).where(MailAccount.id == account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    await session.delete(account)
    await session.commit()

    logger.info(f"Deleted account {account_id}: {account.email}")
    return {"message": "Account deleted successfully"}


@router.get("/{account_id}/stats")
async def get_account_stats(
    account_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """Get statistics for a mail account."""
    from app.models.email import Email
    from app.models.receipt import Receipt

    # Verify account exists
    result = await session.execute(
        select(MailAccount).where(MailAccount.id == account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Count emails
    email_count = await session.execute(
        select(func.count(Email.id)).where(Email.account_id == account_id)
    )

    # Count receipts
    receipt_count = await session.execute(
        select(func.count(Receipt.id))
        .join(Email)
        .where(Email.account_id == account_id)
    )

    return {
        "account_id": account_id,
        "email": account.email,
        "provider": account.provider.value,
        "emails_synced": email_count.scalar() or 0,
        "receipts_extracted": receipt_count.scalar() or 0,
        "last_sync_at": account.last_sync_at,
        "sync_error": account.sync_error,
    }
