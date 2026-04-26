# Accounting Demo

Minimal Streamlit + SQLite demo of double-entry bookkeeping with storno reversals.

## Quickstart (Docker)

```bash
docker compose up --build
```

Open <http://localhost:8501>. SQLite database is created on first start in `./data/accounting.db` and persists across restarts.

To customize currency or DB path, copy the example env file and uncomment the `env_file:` line in `docker-compose.yml`:

```bash
cp .env.example .env
# edit .env, then uncomment env_file in docker-compose.yml
docker compose up --build
```

## Local development

**Linux / macOS:**

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest
.venv/bin/streamlit run app/ui/main.py
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pytest
.\.venv\Scripts\streamlit run app\ui\main.py
```

On Windows you can also double-click `run.bat` — it creates the venv on first run if missing.

## Features

- 4 document types: sales invoice, purchase invoice, customer payment, supplier payment.
- Immutable journal; corrections via storno reversals.
- P&L report (revenue − expense) over a date range.
- Partner registry with outstanding AR / AP.

See `docs/superpowers/specs/2026-04-23-accounting-demo-design.md` for the full design.
