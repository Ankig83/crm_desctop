from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


# ─────────────────────────────────────────────────────────────
# Dataclass
# ─────────────────────────────────────────────────────────────

@dataclass
class RusLine:
    external_id: str = ""
    box_barcode: str = ""
    name: str = ""
    unit: str = "кор"
    qty: float = 0.0
    base_price: float = 0.0
    regular_price_per_box: float = 0.0
    regular_price_per_piece: float = 0.0
    discount_percent: float = 0.0
    line_total: float = 0.0
    units_per_box: int = 0
    boxes_per_pallet: int = 0
    gross_weight_kg: float = 0.0
    volume_m3: float = 0.0
    # matrix_rules может содержать произвольные ключи акций из БД,
    # но также поддерживаются стандартные ключи шаблона:
    #   "prepay_25"    - скидка за предоплату до 25% (%)
    #   "prepay_50"    - скидка за предоплату до 50% (%)
    #   "volume_300"   - скидка за объём > 300 кор (%)
    #   "volume_500"   - скидка за объём > 500 кор (%)
    #   "expiry_pct"   - продуктовая скидка срок годности (%)
    #   "expiry_rub"   - продуктовая скидка (руб)
    #   "promo_15_2_qty"  - акция 15+2 (КОФЕ): кол-во того же товара
    #   "promo_15_2_ids"  - акция 15+2 (КОФЕ): id другого товара
    #   "promo_10_3_qty"  - акция 10+3 (КОНФ): кол-во того же товара
    #   "promo_10_3_ids"  - акция 10+3 (КОНФ): id другого товара
    matrix_rules: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# Style helpers
# ─────────────────────────────────────────────────────────────

FONT_NAME = "Arial"

_THIN = Side(style="thin")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

# Colour palette
_C_BASE_DARK   = "1F4E79"   # dark blue  — row-1 group header base
_C_BASE_LIGHT  = "BDD7EE"   # light blue — row-3 base columns
_C_TOTAL_MID   = "2E75B6"   # mid blue   — totals group
_C_DISC_HEAD   = "ED7D31"   # orange     — discount group header
_C_DISC_SUB    = "FFF2CC"   # yellow     — discount sub/data
_C_PROMO_HEAD  = "70AD47"   # green      — promo group header
_C_PROMO_SUB   = "E2EFDA"   # light green — promo sub/data
_C_LOG_LIGHT   = "D9D9D9"   # grey       — logistics
_C_WHITE       = "FFFFFF"
_C_TOTAL_DATA  = "DEEAF1"   # pale blue  — total data cells


def _font(bold: bool = False, size: int = 9, color: str = "000000") -> Font:
    return Font(name=FONT_NAME, bold=bold, size=size, color=color)


def _fill(rgb: str) -> PatternFill:
    return PatternFill("solid", fgColor=rgb)


def _align(h: str = "center", wrap: bool = True) -> Alignment:
    return Alignment(horizontal=h, vertical="center", wrap_text=wrap)


def _style(cell, bg: str, bold: bool = False, color: str = "000000",
           h: str = "center", wrap: bool = True) -> None:
    cell.font = _font(bold=bold, color=color)
    cell.fill = _fill(bg)
    cell.border = _BORDER
    cell.alignment = _align(h=h, wrap=wrap)


# ─────────────────────────────────────────────────────────────
# Header builder helpers
# ─────────────────────────────────────────────────────────────

def _hdr1(ws, ref: str, value: str, bg: str) -> None:
    """Row-1 group header (white text on dark bg)."""
    c = ws[ref]
    c.value = value
    _style(c, bg, bold=True, color="FFFFFF")


def _hdr2(ws, ref: str, value: str, bg: str, color: str = "000000") -> None:
    """Row-2 sub-group header."""
    c = ws[ref]
    c.value = value
    _style(c, bg, bold=True, color=color)


def _hdr3(ws, ref: str, value: str, bg: str) -> None:
    """Row-3 column label."""
    c = ws[ref]
    c.value = value
    _style(c, bg, bold=True)


# ─────────────────────────────────────────────────────────────
# CLIENT sheet builder
# ─────────────────────────────────────────────────────────────

def _build_client_sheet(ws, client, quote_date: date) -> None:
    ws.title = "CLIENT"

    client_data = [
        ("Дата",                         quote_date.strftime("%d.%m.%Y")),
        ("Имя клиента",                  client.name if client else ""),
        ("ИНН",                          client.inn if client else ""),
        ("Контакт",                      client.contact_person if client else ""),
        ("Телефон",                      client.contacts if client else ""),
        ("Email",                        client.email if client else ""),
        ("Адрес",                        client.addresses if client else ""),
        ("Город/Регион",                 client.city_region_zip if client else ""),
        ("Пункты разгрузки",             client.unload_points if client else ""),
        ("Грузополучатель",              client.consignee_name if client else ""),
        ("Контакт грузополучателя",      client.consignee_contact_person if client else ""),
        ("Адрес грузополучателя",        client.consignee_address if client else ""),
        ("Город/Регион грузополучателя", client.consignee_city_region_zip if client else ""),
        ("Телефон грузополучателя",      client.consignee_phone if client else ""),
        ("Email грузополучателя",        client.consignee_email if client else ""),
    ]

    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 50

    for row_idx, (key, value) in enumerate(client_data, start=1):
        key_cell = ws.cell(row=row_idx, column=1, value=key)
        val_cell = ws.cell(row=row_idx, column=2, value=value)
        key_cell.font = _font(bold=True)
        key_cell.fill = _fill(_C_BASE_LIGHT)
        key_cell.border = _BORDER
        key_cell.alignment = _align(h="left")
        val_cell.font = _font()
        val_cell.fill = _fill(_C_WHITE)
        val_cell.border = _BORDER
        val_cell.alignment = _align(h="left", wrap=False)


# ─────────────────────────────────────────────────────────────
# ORDER sheet builder
# ─────────────────────────────────────────────────────────────

def _build_order_sheet(ws, lines: list[RusLine]) -> None:
    ws.title = "ORDER"

    # ── Row 1: group headers ──────────────────────────────────
    ws.merge_cells("A1:L1");  _hdr1(ws, "A1", "ОСНОВНЫЕ ДАННЫЕ ЗАКАЗА", _C_BASE_DARK)
    ws.merge_cells("M1:R1");  _hdr1(ws, "M1", "СКИДКИ",                  _C_DISC_HEAD)
    ws.merge_cells("S1:V1");  _hdr1(ws, "S1", "АКЦИОННЫЕ УСЛОВИЯ",        _C_PROMO_HEAD)
    ws.merge_cells("W1:Y1");  _hdr1(ws, "W1", "ИТОГОВЫЕ СУММЫ",           _C_TOTAL_MID)
    ws.merge_cells("Z1:AF1"); _hdr1(ws, "Z1", "ЛОГИСТИКА",                _C_LOG_LIGHT)
    ws["Z1"].font = _font(bold=True, color="000000")  # grey bg → dark text

    # ── Row 2: sub-group headers ──────────────────────────────
    for col in range(1, 13):          # A–L
        ws.cell(row=2, column=col).fill = _fill(_C_BASE_LIGHT)
        ws.cell(row=2, column=col).border = _BORDER

    ws.merge_cells("M2:N2"); _hdr2(ws, "M2", "За предоплату %",    _C_DISC_SUB)
    ws.merge_cells("O2:P2"); _hdr2(ws, "O2", "За объём %",          _C_DISC_SUB)
    ws.merge_cells("Q2:R2"); _hdr2(ws, "Q2", "Продуктовая скидка",  _C_DISC_SUB)
    ws.merge_cells("S2:T2"); _hdr2(ws, "S2", "Акция 15+2 (КОФЕ)\nПри покупке 15", _C_PROMO_SUB)
    ws.merge_cells("U2:V2"); _hdr2(ws, "U2", "Акция 10+3 (КОНФ)\nПри покупке 10", _C_PROMO_SUB)

    for col in range(23, 26):         # W–Y
        ws.cell(row=2, column=col).fill = _fill(_C_TOTAL_MID)
        ws.cell(row=2, column=col).border = _BORDER

    for col in range(26, 33):         # Z–AF
        ws.cell(row=2, column=col).fill = _fill(_C_LOG_LIGHT)
        ws.cell(row=2, column=col).border = _BORDER

    # ── Row 3: column labels ──────────────────────────────────
    labels = [
        # col, label,                                   bg
        (1,  "Артикул",                                  _C_BASE_LIGHT),
        (2,  "Баркод коробки",                           _C_BASE_LIGHT),
        (3,  "Наименование Товара",                      _C_BASE_LIGHT),
        (4,  "Ед. Измерения",                            _C_BASE_LIGHT),
        (5,  "Заказ (КОР)",                              _C_BASE_LIGHT),
        (6,  "Кол-во в кор. (ШТ)",                       _C_BASE_LIGHT),
        (7,  "Цена за Штуку\nрег. (РУБ)",                _C_BASE_LIGHT),
        (8,  "Цена Короба\nрег. прайс (РУБ)",            _C_BASE_LIGHT),
        (9,  "Кол-во на паллете\n(КОР)",                 _C_BASE_LIGHT),
        (10, "Скидка %",                                 _C_BASE_LIGHT),
        (11, "Цена итог (КОР)",                          _C_BASE_LIGHT),
        (12, "Итоговая сумма\nзаказа (РУБ)",             _C_BASE_LIGHT),
        (13, "Предоплата\nдо 25% (−2%)",                 _C_DISC_SUB),
        (14, "Предоплата\nдо 50% (−5%)",                 _C_DISC_SUB),
        (15, "Объём\n> 300 кор (−6%)",                   _C_DISC_SUB),
        (16, "Объём\n> 500 кор (−8%)",                   _C_DISC_SUB),
        (17, "Срок годности\n(%)",                       _C_DISC_SUB),
        (18, "Скидка\n(руб)",                            _C_DISC_SUB),
        (19, "Кол-во\nтого же товара",                   _C_PROMO_SUB),
        (20, "id\nдругого товара",                       _C_PROMO_SUB),
        (21, "Кол-во\nтого же товара",                   _C_PROMO_SUB),
        (22, "id\nдругого товара",                       _C_PROMO_SUB),
        (23, "Регулярная\nитоговая сумма (РУБ)",         _C_TOTAL_MID),
        (24, "Итоговая сумма\n+ акция (РУБ)",            _C_TOTAL_MID),
        (25, "Итоговая сумма\nакция + мот (РУБ)",        _C_TOTAL_MID),
        (26, "Масса брутто\n(КГ)",                       _C_LOG_LIGHT),
        (27, "Объём\n(м3)",                              _C_LOG_LIGHT),
        (28, "Итого\nпаллет",                            _C_LOG_LIGHT),
        (29, "Коробов\nв ряде",                          _C_LOG_LIGHT),  # не в RusLine — оставим пустым
        (30, "Рядов\nв паллете",                         _C_LOG_LIGHT),  # не в RusLine — оставим пустым
        (31, "Высота\nс паллетой (мм)",                  _C_LOG_LIGHT),  # не в RusLine — оставим пустым
        (32, "Размер короба\nд*ш*в",                     _C_LOG_LIGHT),  # не в RusLine — оставим пустым
    ]
    for col_num, label, bg in labels:
        c = ws.cell(row=3, column=col_num, value=label)
        color = "FFFFFF" if bg in (_C_TOTAL_MID,) else "000000"
        _style(c, bg, bold=True, color=color)

    # ── Column widths ─────────────────────────────────────────
    widths = [
        9, 18, 38, 7, 9, 10,
        12, 13, 11, 9, 12, 14,
        12, 12, 13, 13, 11, 10,
        13, 14, 13, 14,
        16, 16, 17,
        12, 10, 9, 10, 10, 13, 15,
    ]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ── Row heights ───────────────────────────────────────────
    ws.row_dimensions[1].height = 22
    ws.row_dimensions[2].height = 28
    ws.row_dimensions[3].height = 34

    # ── Data rows ─────────────────────────────────────────────
    mr = matrix_rules = None  # alias per row

    for r, line in enumerate(lines, start=4):
        ws.row_dimensions[r].height = 16
        mr = line.matrix_rules

        # price per unit: if regular_price_per_piece is set use it,
        # else derive from box price / units_per_box
        price_piece = line.regular_price_per_piece or (
            line.regular_price_per_box / line.units_per_box
            if line.units_per_box else 0.0
        )
        price_box = line.regular_price_per_box or line.base_price

        # Итоговая цена за короб с учётом скидки
        price_after_disc = price_box * (1 - line.discount_percent / 100) if line.discount_percent else price_box

        # Итоговая сумма строки
        line_sum = line.qty * price_after_disc if line.qty else 0.0

        # Паллеты
        pallets = (line.qty / line.boxes_per_pallet) if line.boxes_per_pallet and line.qty else 0.0

        row_values = [
            # A–L  базовые
            (1,  line.external_id),
            (2,  line.box_barcode),
            (3,  line.name),
            (4,  line.unit),
            (5,  line.qty if line.qty else None),
            (6,  line.units_per_box if line.units_per_box else None),
            (7,  round(price_piece, 4) if price_piece else None),
            (8,  round(price_box, 4) if price_box else None),
            (9,  line.boxes_per_pallet if line.boxes_per_pallet else None),
            (10, line.discount_percent if line.discount_percent else None),
            (11, round(price_after_disc, 4) if price_after_disc else None),
            (12, round(line_sum, 2) if line_sum else None),
            # M–R  скидки
            (13, mr.get("prepay_25", None)),
            (14, mr.get("prepay_50", None)),
            (15, mr.get("volume_300", None)),
            (16, mr.get("volume_500", None)),
            (17, mr.get("expiry_pct", None)),
            (18, mr.get("expiry_rub", None)),
            # S–V  акции
            (19, mr.get("promo_15_2_qty", None)),
            (20, mr.get("promo_15_2_ids", None)),
            (21, mr.get("promo_10_3_qty", None)),
            (22, mr.get("promo_10_3_ids", None)),
            # W–Y  итоги
            (23, round(line.qty * price_box, 2) if line.qty and price_box else None),
            (24, round(line_sum, 2) if line_sum else None),
            (25, None),   # акция+мот — рассчитывается вручную / доп логикой
            # Z–AF  логистика
            (26, round(line.gross_weight_kg * line.qty, 3) if line.gross_weight_kg and line.qty else None),
            (27, round(line.volume_m3 * line.qty, 4) if line.volume_m3 and line.qty else None),
            (28, round(pallets, 2) if pallets else None),
            (29, None),   # коробов в ряде — нет в RusLine
            (30, None),   # рядов в паллете — нет в RusLine
            (31, None),   # высота с паллетой — нет в RusLine
            (32, None),   # размер короба — нет в RusLine
        ]

        for col_num, val in row_values:
            c = ws.cell(row=r, column=col_num, value=val)
            c.font = _font(size=9)
            c.border = _BORDER

            if col_num <= 12:
                c.fill = _fill(_C_WHITE)
                c.alignment = _align(h="left" if col_num == 3 else "center", wrap=False)
            elif col_num <= 18:
                c.fill = _fill("FFFDE7")
                c.alignment = _align(h="center", wrap=False)
            elif col_num <= 22:
                c.fill = _fill("F1F8E9")
                c.alignment = _align(h="center", wrap=False)
            elif col_num <= 25:
                c.fill = _fill(_C_TOTAL_DATA)
                c.alignment = _align(h="right", wrap=False)
                c.font = _font(size=9, bold=True)
            else:
                c.fill = _fill("FAFAFA")
                c.alignment = _align(h="center", wrap=False)

    # ── Legend ────────────────────────────────────────────────
    legend_row = max(4 + len(lines), 5) + 1
    ws.merge_cells(f"A{legend_row}:AF{legend_row}")
    lc = ws[f"A{legend_row}"]
    lc.value = (
        "ЛЕГЕНДА:  "
        "Предоплата −2% (до 25%) / −5% (до 50%)  |  "
        "Объём −6% (> 300 кор) / −8% (> 500 кор)  |  "
        "Продуктовая: скидка по сроку годности  |  "
        "Акция 15+2 (КОФЕ): купи 15 кор — получи 2 бесплатно  |  "
        "Акция 10+3 (КОНФ): купи 10 кор — получи 3 бесплатно"
    )
    lc.font = Font(name=FONT_NAME, size=8, italic=True, color="595959")
    lc.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws.row_dimensions[legend_row].height = 22

    # ── Freeze panes ──────────────────────────────────────────
    ws.freeze_panes = "E4"


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def export_rus_variant_a(
    path: Path,
    *,
    client,
    quote_date: date,
    lines: list[RusLine],
) -> None:
    wb = Workbook()

    ws_client = wb.active
    _build_client_sheet(ws_client, client, quote_date)

    ws_order = wb.create_sheet("ORDER")
    _build_order_sheet(ws_order, lines)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)