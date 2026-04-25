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
