import threading
from datetime import date
from decimal import Decimal
import sqlite3
from app import repository as repo
from app.models import (
    Partner, Document, DocType, DocStatus, PartnerKind,
    JournalRow, PnLReport, PnLDocRow, PartnerBalance,
)

_write_lock = threading.Lock()


def create_partner(conn: sqlite3.Connection, name: str, kind: PartnerKind) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Partner name must not be empty")
    with _write_lock:
        if repo.partner_name_exists(conn, name):
            raise ValueError(f"Partner with name '{name}' already exists")
        return repo.insert_partner(conn, name, kind)


def list_partners(conn: sqlite3.Connection, kind: PartnerKind | None = None) -> list[Partner]:
    return repo.list_partners(conn, kind=kind)


CENT = Decimal("0.01")

# (doc_type) -> (required partner kind, debit account, credit account)
ACCOUNT_MAP: dict[DocType, tuple[PartnerKind, str, str]] = {
    DocType.SALES_INVOICE:    (PartnerKind.CUSTOMER, "1100", "4000"),
    DocType.CUSTOMER_PAYMENT: (PartnerKind.CUSTOMER, "1000", "1100"),
    DocType.PURCHASE_INVOICE: (PartnerKind.SUPPLIER, "5000", "2000"),
    DocType.SUPPLIER_PAYMENT: (PartnerKind.SUPPLIER, "2000", "1000"),
}


def _validate_amount(amount: Decimal) -> None:
    if amount <= 0:
        raise ValueError("amount must be positive")
    if amount != amount.quantize(CENT):
        raise ValueError("amount has sub-cent precision; max 2 decimals")


def _validate_date(doc_date: date) -> None:
    if doc_date > date.today():
        raise ValueError("doc_date cannot be in the future")


def post_document(
    conn: sqlite3.Connection,
    doc_type: DocType,
    doc_date: date,
    partner_id: int,
    amount: Decimal,
    description: str | None = None,
) -> int:
    _validate_amount(amount)
    _validate_date(doc_date)

    required_kind, dr_acc, cr_acc = ACCOUNT_MAP[doc_type]
    partner = repo.get_partner(conn, partner_id)
    if partner is None:
        raise ValueError(f"Partner id={partner_id} not found")
    if partner.kind != required_kind:
        raise ValueError(
            f"{doc_type.value} requires partner kind {required_kind.value}, "
            f"got {partner.kind.value}"
        )

    amount = amount.quantize(CENT)

    with _write_lock:
        conn.execute("BEGIN IMMEDIATE")
        try:
            doc_id = repo.insert_document(
                conn, doc_type, doc_date, partner_id, amount, description, None,
            )
            repo.insert_journal_entry(conn, doc_id, dr_acc, amount, Decimal("0"))
            repo.insert_journal_entry(conn, doc_id, cr_acc, Decimal("0"), amount)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return doc_id


def reverse_document(conn: sqlite3.Connection, document_id: int) -> int:
    original = repo.get_document(conn, document_id)
    if original is None:
        raise ValueError(f"Document id={document_id} not found")
    if original.reverses_id is not None:
        raise ValueError("Cannot reverse a reversal")
    if original.status == DocStatus.REVERSED:
        raise ValueError("Document is already reversed")

    _, dr_acc, cr_acc = ACCOUNT_MAP[original.doc_type]

    with _write_lock:
        conn.execute("BEGIN IMMEDIATE")
        try:
            rev_id = repo.insert_document(
                conn,
                doc_type=original.doc_type,
                doc_date=date.today(),
                partner_id=original.partner_id,
                amount=original.amount,
                description=f"Reversal of #{original.id}",
                reverses_id=original.id,
            )
            # Swap Dr/Cr on the same accounts
            repo.insert_journal_entry(conn, rev_id, cr_acc, original.amount, Decimal("0"))
            repo.insert_journal_entry(conn, rev_id, dr_acc, Decimal("0"), original.amount)
            repo.update_document_status(conn, original.id, DocStatus.REVERSED)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return rev_id
