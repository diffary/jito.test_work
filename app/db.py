import os
import sqlite3
from decimal import Decimal
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE,
    kind TEXT NOT NULL CHECK (kind IN ('CUSTOMER','SUPPLIER')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_partner_name_nocase
    ON partners(name COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type TEXT NOT NULL CHECK (doc_type IN (
        'SALES_INVOICE','PURCHASE_INVOICE',
        'CUSTOMER_PAYMENT','SUPPLIER_PAYMENT')),
    doc_date TEXT NOT NULL,
    partner_id INTEGER NOT NULL REFERENCES partners(id),
    amount NUMERIC NOT NULL CHECK (amount > 0),
    description TEXT,
    status TEXT NOT NULL DEFAULT 'POSTED'
        CHECK (status IN ('POSTED','REVERSED')),
    reverses_id INTEGER REFERENCES documents(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    account_code TEXT NOT NULL REFERENCES accounts(code),
    debit NUMERIC NOT NULL DEFAULT 0,
    credit NUMERIC NOT NULL DEFAULT 0,
    CHECK ((debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0))
);
CREATE INDEX IF NOT EXISTS idx_journal_doc ON journal_entries(document_id);
CREATE INDEX IF NOT EXISTS idx_journal_account ON journal_entries(account_code);
CREATE INDEX IF NOT EXISTS idx_doc_date ON documents(doc_date);
"""

ACCOUNTS_SEED = [
    ("1000", "Cash", "ASSET"),
    ("1100", "Accounts Receivable", "ASSET"),
    ("2000", "Accounts Payable", "LIABILITY"),
    ("4000", "Revenue", "INCOME"),
    ("5000", "Expense", "EXPENSE"),
]


def _register_decimal():
    sqlite3.register_adapter(Decimal, str)
    sqlite3.register_converter("NUMERIC", lambda b: Decimal(b.decode()))


_register_decimal()


def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or os.environ.get("DB_PATH", "./data/accounting.db")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        path,
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
        isolation_level=None,
    )
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    seed_accounts(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def seed_accounts(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO accounts(code, name, type) VALUES (?, ?, ?)",
        ACCOUNTS_SEED,
    )
