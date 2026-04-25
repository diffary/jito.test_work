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


def list_journal(
    conn: sqlite3.Connection,
    date_from: date | None = None,
    date_to: date | None = None,
    accounts: list[str] | None = None,
) -> list[JournalRow]:
    sql = """SELECT je.id, d.id, d.doc_type, d.doc_date, p.name,
                    je.account_code, a.name, je.debit, je.credit,
                    d.description, d.status
             FROM journal_entries je
             JOIN documents d ON d.id = je.document_id
             JOIN partners p   ON p.id = d.partner_id
             JOIN accounts a   ON a.code = je.account_code
             WHERE 1=1"""
    params: list = []
    if date_from is not None:
        sql += " AND d.doc_date >= ?"
        params.append(date_from.isoformat())
    if date_to is not None:
        sql += " AND d.doc_date <= ?"
        params.append(date_to.isoformat())
    if accounts:
        placeholders = ",".join("?" * len(accounts))
        sql += f" AND je.account_code IN ({placeholders})"
        params.extend(accounts)
    sql += " ORDER BY d.doc_date, je.id"
    return [
        JournalRow(
            entry_id=r[0], doc_id=r[1], doc_type=DocType(r[2]),
            doc_date=date.fromisoformat(r[3]), partner_name=r[4],
            account_code=r[5], account_name=r[6],
            debit=r[7], credit=r[8],
            description=r[9], status=DocStatus(r[10]),
        )
        for r in conn.execute(sql, params)
    ]


def pnl_report(
    conn: sqlite3.Connection,
    date_from: date,
    date_to: date,
) -> PnLReport:
    """P&L over a date range. No document-status filter — arithmetic cancellation
    via reversal entries keeps reports correct. Aggregation in Python to preserve Decimal."""

    def _side(account_code: str) -> tuple[Decimal, list[PnLDocRow]]:
        # Revenue (4000): credit − debit positive. Expense (5000): debit − credit positive.
        rows = conn.execute(
            """SELECT d.id, d.doc_date, p.name, je.debit, je.credit, d.description
               FROM journal_entries je
               JOIN documents d ON d.id = je.document_id
               JOIN partners p ON p.id = d.partner_id
               WHERE je.account_code = ?
                 AND d.doc_date BETWEEN ? AND ?
               ORDER BY d.doc_date, d.id""",
            (account_code, date_from.isoformat(), date_to.isoformat()),
        ).fetchall()
        doc_rows = [
            PnLDocRow(
                doc_id=r[0],
                doc_date=date.fromisoformat(r[1]),
                partner_name=r[2],
                amount=(r[4] - r[3]) if account_code == "4000" else (r[3] - r[4]),
                description=r[5],
            )
            for r in rows
        ]
        total = sum((x.amount for x in doc_rows), Decimal("0"))
        return total, doc_rows

    revenue, rev_rows = _side("4000")
    expense, exp_rows = _side("5000")
    return PnLReport(
        date_from=date_from, date_to=date_to,
        revenue=revenue, expense=expense,
        revenue_rows=rev_rows, expense_rows=exp_rows,
    )


def partner_balances(conn: sqlite3.Connection) -> list[PartnerBalance]:
    """For each partner, outstanding balance on 1100 (AR) or 2000 (AP).
    No status filter — arithmetic via reversal entries handles cancellation.
    Python-side aggregation to preserve Decimal."""
    partners = repo.list_partners(conn)
    result: list[PartnerBalance] = []
    for p in partners:
        target_account = "1100" if p.kind == PartnerKind.CUSTOMER else "2000"
        rows = conn.execute(
            """SELECT je.debit, je.credit, d.doc_date
               FROM journal_entries je
               JOIN documents d ON d.id = je.document_id
               WHERE d.partner_id = ? AND je.account_code = ?""",
            (p.id, target_account),
        ).fetchall()
        if p.kind == PartnerKind.CUSTOMER:
            outstanding = sum((r[0] - r[1] for r in rows), Decimal("0"))
        else:
            outstanding = sum((r[1] - r[0] for r in rows), Decimal("0"))

        # Exclude reversals from invoice_count (a reversed invoice + its reversal
        # would otherwise count as 2). last_activity below intentionally counts
        # reversals — users want to see the partner's most recent touch.
        invoice_count_row = conn.execute(
            """SELECT COUNT(*) FROM documents
               WHERE partner_id = ?
                 AND doc_type IN ('SALES_INVOICE','PURCHASE_INVOICE')
                 AND reverses_id IS NULL
                 AND status = 'POSTED'""",
            (p.id,),
        ).fetchone()
        invoice_count = invoice_count_row[0]

        last_row = conn.execute(
            "SELECT MAX(doc_date) FROM documents WHERE partner_id = ?",
            (p.id,),
        ).fetchone()
        last_activity = date.fromisoformat(last_row[0]) if last_row[0] else None

        result.append(PartnerBalance(
            partner_id=p.id, name=p.name, kind=p.kind,
            outstanding=outstanding,
            invoice_count=invoice_count,
            last_activity=last_activity,
        ))
    return result
