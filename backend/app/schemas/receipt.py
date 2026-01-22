"""Schemas for receipt operations."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.receipt import ExtractionMethod


class AttachmentResponse(BaseModel):
    """Attachment info in receipt response."""

    id: int
    filename: str
    content_type: str
    size_bytes: int

    class Config:
        from_attributes = True


class ReceiptResponse(BaseModel):
    """Receipt data response."""

    id: int
    email_id: int
    vendor_name: Optional[str] = None
    total_amount: Optional[Decimal] = None
    currency: str = "USD"
    receipt_date: Optional[datetime] = None
    receipt_number: Optional[str] = None
    tax_amount: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None
    payment_method: Optional[str] = None
    category: Optional[str] = None
    extraction_method: ExtractionMethod
    confidence_score: Optional[Decimal] = None
    created_at: datetime

    # Email context
    email_subject: Optional[str] = None
    email_sender: Optional[str] = None
    email_received_at: Optional[datetime] = None

    # Attachments
    attachments: List[AttachmentResponse] = []

    class Config:
        from_attributes = True


class ReceiptListResponse(BaseModel):
    """Paginated list of receipts."""

    receipts: List[ReceiptResponse]
    total: int
    page: int
    page_size: int


class ReceiptExtracted(BaseModel):
    """Internal schema for extracted receipt data."""

    vendor_name: Optional[str] = None
    total_amount: Optional[Decimal] = None
    currency: str = "USD"
    receipt_date: Optional[datetime] = None
    receipt_number: Optional[str] = None
    tax_amount: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None
    payment_method: Optional[str] = None
    category: Optional[str] = None
    confidence_score: float = 0.0


class LLMReceiptSchema(BaseModel):
    """Strict JSON schema for LLM extraction - used for validation."""

    vendor_name: Optional[str] = Field(None, description="Name of the vendor/merchant")
    total_amount: Optional[float] = Field(None, ge=0, description="Total amount including tax")
    currency: str = Field("USD", pattern="^[A-Z]{3}$", description="ISO 4217 currency code")
    receipt_date: Optional[str] = Field(None, description="Receipt date in YYYY-MM-DD format")
    receipt_number: Optional[str] = Field(None, description="Receipt/invoice number")
    tax_amount: Optional[float] = Field(None, ge=0, description="Tax amount")
    subtotal: Optional[float] = Field(None, ge=0, description="Subtotal before tax")
    payment_method: Optional[str] = Field(None, description="Payment method used")
    category: Optional[str] = Field(None, description="Category: food, travel, office, utilities, other")

    @field_validator("receipt_date")
    @classmethod
    def validate_date_format(cls, v):
        """Validate date is in YYYY-MM-DD format."""
        if v is not None:
            from datetime import datetime

            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Date must be in YYYY-MM-DD format")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        """Validate category is from allowed list."""
        allowed = {"food", "travel", "office", "utilities", "subscription", "other"}
        if v is not None and v.lower() not in allowed:
            raise ValueError(f"Category must be one of: {', '.join(allowed)}")
        return v.lower() if v else None
