from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook

from crm_desktop.repositories import audit, clients, products, promotions
from crm_desktop.utils.dates import format_dmY, iso, parse_dmY, parse_iso
from crm_desktop.utils.validation import normalize_inn


def _norm_header(s: Any) -> str:
    t = str(s or "").strip().lower().replace("ё", "е")
    return re.sub(r"\s+", " ", t)


@dataclass
class ImportReport:
    errors: list[str] = field(default_factory=list)
    clients_rows: int = 0
    products_rows: int = 0
    promotions_rows: int = 0


def _header_map(row: tuple[Any, ...]) -> dict[str, int]:
    m: dict[str, int] = {}
    for i, cell in enumerate(row):
        key = _norm_header(cell)
        if key:
            m[key] = i
    return m


def _cell(row: tuple[Any, ...], m: dict[str, int], *names: str) -> str:
    for n in names:
        k = _norm_header(n)
        if k in m:
            v = row[m[k]]
            if v is None:
                return ""
            return str(v).strip()
    return ""


def _float_cell(row: tuple[Any, ...], m: dict[str, int], *names: str) -> float | None:
    s = _cell(row, m, *names)
    if s == "":
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def import_clients(conn: sqlite3.Connection, path: Path) -> ImportReport:
    rep = ImportReport()
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows, None)
    if not header:
        rep.errors.append("Файл клиентов пуст.")
        return rep
    hm = _header_map(header)
    for line_no, row in enumerate(rows, start=2):
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        ext = _cell(row, hm, "id клиента", "id")
        name = _cell(row, hm, "название", "наименование")
        inn = normalize_inn(_cell(row, hm, "инн"))
        contacts = _cell(row, hm, "контакты")
        addresses = _cell(row, hm, "адреса", "адрес")
        unload = _cell(row, hm, "пункты разгрузки", "пункт разгрузки")
        contact_person = _cell(row, hm, "контактное лицо")
        email = _cell(row, hm, "электронная почта", "email", "e-mail")
        city_region_zip = _cell(row, hm, "город/штат/почтовый индекс", "город")
        consignee_name = _cell(row, hm, "название компании грузополучателя")
        consignee_contact_person = _cell(row, hm, "контактное лицо грузополучателя")
        consignee_address = _cell(row, hm, "адрес грузополучателя")
        consignee_city_region_zip = _cell(
            row, hm, "город/штат/почтовый индекс грузополучателя"
        )
        consignee_phone = _cell(row, hm, "телефон грузополучателя")
        consignee_email = _cell(
            row,
            hm,
            "электронная почта грузополучателя",
            "email грузополучателя",
            "e-mail грузополучателя",
        )
        if not name and not inn and not ext:
            continue
        try:
            if ext:
                existing = conn.execute(
                    "SELECT id FROM clients WHERE external_id = ?", (ext,)
                ).fetchone()
            else:
                existing = None
            if existing:
                clients.update(
                    conn,
                    int(existing[0]),
                    external_id=ext or None,
                    name=name,
                    inn=inn,
                    contacts=contacts,
                    addresses=addresses,
                    unload_points=unload,
                    contact_person=contact_person,
                    email=email,
                    city_region_zip=city_region_zip,
                    consignee_name=consignee_name,
                    consignee_contact_person=consignee_contact_person,
                    consignee_address=consignee_address,
                    consignee_city_region_zip=consignee_city_region_zip,
                    consignee_phone=consignee_phone,
                    consignee_email=consignee_email,
                    is_new=False,
                )
            else:
                clients.insert(
                    conn,
                    external_id=ext or None,
                    name=name,
                    inn=inn,
                    contacts=contacts,
                    addresses=addresses,
                    unload_points=unload,
                    contact_person=contact_person,
                    email=email,
                    city_region_zip=city_region_zip,
                    consignee_name=consignee_name,
                    consignee_contact_person=consignee_contact_person,
                    consignee_address=consignee_address,
                    consignee_city_region_zip=consignee_city_region_zip,
                    consignee_phone=consignee_phone,
                    consignee_email=consignee_email,
                    is_new=False,
                )
            rep.clients_rows += 1
        except Exception as e:  # noqa: BLE001
            rep.errors.append(f"Клиенты, строка {line_no}: {e}")
    audit.log(conn, "import", "clients", str(path))
    return rep


def import_products(conn: sqlite3.Connection, path: Path) -> ImportReport:
    rep = ImportReport()
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows, None)
    if not header:
        rep.errors.append("Файл товаров пуст.")
        return rep
    hm = _header_map(header)
    for line_no, row in enumerate(rows, start=2):
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        ext = _cell(row, hm, "id товара", "id")
        name = _cell(row, hm, "наименование", "название")
        price = _float_cell(row, hm, "базовая цена", "цена")
        box_barcode = _cell(row, hm, "баркод коробки", "баркод")
        unit = _cell(row, hm, "ед. измерения", "ед измерения", "ед.")
        units_per_box = _float_cell(row, hm, "количество в кор. (шт)", "количество в кор", "шт в коробе")
        regular_piece_price = _float_cell(
            row,
            hm,
            "цена за штуку (руб), регулярная цена",
            "цена за штуку",
            "регулярная цена штуки",
        )
        boxes_per_pallet = _float_cell(
            row, hm, "количество на паллете (кор)", "коробов на паллете"
        )
        gross_weight_kg = _float_cell(row, hm, "масса брутто, (кг)", "масса брутто")
        volume_m3 = _float_cell(row, hm, "объем, (м3)", "объём, (м3)", "объем м3", "объём м3")
        if not name and ext == "":
            continue
        if price is None:
            rep.errors.append(f"Товары, строка {line_no}: нет базовой цены.")
            continue
        try:
            p = products.by_external_id(conn, ext) if ext else None
            if p:
                products.update(
                    conn,
                    p.id,
                    external_id=ext or None,
                    name=name or p.name,
                    base_price=price,
                    box_barcode=box_barcode or p.box_barcode,
                    unit=unit or p.unit or "кор",
                    units_per_box=int(units_per_box if units_per_box is not None else p.units_per_box),
                    regular_piece_price=float(
                        regular_piece_price
                        if regular_piece_price is not None
                        else p.regular_piece_price
                    ),
                    boxes_per_pallet=float(
                        boxes_per_pallet if boxes_per_pallet is not None else p.boxes_per_pallet
                    ),
                    gross_weight_kg=float(
                        gross_weight_kg if gross_weight_kg is not None else p.gross_weight_kg
                    ),
                    volume_m3=float(volume_m3 if volume_m3 is not None else p.volume_m3),
                )
            elif ext:
                products.insert(
                    conn,
                    external_id=ext,
                    name=name or "",
                    base_price=price,
                    box_barcode=box_barcode,
                    unit=unit or "кор",
                    units_per_box=int(units_per_box or 0),
                    regular_piece_price=float(regular_piece_price or 0),
                    boxes_per_pallet=float(boxes_per_pallet or 0),
                    gross_weight_kg=float(gross_weight_kg or 0),
                    volume_m3=float(volume_m3 or 0),
                )
            else:
                products.insert(
                    conn,
                    external_id=None,
                    name=name or "",
                    base_price=price,
                    box_barcode=box_barcode,
                    unit=unit or "кор",
                    units_per_box=int(units_per_box or 0),
                    regular_piece_price=float(regular_piece_price or 0),
                    boxes_per_pallet=float(boxes_per_pallet or 0),
                    gross_weight_kg=float(gross_weight_kg or 0),
                    volume_m3=float(volume_m3 or 0),
                )
            rep.products_rows += 1
        except Exception as e:  # noqa: BLE001
            rep.errors.append(f"Товары, строка {line_no}: {e}")
    audit.log(conn, "import", "products", str(path))
    return rep


def import_promotions(conn: sqlite3.Connection, path: Path) -> ImportReport:
    rep = ImportReport()
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows, None)
    if not header:
        rep.errors.append("Файл акций пуст.")
        return rep
    hm = _header_map(header)
    seen_products: set[str] = set()
    for line_no, row in enumerate(rows, start=2):
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        ext = _cell(row, hm, "id товара", "id")
        ptype = _cell(row, hm, "тип акции", "тип")
        disc = _float_cell(row, hm, "размер скидки", "скидка", "скидка %")
        d1s = _cell(row, hm, "дата начала", "начало")
        d2s = _cell(row, hm, "дата окончания", "окончание", "конец")
        if not ext:
            rep.errors.append(f"Акции, строка {line_no}: нет ID товара.")
            continue
        if ext in seen_products:
            rep.errors.append(f"Акции, строка {line_no}: дубль ID товара {ext} в файле.")
            continue
        seen_products.add(ext)
        if disc is None:
            rep.errors.append(f"Акции, строка {line_no}: нет размера скидки.")
            continue
        try:
            d1 = parse_dmY(d1s)
            d2 = parse_dmY(d2s)
        except ValueError as e:
            rep.errors.append(f"Акции, строка {line_no}: {e}")
            continue
        if d1 > d2:
            rep.errors.append(f"Акции, строка {line_no}: дата начала позже даты окончания.")
            continue
        pr = products.by_external_id(conn, ext)
        if not pr:
            rep.errors.append(f"Акции, строка {line_no}: товар с ID «{ext}» не найден в базе.")
            continue
        try:
            promotions.upsert(
                conn,
                pr.id,
                promo_type=ptype,
                discount_percent=float(disc),
                valid_from_iso=iso(d1),
                valid_to_iso=iso(d2),
            )
            rep.promotions_rows += 1
        except Exception as e:  # noqa: BLE001
            rep.errors.append(f"Акции, строка {line_no}: {e}")
    audit.log(conn, "import", "promotions", str(path))
    return rep


def export_clients(conn: sqlite3.Connection, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "clients"
    ws.append(
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
            "Новый (0/1)",
        ]
    )
    for c in clients.list_all(conn):
        ws.append(
            [
                c.external_id or "",
                c.name,
                c.inn,
                c.contacts,
                c.addresses,
                c.unload_points,
                c.contact_person,
                c.email,
                c.city_region_zip,
                c.consignee_name,
                c.consignee_contact_person,
                c.consignee_address,
                c.consignee_city_region_zip,
                c.consignee_phone,
                c.consignee_email,
                1 if c.is_new else 0,
            ]
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    audit.log(conn, "export", "clients", str(path))


def export_products(conn: sqlite3.Connection, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "products"
    ws.append(
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
    for p in products.list_all(conn):
        ws.append(
            [
                p.external_id or "",
                p.name,
                p.base_price,
                p.box_barcode,
                p.unit,
                p.units_per_box,
                p.regular_piece_price,
                p.boxes_per_pallet,
                p.gross_weight_kg,
                p.volume_m3,
            ]
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    audit.log(conn, "export", "products", str(path))


def export_promotions(conn: sqlite3.Connection, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "promotions"
    ws.append(
        ["ID товара", "Тип акции", "Размер скидки", "Дата начала", "Дата окончания"]
    )
    for r in promotions.list_all(conn):
        d1 = parse_iso(r.valid_from_iso) if r.valid_from_iso else None
        d2 = parse_iso(r.valid_to_iso) if r.valid_to_iso else None
        ws.append(
            [
                r.product_external_id or "",
                r.promo_type,
                r.discount_percent,
                format_dmY(d1) if d1 else "",
                format_dmY(d2) if d2 else "",
            ]
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    audit.log(conn, "export", "promotions", str(path))
