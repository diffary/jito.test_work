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
