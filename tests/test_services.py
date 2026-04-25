from decimal import Decimal
import pytest
from app.services import create_partner, list_partners as svc_list_partners
from app.models import PartnerKind


def test_create_partner_returns_id(db):
    pid = create_partner(db, "Acme", PartnerKind.CUSTOMER)
    assert isinstance(pid, int) and pid > 0


def test_create_partner_rejects_duplicate_name_case_insensitive(db):
    create_partner(db, "Acme", PartnerKind.CUSTOMER)
    with pytest.raises(ValueError, match="already exists"):
        create_partner(db, "ACME", PartnerKind.CUSTOMER)
    with pytest.raises(ValueError, match="already exists"):
        create_partner(db, "acme", PartnerKind.SUPPLIER)


def test_create_partner_rejects_empty_name(db):
    with pytest.raises(ValueError, match="name"):
        create_partner(db, "   ", PartnerKind.CUSTOMER)


def test_list_partners_filter_by_kind(db):
    create_partner(db, "Acme", PartnerKind.CUSTOMER)
    create_partner(db, "Supplies Co", PartnerKind.SUPPLIER)
    customers = svc_list_partners(db, kind=PartnerKind.CUSTOMER)
    assert {p.name for p in customers} == {"Acme"}


from datetime import date, timedelta
from app.services import post_document
from app.models import DocType


TODAY = date.today()


# --- Double-entry basics ---

def test_sales_invoice_creates_AR_debit_and_revenue_credit(db, customer):
    doc_id = post_document(db, DocType.SALES_INVOICE, TODAY, customer,
                           Decimal("100.00"), "Test sale")
    entries = _entries_for(db, doc_id)
    assert _dr_cr(entries) == {"1100": (Decimal("100.00"), Decimal("0")),
                               "4000": (Decimal("0"), Decimal("100.00"))}


def test_purchase_invoice_creates_expense_debit_and_AP_credit(db, supplier):
    doc_id = post_document(db, DocType.PURCHASE_INVOICE, TODAY, supplier,
                           Decimal("50.00"), None)
    assert _dr_cr(_entries_for(db, doc_id)) == {
        "5000": (Decimal("50.00"), Decimal("0")),
        "2000": (Decimal("0"), Decimal("50.00")),
    }


def test_customer_payment_clears_AR_and_increases_cash(db, customer):
    doc_id = post_document(db, DocType.CUSTOMER_PAYMENT, TODAY, customer,
                           Decimal("30.00"), None)
    assert _dr_cr(_entries_for(db, doc_id)) == {
        "1000": (Decimal("30.00"), Decimal("0")),
        "1100": (Decimal("0"), Decimal("30.00")),
    }


def test_supplier_payment_clears_AP_and_decreases_cash(db, supplier):
    doc_id = post_document(db, DocType.SUPPLIER_PAYMENT, TODAY, supplier,
                           Decimal("20.00"), None)
    assert _dr_cr(_entries_for(db, doc_id)) == {
        "2000": (Decimal("20.00"), Decimal("0")),
        "1000": (Decimal("0"), Decimal("20.00")),
    }


def test_journal_balanced_invariant(db, customer, supplier):
    post_document(db, DocType.SALES_INVOICE, TODAY, customer, Decimal("100"), None)
    post_document(db, DocType.PURCHASE_INVOICE, TODAY, supplier, Decimal("40"), None)
    post_document(db, DocType.CUSTOMER_PAYMENT, TODAY, customer, Decimal("60"), None)
    # Aggregate in Python to preserve Decimal — SQL SUM coerces NUMERIC to REAL.
    rows = db.execute("SELECT debit, credit FROM journal_entries").fetchall()
    total_dr = sum((r[0] for r in rows), Decimal("0"))
    total_cr = sum((r[1] for r in rows), Decimal("0"))
    assert total_dr == total_cr
    assert total_dr > 0  # sanity: we actually wrote entries


# --- Validation ---

def test_negative_amount_rejected(db, customer):
    with pytest.raises(ValueError, match="amount"):
        post_document(db, DocType.SALES_INVOICE, TODAY, customer, Decimal("-1"), None)


def test_zero_amount_rejected(db, customer):
    with pytest.raises(ValueError, match="amount"):
        post_document(db, DocType.SALES_INVOICE, TODAY, customer, Decimal("0"), None)


def test_future_doc_date_rejected(db, customer):
    with pytest.raises(ValueError, match="future"):
        post_document(db, DocType.SALES_INVOICE, TODAY + timedelta(days=1),
                      customer, Decimal("10"), None)


def test_sub_cent_precision_rejected(db, customer):
    with pytest.raises(ValueError, match="precision"):
        post_document(db, DocType.SALES_INVOICE, TODAY, customer,
                      Decimal("10.123"), None)


def test_ten_dot_one_accepted(db, customer):
    doc_id = post_document(db, DocType.SALES_INVOICE, TODAY, customer,
                           Decimal("10.1"), None)
    assert doc_id > 0


def test_sales_invoice_with_supplier_rejected(db, supplier):
    with pytest.raises(ValueError, match="kind"):
        post_document(db, DocType.SALES_INVOICE, TODAY, supplier,
                      Decimal("10"), None)


def test_purchase_invoice_with_customer_rejected(db, customer):
    with pytest.raises(ValueError, match="kind"):
        post_document(db, DocType.PURCHASE_INVOICE, TODAY, customer,
                      Decimal("10"), None)


def test_customer_payment_with_supplier_rejected(db, supplier):
    with pytest.raises(ValueError, match="kind"):
        post_document(db, DocType.CUSTOMER_PAYMENT, TODAY, supplier,
                      Decimal("10"), None)


def test_supplier_payment_with_customer_rejected(db, customer):
    with pytest.raises(ValueError, match="kind"):
        post_document(db, DocType.SUPPLIER_PAYMENT, TODAY, customer,
                      Decimal("10"), None)


def test_unknown_partner_id_rejected(db):
    with pytest.raises(ValueError, match="not found"):
        post_document(db, DocType.SALES_INVOICE, TODAY, 9999,
                      Decimal("10"), None)


# --- helpers ---

def _entries_for(db, doc_id):
    return list(db.execute(
        "SELECT account_code, debit, credit FROM journal_entries WHERE document_id = ?",
        (doc_id,)
    ))


def _dr_cr(entries):
    return {e[0]: (e[1], e[2]) for e in entries}
