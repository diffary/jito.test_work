# Accounting Demo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal Streamlit accounting demo that posts double-entry journal entries for four document types (sales/purchase invoices, customer/supplier payments), supports storno reversal, and reports P&L and partner balances over SQLite.

**Architecture:** Layered — Streamlit UI (thin) → `services.py` (all business logic + posting rules + `threading.Lock`) → `repository.py` (pure SQL) → SQLite (file, or `:memory:` for tests). Immutable journal; corrections via storno (new doc with swapped Dr/Cr). No status filter in reports — arithmetic cancellation handles reversals.

**Tech Stack:** Python 3.11, Streamlit 1.40, SQLite, pytest 8.3, Docker.

**Spec:** `docs/superpowers/specs/2026-04-23-accounting-demo-design.md` — read before starting.

**Working directory:** `d:/files/test_project/`

---

## File Structure

### App package (`app/`)
| File | Responsibility |
|---|---|
| `app/__init__.py` | Empty marker. |
| `app/db.py` | Connection factory (`connect`), schema init (`init_schema`), seed accounts (`seed_accounts`), Decimal adapter/converter registration. |
| `app/models.py` | `@dataclass`: `Partner`, `Document`, `JournalEntry`, `JournalRow`, `PnLReport`, `PartnerBalance`, enums `DocType`, `PartnerKind`, `DocStatus`. |
| `app/repository.py` | Pure-SQL CRUD. No business logic. Functions: `insert_partner`, `list_partners`, `get_partner`, `partner_name_exists`, `insert_document`, `get_document`, `update_document_status`, `list_documents`, `insert_journal_entry`, `list_journal_entries`. |
| `app/services.py` | Business logic: `create_partner`, `list_partners` (wrapper), `post_document`, `reverse_document`, `list_journal`, `pnl_report`, `partner_balances`. Uses module-level `threading.Lock` to serialize writes. Holds the `ACCOUNT_MAP` table. |
| `app/formatting.py` | `format_money(Decimal) -> str` reading `CURRENCY` env var. |
| `app/ui/__init__.py` | Empty marker. |
| `app/ui/_session.py` | Shared helpers imported by every Streamlit script: `get_conn()` (cached sqlite3 connection). Lives here — NOT in `main.py` — so that page modules can import it without triggering dashboard rendering as a side-effect of module import. |
| `app/ui/main.py` | Streamlit entry point (Dashboard). Guarded with `if __name__ == "__main__"`. |
| `app/ui/pages/1_Documents.py` | Post documents + reverse. |
| `app/ui/pages/2_Journal.py` | Journal table with filters + CSV export. |
| `app/ui/pages/3_Partners.py` | Partner CRUD + balances. |
| `app/ui/pages/4_Reports.py` | P&L report + CSV export. |

### Tests (`tests/`)
| File | Responsibility |
|---|---|
| `tests/__init__.py` | Empty marker. |
| `tests/conftest.py` | Fixtures: `db` (in-memory SQLite with schema + seeded accounts), `customer`, `supplier`. |
| `tests/test_services.py` | Double-entry, reversal, validation, partner-balance scenarios. |
| `tests/test_pnl.py` | P&L scenarios (date range, cancellation, past-period stability). |

### Project root
| File | Responsibility |
|---|---|
| `requirements.txt` | Pinned deps. |
| `pytest.ini` | Pytest config. |
| `Dockerfile` | Python 3.11 slim + streamlit. |
| `docker-compose.yml` | App service with volume mount. |
| `.env.example` | `CURRENCY=USD`, `DB_PATH=/app/data/accounting.db`. |
| `.dockerignore` | Exclude `.venv`, `data/`, `__pycache__`, `tests/`, `docs/`. |
| `.gitignore` | Exclude `.venv`, `data/*.db`, `__pycache__`, `.pytest_cache`, `.env`. |
| `README.md` | Quickstart. |

---

## Testing strategy (recap)

- Service layer only. UI not covered.
- Real SQLite but `:memory:`, fresh DB per test.
- Target: ~27 tests, `pytest -q` ≤ 1 s.

---

## Task 1: Project scaffolding + git init

**Files:**
- Create: `app/__init__.py`, `app/ui/__init__.py`, `app/ui/pages/.gitkeep`, `tests/__init__.py`, `data/.gitkeep`, `requirements.txt`, `pytest.ini`, `.gitignore`, `.dockerignore`, `.env.example`

- [ ] **Step 1: Initialize git repo**

```bash
cd d:/files/test_project
git init
# Stage only files that already exist on disk (spec + history + plan).
git add docs/ PROMPT_HISTORY.md 2>/dev/null || true
git status
```
If the commit below fails because nothing is staged, skip it and fold the first commit into Step 10.

```bash
git commit -m "chore: initial commit with spec and plan" || echo "nothing to commit yet"
```

- [ ] **Step 2: Create package directories and markers**

```bash
mkdir -p app/ui/pages tests data
touch app/__init__.py app/ui/__init__.py tests/__init__.py data/.gitkeep app/ui/pages/.gitkeep
```

- [ ] **Step 3: Write `requirements.txt`**

```
streamlit==1.40.0
pytest==8.3.3
```

- [ ] **Step 4: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -q
```

- [ ] **Step 5: Write `.gitignore`**

```
.venv/
venv/
__pycache__/
*.pyc
.pytest_cache/
.env
data/*.db
.DS_Store
```

- [ ] **Step 6: Write `.dockerignore`**

```
.git
.venv
venv
__pycache__
*.pyc
.pytest_cache
data
tests
docs
.env
```

- [ ] **Step 7: Write `.env.example`**

```
CURRENCY=USD
DB_PATH=./data/accounting.db
```

- [ ] **Step 8: Install deps (local dev)**

Run: `python -m venv .venv && .venv/Scripts/pip install -r requirements.txt`
Expected: Successfully installed streamlit-1.40.0 pytest-8.3.3 (and transitive deps).

- [ ] **Step 9: Verify pytest discovers no tests yet**

Run: `.venv/Scripts/pytest`
Expected: `no tests ran`.

- [ ] **Step 10: Commit**

```bash
git add app/ tests/ data/ requirements.txt pytest.ini .gitignore .dockerignore .env.example
git commit -m "chore: project scaffolding"
```

---

## Task 2: Database layer — schema, Decimal adapters, seed

**Files:**
- Create: `app/db.py`, `tests/conftest.py`, `tests/test_db.py`

- [ ] **Step 1: Write failing schema test**

Create `tests/test_db.py`:

```python
import sqlite3
from decimal import Decimal
from app.db import connect, init_schema, seed_accounts


def test_init_schema_creates_all_tables(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
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
```

- [ ] **Step 2: Run test, verify it fails**

Run: `.venv/Scripts/pytest tests/test_db.py -v`
Expected: `ModuleNotFoundError: app.db`.

- [ ] **Step 3: Implement `app/db.py`**

```python
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
        isolation_level=None,  # autocommit; transactions via explicit BEGIN
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
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `.venv/Scripts/pytest tests/test_db.py -v`
Expected: 4 passed.

- [ ] **Step 5: Write `tests/conftest.py`**

```python
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
```

- [ ] **Step 6: Commit**

```bash
git add app/db.py tests/conftest.py tests/test_db.py
git commit -m "feat(db): schema, Decimal adapters, account seeding"
```

---

## Task 3: Data models (dataclasses + enums)

**Files:**
- Create: `app/models.py`, `tests/test_models.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run test, verify fail**

Run: `.venv/Scripts/pytest tests/test_models.py -v`
Expected: `ModuleNotFoundError: app.models`.

- [ ] **Step 3: Implement `app/models.py`**

```python
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class PartnerKind(str, Enum):
    CUSTOMER = "CUSTOMER"
    SUPPLIER = "SUPPLIER"


class DocType(str, Enum):
    SALES_INVOICE = "SALES_INVOICE"
    PURCHASE_INVOICE = "PURCHASE_INVOICE"
    CUSTOMER_PAYMENT = "CUSTOMER_PAYMENT"
    SUPPLIER_PAYMENT = "SUPPLIER_PAYMENT"


class DocStatus(str, Enum):
    POSTED = "POSTED"
    REVERSED = "REVERSED"


@dataclass(frozen=True)
class Partner:
    id: int
    name: str
    kind: PartnerKind
    created_at: str


@dataclass(frozen=True)
class Document:
    id: int
    doc_type: DocType
    doc_date: date
    partner_id: int
    amount: Decimal
    description: str | None
    status: DocStatus
    reverses_id: int | None
    created_at: str


@dataclass(frozen=True)
class JournalEntry:
    id: int
    document_id: int
    account_code: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class JournalRow:
    """Joined view for UI: entry + document + partner + account name."""
    entry_id: int
    doc_id: int
    doc_type: DocType
    doc_date: date
    partner_name: str
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal
    description: str | None
    status: DocStatus


@dataclass(frozen=True)
class PnLDocRow:
    doc_id: int
    doc_date: date
    partner_name: str
    amount: Decimal  # signed: positive = contributes, negative = reversal entry
    description: str | None


@dataclass(frozen=True)
class PnLReport:
    date_from: date
    date_to: date
    revenue: Decimal
    expense: Decimal
    revenue_rows: list[PnLDocRow] = field(default_factory=list)
    expense_rows: list[PnLDocRow] = field(default_factory=list)

    @property
    def net_income(self) -> Decimal:
        return self.revenue - self.expense


@dataclass(frozen=True)
class PartnerBalance:
    partner_id: int
    name: str
    kind: PartnerKind
    outstanding: Decimal  # AR for customers (Dr−Cr on 1100); AP for suppliers (Cr−Dr on 2000)
    invoice_count: int
    last_activity: date | None
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/Scripts/pytest tests/test_models.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat(models): dataclasses and enums for domain types"
```

---

## Task 4: Repository layer

**Files:**
- Create: `app/repository.py`, `tests/test_repository.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_repository.py`:

```python
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
```

- [ ] **Step 2: Run tests, verify fail**

Run: `.venv/Scripts/pytest tests/test_repository.py -v`
Expected: `ModuleNotFoundError: app.repository`.

- [ ] **Step 3: Implement `app/repository.py`**

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/Scripts/pytest tests/test_repository.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add app/repository.py tests/test_repository.py
git commit -m "feat(repository): CRUD for partners, documents, journal entries"
```

---

## Task 5: Services — partners (create + list)

**Files:**
- Create: `app/services.py`
- Modify: `tests/conftest.py` (add `customer`, `supplier` fixtures)
- Create: `tests/test_services.py` (initial partner tests)

- [ ] **Step 1: Write failing test**

Create `tests/test_services.py`:

```python
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
```

Extend `tests/conftest.py`:

```python
@pytest.fixture
def customer(db):
    from app.services import create_partner
    from app.models import PartnerKind
    pid = create_partner(db, "Acme Corp", PartnerKind.CUSTOMER)
    return pid


@pytest.fixture
def supplier(db):
    from app.services import create_partner
    from app.models import PartnerKind
    pid = create_partner(db, "Office Ltd", PartnerKind.SUPPLIER)
    return pid
```

- [ ] **Step 2: Run tests, verify fail**

Run: `.venv/Scripts/pytest tests/test_services.py -v`
Expected: `ModuleNotFoundError: app.services`.

- [ ] **Step 3: Implement `app/services.py` (partner functions only for now)**

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/Scripts/pytest tests/test_services.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services.py tests/test_services.py tests/conftest.py
git commit -m "feat(services): create_partner with case-insensitive uniqueness"
```

---

## Task 6: Services — `post_document` with all 4 doc types + validation

**Files:**
- Modify: `app/services.py`
- Modify: `tests/test_services.py`

- [ ] **Step 1: Append failing tests**

Add to `tests/test_services.py`:

```python
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
```

- [ ] **Step 2: Run tests, verify fail**

Run: `.venv/Scripts/pytest tests/test_services.py -v`
Expected: 14 new tests failing on missing `post_document`.

- [ ] **Step 3: Implement `post_document` in `app/services.py`**

Append:

```python
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
            f"{doc_type.value} requires {required_kind.value} partner, "
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/Scripts/pytest tests/test_services.py -v`
Expected: all 18 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services.py tests/test_services.py
git commit -m "feat(services): post_document with validation and 4 doc types"
```

---

## Task 7: Services — `reverse_document`

**Files:**
- Modify: `app/services.py`, `tests/test_services.py`

- [ ] **Step 1: Append failing tests**

```python
from app.services import reverse_document
from app.models import DocStatus


def test_reverse_sales_invoice_creates_mirrored_entries(db, customer):
    original_id = post_document(db, DocType.SALES_INVOICE, TODAY, customer,
                                Decimal("100.00"), "Sale")
    rev_id = reverse_document(db, original_id)

    # Original flipped
    (status,) = db.execute("SELECT status FROM documents WHERE id=?", (original_id,)).fetchone()
    assert status == "REVERSED"

    # Reversal entries: Dr 4000 / Cr 1100
    rev_entries = _entries_for(db, rev_id)
    assert _dr_cr(rev_entries) == {
        "4000": (Decimal("100.00"), Decimal("0")),
        "1100": (Decimal("0"), Decimal("100.00")),
    }

    # Reversal links to original
    (reverses_id,) = db.execute("SELECT reverses_id FROM documents WHERE id=?", (rev_id,)).fetchone()
    assert reverses_id == original_id


def test_reversal_gets_today_as_doc_date(db, customer):
    original_id = post_document(
        db, DocType.SALES_INVOICE,
        date(2026, 1, 15), customer, Decimal("10"), None,
    )
    rev_id = reverse_document(db, original_id)
    (rev_date,) = db.execute("SELECT doc_date FROM documents WHERE id=?", (rev_id,)).fetchone()
    assert rev_date == TODAY.isoformat()


def test_cannot_reverse_already_reversed(db, customer):
    doc_id = post_document(db, DocType.SALES_INVOICE, TODAY, customer, Decimal("10"), None)
    reverse_document(db, doc_id)
    with pytest.raises(ValueError, match="already reversed"):
        reverse_document(db, doc_id)


def test_cannot_reverse_a_reversal(db, customer):
    doc_id = post_document(db, DocType.SALES_INVOICE, TODAY, customer, Decimal("10"), None)
    rev_id = reverse_document(db, doc_id)
    with pytest.raises(ValueError, match="reversal"):
        reverse_document(db, rev_id)


def test_cannot_reverse_nonexistent(db):
    with pytest.raises(ValueError, match="not found"):
        reverse_document(db, 99999)


def test_journal_remains_balanced_after_reversal(db, customer):
    post_document(db, DocType.SALES_INVOICE, TODAY, customer, Decimal("100"), None)
    doc_id = post_document(db, DocType.SALES_INVOICE, TODAY, customer, Decimal("40"), None)
    reverse_document(db, doc_id)
    rows = db.execute("SELECT debit, credit FROM journal_entries").fetchall()
    total_dr = sum((r[0] for r in rows), Decimal("0"))
    total_cr = sum((r[1] for r in rows), Decimal("0"))
    assert total_dr == total_cr
```

- [ ] **Step 2: Run tests, verify fail**

Run: `.venv/Scripts/pytest tests/test_services.py::test_reverse_sales_invoice_creates_mirrored_entries -v`
Expected: `ImportError: cannot import name 'reverse_document'`.

- [ ] **Step 3: Implement `reverse_document`**

Append to `app/services.py`:

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/Scripts/pytest tests/test_services.py -v`
Expected: all tests pass, including the 6 new reversal ones.

- [ ] **Step 5: Commit**

```bash
git add app/services.py tests/test_services.py
git commit -m "feat(services): reverse_document with mirrored entries"
```

---

## Task 8: Services — `list_journal` with filters

**Files:**
- Modify: `app/services.py`, `tests/test_services.py`

- [ ] **Step 1: Append failing tests**

```python
from app.services import list_journal


def test_list_journal_returns_joined_rows(db, customer):
    doc_id = post_document(db, DocType.SALES_INVOICE, TODAY, customer,
                           Decimal("100"), "A sale")
    rows = list_journal(db)
    assert len(rows) == 2
    assert {r.account_code for r in rows} == {"1100", "4000"}
    assert all(r.partner_name == "Acme Corp" for r in rows)
    assert all(r.doc_id == doc_id for r in rows)
    assert {r.account_name for r in rows} == {"Accounts Receivable", "Revenue"}


def test_list_journal_date_filter(db, customer):
    post_document(db, DocType.SALES_INVOICE, date(2026, 1, 15), customer,
                  Decimal("10"), None)
    post_document(db, DocType.SALES_INVOICE, date(2026, 3, 15), customer,
                  Decimal("20"), None)
    rows = list_journal(db, date_from=date(2026, 2, 1), date_to=date(2026, 2, 28))
    assert rows == []
    rows = list_journal(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert all(r.doc_date == date(2026, 1, 15) for r in rows)


def test_list_journal_account_filter(db, customer):
    post_document(db, DocType.SALES_INVOICE, TODAY, customer, Decimal("10"), None)
    rows = list_journal(db, accounts=["4000"])
    assert {r.account_code for r in rows} == {"4000"}
```

- [ ] **Step 2: Run tests, verify fail**

Expected: ImportError.

- [ ] **Step 3: Implement `list_journal`**

Append to `app/services.py`:

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/Scripts/pytest tests/test_services.py -v`

- [ ] **Step 5: Commit**

```bash
git add app/services.py tests/test_services.py
git commit -m "feat(services): list_journal with date/account filters"
```

---

## Task 9: Services — `pnl_report` (no status filter)

**Files:**
- Modify: `app/services.py`
- Create: `tests/test_pnl.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_pnl.py`:

```python
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
    """Invoice on Jan 10, reversal also in Jan → revenue = 0."""
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
```

- [ ] **Step 2: Run tests, verify fail**

Expected: `ImportError: pnl_report`.

- [ ] **Step 3: Implement `pnl_report`**

Append to `app/services.py`:

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/Scripts/pytest tests/test_pnl.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services.py tests/test_pnl.py
git commit -m "feat(services): pnl_report with date-range, Python aggregation"
```

---

## Task 10: Services — `partner_balances`

**Files:**
- Modify: `app/services.py`, `tests/test_services.py`

- [ ] **Step 1: Append failing tests**

```python
from app.services import partner_balances


def test_customer_AR_decreases_after_payment(db, customer):
    post_document(db, DocType.SALES_INVOICE, TODAY, customer, Decimal("100"), None)
    post_document(db, DocType.CUSTOMER_PAYMENT, TODAY, customer, Decimal("30"), None)
    balances = {b.partner_id: b for b in partner_balances(db)}
    assert balances[customer].outstanding == Decimal("70")


def test_supplier_AP_decreases_after_payment(db, supplier):
    post_document(db, DocType.PURCHASE_INVOICE, TODAY, supplier, Decimal("100"), None)
    post_document(db, DocType.SUPPLIER_PAYMENT, TODAY, supplier, Decimal("40"), None)
    balances = {b.partner_id: b for b in partner_balances(db)}
    assert balances[supplier].outstanding == Decimal("60")


def test_overpayment_produces_negative_AR_balance(db, customer):
    post_document(db, DocType.CUSTOMER_PAYMENT, TODAY, customer, Decimal("50"), None)
    balances = {b.partner_id: b for b in partner_balances(db)}
    assert balances[customer].outstanding == Decimal("-50")


def test_invoice_and_reversal_net_to_zero_in_partner_balance(db, customer):
    doc_id = post_document(db, DocType.SALES_INVOICE, TODAY, customer,
                           Decimal("100"), None)
    reverse_document(db, doc_id)
    balances = {b.partner_id: b for b in partner_balances(db)}
    assert balances[customer].outstanding == Decimal("0")


def test_invoice_count_excludes_reversals(db, customer):
    """Original + reversal must not count as 2 invoices."""
    d1 = post_document(db, DocType.SALES_INVOICE, TODAY, customer, Decimal("10"), None)
    d2 = post_document(db, DocType.SALES_INVOICE, TODAY, customer, Decimal("20"), None)
    reverse_document(db, d1)
    balances = {b.partner_id: b for b in partner_balances(db)}
    # Only the non-reversed invoice (d2) counts.
    assert balances[customer].invoice_count == 1
```

- [ ] **Step 2: Run tests, verify fail**

Expected: ImportError.

- [ ] **Step 3: Implement `partner_balances`**

Append to `app/services.py`:

```python
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

        # Exclude reversals (reverses_id IS NOT NULL) so a reversed invoice
        # doesn't inflate the count to 2. `last_activity` below keeps reversals
        # — users want to see when the partner was last touched.
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/Scripts/pytest -v`

- [ ] **Step 5: Commit**

```bash
git add app/services.py tests/test_services.py
git commit -m "feat(services): partner_balances via arithmetic cancellation"
```

---

## Task 11: Formatting helper

**Files:**
- Create: `app/formatting.py`, `tests/test_formatting.py`

- [ ] **Step 1: Write failing test**

```python
import os
from decimal import Decimal
from app.formatting import format_money


def test_format_money_usd_default(monkeypatch):
    monkeypatch.delenv("CURRENCY", raising=False)
    assert format_money(Decimal("1234.5")) == "$1,234.50"


def test_format_money_negative():
    assert format_money(Decimal("-10.00")).startswith("-$")


def test_format_money_custom_currency(monkeypatch):
    monkeypatch.setenv("CURRENCY", "EUR")
    assert format_money(Decimal("99.99")) == "€99.99"


def test_format_money_unknown_currency_falls_back_to_code(monkeypatch):
    monkeypatch.setenv("CURRENCY", "XYZ")
    assert format_money(Decimal("1.00")) == "XYZ 1.00"
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Implement `app/formatting.py`**

```python
import os
from decimal import Decimal

_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "RUB": "₽"}


def format_money(value: Decimal) -> str:
    code = os.environ.get("CURRENCY", "USD").upper()
    quantized = Decimal(value).quantize(Decimal("0.01"))
    negative = quantized < 0
    abs_str = f"{abs(quantized):,.2f}"
    if code in _SYMBOLS:
        body = f"{_SYMBOLS[code]}{abs_str}"
    else:
        body = f"{code} {abs_str}"
    return f"-{body}" if negative else body
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add app/formatting.py tests/test_formatting.py
git commit -m "feat(formatting): format_money honors CURRENCY env var"
```

---

## Task 12: UI — shared session + Dashboard entry point

**Files:**
- Create: `app/ui/_session.py`, `app/ui/main.py`

- [ ] **Step 1: Create `app/ui/_session.py`**

This module is imported by every Streamlit script. Keeping the cached connection here (NOT in `main.py`) prevents page modules from accidentally re-rendering the dashboard when they import shared helpers.

```python
import os
import streamlit as st
from app.db import connect


@st.cache_resource
def get_conn():
    return connect(os.environ.get("DB_PATH", "./data/accounting.db"))
```

- [ ] **Step 2: Implement Dashboard**

```python
from datetime import date
from decimal import Decimal
import streamlit as st
from app.ui._session import get_conn
from app import services, repository as repo
from app.formatting import format_money


def _month_range():
    today = date.today()
    first = today.replace(day=1)
    return first, today


def main():
    st.set_page_config(page_title="Accounting Demo", layout="wide")
    st.title("Accounting Demo — Dashboard")

    conn = get_conn()

    # Cash balance: Dr 1000 - Cr 1000 across all entries
    rows = conn.execute(
        "SELECT debit, credit FROM journal_entries WHERE account_code = '1000'"
    ).fetchall()
    cash = sum((r[0] - r[1] for r in rows), Decimal("0"))

    balances = services.partner_balances(conn)
    ar = sum((b.outstanding for b in balances if b.kind.value == "CUSTOMER"), Decimal("0"))
    ap = sum((b.outstanding for b in balances if b.kind.value == "SUPPLIER"), Decimal("0"))

    c1, c2, c3 = st.columns(3)
    c1.metric("Cash (1000)", format_money(cash))
    c2.metric("Accounts Receivable", format_money(ar))
    c3.metric("Accounts Payable", format_money(ap))

    st.divider()

    d_from, d_to = _month_range()
    st.subheader(f"P&L — current month ({d_from} → {d_to})")
    pnl = services.pnl_report(conn, d_from, d_to)
    c1, c2, c3 = st.columns(3)
    c1.metric("Revenue", format_money(pnl.revenue))
    c2.metric("Expense", format_money(pnl.expense))
    c3.metric("Net Income", format_money(pnl.net_income))

    st.divider()
    st.subheader("Recent documents")
    docs = repo.list_documents(conn)[:5]
    if not docs:
        st.info("No documents yet. Add a partner, then post a document.")
    else:
        st.dataframe(
            [{"ID": d.id, "Type": d.doc_type.value, "Date": d.doc_date.isoformat(),
              "Amount": format_money(d.amount), "Status": d.status.value}
             for d in docs],
            use_container_width=True, hide_index=True,
        )


if __name__ == "__main__":
    main()
```

**Why the guard matters:** Streamlit launches this file as `__main__`. Page modules import `get_conn` from `_session.py` (not from `main.py`), so they never trigger `main()`. The guard is defence-in-depth in case something does end up importing `app.ui.main`.

- [ ] **Step 3: Smoke-test locally**

Run: `.venv/Scripts/streamlit run app/ui/main.py`
Expected: Dashboard loads on http://localhost:8501. Cash / AR / AP all 0. P&L all 0. "No documents yet" message.

- [ ] **Step 4: Commit**

```bash
git add app/ui/_session.py app/ui/main.py
git commit -m "feat(ui): dashboard + shared _session helper"
```

---

## Task 13: UI — Partners page

**Files:**
- Create: `app/ui/pages/3_Partners.py`

(Create this before Documents so that there are partners to select.)

- [ ] **Step 1: Implement page**

```python
import streamlit as st
from app.ui._session import get_conn
from app import services
from app.formatting import format_money
from app.models import PartnerKind

st.set_page_config(page_title="Partners", layout="wide")
st.title("Partners")
conn = get_conn()

with st.expander("Add partner", expanded=False):
    with st.form("add_partner", clear_on_submit=True):
        name = st.text_input("Name")
        kind = st.radio("Kind", [PartnerKind.CUSTOMER.value, PartnerKind.SUPPLIER.value])
        submitted = st.form_submit_button("Create")
        if submitted:
            try:
                services.create_partner(conn, name, PartnerKind(kind))
                st.success(f"Partner '{name}' created")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

st.divider()

balances = services.partner_balances(conn)

def _render(kind_label: str, kind: PartnerKind):
    st.subheader(f"{kind_label}s")
    rows = [b for b in balances if b.kind == kind]
    if not rows:
        st.info("None yet.")
        return
    col_name = f"Outstanding {'AR' if kind == PartnerKind.CUSTOMER else 'AP'}"
    data = [
        {"Name": b.name,
         col_name: float(b.outstanding),  # float for column_config formatting
         "# Invoices": b.invoice_count,
         "Last activity": b.last_activity.isoformat() if b.last_activity else "—"}
        for b in rows
    ]
    # Spec §7: negative balance (prepayment) shown in info color, not error.
    # Streamlit's native option is column_config with a progress/number column; we
    # use a simple conditional st.caption below the table for clarity.
    st.dataframe(
        data,
        use_container_width=True, hide_index=True,
        column_config={col_name: st.column_config.NumberColumn(format="%.2f")},
    )
    prepaid = [b for b in rows if b.outstanding < 0]
    if prepaid:
        st.info(
            "Prepayments (negative balance) — "
            + ", ".join(f"{b.name}: {format_money(b.outstanding)}" for b in prepaid)
        )

_render("Customer", PartnerKind.CUSTOMER)
_render("Supplier", PartnerKind.SUPPLIER)
```

- [ ] **Step 2: Smoke-test**

Add a customer and a supplier via the UI. Verify they appear with 0 outstanding.

- [ ] **Step 3: Commit**

```bash
git add app/ui/pages/3_Partners.py
git commit -m "feat(ui): partners page with add + balance tables"
```

---

## Task 14: UI — Documents page

**Files:**
- Create: `app/ui/pages/1_Documents.py`

- [ ] **Step 1: Implement page**

```python
from datetime import date
from decimal import Decimal
import streamlit as st
from app.ui._session import get_conn
from app import services, repository as repo
from app.formatting import format_money
from app.models import DocType, DocStatus, PartnerKind

st.set_page_config(page_title="Documents", layout="wide")
st.title("Documents")
conn = get_conn()

DOC_CONFIG = [
    ("Sales Invoice",      DocType.SALES_INVOICE,    PartnerKind.CUSTOMER),
    ("Purchase Invoice",   DocType.PURCHASE_INVOICE, PartnerKind.SUPPLIER),
    ("Customer Payment",   DocType.CUSTOMER_PAYMENT, PartnerKind.CUSTOMER),
    ("Supplier Payment",   DocType.SUPPLIER_PAYMENT, PartnerKind.SUPPLIER),
]

tabs = st.tabs([label for label, *_ in DOC_CONFIG])
for tab, (label, dtype, pkind) in zip(tabs, DOC_CONFIG):
    with tab:
        partners = services.list_partners(conn, kind=pkind)
        if not partners:
            st.info(f"No {pkind.value.lower()}s yet — add one on the Partners page.")
            continue
        with st.form(f"post_{dtype.value}", clear_on_submit=True):
            doc_date = st.date_input("Date", value=date.today(), max_value=date.today())
            partner = st.selectbox(
                "Partner", partners,
                format_func=lambda p: p.name, key=f"p_{dtype.value}",
            )
            amount = st.number_input("Amount", min_value=0.01, step=0.01, format="%.2f")
            desc = st.text_input("Description (optional)")
            submitted = st.form_submit_button(f"Post {label}")
            if submitted:
                try:
                    doc_id = services.post_document(
                        conn, dtype, doc_date, partner.id,
                        Decimal(str(amount)).quantize(Decimal("0.01")),
                        desc or None,
                    )
                    st.success(f"Document #{doc_id} posted")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

st.divider()
st.subheader("All documents")
docs = repo.list_documents(conn)
if not docs:
    st.info("No documents yet.")
else:
    for d in docs:
        partner = repo.get_partner(conn, d.partner_id)
        cols = st.columns([1, 2, 2, 2, 2, 2, 1])
        cols[0].write(f"**#{d.id}**")
        cols[1].write(d.doc_type.value)
        cols[2].write(d.doc_date.isoformat())
        cols[3].write(partner.name if partner else "—")
        cols[4].write(format_money(d.amount))
        cols[5].write(d.status.value + (f" (reverses #{d.reverses_id})" if d.reverses_id else ""))
        can_reverse = d.status == DocStatus.POSTED and d.reverses_id is None
        if can_reverse:
            if cols[6].button("Reverse", key=f"rev_{d.id}"):
                try:
                    services.reverse_document(conn, d.id)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
```

- [ ] **Step 2: Smoke-test**

Create a customer on Partners page, then post a sales invoice. Verify success banner, document appears in "All documents". Click Reverse — verify status flips.

- [ ] **Step 3: Commit**

```bash
git add app/ui/pages/1_Documents.py
git commit -m "feat(ui): documents page with tabs for 4 doc types + reverse"
```

---

## Task 15: UI — Journal page

**Files:**
- Create: `app/ui/pages/2_Journal.py`

- [ ] **Step 1: Implement page**

```python
import io
import csv
from datetime import date, timedelta
from decimal import Decimal
import streamlit as st
from app.ui._session import get_conn
from app import services
from app.formatting import format_money

st.set_page_config(page_title="Journal", layout="wide")
st.title("Journal")
conn = get_conn()

with st.sidebar:
    st.header("Filters")
    today = date.today()
    d_from = st.date_input("From", value=today - timedelta(days=30))
    d_to = st.date_input("To", value=today)
    all_accounts = ["1000", "1100", "2000", "4000", "5000"]
    accounts = st.multiselect("Accounts", all_accounts, default=all_accounts)

rows = services.list_journal(conn, date_from=d_from, date_to=d_to, accounts=accounts)

# We also need reverses_id per row to style reversal documents (spec §7).
# list_journal's JournalRow doesn't carry it — fetch a {doc_id: reverses_id} map.
reverses_map = {
    r[0]: r[1] for r in conn.execute(
        "SELECT id, reverses_id FROM documents"
    )
}

if not rows:
    st.info("No entries match filters.")
else:
    display = []
    for r in rows:
        is_reversal = reverses_map.get(r.doc_id) is not None
        is_reversed_original = r.status.value == "REVERSED"
        # Mark with unicode to visually distinguish (Streamlit dataframe doesn't
        # support per-row CSS directly; markers + a legend are clearer for a demo).
        marker = "↶ " if is_reversal else ("✗ " if is_reversed_original else "")
        display.append({
            "Date": r.doc_date.isoformat(),
            "Doc#": f"{marker}{r.doc_id}",
            "Type": r.doc_type.value,
            "Partner": r.partner_name,
            "Account": f"{r.account_code} {r.account_name}",
            "Debit": format_money(r.debit) if r.debit > 0 else "",
            "Credit": format_money(r.credit) if r.credit > 0 else "",
            "Description": r.description or "",
            "Status": r.status.value,
        })
    st.caption("Legend: ↶ = reversal entry • ✗ = original that was reversed")
    st.dataframe(display, use_container_width=True, hide_index=True)

    total_dr = sum((r.debit for r in rows), Decimal("0"))
    total_cr = sum((r.credit for r in rows), Decimal("0"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Σ Debit", format_money(total_dr))
    c2.metric("Σ Credit", format_money(total_cr))
    c3.metric("Balanced?", "YES" if total_dr == total_cr else "NO")

    # CSV export
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(display[0].keys()))
    w.writeheader()
    w.writerows(display)
    st.download_button(
        "Export CSV", data=buf.getvalue(),
        file_name=f"journal_{d_from}_{d_to}.csv", mime="text/csv",
    )
```

- [ ] **Step 2: Smoke-test**

Post a couple of invoices and verify journal shows entries, filters work, Σ Debit == Σ Credit, CSV downloads.

- [ ] **Step 3: Commit**

```bash
git add app/ui/pages/2_Journal.py
git commit -m "feat(ui): journal page with filters and CSV export"
```

---

## Task 16: UI — P&L Reports page

**Files:**
- Create: `app/ui/pages/4_Reports.py`

- [ ] **Step 1: Implement page**

```python
import io
import csv
from datetime import date
import streamlit as st
from app.ui._session import get_conn
from app import services
from app.formatting import format_money

st.set_page_config(page_title="P&L", layout="wide")
st.title("P&L Report")
conn = get_conn()

today = date.today()
first = today.replace(day=1)
c1, c2 = st.columns(2)
d_from = c1.date_input("From", value=first)
d_to = c2.date_input("To", value=today)

if d_from > d_to:
    st.error("'From' must be ≤ 'To'")
    st.stop()

pnl = services.pnl_report(conn, d_from, d_to)

m1, m2, m3 = st.columns(3)
# Spec §7: color cues — revenue green (positive is good), expense red (inverse:
# higher is "worse"), net income sign-colored. Use Streamlit's delta_color.
m1.metric("Revenue", format_money(pnl.revenue),
          delta=format_money(pnl.revenue) if pnl.revenue else None,
          delta_color="normal")
m2.metric("Expense", format_money(pnl.expense),
          delta=format_money(pnl.expense) if pnl.expense else None,
          delta_color="inverse")
net_delta = format_money(pnl.net_income) if pnl.net_income else None
m3.metric("Net Income", format_money(pnl.net_income),
          delta=net_delta, delta_color="normal")

st.divider()

st.subheader("Revenue by document")
if pnl.revenue_rows:
    st.dataframe(
        [{"Date": r.doc_date.isoformat(), "Doc#": r.doc_id,
          "Partner": r.partner_name, "Amount": format_money(r.amount),
          "Description": r.description or ""}
         for r in pnl.revenue_rows],
        use_container_width=True, hide_index=True,
    )
else:
    st.info("No revenue entries in range.")

st.subheader("Expense by document")
if pnl.expense_rows:
    st.dataframe(
        [{"Date": r.doc_date.isoformat(), "Doc#": r.doc_id,
          "Partner": r.partner_name, "Amount": format_money(r.amount),
          "Description": r.description or ""}
         for r in pnl.expense_rows],
        use_container_width=True, hide_index=True,
    )
else:
    st.info("No expense entries in range.")

# Combined CSV export
buf = io.StringIO()
w = csv.writer(buf)
w.writerow(["Section", "Date", "Doc#", "Partner", "Amount", "Description"])
for r in pnl.revenue_rows:
    w.writerow(["revenue", r.doc_date.isoformat(), r.doc_id, r.partner_name, r.amount, r.description or ""])
for r in pnl.expense_rows:
    w.writerow(["expense", r.doc_date.isoformat(), r.doc_id, r.partner_name, r.amount, r.description or ""])
st.download_button(
    "Export CSV", data=buf.getvalue(),
    file_name=f"pnl_{d_from}_{d_to}.csv", mime="text/csv",
)
```

- [ ] **Step 2: Smoke-test**

With sample data, verify P&L metrics update when date range changes; reversal inside range cancels revenue/expense.

- [ ] **Step 3: Commit**

```bash
git add app/ui/pages/4_Reports.py
git commit -m "feat(ui): P&L reports page with breakdown and CSV"
```

---

## Task 17: Docker + compose + README

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `README.md`

- [ ] **Step 1: Write `Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DB_PATH=/app/data/accounting.db \
    CURRENCY=USD
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').status==200 else 1)"
CMD ["streamlit", "run", "app/ui/main.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
services:
  app:
    build: .
    ports: ["8501:8501"]
    volumes:
      - ./data:/app/data
    env_file: .env
    restart: unless-stopped
```

- [ ] **Step 3: Write `README.md`**

```markdown
# Accounting Demo

Minimal Streamlit + SQLite demo of double-entry bookkeeping with storno reversals.

## Quickstart (Docker)

```bash
cp .env.example .env     # optional — defaults work
docker compose up --build
```

Open http://localhost:8501.

## Local development

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/pytest
.venv/Scripts/streamlit run app/ui/main.py
```

## Features

- 4 document types: sales invoice, purchase invoice, customer payment, supplier payment.
- Immutable journal; corrections via storno reversals.
- P&L report (revenue − expense) over a date range.
- Partner registry with outstanding AR / AP.

See `docs/superpowers/specs/2026-04-23-accounting-demo-design.md` for the full design.
```

- [ ] **Step 4: Build and run via Docker**

```bash
docker compose up --build
```
Expected: boots on http://localhost:8501, `docker ps` shows `healthy`.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml README.md
git commit -m "chore(docker): Dockerfile, compose, README with quickstart"
```

---

## Task 18: Final end-to-end validation

- [ ] **Step 1: Clean state smoke test**

```bash
rm -rf data/*.db
docker compose down
docker compose up --build
```
Open http://localhost:8501.

- [ ] **Step 2: Walk through acceptance criteria**

Verify each AC from spec §12:
- AC1: App boots, `data/accounting.db` created, healthcheck OK.
- AC2: Post one of each doc type; verify journal shows matching two entries on correct accounts.
- AC3: Reverse a sales invoice; original → REVERSED, reversal created with today's date, button disappears on reversal.
- AC4: Journal `Σ Debit == Σ Credit`.
- AC5: P&L for a month containing the reversal shows 0 on affected side. Post a reversal in "next month" (by reposting after time travel, skip if cumbersome) — verify past period unchanged.
- AC6: Invoice + reversal → partner balance 0.
- AC7: `pytest -q` all green in <1s.
- AC8: README steps end-to-end work.

- [ ] **Step 3: Final commit (if any lint/typo fixes)**

```bash
git add .
git commit -m "chore: final polish after e2e validation"
```

---

## Execution Handoff

Plan complete. Execute either via:
- `superpowers:subagent-driven-development` — fresh subagent per task, review between.
- `superpowers:executing-plans` — inline execution with checkpoints.
