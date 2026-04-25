import sqlite3
from decimal import Decimal
from app.db import connect, init_schema, seed_accounts


def test_init_schema_creates_all_tables():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert tables == {"accounts", "partners", "documents", "journal_entries"}


def test_seed_accounts_inserts_five_fixed_accounts():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    seed_accounts(conn)
    rows = list(conn.execute("SELECT code, name, type FROM accounts ORDER BY code"))
    assert rows == [
        ("1000", "Cash", "ASSET"),
        ("1100", "Accounts Receivable", "ASSET"),
        ("2000", "Accounts Payable", "LIABILITY"),
        ("4000", "Revenue", "INCOME"),
        ("5000", "Expense", "EXPENSE"),
    ]


def test_seed_accounts_is_idempotent():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    seed_accounts(conn)
    seed_accounts(conn)  # must not raise
    count, = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()
    assert count == 5


def test_connect_registers_decimal_roundtrip(tmp_path):
    db_file = tmp_path / "t.db"
    conn = connect(str(db_file))
    conn.execute("CREATE TABLE t(x NUMERIC)")
    conn.execute("INSERT INTO t(x) VALUES (?)", (Decimal("12.34"),))
    (v,) = conn.execute("SELECT x FROM t").fetchone()
    assert v == Decimal("12.34")
    assert isinstance(v, Decimal)
