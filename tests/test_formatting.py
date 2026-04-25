import os
from decimal import Decimal
from app.formatting import format_money


def test_format_money_usd_default(monkeypatch):
    monkeypatch.delenv("CURRENCY", raising=False)
    assert format_money(Decimal("1234.5")) == "$1,234.50"


def test_format_money_negative(monkeypatch):
    monkeypatch.delenv("CURRENCY", raising=False)
    assert format_money(Decimal("-10.00")).startswith("-$")


def test_format_money_custom_currency(monkeypatch):
    monkeypatch.setenv("CURRENCY", "EUR")
    assert format_money(Decimal("99.99")) == "€99.99"


def test_format_money_unknown_currency_falls_back_to_code(monkeypatch):
    monkeypatch.setenv("CURRENCY", "XYZ")
    assert format_money(Decimal("1.00")) == "XYZ 1.00"
