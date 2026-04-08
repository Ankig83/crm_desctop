from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


# ─────────────────────────────────────────────────────────────
# Вспомогательные типы
# ─────────────────────────────────────────────────────────────

@dataclass
class DiscountResult:
    """Детализация применённых скидок — для отображения и экспорта."""
    base_price: float           # цена за единицу до скидок
    qty: float                  # количество
    gross: float                # base_price * qty (без скидок)

    client_type_pct: float = 0.0    # скидка по типу клиента (%)
    promo_pct: float = 0.0          # скидка акции по датам (%)
    prepay_pct: float = 0.0         # скидка за предоплату (%) — зарезервировано
    volume_pct: float = 0.0         # скидка за объём (%) — зарезервировано
    product_pct: float = 0.0        # продуктовая скидка (%) — зарезервировано

    @property
    def total_pct(self) -> float:
        """Суммарная скидка в процентах (скидки не перемножаются, а складываются,
        но не могут превысить 100%)."""
        return min(
            self.client_type_pct
            + self.promo_pct
            + self.prepay_pct
            + self.volume_pct
            + self.product_pct,
            100.0,
        )

    @property
    def net(self) -> float:
        """Итоговая сумма строки после всех скидок."""
        return round(self.gross * (1.0 - self.total_pct / 100.0), 2)

    @property
    def discount_amount(self) -> float:
        """Сумма скидки в рублях."""
        return round(self.gross - self.net, 2)


# ─────────────────────────────────────────────────────────────
# Проверка периода акции
# ─────────────────────────────────────────────────────────────

def discount_applies(quote_date: date, valid_from: date, valid_to: date) -> bool:
    return valid_from <= quote_date <= valid_to


# ─────────────────────────────────────────────────────────────
# Основная функция расчёта
# ─────────────────────────────────────────────────────────────

def calculate_line(
    base_price: float,
    qty: float,
    quote_date: date,
    *,
    # скидка по типу клиента
    client_type_pct: float = 0.0,
    # акционная скидка по датам
    promo_discount_pct: float = 0.0,
    promo_valid_from: date | None = None,
    promo_valid_to: date | None = None,
    # зарезервировано — будут подключены на следующем шаге
    prepay_pct: float = 0.0,
    volume_pct: float = 0.0,
    product_pct: float = 0.0,
) -> DiscountResult:
    """
    Считает итоговую сумму строки заказа с учётом всех скидок.

    Порядок применения скидок:
      1. Скидка по типу клиента (всегда, если > 0)
      2. Акционная скидка (только если дата попадает в период)
      3. За предоплату / объём / продуктовая (зарезервировано)

    Скидки суммируются (не перемножаются), суммарно не более 100%.
    """
    gross = base_price * qty

    result = DiscountResult(
        base_price=base_price,
        qty=qty,
        gross=gross,
    )

    # 1. Скидка по типу клиента
    result.client_type_pct = min(max(client_type_pct, 0.0), 100.0)

    # 2. Акционная скидка — только если период задан и дата попадает в него
    if (
        promo_discount_pct > 0
        and promo_valid_from is not None
        and promo_valid_to is not None
        and discount_applies(quote_date, promo_valid_from, promo_valid_to)
    ):
        result.promo_pct = min(max(promo_discount_pct, 0.0), 100.0)

    # 3. Зарезервировано (подключим на следующем шаге)
    result.prepay_pct = min(max(prepay_pct, 0.0), 100.0)
    result.volume_pct = min(max(volume_pct, 0.0), 100.0)
    result.product_pct = min(max(product_pct, 0.0), 100.0)

    return result


# ─────────────────────────────────────────────────────────────
# Обратная совместимость — старый интерфейс не ломается
# ─────────────────────────────────────────────────────────────

def line_total(
    base_price: float,
    qty: float,
    discount_percent: float,
    quote_date: date,
    valid_from: date | None,
    valid_to: date | None,
    client_type_pct: float = 0.0,   # ← новый необязательный параметр
) -> float:
    """
    Совместимая обёртка для существующих вызовов в quote_tab.py.
    Возвращает float как раньше, но теперь учитывает тип клиента.
    """
    result = calculate_line(
        base_price=base_price,
        qty=qty,
        quote_date=quote_date,
        client_type_pct=client_type_pct,
        promo_discount_pct=discount_percent,
        promo_valid_from=valid_from,
        promo_valid_to=valid_to,
    )
    return result.net