from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook

from crm_desktop.repositories import audit, clients, products, promotions
from crm_desktop.utils.bonus_ids import (
    missing_product_external_ids,
    normalize_product_external_ids_csv,
    parse_product_external_ids_csv,
)
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


def _row_is_empty(row: tuple[Any, ...]) -> bool:
    return all(v is None or str(v).strip() == "" for v in row)


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


def _raw_cell_by_index(row: tuple[Any, ...], idx: int) -> str:
    if idx < 0 or idx >= len(row):
        return ""
    v = row[idx]
    if v is None:
        return ""
    return str(v).strip()


def _float_cell(row: tuple[Any, ...], m: dict[str, int], *names: str) -> float | None:
    s = _cell(row, m, *names)
    if s == "":
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _find_header_row(
    rows: list[tuple[Any, ...]],
    required_headers: tuple[str, ...],
) -> tuple[int, tuple[Any, ...], dict[str, int]] | None:
    for idx, row in enumerate(rows):
        if _row_is_empty(row):
            continue
        hm = _header_map(row)
        if all(_norm_header(h) in hm for h in required_headers):
            return idx, row, hm
    return None


def _load_rows_with_openpyxl(path: Path) -> list[tuple[Any, ...]]:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    return [tuple(r) for r in ws.iter_rows(values_only=True)]


def _load_rows_with_calamine(path: Path) -> list[tuple[Any, ...]]:
    try:
        import pandas as pd
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("Для fallback-импорта нужен pandas.") from e
    try:
        df = pd.read_excel(path, sheet_name=0, engine="calamine", header=None, dtype=str)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("Не удалось прочитать файл через calamine.") from e
    rows: list[tuple[Any, ...]] = []
    for rec in df.itertuples(index=False, name=None):
        cleaned: list[str] = []
        for v in rec:
            s = "" if v is None else str(v)
            if s.strip().lower() == "nan":
                s = ""
            cleaned.append(s)
        rows.append(tuple(cleaned))
    return rows


def _extract_matrix_rules_json(
    row: tuple[Any, ...],
    header_row: tuple[Any, ...],
    hm: dict[str, int],
) -> str:
    known = {
        _norm_header("id товара"),
        _norm_header("id"),
        _norm_header("тип акции"),
        _norm_header("тип"),
        _norm_header("размер скидки"),
        _norm_header("скидка"),
        _norm_header("скидка %"),
        _norm_header("дата начала"),
        _norm_header("начало"),
        _norm_header("дата окончания"),
        _norm_header("окончание"),
        _norm_header("конец"),
        _norm_header("id товаров-бонусов (через запятую)"),
        _norm_header("id товаров бонуса"),
        _norm_header("id товаров-бонусов"),
        _norm_header("бонусные id"),
        _norm_header("id бонусных товаров"),
        _norm_header("id бонусов"),
        _norm_header("товары бонусом"),
    }
    matrix: dict[str, str] = {}
    for h, idx in hm.items():
        if h in known:
            continue
        val = _raw_cell_by_index(row, idx)
        original_header = _raw_cell_by_index(header_row, idx)
        matrix[(original_header or h)] = val
    if not matrix:
        return ""
    return json.dumps(matrix, ensure_ascii=False)


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
        if row is None or _row_is_empty(row):
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
        if row is None or _row_is_empty(row):
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
    required_headers = ("id товара", "размер скидки")
    rows_data: list[tuple[Any, ...]]
    try:
        rows_data = _load_rows_with_openpyxl(path)
    except Exception as e_openpyxl:  # noqa: BLE001
        try:
            rows_data = _load_rows_with_calamine(path)
        except Exception as e_calamine:  # noqa: BLE001
            rep.errors.append(
                "Не удалось прочитать файл акций. "
                f"openpyxl: {e_openpyxl}. calamine: {e_calamine}"
            )
            return rep

    if not rows_data:
        rep.errors.append("Файл акций пуст.")
        return rep
    header_info = _find_header_row(rows_data, required_headers)
    if header_info is None:
        rep.errors.append(
            "Не найдена строка заголовков акций (ожидаются колонки 'ID товара' и 'Размер скидки')."
        )
        return rep
    header_idx, header_row, hm = header_info
    seen_products: set[str] = set()
    for line_no, row in enumerate(rows_data[header_idx + 1 :], start=header_idx + 2):
        if row is None or _row_is_empty(row):
            continue
        ext = _cell(row, hm, "id товара", "id")
        ptype = _cell(row, hm, "тип акции", "тип")
        disc = _float_cell(row, hm, "размер скидки", "скидка", "скидка %")
        d1s = _cell(row, hm, "дата начала", "начало")
        d2s = _cell(row, hm, "дата окончания", "окончание", "конец")
        bonus_raw = _cell(
            row,
            hm,
            "id товаров-бонусов (через запятую)",
            "id товаров бонуса",
            "id товаров-бонусов",
            "бонусные id",
            "id бонусных товаров",
            "id бонусов",
            "товары бонусом",
        )
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
        parsed_bonus = parse_product_external_ids_csv(bonus_raw)
        bonus_norm = normalize_product_external_ids_csv(bonus_raw)
        if parsed_bonus:
            miss = missing_product_external_ids(conn, parsed_bonus)
            if miss:
                rep.errors.append(
                    f"Акции, строка {line_no}: не найдены товары с ID (бонус): {', '.join(miss)}."
                )
                continue
        try:
            promotions.upsert(
                conn,
                pr.id,
                promo_type=ptype,
                discount_percent=float(disc),
                valid_from_iso=iso(d1),
                valid_to_iso=iso(d2),
                bonus_other_product_ids=bonus_norm,
                matrix_rules_json=_extract_matrix_rules_json(row, header_row, hm),
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
        [
            "ID товара",
            "Тип акции",
            "Размер скидки",
            "Дата начала",
            "Дата окончания",
            "ID товаров-бонусов (через запятую)",
        ]
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
                r.bonus_other_product_ids or "",
            ]
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    audit.log(conn, "export", "promotions", str(path))
