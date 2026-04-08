from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from crm_desktop.adapters.rus_export import RusLine, export_rus_variant_a


def test_rus_export_contains_all_matrix_columns_with_zeros(tmp_path: Path) -> None:
    out = tmp_path / "RUS.xlsx"
    export_rus_variant_a(
        out,
        client=None,
        quote_date=date(2026, 4, 7),
        lines=[
            RusLine(
                external_id="P1",
                box_barcode="",
                name="Товар 1",
                unit="кор",
                qty=1,
                regular_price_per_box=100,
                regular_price_per_piece=10,
                units_per_box=10,
                boxes_per_pallet=20,
                gross_weight_kg=1,
                volume_m3=0.1,
                base_price=100,
                discount_percent=0,
                line_total=100,
                matrix_rules={"Предоплата -2%": "2", "15+2": "1"},
            ),
            RusLine(
                external_id="P2",
                box_barcode="",
                name="Товар 2",
                unit="кор",
                qty=1,
                regular_price_per_box=200,
                regular_price_per_piece=20,
                units_per_box=10,
                boxes_per_pallet=20,
                gross_weight_kg=1,
                volume_m3=0.1,
                base_price=200,
                discount_percent=0,
                line_total=200,
                matrix_rules={"15+2": "1"},
            ),
        ],
    )
    wb = load_workbook(out, data_only=True)
    ws = wb.active
    headers = [ws.cell(row=24, column=i).value for i in range(1, ws.max_column + 1)]
    assert "Предоплата -2%" in headers
    assert "15+2" in headers
    col_prepay = headers.index("Предоплата -2%") + 1
    assert ws.cell(row=25, column=col_prepay).value == "2"
    assert ws.cell(row=26, column=col_prepay).value == 0
