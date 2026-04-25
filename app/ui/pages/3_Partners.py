import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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
         col_name: float(b.outstanding),
         "# Invoices": b.invoice_count,
         "Last activity": b.last_activity.isoformat() if b.last_activity else "—"}
        for b in rows
    ]
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
