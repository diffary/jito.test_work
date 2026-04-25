from datetime import date
from decimal import Decimal
import pytest
from app.repository import (
    insert_partner, list_partners, get_partner, partner_name_exists,
    insert_document, get_document, update_document_status, list_documents,
    insert_journal_entry, list_journal_entries,
)
from app.models import PartnerKind, DocType, DocStatus


def test_insert_and_get_partner(db):
    pid = insert_partner(db, "Acme", PartnerKind.CUSTOMER)
    p = get_partner(db, pid)
    assert p.name == "Acme"
    assert p.kind == PartnerKind.CUSTOMER


def test_list_partners_filter_by_kind(db):
    insert_partner(db, "Acme", PartnerKind.CUSTOMER)
    insert_partner(db, "Beta", PartnerKind.SUPPLIER)
    customers = list_partners(db, kind=PartnerKind.CUSTOMER)
    assert {p.name for p in customers} == {"Acme"}
    all_ = list_partners(db)
    assert {p.name for p in all_} == {"Acme", "Beta"}


def test_partner_name_exists_case_insensitive(db):
    insert_partner(db, "Acme", PartnerKind.CUSTOMER)
    assert partner_name_exists(db, "acme") is True
    assert partner_name_exists(db, "ACME") is True
    assert partner_name_exists(db, "Other") is False


def test_insert_document_and_entries_in_transaction(db):
    pid = insert_partner(db, "Acme", PartnerKind.CUSTOMER)
    doc_id = insert_document(
        db,
        doc_type=DocType.SALES_INVOICE,
        doc_date=date(2026, 4, 10),
        partner_id=pid,
        amount=Decimal("100.00"),
        description="Test",
        reverses_id=None,
    )
    insert_journal_entry(db, doc_id, "1100", Decimal("100.00"), Decimal("0"))
    insert_journal_entry(db, doc_id, "4000", Decimal("0"), Decimal("100.00"))
    doc = get_document(db, doc_id)
    assert doc.amount == Decimal("100.00")
    assert doc.status == DocStatus.POSTED
    entries = list_journal_entries(db, document_id=doc_id)
    assert len(entries) == 2


def test_get_document_returns_none_for_unknown_id(db):
    assert get_document(db, 99999) is None


def test_update_document_status(db):
    pid = insert_partner(db, "Acme", PartnerKind.CUSTOMER)
    doc_id = insert_document(
        db, DocType.SALES_INVOICE, date(2026, 4, 10), pid,
        Decimal("50.00"), None, None,
    )
    update_document_status(db, doc_id, DocStatus.REVERSED)
    assert get_document(db, doc_id).status == DocStatus.REVERSED


def test_list_journal_entries_date_and_account_filters(db):
    pid = insert_partner(db, "Acme", PartnerKind.CUSTOMER)
    d1 = insert_document(db, DocType.SALES_INVOICE, date(2026, 4, 10), pid,
                         Decimal("10"), None, None)
    d2 = insert_document(db, DocType.SALES_INVOICE, date(2026, 5, 10), pid,
                         Decimal("20"), None, None)
    insert_journal_entry(db, d1, "1100", Decimal("10"), Decimal("0"))
    insert_journal_entry(db, d1, "4000", Decimal("0"), Decimal("10"))
    insert_journal_entry(db, d2, "1100", Decimal("20"), Decimal("0"))
    insert_journal_entry(db, d2, "4000", Decimal("0"), Decimal("20"))

    april = list_journal_entries(db, date_from=date(2026, 4, 1), date_to=date(2026, 4, 30))
    assert {e.document_id for e in april} == {d1}

    only_4000 = list_journal_entries(db, accounts=["4000"])
    assert {e.account_code for e in only_4000} == {"4000"}
