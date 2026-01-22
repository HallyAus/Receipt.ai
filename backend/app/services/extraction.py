"""Receipt extraction service with rules-based and LLM extraction."""
import json
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.email import Email
from app.models.receipt import ExtractionMethod, Receipt
from app.schemas.receipt import LLMReceiptSchema, ReceiptExtracted

logger = logging.getLogger(__name__)
settings = get_settings()

# Common receipt patterns
VENDOR_PATTERNS = [
    r"(?:from|order from|purchase from|receipt from)[:\s]+([A-Za-z0-9\s&'-]+)",
    r"^([A-Za-z0-9\s&'-]{3,30})\s+(?:receipt|invoice|order)",
    r"(?:thank you for (?:your )?(?:order|purchase) (?:from|at|with))[:\s]+([A-Za-z0-9\s&'-]+)",
]

AMOUNT_PATTERNS = [
    r"(?:total|amount|charged|paid|payment)[:\s]*\$?([\d,]+\.?\d{0,2})",
    r"\$\s*([\d,]+\.\d{2})\s*(?:total|usd)?",
    r"(?:grand total|order total)[:\s]*\$?([\d,]+\.?\d{0,2})",
]

TAX_PATTERNS = [
    r"(?:tax|vat|gst)[:\s]*\$?([\d,]+\.?\d{0,2})",
    r"(?:sales tax)[:\s]*\$?([\d,]+\.?\d{0,2})",
]

DATE_PATTERNS = [
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",  # MM/DD/YYYY or DD/MM/YYYY
    r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",  # YYYY-MM-DD
    r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",  # Month DD, YYYY
    r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",  # DD Month YYYY
]

RECEIPT_NUMBER_PATTERNS = [
    r"(?:receipt|invoice|order|confirmation|transaction)[\s#:]*([A-Za-z0-9-]+)",
    r"#\s*([A-Za-z0-9-]+)",
]

# Vendor name normalization
KNOWN_VENDORS = {
    "amazon": "Amazon",
    "uber": "Uber",
    "lyft": "Lyft",
    "doordash": "DoorDash",
    "grubhub": "Grubhub",
    "netflix": "Netflix",
    "spotify": "Spotify",
    "apple": "Apple",
    "google": "Google",
    "microsoft": "Microsoft",
    "dropbox": "Dropbox",
    "slack": "Slack",
    "zoom": "Zoom",
    "airbnb": "Airbnb",
    "expedia": "Expedia",
    "southwest": "Southwest Airlines",
    "delta": "Delta Airlines",
    "united": "United Airlines",
    "american": "American Airlines",
}


class ExtractionService:
    """Extract receipt data using rules-based approach with optional LLM fallback."""

    def __init__(self, session: Session):
        """Initialize extraction service.

        Args:
            session: Database session
        """
        self.session = session
        self.llm_enabled = settings.llm_enabled and settings.openai_api_key

    def extract_from_email(self, email: Email) -> Optional[Receipt]:
        """Extract receipt data from an email.

        Args:
            email: Email to extract from

        Returns:
            Receipt object if extraction successful, None otherwise
        """
        # Combine subject and body for extraction
        text = f"{email.subject or ''}\n{email.body_snippet or ''}"

        # Try rules-based extraction first
        extracted = self._rules_extraction(text, email.sender)

        # Calculate confidence based on filled fields
        extracted.confidence_score = self._calculate_confidence(extracted)

        # If confidence is low and LLM is enabled, try LLM extraction
        if extracted.confidence_score < 0.5 and self.llm_enabled:
            logger.info(f"Low confidence ({extracted.confidence_score}), trying LLM extraction for email {email.id}")
            llm_extracted = self._llm_extraction(text)
            if llm_extracted and self._calculate_confidence(llm_extracted) > extracted.confidence_score:
                extracted = llm_extracted
                extraction_method = ExtractionMethod.LLM
            else:
                extraction_method = ExtractionMethod.RULES
        else:
            extraction_method = ExtractionMethod.RULES

        # Only create receipt if we have minimum viable data
        if not self._has_minimum_data(extracted):
            logger.info(f"Insufficient data extracted from email {email.id}")
            email.processed = 2  # Mark as no receipt found
            self.session.commit()
            return None

        # Create receipt record
        receipt = Receipt(
            email_id=email.id,
            vendor_name=extracted.vendor_name,
            total_amount=extracted.total_amount,
            currency=extracted.currency,
            receipt_date=extracted.receipt_date,
            receipt_number=extracted.receipt_number,
            tax_amount=extracted.tax_amount,
            subtotal=extracted.subtotal,
            payment_method=extracted.payment_method,
            category=extracted.category,
            extraction_method=extraction_method,
            confidence_score=Decimal(str(extracted.confidence_score)),
            raw_extracted_data=json.dumps(extracted.model_dump(), default=str),
        )

        self.session.add(receipt)
        email.processed = 1  # Mark as processed with receipt
        self.session.commit()

        return receipt

    def _rules_extraction(self, text: str, sender: Optional[str] = None) -> ReceiptExtracted:
        """Extract receipt data using regex patterns.

        Args:
            text: Combined email text (subject + body)
            sender: Email sender address

        Returns:
            ReceiptExtracted with found fields
        """
        extracted = ReceiptExtracted()
        text_lower = text.lower()

        # Extract vendor name
        vendor = self._extract_vendor(text, sender)
        if vendor:
            extracted.vendor_name = vendor

        # Extract amounts
        amount = self._extract_amount(text)
        if amount:
            extracted.total_amount = amount

        tax = self._extract_tax(text)
        if tax:
            extracted.tax_amount = tax

        if extracted.total_amount and extracted.tax_amount:
            extracted.subtotal = extracted.total_amount - extracted.tax_amount

        # Extract date
        receipt_date = self._extract_date(text)
        if receipt_date:
            extracted.receipt_date = receipt_date

        # Extract receipt number
        receipt_number = self._extract_receipt_number(text)
        if receipt_number:
            extracted.receipt_number = receipt_number

        # Infer category from vendor and keywords
        extracted.category = self._infer_category(text_lower, extracted.vendor_name)

        return extracted

    def _extract_vendor(self, text: str, sender: Optional[str] = None) -> Optional[str]:
        """Extract vendor name from text or sender."""
        # Try to extract from sender domain first
        if sender:
            # Extract domain from email
            match = re.search(r"@([a-zA-Z0-9-]+)\.", sender)
            if match:
                domain = match.group(1).lower()
                if domain in KNOWN_VENDORS:
                    return KNOWN_VENDORS[domain]

        # Try regex patterns
        for pattern in VENDOR_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                vendor = match.group(1).strip()
                # Normalize if known
                vendor_lower = vendor.lower()
                for key, value in KNOWN_VENDORS.items():
                    if key in vendor_lower:
                        return value
                return vendor.title()

        return None

    def _extract_amount(self, text: str) -> Optional[Decimal]:
        """Extract total amount from text."""
        for pattern in AMOUNT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(",", "")
                    return Decimal(amount_str)
                except (InvalidOperation, ValueError):
                    continue
        return None

    def _extract_tax(self, text: str) -> Optional[Decimal]:
        """Extract tax amount from text."""
        for pattern in TAX_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(",", "")
                    return Decimal(amount_str)
                except (InvalidOperation, ValueError):
                    continue
        return None

    def _extract_date(self, text: str) -> Optional[datetime]:
        """Extract receipt date from text."""
        for pattern in DATE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                # Try various date formats
                formats = [
                    "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y",
                    "%Y-%m-%d", "%Y/%m/%d",
                    "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y",
                    "%d %B %Y", "%d %b %Y",
                    "%m/%d/%y", "%d/%m/%y",
                ]
                for fmt in formats:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
        return None

    def _extract_receipt_number(self, text: str) -> Optional[str]:
        """Extract receipt/order number from text."""
        for pattern in RECEIPT_NUMBER_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                number = match.group(1).strip()
                if len(number) >= 4:  # Minimum length for valid number
                    return number
        return None

    def _infer_category(self, text_lower: str, vendor: Optional[str] = None) -> Optional[str]:
        """Infer receipt category from text and vendor."""
        categories = {
            "food": ["restaurant", "food", "meal", "dinner", "lunch", "breakfast", "cafe", "coffee",
                     "doordash", "grubhub", "ubereats", "postmates"],
            "travel": ["flight", "hotel", "airline", "airbnb", "expedia", "booking", "uber", "lyft",
                       "rental car", "travel"],
            "subscription": ["subscription", "monthly", "annual", "renewal", "netflix", "spotify",
                            "adobe", "microsoft 365", "dropbox"],
            "office": ["office", "supplies", "equipment", "software", "hardware", "computer"],
            "utilities": ["utility", "electric", "gas", "water", "internet", "phone", "mobile"],
        }

        for category, keywords in categories.items():
            if any(keyword in text_lower for keyword in keywords):
                return category
            if vendor and any(keyword in vendor.lower() for keyword in keywords):
                return category

        return "other"

    def _calculate_confidence(self, extracted: ReceiptExtracted) -> float:
        """Calculate confidence score based on filled fields.

        Args:
            extracted: Extracted data

        Returns:
            Confidence score between 0 and 1
        """
        score = 0.0
        weights = {
            "vendor_name": 0.25,
            "total_amount": 0.35,
            "receipt_date": 0.20,
            "receipt_number": 0.10,
            "category": 0.10,
        }

        if extracted.vendor_name:
            score += weights["vendor_name"]
        if extracted.total_amount:
            score += weights["total_amount"]
        if extracted.receipt_date:
            score += weights["receipt_date"]
        if extracted.receipt_number:
            score += weights["receipt_number"]
        if extracted.category and extracted.category != "other":
            score += weights["category"]

        return min(score, 1.0)

    def _has_minimum_data(self, extracted: ReceiptExtracted) -> bool:
        """Check if we have minimum required data for a receipt.

        Args:
            extracted: Extracted data

        Returns:
            True if minimum data present
        """
        # Need at least vendor OR amount to consider it a receipt
        return bool(extracted.vendor_name or extracted.total_amount)

    def _llm_extraction(self, text: str) -> Optional[ReceiptExtracted]:
        """Extract receipt data using LLM.

        Args:
            text: Text to extract from

        Returns:
            ReceiptExtracted if successful and valid, None otherwise
        """
        if not self.llm_enabled:
            return None

        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)

            prompt = f"""Extract receipt information from the following email text.
Return a JSON object with these fields (use null for missing values):
- vendor_name: string (name of the merchant/vendor)
- total_amount: number (total amount including tax)
- currency: string (3-letter ISO currency code, default USD)
- receipt_date: string (date in YYYY-MM-DD format)
- receipt_number: string (receipt/invoice/order number)
- tax_amount: number (tax amount if shown)
- subtotal: number (subtotal before tax)
- payment_method: string (credit card, debit, etc.)
- category: string (one of: food, travel, office, utilities, subscription, other)

Email text:
{text[:2000]}

Return only valid JSON, no explanation."""

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=500,
            )

            # Parse and validate response
            content = response.choices[0].message.content.strip()

            # Try to extract JSON from response
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            data = json.loads(content)

            # Strict schema validation
            validated = LLMReceiptSchema(**data)

            # Convert to ReceiptExtracted
            extracted = ReceiptExtracted(
                vendor_name=validated.vendor_name,
                total_amount=Decimal(str(validated.total_amount)) if validated.total_amount else None,
                currency=validated.currency,
                receipt_date=datetime.strptime(validated.receipt_date, "%Y-%m-%d") if validated.receipt_date else None,
                receipt_number=validated.receipt_number,
                tax_amount=Decimal(str(validated.tax_amount)) if validated.tax_amount else None,
                subtotal=Decimal(str(validated.subtotal)) if validated.subtotal else None,
                payment_method=validated.payment_method,
                category=validated.category,
            )
            extracted.confidence_score = self._calculate_confidence(extracted)

            return extracted

        except ValidationError as e:
            logger.warning(f"LLM response failed schema validation: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"LLM response is not valid JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return None
