from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class Line(BaseModel):
    description: str = ""
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    tax_type: str | None = None
    tax_rate: Decimal | None = None
    classification_code: str | None = None
    line_total: Decimal | None = None


class Extracted(BaseModel):
    """What an extractor returns. `lines=None` means 'not extracted' (line rules are skipped)."""

    supplier_name: str | None = None
    supplier_tin: str | None = None
    supplier_id_type: str | None = None
    supplier_id_value: str | None = None
    invoice_number: str | None = None
    issue_date: date | None = None
    currency: str | None = None
    exchange_rate: Decimal | None = None
    lines: list[Line] | None = None
    subtotal: Decimal | None = None
    tax_total: Decimal | None = None
    total: Decimal | None = None
    has_uin: bool | None = None
    field_confidence: dict[str, float] = Field(default_factory=dict)


CRITICAL_FIELDS = ["invoice_number", "issue_date", "supplier_tin", "currency", "total"]
HEADER_FIELDS = CRITICAL_FIELDS + ["supplier_name", "subtotal", "tax_total"]
