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
