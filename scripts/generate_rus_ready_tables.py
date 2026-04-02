# -*- coding: utf-8 -*-
"""Генерация расширенных таблиц клиентов/товаров под шаблон RUS (без акций)."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
OUT_CLIENTS = ROOT / "templates" / "КЛИЕНТЫ_RUS.xlsx"
OUT_PRODUCTS = ROOT / "templates" / "ТОВАРЫ_RUS.xlsx"


def _clients_rows() -> list[list[str]]:
    rows: list[list[str]] = []
    for i in range(1, 31):
        cid = f"CL-{i:03d}"
        name = f'ООО "ТестКлиент {i:02d}"'
        inn = f"77{i:08d}"[-10:]
        contact = f"Иванов Иван {i:02d}"
        phone = f"+7 900 {100+i:03d}-{10+i:02d}-{20+i:02d}"
        email = f"client{i:02d}@example.ru"
        addr = f"г. Москва, ул. Тестовая, д. {i}"
        city = "г. Москва, 101000"
        unload = f"Склад {i % 5 + 1}, ворота {i % 8 + 1}"
        ship_name = name
        ship_contact = contact
        ship_addr = f"г. Москва, ул. Складская, д. {i}"
        ship_city = "г. Москва, 101000"
        ship_phone = phone
        ship_email = email
        rows.append(
            [
                cid,
                name,
                inn,
                phone,
                addr,
                unload,
                contact,
                email,
                city,
                ship_name,
                ship_contact,
                ship_addr,
                ship_city,
                ship_phone,
                ship_email,
            ]
        )
    return rows


def _products_rows() -> list[list[object]]:
    data = [
        ("T-001", "Цемент М500, мешок 50 кг", 385.0),
        ("T-002", "Песок строительный, 1 т", 620.0),
        ("T-003", "Щебень фр. 20-40, 1 т", 890.0),
        ("T-004", "Арматура А12, пог. м", 72.5),
        ("T-005", "Доска обрезная 50x200x6000", 1850.0),
        ("T-006", "Гвозди строительные 100 мм, кг", 95.0),
        ("T-007", "Профнастил С8, м2", 410.0),
        ("T-008", "Минеральная вата 100 мм, уп.", 780.0),
        ("T-009", "Плиточный клей, мешок 25 кг", 420.0),
        ("T-010", "Праймер битумный, ведро 18 л", 1150.0),
    ]
    rows: list[list[object]] = []
    for idx, (external_id, name, base_price) in enumerate(data, start=1):
        barcode = f"1899100{21000000+idx:08d}"
        unit = "кор"
        units_per_box = 20 + (idx % 5) * 4
        piece_price = round(base_price / max(units_per_box, 1), 2)
        boxes_per_pallet = 40 + (idx % 4) * 10
        gross_weight = round(6.5 + idx * 0.8, 2)
        volume_m3 = round(0.12 + idx * 0.03, 3)
        rows.append(
            [
                external_id,
                name,
                base_price,
                barcode,
                unit,
                units_per_box,
                piece_price,
                boxes_per_pallet,
                gross_weight,
                volume_m3,
            ]
        )
    return rows


def main() -> None:
    OUT_CLIENTS.parent.mkdir(parents=True, exist_ok=True)

    wb_c = Workbook()
    ws_c = wb_c.active
    ws_c.title = "Клиенты"
    ws_c.append(
        [
            "ID клиента",
            "Название",
            "ИНН",
            "Контакты",
            "Адреса",
            "Пункты разгрузки",
            "Контактное лицо",
            "Электронная почта",
            "Город/Штат/Почтовый индекс",
            "Название компании грузополучателя",
            "Контактное лицо грузополучателя",
            "Адрес грузополучателя",
            "Город/Штат/Почтовый индекс грузополучателя",
            "Телефон грузополучателя",
            "Электронная почта грузополучателя",
        ]
    )
    for row in _clients_rows():
        ws_c.append(row)
    wb_c.save(OUT_CLIENTS)

    wb_p = Workbook()
    ws_p = wb_p.active
    ws_p.title = "Товары"
    ws_p.append(
        [
            "ID товара",
            "Наименование",
            "Базовая цена",
            "Баркод коробки",
            "Ед. измерения",
            "Количество в кор. (ШТ)",
            "Цена за штуку (РУБ), регулярная цена",
            "Количество на паллете (КОР)",
            "масса брутто, (КГ)",
            "объём, (м3)",
        ]
    )
    for row in _products_rows():
        ws_p.append(row)
    wb_p.save(OUT_PRODUCTS)

    print(OUT_CLIENTS.resolve())
    print(OUT_PRODUCTS.resolve())


if __name__ == "__main__":
    main()

