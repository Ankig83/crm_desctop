from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from openpyxl import Workbook

from crm_desktop.repositories.clients import Client
from crm_desktop.utils.dates import format_dmY


@dataclass
class RusLine:
    external_id: str
    box_barcode: str
    name: str
    unit: str
    qty: float
    regular_price_per_box: float
    regular_price_per_piece: float
    units_per_box: int
    boxes_per_pallet: float
    gross_weight_kg: float
    volume_m3: float
    base_price: float
    discount_percent: float
    line_total: float


def export_rus_variant_a(
    path: Path,
    *,
    client: Client | None,
    quote_date: date,
    lines: list[RusLine],
) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "RUS"

    ws["A1"] = "No:"
    ws["A3"] = "Информация о Покупателе"
    ws["A4"] = "Название компании"
    ws["B4"] = client.name if client else ""
    ws["A5"] = "ИНН"
    ws["B5"] = client.inn if client else ""
    ws["A6"] = "Контактное лицо"
    ws["B6"] = (client.contact_person if client and client.contact_person else (client.contacts if client else ""))
    ws["A7"] = "Адрес"
    ws["B7"] = client.addresses if client else ""
    ws["A8"] = "Город/Штат/Почтовый индекс"
    ws["B8"] = client.city_region_zip if client else ""
    ws["A9"] = "Телефон"
    ws["B9"] = client.contacts if client else ""
    ws["A10"] = "Электронная почта"
    ws["B10"] = client.email if client else ""
    ws["A12"] = "Информация о Грузополучателе"
    ws["A13"] = "Название Компании"
    ws["B13"] = (client.consignee_name if client and client.consignee_name else (client.name if client else ""))
    ws["A14"] = "Контактное Лицо"
    ws["B14"] = (
        client.consignee_contact_person
        if client and client.consignee_contact_person
        else (client.contact_person if client else "")
    )
    ws["A15"] = "Адрес"
    ws["B15"] = (client.consignee_address if client and client.consignee_address else (client.addresses if client else ""))
    ws["A16"] = "Город/Штат/Почтовый Индекс"
    ws["B16"] = (
        client.consignee_city_region_zip
        if client and client.consignee_city_region_zip
        else (client.city_region_zip if client else "")
    )
    ws["A17"] = "Телефон"
    ws["B17"] = (client.consignee_phone if client and client.consignee_phone else (client.contacts if client else ""))
    ws["A18"] = "Электронная почта"
    ws["B18"] = (client.consignee_email if client and client.consignee_email else (client.email if client else ""))
    ws["A20"] = "ДАТА ЗАКАЗА"
    ws["B20"] = format_dmY(quote_date)
    ws["A21"] = "ДАТА ДОСТАВКИ"
    ws["B21"] = ""

    start_row = 24
    headers = [
        "Артикул",
        "Баркод коробки",
        "Наименование товара",
        "Ед. измерения",
        "Заказ",
        "Цена итог (КОР)",
        "Скидка, %",
        "Итоговая цена заказа",
        "Цена за Штуку (РУБ), регулярная цена",
        "Количество в кор. (ШТ)",
        "Цена Короба рег. прайс (РУБ)",
        "Количество на паллете (КОР)",
        "Итого Паллет",
        "масса брутто, (КГ)",
        "объем, (м3)",
    ]
    for col, h in enumerate(headers, start=1):
        ws.cell(row=start_row, column=col, value=h)

    regular_total = 0.0
    discount_total = 0.0
    row = start_row + 1
    for line in lines:
        regular = line.base_price * line.qty
        regular_total += regular
        discount_total += line.line_total
        ws.cell(row=row, column=1, value=line.external_id)
        ws.cell(row=row, column=2, value=line.box_barcode)
        ws.cell(row=row, column=3, value=line.name)
        ws.cell(row=row, column=4, value=line.unit)
        ws.cell(row=row, column=5, value=line.qty)
        ws.cell(row=row, column=6, value=round(line.line_total / line.qty, 2) if line.qty else 0.0)
        ws.cell(row=row, column=7, value=round(line.discount_percent, 2))
        ws.cell(row=row, column=8, value=round(line.line_total, 2))
        ws.cell(row=row, column=9, value=round(line.regular_price_per_piece, 2))
        ws.cell(row=row, column=10, value=line.units_per_box)
        ws.cell(row=row, column=11, value=round(line.regular_price_per_box, 2))
        ws.cell(row=row, column=12, value=line.boxes_per_pallet)
        ws.cell(row=row, column=13, value=round(line.qty / line.boxes_per_pallet, 3) if line.boxes_per_pallet else 0.0)
        ws.cell(row=row, column=14, value=line.gross_weight_kg)
        ws.cell(row=row, column=15, value=line.volume_m3)
        row += 1

    ws.cell(row=row + 1, column=1, value="ИТОГО (регулярно)")
    ws.cell(row=row + 1, column=8, value=round(regular_total, 2))
    ws.cell(row=row + 2, column=1, value="ИТОГО (с акцией, Вариант A)")
    ws.cell(row=row + 2, column=8, value=round(discount_total, 2))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
