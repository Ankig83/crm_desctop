from pathlib import Path
import sqlite3

from openpyxl import Workbook

from crm_desktop.adapters.excel_io import import_promotions
from crm_desktop.db.database import init_db
from crm_desktop.repositories import products, promotions


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    return conn


def _write_promotions_file(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(("Прайс заказчика", "", "", "", ""))
    ws.append(("Сформировано автоматически", "", "", "", ""))
    ws.append(("ID товара", "Тип акции", "Размер скидки", "Дата начала", "Дата окончания"))
    ws.append(("P-001", "Сезон", 10, "01.04.2026", "30.04.2026"))
    wb.save(path)


def test_import_promotions_skips_multiline_header(tmp_path: Path) -> None:
    conn = _conn()
    products.insert(conn, external_id="P-001", name="Товар 1", base_price=100.0)
    xlsx_path = tmp_path / "promotions.xlsx"
    _write_promotions_file(xlsx_path)

    rep = import_promotions(conn, xlsx_path)

    assert rep.errors == []
    assert rep.promotions_rows == 1
    rows = promotions.list_all(conn)
    assert len(rows) == 1
    assert rows[0].product_external_id == "P-001"
    assert rows[0].discount_percent == 10.0
