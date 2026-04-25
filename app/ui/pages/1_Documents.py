import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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
