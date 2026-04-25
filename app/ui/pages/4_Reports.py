import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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
