from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class PartnerKind(str, Enum):
    CUSTOMER = "CUSTOMER"
    SUPPLIER = "SUPPLIER"


class DocType(str, Enum):
    SALES_INVOICE = "SALES_INVOICE"
    PURCHASE_INVOICE = "PURCHASE_INVOICE"
    CUSTOMER_PAYMENT = "CUSTOMER_PAYMENT"
    SUPPLIER_PAYMENT = "SUPPLIER_PAYMENT"


class DocStatus(str, Enum):
    POSTED = "POSTED"
    REVERSED = "REVERSED"


@dataclass(frozen=True)
class Partner:
    id: int
    name: str
    kind: PartnerKind
    created_at: str


@dataclass(frozen=True)
class Document:
    id: int
    doc_type: DocType
    doc_date: date
    partner_id: int
    amount: Decimal
    description: str | None
    status: DocStatus
    reverses_id: int | None
    created_at: str


@dataclass(frozen=True)
class JournalEntry:
    id: int
    document_id: int
    account_code: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class JournalRow:
    """Joined view for UI: entry + document + partner + account name."""
    entry_id: int
    doc_id: int
    doc_type: DocType
    doc_date: date
    partner_name: str
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal
    description: str | None
    status: DocStatus


@dataclass(frozen=True)
class PnLDocRow:
    doc_id: int
    doc_date: date
    partner_name: str
    amount: Decimal
    description: str | None


@dataclass(frozen=True)
class PnLReport:
    date_from: date
    date_to: date
    revenue: Decimal
    expense: Decimal
    revenue_rows: list[PnLDocRow] = field(default_factory=list)
    expense_rows: list[PnLDocRow] = field(default_factory=list)

    @property
    def net_income(self) -> Decimal:
        return self.revenue - self.expense


@dataclass(frozen=True)
class PartnerBalance:
    partner_id: int
    name: str
    kind: PartnerKind
    outstanding: Decimal
    invoice_count: int
    last_activity: date | None
