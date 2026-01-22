"""Receipt model for extracted receipt data."""
import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class ExtractionMethod(str, enum.Enum):
    """How the receipt data was extracted."""

    RULES = "rules"
    LLM = "llm"
    MANUAL = "manual"


class Receipt(Base):
    """Extracted receipt data from email or attachment."""

    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Core receipt data
    vendor_name = Column(String(255), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(3), default="USD", nullable=False)
    receipt_date = Column(DateTime, nullable=True)

    # Additional fields
    receipt_number = Column(String(100), nullable=True)
    tax_amount = Column(Numeric(12, 2), nullable=True)
    subtotal = Column(Numeric(12, 2), nullable=True)
    payment_method = Column(String(50), nullable=True)
    category = Column(String(50), nullable=True)

    # Extraction metadata
    extraction_method = Column(Enum(ExtractionMethod), nullable=False)
    confidence_score = Column(Numeric(3, 2), nullable=True)  # 0.00 to 1.00
    raw_extracted_data = Column(Text, nullable=True)  # JSON of all extracted fields

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    email = relationship("Email", back_populates="receipt")

    def __repr__(self) -> str:
        return f"<Receipt {self.id}: {self.vendor_name} ${self.total_amount}>"
