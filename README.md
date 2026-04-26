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

On Windows you can also double-click `run.bat` to start the app.

## Features

- 4 document types: sales invoice, purchase invoice, customer payment, supplier payment.
- Immutable journal; corrections via storno reversals.
- P&L report (revenue − expense) over a date range.
- Partner registry with outstanding AR / AP.

See `docs/superpowers/specs/2026-04-23-accounting-demo-design.md` for the full design.
