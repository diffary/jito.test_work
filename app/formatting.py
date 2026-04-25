import os
from decimal import Decimal

_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "RUB": "₽"}


def format_money(value: Decimal) -> str:
    code = os.environ.get("CURRENCY", "USD").upper()
    quantized = Decimal(value).quantize(Decimal("0.01"))
    negative = quantized < 0
    abs_str = f"{abs(quantized):,.2f}"
    if code in _SYMBOLS:
        body = f"{_SYMBOLS[code]}{abs_str}"
    else:
        body = f"{code} {abs_str}"
    return f"-{body}" if negative else body
