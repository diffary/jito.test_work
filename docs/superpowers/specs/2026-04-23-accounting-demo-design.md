# Accounting Demo — Design Spec

**Date:** 2026-04-23
**Status:** Approved by user (brainstorming complete)
**Working directory:** `d:/files/test_project/`

---

## 1. Purpose & Scope

A minimal web application demonstrating the core mechanics of double-entry bookkeeping. Educational/demo purpose, not production accounting.

**In scope:**
- Create four document types (sales invoice, purchase invoice, customer payment, supplier payment).
- Each posted document automatically generates two balanced journal entries (debit + credit).
- Immutable journal: documents cannot be edited or deleted; only reversed via storno.
- Journal viewer with date and account filters.
- Simplified P&L report (revenue − expense) over a date range.
- Partner registry with outstanding AR / AP balances.

**Out of scope (explicit non-goals):**
- Authentication / multi-user data isolation.
- Multi-currency or exchange rates.
- Line items / VAT / tax accounts.
- Period closing, fiscal year locking.
- General-ledger printout, trial balance report (could be added later).

---

## 2. Tech Stack & Constraints

- **Language:** Python 3.11 (matches Docker base image; spec originally said "3.10+", pinned to 3.11 for parity with the container)
- **UI:** Streamlit (multi-page mode via `pages/` folder)
- **Database:** SQLite (single file; in-memory for tests)
- **Containerization:** Docker + docker-compose
- **Currency:** Single currency, default `USD`, configurable via env var `CURRENCY`
- **UI language:** English (chart of accounts is in English)

**Fixed chart of accounts (must not change):**

| Code | Name                | Type      |
|------|---------------------|-----------|
| 1000 | Cash                | ASSET     |
| 1100 | Accounts Receivable | ASSET     |
| 2000 | Accounts Payable    | LIABILITY |
| 4000 | Revenue             | INCOME    |
| 5000 | Expense             | EXPENSE   |

---

## 3. Approved Design Decisions (Brainstorming Outcome)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Bookkeeping model | **Accrual + payments (separate documents)** | Uses all 5 fixed accounts; partner balances change over time as payments arrive. |
| 2 | Document line items | **None — single total per document** | Requirement says "simple form"; double-entry is equally illustrative on a single amount. |
| 3 | Mutability | **Immutable; reverse via storno** | Authentic accounting behavior; reinforces educational value. |
| 4 | Currency / locale | **Single currency, USD, English UI; `CURRENCY` env var for display** | Simplest schema; `Decimal` only, no FX. |
| 5 | Authentication | **None** | Keeps focus on accounting logic; not in original requirements. |

---

## 4. Architecture

Layered architecture (Approach 2 from brainstorming):

```
Streamlit UI  →  services.py  →  repository.py  →  SQLite
                 (business        (CRUD, raw
                  logic, all      SQL only)
                  posting rules)
```

- **`db.py`** — connection factory, schema init, seed data for `accounts`.
- **`models.py`** — `@dataclass` types: `Document`, `JournalEntry`, `Partner`, `JournalRow`, `PnLReport`, `PartnerBalance`.
- **`repository.py`** — pure SQL CRUD. Returns dataclasses. No business logic.
- **`services.py`** — `post_document`, `reverse_document`, `pnl_report`, `partner_balances`, `list_journal`. Holds all posting rules and validation. Single source of truth for double-entry logic.
- **`formatting.py`** — `format_money(decimal) -> str` reads `CURRENCY` env var.
- **`ui/main.py` + `ui/pages/*.py`** — thin Streamlit views. No SQL, no posting logic.

**Why this layering:** the educational essence of the app — how a document becomes two balanced journal entries — lives in one file (`services.py`), readable end-to-end. UI pages are renderers.

---

## 5. Data Model

```sql
CREATE TABLE accounts (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL  -- 'ASSET'|'LIABILITY'|'INCOME'|'EXPENSE'
);

CREATE TABLE partners (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL COLLATE NOCASE,
    kind        TEXT NOT NULL CHECK (kind IN ('CUSTOMER','SUPPLIER')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX idx_partner_name_nocase ON partners(name COLLATE NOCASE);

CREATE TABLE documents (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type     TEXT NOT NULL CHECK (doc_type IN (
                   'SALES_INVOICE','PURCHASE_INVOICE',
                   'CUSTOMER_PAYMENT','SUPPLIER_PAYMENT')),
    doc_date     TEXT NOT NULL,                -- ISO 'YYYY-MM-DD'
    partner_id   INTEGER NOT NULL REFERENCES partners(id),
    amount       NUMERIC NOT NULL CHECK (amount > 0),
    description  TEXT,
    status       TEXT NOT NULL DEFAULT 'POSTED'
                 CHECK (status IN ('POSTED','REVERSED')),
    reverses_id  INTEGER REFERENCES documents(id),
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE journal_entries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id    INTEGER NOT NULL REFERENCES documents(id),
    account_code   TEXT NOT NULL REFERENCES accounts(code),
    debit          NUMERIC NOT NULL DEFAULT 0,
    credit         NUMERIC NOT NULL DEFAULT 0,
    CHECK ((debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0))
);

CREATE INDEX idx_journal_doc      ON journal_entries(document_id);
CREATE INDEX idx_journal_account  ON journal_entries(account_code);
CREATE INDEX idx_doc_date         ON documents(doc_date);
```

**Key implementation notes:**
- All amounts stored as `NUMERIC`. Python side uses `decimal.Decimal` quantized to 2 dp (`Decimal('0.01')`).
- **Decimal round-trip — explicit requirement:** `db.py` MUST call:
  ```python
  sqlite3.register_adapter(Decimal, str)
  sqlite3.register_converter("NUMERIC", lambda b: Decimal(b.decode()))
  ```
  and `connect(..., detect_types=sqlite3.PARSE_DECLTYPES)`.
- **No `SUM()` in SQL for money.** SQLite's `SUM()` coerces NUMERIC-affinity rows to REAL, reintroducing float error. Aggregation must be performed in Python: `SELECT debit, credit FROM ... WHERE ...` then `sum(rows, Decimal('0'))`. Applies to `pnl_report` and `partner_balances`.
- `journal_entries` is append-only by convention. No UPDATE path in `repository.py` for it.
- `documents.status` flips to `REVERSED` only as part of `reverse_document` transaction.
- Reversal documents have `reverses_id IS NOT NULL`; their own `status` stays `POSTED` (they are valid entries).
- Single `BEGIN IMMEDIATE; INSERT document; INSERT 2 entries; COMMIT;` transaction guarantees the journal is always balanced. `BEGIN IMMEDIATE` acquires a write lock up front and avoids `SQLITE_BUSY` under rapid reruns.

---

## 6. Posting Logic

For each document type, posting creates exactly two journal entries on the document amount.

| `doc_type`         | Required partner kind | Debit account     | Credit account      |
|--------------------|-----------------------|-------------------|---------------------|
| `SALES_INVOICE`    | CUSTOMER              | 1100 AR           | 4000 Revenue        |
| `CUSTOMER_PAYMENT` | CUSTOMER              | 1000 Cash         | 1100 AR             |
| `PURCHASE_INVOICE` | SUPPLIER              | 5000 Expense      | 2000 AP             |
| `SUPPLIER_PAYMENT` | SUPPLIER              | 2000 AP           | 1000 Cash           |

**Reversal:** copy of the original with `reverses_id = original.id`, journal entries with debit/credit swapped on the same accounts. Sets `original.status = 'REVERSED'`. The reversal document itself is `POSTED` and cannot be reversed again.

### Service API

```python
def create_partner(name: str, kind: PartnerKind) -> int: ...

def list_partners(kind: PartnerKind | None = None) -> list[Partner]: ...

def post_document(
    doc_type: DocType,
    doc_date: date,
    partner_id: int,
    amount: Decimal,
    description: str | None = None,
) -> int: ...

def reverse_document(document_id: int) -> int:
    """Reversal gets doc_date = today (never backdated). Returns new doc id."""

def list_journal(
    date_from: date | None = None,
    date_to: date | None = None,
    accounts: list[str] | None = None,
) -> list[JournalRow]: ...

def pnl_report(date_from: date, date_to: date) -> PnLReport: ...

def partner_balances() -> list[PartnerBalance]: ...
```

**Concurrency note:** `post_document` and `reverse_document` are guarded by a module-level `threading.Lock` to serialize writes against the shared cached `sqlite3.Connection`. Streamlit reruns can overlap mid-transaction otherwise.

### Validation rules (raise `ValueError`)

1. `amount > 0` and `amount == amount.quantize(Decimal('0.01'))` — i.e., `Decimal('10')`, `Decimal('10.1')`, and `Decimal('10.10')` all pass; `Decimal('10.123')` fails. The predicate is "no precision below cents", not "exactly two fractional digits".
2. Partner kind must match `doc_type` (sales/customer-payment ↔ CUSTOMER, purchase/supplier-payment ↔ SUPPLIER).
3. `doc_date <= today` (no future-dated documents). Applies to user-supplied dates on `post_document`. Reversal documents set `doc_date = today` internally and are not subject to user-supplied date validation.
4. `reverse_document`: target document must exist, must have `status='POSTED'`, and must have `reverses_id IS NULL` (cannot reverse a reversal). Non-existent id → `ValueError`.
5. `partner.name` unique on creation (case-insensitive); `partner.kind` immutable after creation (no update API exposed).

**Allowed by design (not errors):**
- Customer payment when AR balance is zero or negative (creates a prepayment / negative AR balance, surfaced in partner registry as informational).
- Multiple invoices on the same date for the same partner.

### P&L semantics — key rule: ignore `documents.status` filter

The immutable journal + reversal-as-a-new-document model makes arithmetic correct without any status filter. Filtering out `status='REVERSED'` would silently mutate past-period P&L whenever a reversal is posted in a later period (the reversal flips the original's status, retroactively excluding it from the already-reported period). That is not the intended semantic.

**Rule:** P&L queries across ALL journal entries (both from POSTED-originals and POSTED-reversals and REVERSED-originals), filtered ONLY by the document's `doc_date` within the reporting range.

- `revenue` = sum of `credit` on account `4000` − sum of `debit` on account `4000`, over journal entries whose document's `doc_date` is in `[date_from, date_to]`.
- `expense` = sum of `debit` on account `5000` − sum of `credit` on account `5000`, with the same date filter.
- `net_income` = `revenue − expense`.
- Aggregation performed in Python over `Decimal` rows (see §5 note).

**Worked example:** sales invoice +$100 dated 2026-04-10 (Cr 4000 = +100). Reversal dated today (2026-04-23), Dr 4000 = 100.
- P&L for April: invoice date (04-10) is in range, reversal date (04-23) is in range → revenue = 100 − 100 = 0. ✅
- P&L for January–March: both entries out of range → revenue = 0. ✅
- Reversal posted in May for an April invoice: April P&L keeps the $100 revenue (original in range, reversal out of range). The reversal appears in May's P&L as a $100 negative contribution. This is a deliberate choice: reversals affect the period in which they are posted, and past-period reports remain stable once issued.

`PnLReport` also returns per-document breakdowns (revenue-side and expense-side, including reversal rows displayed with sign) for UI rendering.

### Partner balance semantics — same rule: ignore status filter

For a CUSTOMER: outstanding AR = sum of `debit on 1100` − sum of `credit on 1100` across ALL that partner's journal entries on account 1100 (no status filter, no date filter).
For a SUPPLIER: outstanding AP = sum of `credit on 2000` − sum of `debit on 2000` across ALL that partner's journal entries on account 2000.

Reversal correctness is guaranteed by construction: a reversal's swapped entry on the same account and partner exactly cancels the original's entry. No status filter needed or wanted.

---

## 7. UI (Streamlit)

Streamlit's built-in multi-page mode via the `pages/` folder. Sidebar navigation is automatic.

**`ui/main.py` — Dashboard (entry point)**
- Cash balance (account 1000), total AR, total AP.
- Current-month P&L summary (revenue / expense / net).
- Last 5 documents (any type).

**`pages/1_Documents.py`**
- 4 tabs, one per document type.
- Each tab: a `st.form` with date_input, partner selectbox (filtered by required kind), `number_input` (min 0.01, step 0.01, format "%.2f"), description, submit button.
- On submit → call `services.post_document(...)`. On `ValueError` → `st.error`. On success → `st.success("Document #N posted")` + `st.rerun()`.
- Below: full document list with a "Reverse" button shown only for documents with `status='POSTED'` AND `reverses_id IS NULL`.

**`pages/2_Journal.py`**
- Sidebar filters: `date_from`, `date_to`, multi-select accounts.
- Table columns: Date | Doc# | Doc Type | Partner | Account | Debit | Credit | Description | Status.
- Footer: ΣDebit, ΣCredit (must always be equal — visual balance indicator).
- "Export CSV" button (`st.download_button`).
- Reversed documents and reversal documents are visually distinguished (e.g., italic / muted color via dataframe styling).

**`pages/3_Partners.py`**
- "Add partner" form: name, kind (radio CUSTOMER/SUPPLIER).
- Customers table: Name | Outstanding AR | # Invoices | Last Activity.
- Suppliers table: Name | Outstanding AP | # Invoices | Last Activity.
- Negative balance (prepayment) highlighted in info color, not error.

**`pages/4_Reports.py`**
- Two date_inputs (default = current month).
- "Generate" button → calls `pnl_report(...)`.
- Three metric cards: Revenue (green), Expense (red), Net Income (color reflects sign).
- Two tables: "Revenue by document", "Expense by document".
- "Export CSV" button.

**Streamlit-specific implementation notes:**
- Money formatting: `format_money(d)` reads `CURRENCY` env var with default `USD`, returns `"$1,234.56"`-style string.
- DB connection: `@st.cache_resource` returns one `sqlite3.Connection` (opened with `check_same_thread=False`, `isolation_level=None`, `detect_types=PARSE_DECLTYPES`). Cached connection is shared across Streamlit's worker threads; `services.py` serializes writes with a module-level `threading.Lock` (see §6).
- **Do NOT** use `@st.cache_data` on data-fetching functions — data mutates (post / reverse) and stale caches would give wrong balances. Volume is tiny; uncached queries are instant.
- **Import path:** Streamlit is launched with `streamlit run app/ui/main.py` from the project root (and from `/app` inside the container). UI modules import services as `from app.services import ...`. The Docker image sets `ENV PYTHONPATH=/app` defensively.

---

## 8. Project Layout

```
test_project/
├── app/
│   ├── __init__.py
│   ├── db.py
│   ├── models.py
│   ├── repository.py
│   ├── services.py
│   ├── formatting.py
│   └── ui/
│       ├── main.py
│       └── pages/
│           ├── 1_Documents.py
│           ├── 2_Journal.py
│           ├── 3_Partners.py
│           └── 4_Reports.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_services.py
│   └── test_pnl.py
├── data/                     # gitignored, mounted as volume
│   └── .gitkeep
├── docs/superpowers/specs/
│   └── 2026-04-23-accounting-demo-design.md
├── .dockerignore
├── .gitignore
├── .env.example              # CURRENCY=USD, DB_PATH=/app/data/accounting.db
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── PROMPT_HISTORY.md
└── README.md
```

---

## 9. Configuration

| Env var       | Default                       | Purpose                              |
|---------------|-------------------------------|--------------------------------------|
| `DB_PATH`     | `./data/accounting.db`        | SQLite file path                     |
| `CURRENCY`    | `USD`                         | Currency code for display formatting |
| `PYTHONPATH`  | `/app` (Docker only)          | Ensures `app.*` import path resolves |

**`requirements.txt`:**
```
streamlit==1.40.0
pytest==8.3.3
```

**`pytest.ini`:**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -q
```

---

## 10. Docker

**`Dockerfile`:**
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
# Python-native healthcheck — python:3.11-slim does NOT include curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').status==200 else 1)"
CMD ["streamlit", "run", "app/ui/main.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
```

**`docker-compose.yml`:**
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

**DB initialization:** `db.connect()` checks for table existence; if missing, creates schema and seeds the 5 accounts. Idempotent on subsequent starts.

---

## 11. Testing Strategy

Only the service layer is tested. UI layer is intentionally not covered — not cost-effective for a demo.

**Fixture approach:** real SQLite, but `:memory:`. Fresh DB per test via `conftest.py`. No mocks.

```python
@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
    init_schema(conn)
    seed_accounts(conn)
    yield conn
    conn.close()

@pytest.fixture
def customer(db): return create_partner(db, "Acme Corp", "CUSTOMER")

@pytest.fixture
def supplier(db): return create_partner(db, "Office Ltd", "SUPPLIER")
```

**Test scenarios:**

*Double-entry basics*
1. `post_sales_invoice_creates_AR_debit_and_revenue_credit`
2. `post_purchase_invoice_creates_expense_debit_and_AP_credit`
3. `post_customer_payment_clears_AR_and_increases_cash`
4. `post_supplier_payment_clears_AP_and_decreases_cash`
5. `journal_balanced_invariant` — after any sequence of operations, ΣDebit == ΣCredit.

*Reversal*
6. `reverse_sales_invoice_creates_mirrored_entries_on_same_accounts`
7. `reversal_gets_today_as_doc_date_not_original_date`
8. `cannot_reverse_already_reversed_document`
9. `cannot_reverse_a_reversal`
10. `cannot_reverse_nonexistent_document_id`
11. `journal_remains_balanced_after_reversal`

*Validation*
12. `negative_amount_rejected`
13. `zero_amount_rejected`
14. `future_doc_date_rejected`
15. `sales_invoice_with_supplier_partner_rejected` (and the 3 symmetric cases for the other doc types)
16. `amount_with_sub_cent_precision_rejected` — e.g. `Decimal('10.123')`
17. `amount_equal_to_ten_dot_one_is_accepted` — pins the "no precision below cents" predicate
18. `duplicate_partner_name_rejected_case_insensitive`

*Partner balances — no status filter, arithmetic cancels via reversal entries*
19. `customer_AR_decreases_after_payment`
20. `supplier_AP_decreases_after_payment`
21. `overpayment_produces_negative_AR_balance`
22. `reversed_invoice_and_its_reversal_net_to_zero_in_partner_balance` (replaces the older "excluded" test — proves arithmetic, not filtering)

*P&L (`test_pnl.py`) — no status filter, date-range only*
23. `pnl_returns_zero_for_empty_period`
24. `pnl_includes_only_documents_in_date_range`
25. `pnl_invoice_and_reversal_both_in_period_net_to_zero`
26. `pnl_invoice_in_period_reversal_in_later_period_keeps_invoice_in_original_period` — pins the "past periods are stable" semantic
27. `pnl_net_income_equals_revenue_minus_expense`

**Target:** ~27 tests, runtime ≤ 1 s.

**Explicitly NOT covered:**
- Streamlit UI (no integration tests in this demo).
- Docker build (manual `docker compose up` smoke check).
- Concurrency (single-user demo; no WAL needed).

---

## 12. Acceptance Criteria

The build is "done" when all of the following hold:

1. `docker compose up --build` boots the app on `http://localhost:8501` without errors; SQLite file is created in `./data/`; Docker `HEALTHCHECK` reports `healthy` within 60 s.
2. All four document types can be posted via the UI; each generates exactly two journal entries on the correct accounts (see §6 table).
3. Reversing a document creates a mirror document (swapped Dr/Cr, same accounts, `doc_date = today`) and flips the original's status to `REVERSED`. The reversal itself cannot be reversed and its button is absent/disabled in UI.
4. Journal page shows ΣDebit == ΣCredit at all times (all journal entries, regardless of date filter).
5. P&L for date range `[D1, D2]` produces `revenue − expense` computed across ALL journal entries whose document's `doc_date` falls in `[D1, D2]` (no document-status filter). Posting a reversal in a later period does NOT retroactively change a past period's P&L.
6. Partner registry shows outstanding AR/AP computed across ALL that partner's journal entries on account 1100/2000 (no status filter). An invoice followed by its reversal produces a partner balance of zero.
7. `pytest` passes all ~27 tests in under 1 second.
8. README "Quickstart" works end-to-end on a fresh machine with only Docker installed. The documented steps are exactly:
   1. Clone/copy the project directory.
   2. `cp .env.example .env` (optional — defaults work).
   3. `docker compose up --build`.
   4. Open `http://localhost:8501` in a browser.
