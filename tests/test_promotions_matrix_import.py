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


def test_import_promotions_saves_unknown_columns_as_matrix_json(tmp_path: Path) -> None:
    conn = _conn()
    products.insert(conn, external_id="P-001", name="Товар 1", base_price=100.0)
    wb = Workbook()
    ws = wb.active
    ws.append(
        (
            "ID товара",
            "Тип акции",
            "Размер скидки",
            "Дата начала",
            "Дата окончания",
            "Предоплата -2%",
            "15+2",
        )
    )
    ws.append(("P-001", "Сезон", 10, "01.04.2026", "30.04.2026", "да", "вкл"))
    path = tmp_path / "promo_matrix.xlsx"
    wb.save(path)

    rep = import_promotions(conn, path)
    assert rep.errors == []
    row = promotions.get_for_product(conn, products.by_external_id(conn, "P-001").id)  # type: ignore[union-attr]
    assert row is not None
    assert "предоплата -2%" in row.matrix_rules_json
    assert "15+2" in row.matrix_rules_json
