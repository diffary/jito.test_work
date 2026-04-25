from datetime import date
from decimal import Decimal
from app.models import (
    Partner, Document, JournalEntry, JournalRow,
    PnLReport, PartnerBalance,
    PartnerKind, DocType, DocStatus,
)


def test_enums_have_expected_values():
    assert PartnerKind.CUSTOMER.value == "CUSTOMER"
    assert PartnerKind.SUPPLIER.value == "SUPPLIER"
    assert {d.value for d in DocType} == {
        "SALES_INVOICE", "PURCHASE_INVOICE",
        "CUSTOMER_PAYMENT", "SUPPLIER_PAYMENT",
    }
    assert {s.value for s in DocStatus} == {"POSTED", "REVERSED"}


def test_partner_is_frozen_dataclass():
    p = Partner(id=1, name="A", kind=PartnerKind.CUSTOMER, created_at="2026-04-25")
    assert p.id == 1


def test_pnl_net_income_property():
    r = PnLReport(
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
        revenue=Decimal("100"),
        expense=Decimal("30"),
        revenue_rows=[],
        expense_rows=[],
    )
    assert r.net_income == Decimal("70")
