from datetime import date
from decimal import Decimal
import pytest
from app.services import post_document, reverse_document, pnl_report
from app.models import DocType


def test_pnl_returns_zero_for_empty_period(db):
    r = pnl_report(db, date(2026, 1, 1), date(2026, 1, 31))
    assert r.revenue == Decimal("0")
    assert r.expense == Decimal("0")
    assert r.net_income == Decimal("0")


def test_pnl_includes_only_documents_in_range(db, customer, supplier):
    post_document(db, DocType.SALES_INVOICE, date(2026, 1, 15), customer,
                  Decimal("100"), None)
    post_document(db, DocType.PURCHASE_INVOICE, date(2026, 1, 20), supplier,
                  Decimal("30"), None)
    # Out of range
    post_document(db, DocType.SALES_INVOICE, date(2026, 2, 10), customer,
                  Decimal("999"), None)

    r = pnl_report(db, date(2026, 1, 1), date(2026, 1, 31))
    assert r.revenue == Decimal("100")
    assert r.expense == Decimal("30")
    assert r.net_income == Decimal("70")


def test_pnl_invoice_and_reversal_in_same_period_net_to_zero(db, customer, monkeypatch):
    """Invoice on Jan 10, reversal also in Jan -> revenue = 0."""
    import app.services as svc
    from datetime import date as _date

    class _D(_date):
        @classmethod
        def today(cls):
            return _date(2026, 1, 20)

    monkeypatch.setattr(svc, "date", _D)  # so reverse_document uses Jan 20

    doc_id = post_document(db, DocType.SALES_INVOICE, date(2026, 1, 10), customer,
                           Decimal("100"), None)
    reverse_document(db, doc_id)

    r = pnl_report(db, date(2026, 1, 1), date(2026, 1, 31))
    assert r.revenue == Decimal("0")
    assert r.net_income == Decimal("0")


def test_pnl_invoice_in_period_reversal_in_later_period_keeps_invoice_in_original_period(
    db, customer, monkeypatch
):
    """January invoice stays in January P&L even when reversed in February."""
    import app.services as svc
    from datetime import date as _date

    class _Feb(_date):
        @classmethod
        def today(cls):
            return _date(2026, 2, 15)

    doc_id = post_document(db, DocType.SALES_INVOICE, date(2026, 1, 10), customer,
                           Decimal("100"), None)

    monkeypatch.setattr(svc, "date", _Feb)
    reverse_document(db, doc_id)

    r_jan = pnl_report(db, date(2026, 1, 1), date(2026, 1, 31))
    assert r_jan.revenue == Decimal("100")  # original stays in Jan

    r_feb = pnl_report(db, date(2026, 2, 1), date(2026, 2, 28))
    assert r_feb.revenue == Decimal("-100")  # reversal dated Feb


def test_pnl_net_income_equals_revenue_minus_expense(db, customer, supplier):
    post_document(db, DocType.SALES_INVOICE, date(2026, 1, 10), customer,
                  Decimal("500"), None)
    post_document(db, DocType.PURCHASE_INVOICE, date(2026, 1, 11), supplier,
                  Decimal("150"), None)
    r = pnl_report(db, date(2026, 1, 1), date(2026, 1, 31))
    assert r.net_income == r.revenue - r.expense == Decimal("350")
