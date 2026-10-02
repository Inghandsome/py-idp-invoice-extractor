from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InvoiceData:
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    currency: Optional[str] = None
    raw_fields: dict = field(default_factory=dict)
