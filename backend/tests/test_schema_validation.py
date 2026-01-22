"""Tests for LLM response schema validation rejection."""
import pytest
from pydantic import ValidationError

from app.schemas.receipt import LLMReceiptSchema


class TestLLMSchemaValidation:
    """Test that invalid LLM responses are rejected."""

    def test_valid_schema_accepted(self):
        """Valid LLM response should be accepted."""
        data = {
            "vendor_name": "Amazon",
            "total_amount": 99.99,
            "currency": "USD",
            "receipt_date": "2024-01-15",
            "receipt_number": "ORDER-123",
            "tax_amount": 8.50,
            "subtotal": 91.49,
            "payment_method": "Credit Card",
            "category": "office",
        }
        schema = LLMReceiptSchema(**data)
        assert schema.vendor_name == "Amazon"
        assert schema.total_amount == 99.99
        assert schema.currency == "USD"

    def test_minimal_valid_schema(self):
        """Minimal valid schema should be accepted."""
        data = {
            "vendor_name": "Store",
            "total_amount": 10.00,
        }
        schema = LLMReceiptSchema(**data)
        assert schema.vendor_name == "Store"
        assert schema.currency == "USD"  # Default

    def test_invalid_currency_code_rejected(self):
        """Invalid currency code should be rejected."""
        data = {
            "vendor_name": "Store",
            "total_amount": 10.00,
            "currency": "INVALID",  # Not 3 letters
        }
        with pytest.raises(ValidationError) as exc_info:
            LLMReceiptSchema(**data)
        assert "currency" in str(exc_info.value)

    def test_lowercase_currency_rejected(self):
        """Lowercase currency code should be rejected."""
        data = {
            "vendor_name": "Store",
            "total_amount": 10.00,
            "currency": "usd",  # Should be uppercase
        }
        with pytest.raises(ValidationError) as exc_info:
            LLMReceiptSchema(**data)
        assert "currency" in str(exc_info.value)

    def test_invalid_date_format_rejected(self):
        """Invalid date format should be rejected."""
        invalid_dates = [
            "01-15-2024",  # Wrong separator position
            "2024/01/15",  # Wrong separator
            "January 15, 2024",  # Human readable
            "15-01-2024",  # DD-MM-YYYY
            "2024-1-15",  # Single digit month
            "2024-01-5",  # Single digit day
            "not-a-date",
        ]

        for invalid_date in invalid_dates:
            data = {
                "vendor_name": "Store",
                "total_amount": 10.00,
                "receipt_date": invalid_date,
            }
            with pytest.raises(ValidationError) as exc_info:
                LLMReceiptSchema(**data)
            assert "receipt_date" in str(exc_info.value) or "Date" in str(exc_info.value)

    def test_valid_date_format_accepted(self):
        """Valid YYYY-MM-DD date should be accepted."""
        valid_dates = [
            "2024-01-15",
            "2023-12-31",
            "2024-02-29",  # Leap year
        ]

        for valid_date in valid_dates:
            data = {
                "vendor_name": "Store",
                "total_amount": 10.00,
                "receipt_date": valid_date,
            }
            schema = LLMReceiptSchema(**data)
            assert schema.receipt_date == valid_date

    def test_negative_amount_rejected(self):
        """Negative amounts should be rejected."""
        data = {
            "vendor_name": "Store",
            "total_amount": -10.00,
        }
        with pytest.raises(ValidationError) as exc_info:
            LLMReceiptSchema(**data)
        assert "total_amount" in str(exc_info.value)

    def test_negative_tax_rejected(self):
        """Negative tax should be rejected."""
        data = {
            "vendor_name": "Store",
            "total_amount": 10.00,
            "tax_amount": -1.00,
        }
        with pytest.raises(ValidationError) as exc_info:
            LLMReceiptSchema(**data)
        assert "tax_amount" in str(exc_info.value)

    def test_invalid_category_rejected(self):
        """Invalid category should be rejected."""
        data = {
            "vendor_name": "Store",
            "total_amount": 10.00,
            "category": "invalid_category",
        }
        with pytest.raises(ValidationError) as exc_info:
            LLMReceiptSchema(**data)
        assert "category" in str(exc_info.value)

    def test_valid_categories_accepted(self):
        """Valid categories should be accepted."""
        valid_categories = ["food", "travel", "office", "utilities", "subscription", "other"]

        for category in valid_categories:
            data = {
                "vendor_name": "Store",
                "total_amount": 10.00,
                "category": category,
            }
            schema = LLMReceiptSchema(**data)
            assert schema.category == category

    def test_category_case_insensitive(self):
        """Categories should be case-insensitive."""
        data = {
            "vendor_name": "Store",
            "total_amount": 10.00,
            "category": "FOOD",
        }
        schema = LLMReceiptSchema(**data)
        assert schema.category == "food"

    def test_null_values_accepted(self):
        """Null values for optional fields should be accepted."""
        data = {
            "vendor_name": None,
            "total_amount": None,
            "currency": "USD",
            "receipt_date": None,
            "tax_amount": None,
        }
        schema = LLMReceiptSchema(**data)
        assert schema.vendor_name is None
        assert schema.total_amount is None

    def test_extra_fields_ignored(self):
        """Extra fields from LLM should be handled gracefully."""
        data = {
            "vendor_name": "Store",
            "total_amount": 10.00,
            "extra_field": "should be ignored",
            "another_field": 123,
        }
        # Pydantic by default ignores extra fields
        schema = LLMReceiptSchema(**data)
        assert schema.vendor_name == "Store"
        assert not hasattr(schema, "extra_field")

    def test_string_amount_rejected(self):
        """String amount should be rejected (must be number)."""
        data = {
            "vendor_name": "Store",
            "total_amount": "$10.00",  # String with currency symbol
        }
        with pytest.raises(ValidationError):
            LLMReceiptSchema(**data)

    def test_empty_string_vendor_accepted(self):
        """Empty string vendor should be accepted (it's optional)."""
        data = {
            "vendor_name": "",
            "total_amount": 10.00,
        }
        schema = LLMReceiptSchema(**data)
        assert schema.vendor_name == ""
