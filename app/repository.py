import sqlite3
from datetime import date
from decimal import Decimal
from app.models import (
    Partner, Document, JournalEntry,
    PartnerKind, DocType, DocStatus,
)


def insert_partner(conn: sqlite3.Connection, name: str, kind: PartnerKind) -> int:
    cur = conn.execute(
        "INSERT INTO partners(name, kind) VALUES (?, ?)",
        (name, kind.value),
    )
    return cur.lastrowid


def list_partners(conn: sqlite3.Connection, kind: PartnerKind | None = None) -> list[Partner]:
    sql = "SELECT id, name, kind, created_at FROM partners"
    params: tuple = ()
    if kind is not None:
        sql += " WHERE kind = ?"
        params = (kind.value,)
    sql += " ORDER BY name COLLATE NOCASE"
    return [
        Partner(id=r[0], name=r[1], kind=PartnerKind(r[2]), created_at=r[3])
        for r in conn.execute(sql, params)
    ]


def get_partner(conn: sqlite3.Connection, partner_id: int) -> Partner | None:
    row = conn.execute(
        "SELECT id, name, kind, created_at FROM partners WHERE id = ?",
        (partner_id,),
    ).fetchone()
    if row is None:
        return None
    return Partner(id=row[0], name=row[1], kind=PartnerKind(row[2]), created_at=row[3])


def partner_name_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM partners WHERE name = ? COLLATE NOCASE LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def insert_document(
    conn: sqlite3.Connection,
    doc_type: DocType,
    doc_date: date,
    partner_id: int,
    amount: Decimal,
    description: str | None,
    reverses_id: int | None,
) -> int:
    cur = conn.execute(
        """INSERT INTO documents(doc_type, doc_date, partner_id, amount,
                                 description, reverses_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (doc_type.value, doc_date.isoformat(), partner_id, amount,
         description, reverses_id),
    )
    return cur.lastrowid


def get_document(conn: sqlite3.Connection, doc_id: int) -> Document | None:
    row = conn.execute(
        """SELECT id, doc_type, doc_date, partner_id, amount, description,
                  status, reverses_id, created_at
           FROM documents WHERE id = ?""",
        (doc_id,),
    ).fetchone()
    if row is None:
        return None
    return Document(
        id=row[0],
        doc_type=DocType(row[1]),
        doc_date=date.fromisoformat(row[2]),
        partner_id=row[3],
        amount=row[4],
        description=row[5],
        status=DocStatus(row[6]),
        reverses_id=row[7],
        created_at=row[8],
    )


def update_document_status(conn: sqlite3.Connection, doc_id: int, status: DocStatus) -> None:
    conn.execute(
        "UPDATE documents SET status = ? WHERE id = ?",
        (status.value, doc_id),
    )


def list_documents(conn: sqlite3.Connection) -> list[Document]:
    rows = conn.execute(
        """SELECT id, doc_type, doc_date, partner_id, amount, description,
                  status, reverses_id, created_at
           FROM documents ORDER BY id DESC"""
    ).fetchall()
    return [
        Document(
            id=r[0], doc_type=DocType(r[1]), doc_date=date.fromisoformat(r[2]),
            partner_id=r[3], amount=r[4], description=r[5],
            status=DocStatus(r[6]), reverses_id=r[7], created_at=r[8],
        )
        for r in rows
    ]


def insert_journal_entry(
    conn: sqlite3.Connection,
    document_id: int,
    account_code: str,
    debit: Decimal,
    credit: Decimal,
) -> int:
    cur = conn.execute(
        "INSERT INTO journal_entries(document_id, account_code, debit, credit) VALUES (?, ?, ?, ?)",
        (document_id, account_code, debit, credit),
    )
    return cur.lastrowid


def list_journal_entries(
    conn: sqlite3.Connection,
    document_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    accounts: list[str] | None = None,
) -> list[JournalEntry]:
    sql = """SELECT je.id, je.document_id, je.account_code, je.debit, je.credit
             FROM journal_entries je
             JOIN documents d ON d.id = je.document_id
             WHERE 1=1"""
    params: list = []
    if document_id is not None:
        sql += " AND je.document_id = ?"
        params.append(document_id)
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
    sql += " ORDER BY je.id"
    return [
        JournalEntry(id=r[0], document_id=r[1], account_code=r[2],
                     debit=r[3], credit=r[4])
        for r in conn.execute(sql, params)
    ]
