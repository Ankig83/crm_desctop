from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class DiscountResult:
    base_price: float
    qty: float
    gross: float
    client_type_pct: float = 0.0
    promo_pct: float = 0.0
    prepay_pct: float = 0.0
    volume_pct: float = 0.0
    product_pct: float = 0.0

    @property
    def total_pct(self) -> float:
        return min(
            self.client_type_pct + self.promo_pct + self.prepay_pct
            + self.volume_pct + self.product_pct,
            100.0,
        )

    @property
    def net(self) -> float:
        return round(self.gross * (1.0 - self.total_pct / 100.0), 2)

    @property
    def discount_amount(self) -> float:
        return round(self.gross - self.net, 2)


def discount_applies(quote_date: date, valid_from: date, valid_to: date) -> bool:
    return valid_from <= quote_date <= valid_to


def calculate_line(
    base_price: float,
    qty: float,
    quote_date: date,
    *,
    client_type_pct: float = 0.0,
    promo_discount_pct: float = 0.0,
    promo_valid_from: date | None = None,
    promo_valid_to: date | None = None,
    prepay_pct: float = 0.0,
    volume_pct: float = 0.0,
    product_pct: float = 0.0,
) -> DiscountResult:
    gross = base_price * qty
    result = DiscountResult(base_price=base_price, qty=qty, gross=gross)
    result.client_type_pct = min(max(client_type_pct, 0.0), 100.0)
    if (
        promo_discount_pct > 0
        and promo_valid_from is not None
        and promo_valid_to is not None
        and discount_applies(quote_date, promo_valid_from, promo_valid_to)
    ):
        result.promo_pct = min(max(promo_discount_pct, 0.0), 100.0)
    result.prepay_pct  = min(max(prepay_pct,  0.0), 100.0)
    result.volume_pct  = min(max(volume_pct,  0.0), 100.0)
    result.product_pct = min(max(product_pct, 0.0), 100.0)
    return result


def line_total(
    base_price: float,
    qty: float,
    discount_percent: float,
    quote_date: date,
    valid_from: date | None,
    valid_to: date | None,
    client_type_pct: float = 0.0,
    prepay_pct: float = 0.0,
    volume_pct: float = 0.0,    # ← Этап 2
    product_pct: float = 0.0,   # ← Этап 3
) -> float:
    return calculate_line(
        base_price=base_price,
        qty=qty,
        quote_date=quote_date,
        client_type_pct=client_type_pct,
        promo_discount_pct=discount_percent,
        promo_valid_from=valid_from,
        promo_valid_to=valid_to,
        prepay_pct=prepay_pct,
        volume_pct=volume_pct,
        product_pct=product_pct,
    ).net