import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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
# JournalRow doesn't carry it — fetch a {doc_id: reverses_id} map.
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
        # Markers visually distinguish reversal-related rows (Streamlit dataframe
        # doesn't support per-row CSS; markers + a legend are clearer for a demo).
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
