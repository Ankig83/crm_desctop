from __future__ import annotations

from datetime import date


def discount_applies(quote_date: date, valid_from: date, valid_to: date) -> bool:
    return valid_from <= quote_date <= valid_to


def line_total(
    base_price: float,
    qty: float,
    discount_percent: float,
    quote_date: date,
    valid_from: date | None,
    valid_to: date | None,
) -> float:
    gross = base_price * qty
    if valid_from is None or valid_to is None:
        return gross
    if discount_percent <= 0:
        return gross
    if not discount_applies(quote_date, valid_from, valid_to):
        return gross
    p = min(max(discount_percent, 0.0), 100.0)
    return gross * (1.0 - p / 100.0)
