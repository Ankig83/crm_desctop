# -*- coding: utf-8 -*-
"""Генерация templates/ТОВАРЫ.xlsx и templates/АКЦИИ.xlsx (по 10 строк, тестовые данные)."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
OUT_PRODUCTS = ROOT / "templates" / "ТОВАРЫ.xlsx"
OUT_PROMO = ROOT / "templates" / "АКЦИИ.xlsx"

PRODUCTS: list[tuple[str, str, float]] = [
    ("T-001", "Цемент М500, мешок 50 кг", 385.0),
    ("T-002", "Песок строительный, 1 т", 620.0),
    ("T-003", "Щебень фр. 20–40, 1 т", 890.0),
    ("T-004", "Арматура А12, пог. м", 72.5),
    ("T-005", "Доска обрезная 50×200×6000", 1850.0),
    ("T-006", "Гвозди строительные 100 мм, кг", 95.0),
    ("T-007", "Профнастил С8, м²", 410.0),
    ("T-008", "Минеральная вата 100 мм, уп.", 780.0),
    ("T-009", "Плиточный клей, мешок 25 кг", 420.0),
    ("T-010", "Праймер битумный, ведро 18 л", 1150.0),
]

# Акции: тот же ID товара, тип, %, период ДД.ММ.ГГГГ (импорт в программе)
PROMOTIONS: list[tuple[str, str, float, str, str]] = [
    ("T-001", "Процент", 5.0, "01.03.2026", "30.06.2026"),
    ("T-002", "Процент", 7.0, "15.03.2026", "15.05.2026"),
    ("T-003", "Процент", 10.0, "01.01.2026", "31.12.2026"),
    ("T-004", "Процент", 3.0, "01.04.2026", "30.04.2026"),
    ("T-005", "Процент", 12.0, "10.03.2026", "10.09.2026"),
    ("T-006", "Процент", 0.0, "01.03.2026", "31.03.2026"),  # 0% — без скидки по логике
    ("T-007", "Процент", 8.0, "20.02.2026", "20.08.2026"),
    ("T-008", "Процент", 15.0, "01.03.2026", "31.05.2026"),
    ("T-009", "Процент", 6.0, "05.04.2026", "05.07.2026"),
    ("T-010", "Процент", 9.0, "01.03.2026", "28.02.2027"),
]


def main() -> None:
    OUT_PRODUCTS.parent.mkdir(parents=True, exist_ok=True)

    wb_p = Workbook()
    ws_p = wb_p.active
    ws_p.title = "Товары"
    ws_p.append(["ID товара", "Наименование", "Базовая цена"])
    for row in PRODUCTS:
        ws_p.append(list(row))
    wb_p.save(OUT_PRODUCTS)

    wb_a = Workbook()
    ws_a = wb_a.active
    ws_a.title = "Акции"
    ws_a.append(
        ["ID товара", "Тип акции", "Размер скидки", "Дата начала", "Дата окончания"]
    )
    for row in PROMOTIONS:
        ws_a.append(list(row))
    wb_a.save(OUT_PROMO)

    print(OUT_PRODUCTS.resolve())
    print(OUT_PROMO.resolve())


if __name__ == "__main__":
    main()
