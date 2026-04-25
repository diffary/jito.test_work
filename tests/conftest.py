import sqlite3
import pytest
from app.db import init_schema, seed_accounts, _register_decimal


@pytest.fixture
def db():
    _register_decimal()
    conn = sqlite3.connect(
        ":memory:",
        detect_types=sqlite3.PARSE_DECLTYPES,
        isolation_level=None,
    )
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    seed_accounts(conn)
    yield conn
    conn.close()
