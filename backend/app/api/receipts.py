"""Receipt management routes."""
import csv
import io
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_async_session
from app.models.account import MailAccount
from app.models.attachment import Attachment
from app.models.email import Email
from app.models.receipt import Receipt
from app.schemas.receipt import ReceiptResponse, ReceiptListResponse, AttachmentResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=ReceiptListResponse)
async def list_receipts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    account_id: Optional[int] = Query(None),
    vendor: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    """List receipts with filtering and pagination."""
    # Build query
    query = (
        select(Receipt)
        .join(Email)
        .options(selectinload(Receipt.email).selectinload(Email.attachments))
    )

    # Apply filters
    if account_id:
        query = query.where(Email.account_id == account_id)
    if vendor:
        query = query.where(Receipt.vendor_name.ilike(f"%{vendor}%"))
    if category:
        query = query.where(Receipt.category == category)
    if date_from:
        query = query.where(Receipt.receipt_date >= date_from)
    if date_to:
        query = query.where(Receipt.receipt_date <= date_to)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Receipt.created_at.desc()).offset(offset).limit(page_size)

    result = await session.execute(query)
    receipts = result.scalars().all()

    # Build response with email context
    receipt_responses = []
    for r in receipts:
        resp = ReceiptResponse(
            id=r.id,
            email_id=r.email_id,
            vendor_name=r.vendor_name,
            total_amount=r.total_amount,
            currency=r.currency,
            receipt_date=r.receipt_date,
            receipt_number=r.receipt_number,
            tax_amount=r.tax_amount,
            subtotal=r.subtotal,
            payment_method=r.payment_method,
            category=r.category,
            extraction_method=r.extraction_method,
            confidence_score=r.confidence_score,
            created_at=r.created_at,
            email_subject=r.email.subject if r.email else None,
            email_sender=r.email.sender if r.email else None,
            email_received_at=r.email.received_at if r.email else None,
            attachments=[
                AttachmentResponse.model_validate(a) for a in (r.email.attachments if r.email else [])
            ],
        )
        receipt_responses.append(resp)

    return ReceiptListResponse(
        receipts=receipt_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/export")
async def export_receipts_csv(
    account_id: Optional[int] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    """Export receipts as CSV."""
    # Build query
    query = select(Receipt).join(Email).options(selectinload(Receipt.email))

    if account_id:
        query = query.where(Email.account_id == account_id)
    if date_from:
        query = query.where(Receipt.receipt_date >= date_from)
    if date_to:
        query = query.where(Receipt.receipt_date <= date_to)

    query = query.order_by(Receipt.receipt_date.desc())

    result = await session.execute(query)
    receipts = result.scalars().all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "ID",
        "Date",
        "Vendor",
        "Amount",
        "Currency",
        "Tax",
        "Subtotal",
        "Category",
        "Receipt Number",
        "Payment Method",
        "Email Subject",
        "Email From",
        "Confidence",
        "Extraction Method",
    ])

    # Data rows
    for r in receipts:
        writer.writerow([
            r.id,
            r.receipt_date.strftime("%Y-%m-%d") if r.receipt_date else "",
            r.vendor_name or "",
            str(r.total_amount) if r.total_amount else "",
            r.currency,
            str(r.tax_amount) if r.tax_amount else "",
            str(r.subtotal) if r.subtotal else "",
            r.category or "",
            r.receipt_number or "",
            r.payment_method or "",
            r.email.subject if r.email else "",
            r.email.sender if r.email else "",
            str(r.confidence_score) if r.confidence_score else "",
            r.extraction_method.value if r.extraction_method else "",
        ])

    output.seek(0)

    # Generate filename with date
    filename = f"receipts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(
    receipt_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """Get a specific receipt with details."""
    result = await session.execute(
        select(Receipt)
        .where(Receipt.id == receipt_id)
        .options(selectinload(Receipt.email).selectinload(Email.attachments))
    )
    receipt = result.scalar_one_or_none()

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    return ReceiptResponse(
        id=receipt.id,
        email_id=receipt.email_id,
        vendor_name=receipt.vendor_name,
        total_amount=receipt.total_amount,
        currency=receipt.currency,
        receipt_date=receipt.receipt_date,
        receipt_number=receipt.receipt_number,
        tax_amount=receipt.tax_amount,
        subtotal=receipt.subtotal,
        payment_method=receipt.payment_method,
        category=receipt.category,
        extraction_method=receipt.extraction_method,
        confidence_score=receipt.confidence_score,
        created_at=receipt.created_at,
        email_subject=receipt.email.subject if receipt.email else None,
        email_sender=receipt.email.sender if receipt.email else None,
        email_received_at=receipt.email.received_at if receipt.email else None,
        attachments=[
            AttachmentResponse.model_validate(a) for a in (receipt.email.attachments if receipt.email else [])
        ],
    )


@router.delete("/{receipt_id}")
async def delete_receipt(
    receipt_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """Delete a receipt."""
    result = await session.execute(
        select(Receipt).where(Receipt.id == receipt_id)
    )
    receipt = result.scalar_one_or_none()

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    await session.delete(receipt)
    await session.commit()

    logger.info(f"Deleted receipt {receipt_id}")
    return {"message": "Receipt deleted successfully"}


@router.get("/stats/summary")
async def get_receipt_stats(
    account_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    """Get receipt statistics summary."""
    from sqlalchemy import case

    # Base query
    base = select(Receipt).join(Email)
    if account_id:
        base = base.where(Email.account_id == account_id)

    # Total count
    total_result = await session.execute(
        select(func.count(Receipt.id)).select_from(base.subquery())
    )
    total_count = total_result.scalar() or 0

    # Total amount
    amount_result = await session.execute(
        select(func.sum(Receipt.total_amount)).select_from(base.subquery())
    )
    total_amount = amount_result.scalar() or 0

    # By category
    category_query = (
        select(Receipt.category, func.count(Receipt.id), func.sum(Receipt.total_amount))
        .join(Email)
        .group_by(Receipt.category)
    )
    if account_id:
        category_query = category_query.where(Email.account_id == account_id)

    category_result = await session.execute(category_query)
    by_category = {
        row[0] or "uncategorized": {"count": row[1], "amount": float(row[2] or 0)}
        for row in category_result
    }

    # By month (last 12 months)
    month_query = (
        select(
            func.date_trunc("month", Receipt.receipt_date).label("month"),
            func.count(Receipt.id),
            func.sum(Receipt.total_amount),
        )
        .join(Email)
        .where(Receipt.receipt_date.isnot(None))
        .group_by("month")
        .order_by("month")
        .limit(12)
    )
    if account_id:
        month_query = month_query.where(Email.account_id == account_id)

    month_result = await session.execute(month_query)
    by_month = [
        {
            "month": row[0].strftime("%Y-%m") if row[0] else None,
            "count": row[1],
            "amount": float(row[2] or 0),
        }
        for row in month_result
    ]

    return {
        "total_count": total_count,
        "total_amount": float(total_amount),
        "by_category": by_category,
        "by_month": by_month,
    }
