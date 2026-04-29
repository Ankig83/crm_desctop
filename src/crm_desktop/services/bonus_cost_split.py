"""Распределение каталожной стоимости подарочных коробок по оплачиваемым строкам.

Заказчик: одна общая «корзина» подарков; копейки; режимы «поровну по коробкам»
или «доля % на основной товар».
"""
from __future__ import annotations


def split_amount_by_boxes(amount: float, box_counts: list[float]) -> list[float]:
    """Разбить ``amount`` (₽, уже округлённый до сотых) пропорционально числу коробок.

    Сумма элементов результата с точностью до копеек совпадает с ``amount``.
    При нулевых данных возвращает нули.
    """
    amount = round(float(amount), 2)
    n = len(box_counts)
    if n == 0:
        return []
    if amount <= 0:
        return [0.0] * n
    total_boxes = sum(float(x) for x in box_counts)
    if total_boxes <= 0:
        return [0.0] * n
    parts = [round(amount * float(bq) / total_boxes, 2) for bq in box_counts]
    diff = round(amount - sum(parts), 2)
    if parts and abs(diff) >= 0.005:
        parts[-1] = round(parts[-1] + diff, 2)
    return parts


def parts_main_gift_even(V: float, n_main: float, n_gift: float) -> tuple[float, float]:
    """Режим (а): доля как N_main / (N_main + N_gift)."""
    V = round(float(V), 2)
    d = n_main + n_gift
    if V <= 0 or d <= 0:
        return 0.0, 0.0
    part_main = round(V * float(n_main) / d, 2)
    part_gift = round(V - part_main, 2)
    return part_main, part_gift


def parts_main_gift_ratio(V: float, main_pct: float) -> tuple[float, float]:
    """Режим (б): main_pct % суммы V на основной товар, остальное на подарки."""
    V = round(float(V), 2)
    p = max(0.0, min(100.0, float(main_pct)))
    part_main = round(V * p / 100.0, 2)
    part_gift = round(V - part_main, 2)
    return part_main, part_gift
