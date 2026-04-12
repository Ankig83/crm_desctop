from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crm_desktop.repositories import audit, products


# Колонки: 0=id (скрыта), далее — все поля продукта
_COL_EXT        = 1
_COL_NAME       = 2
_COL_PRICE      = 3
_COL_BARCODE    = 4
_COL_UNIT       = 5
_COL_UNITS_BOX  = 6
_COL_PIECE      = 7
_COL_PALLET     = 8
_COL_WEIGHT     = 9
_COL_VOL        = 10
# ← новые логистические
_COL_BOX_ROW    = 11   # коробов в ряде
_COL_ROWS_PAL   = 12   # рядов в паллете
_COL_PAL_H      = 13   # высота с паллетой (мм)
_COL_BOX_DIM    = 14   # размер короба д*ш*в


class ProductsTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._block = False

        self._table = QTableWidget()
        self._table.setColumnCount(15)
        self._table.setHorizontalHeaderLabels([
            "#",
            "ID товара",
            "Наименование",
            "Базовая цена\n(кор)",
            "Баркод коробки",
            "Ед.",
            "Шт в кор",
            "Цена шт",
            "Кор на паллете",
            "Брутто кг",
            "Объём м³",
            "Кор в ряде",       # ← новое
            "Рядов в пал.",     # ← новое
            "Высота пал. мм",   # ← новое
            "Размер короба\nд*ш*в",  # ← новое
        ])
        self._table.hideColumn(0)
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.horizontalHeader().setDefaultSectionSize(100)
        self._table.setColumnWidth(_COL_NAME, 220)
        self._table.setColumnWidth(_COL_BARCODE, 140)
        self._table.setColumnWidth(_COL_BOX_DIM, 120)
        self._table.cellChanged.connect(self._on_cell_changed)

        btn_add = QPushButton("Добавить товар")
        btn_add.clicked.connect(self._add_row)
        btn_del = QPushButton("Удалить строку")
        btn_del.clicked.connect(self._delete_row)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Поиск по названию или ID товара…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)

        top_row = QHBoxLayout()
        top_row.addWidget(btn_add)
        top_row.addWidget(btn_del)
        top_row.addStretch()

        lay = QVBoxLayout(self)
        lay.addLayout(top_row)
        lay.addWidget(self._search)
        lay.addWidget(self._table)
        self.reload()

    def _apply_filter(self) -> None:
        """Скрывает строки таблицы, не совпадающие с текстом поиска."""
        q = self._search.text().strip().lower()
        for r in range(self._table.rowCount()):
            if q == "":
                self._table.setRowHidden(r, False)
                continue
            name_it = self._table.item(r, _COL_NAME)
            ext_it  = self._table.item(r, _COL_EXT)
            name_txt = name_it.text().lower() if name_it else ""
            ext_txt  = ext_it.text().lower()  if ext_it  else ""
            self._table.setRowHidden(r, q not in name_txt and q not in ext_txt)

    def reload(self) -> None:
        self._block = True
        self._table.setRowCount(0)
        for p in products.list_all(self._conn):
            r = self._table.rowCount()
            self._table.insertRow(r)
            # скрытый id
            id_it = QTableWidgetItem(str(p.id))
            id_it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(r, 0, id_it)
            # основные поля
            self._table.setItem(r, _COL_EXT,       QTableWidgetItem(p.external_id or ""))
            self._table.setItem(r, _COL_NAME,      QTableWidgetItem(p.name))
            self._table.setItem(r, _COL_PRICE,     QTableWidgetItem(str(p.base_price)))
            self._table.setItem(r, _COL_BARCODE,   QTableWidgetItem(p.box_barcode))
            self._table.setItem(r, _COL_UNIT,      QTableWidgetItem(p.unit or "кор"))
            self._table.setItem(r, _COL_UNITS_BOX, QTableWidgetItem(str(p.units_per_box)))
            self._table.setItem(r, _COL_PIECE,     QTableWidgetItem(str(p.regular_piece_price)))
            self._table.setItem(r, _COL_PALLET,    QTableWidgetItem(str(p.boxes_per_pallet)))
            self._table.setItem(r, _COL_WEIGHT,    QTableWidgetItem(str(p.gross_weight_kg)))
            self._table.setItem(r, _COL_VOL,       QTableWidgetItem(str(p.volume_m3)))
            # новые логистические поля
            self._table.setItem(r, _COL_BOX_ROW,   QTableWidgetItem(str(p.boxes_in_row)))
            self._table.setItem(r, _COL_ROWS_PAL,  QTableWidgetItem(str(p.rows_per_pallet)))
            self._table.setItem(r, _COL_PAL_H,     QTableWidgetItem(str(p.pallet_height_mm)))
            self._table.setItem(r, _COL_BOX_DIM,   QTableWidgetItem(p.box_dimensions))
        self._block = False
        self._apply_filter()

    def _row_pid(self, row: int) -> int | None:
        it = self._table.item(row, 0)
        if not it:
            return None
        try:
            return int(it.text())
        except ValueError:
            return None

    def _txt(self, row: int, col: int) -> str:
        it = self._table.item(row, col)
        return it.text().strip() if it else ""

    def _float(self, row: int, col: int, label: str) -> float | None:
        s = self._txt(row, col).replace(",", ".")
        if s == "":
            return 0.0
        try:
            return float(s)
        except ValueError:
            QMessageBox.warning(self, "Число", f"Введите число: «{label}».")
            return None

    def _int(self, row: int, col: int, label: str) -> int | None:
        s = self._txt(row, col)
        if s == "":
            return 0
        try:
            v = int(float(s.replace(",", ".")))
            if v < 0:
                raise ValueError
            return v
        except ValueError:
            QMessageBox.warning(self, "Число", f"Введите целое неотрицательное число: «{label}».")
            return None

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._block or col == 0:
            return
        pid = self._row_pid(row)
        if pid is None:
            return

        ext       = self._txt(row, _COL_EXT) or None
        name      = self._txt(row, _COL_NAME)
        price     = self._float(row, _COL_PRICE, "Базовая цена")
        barcode   = self._txt(row, _COL_BARCODE)
        unit      = self._txt(row, _COL_UNIT) or "кор"

        units_box = self._int(row, _COL_UNITS_BOX, "Шт в кор")
        piece     = self._float(row, _COL_PIECE, "Цена шт")
        pallet    = self._float(row, _COL_PALLET, "Кор на паллете")
        weight    = self._float(row, _COL_WEIGHT, "Брутто кг")
        vol       = self._float(row, _COL_VOL, "Объём м³")
        box_row   = self._int(row, _COL_BOX_ROW, "Кор в ряде")
        rows_pal  = self._int(row, _COL_ROWS_PAL, "Рядов в паллете")
        pal_h     = self._int(row, _COL_PAL_H, "Высота паллеты мм")
        box_dim   = self._txt(row, _COL_BOX_DIM)

        # Если хоть одно обязательное поле не распарсилось — не сохраняем
        if any(v is None for v in (price, units_box, piece, pallet, weight, vol, box_row, rows_pal, pal_h)):
            return

        products.update(
            self._conn, pid,
            external_id=ext,
            name=name,
            base_price=price,
            box_barcode=barcode,
            unit=unit,
            units_per_box=units_box,
            regular_piece_price=piece,
            boxes_per_pallet=pallet,
            gross_weight_kg=weight,
            volume_m3=vol,
            boxes_in_row=box_row,
            rows_per_pallet=rows_pal,
            pallet_height_mm=pal_h,
            box_dimensions=box_dim,
        )

    def _add_row(self) -> None:
        nid = products.insert(self._conn, external_id=None, name="", base_price=0.0)
        audit.log(self._conn, "create", "product", str(nid))
        self.reload()

    def _delete_row(self) -> None:
        r = self._table.currentRow()
        if r < 0:
            return
        pid = self._row_pid(r)
        if pid is None:
            return
        if QMessageBox.question(
            self, "Удалить", "Удалить товар и связанную акцию?"
        ) != QMessageBox.StandardButton.Yes:
            return
        products.delete(self._conn, pid)
        audit.log(self._conn, "delete", "product", str(pid))
        self.reload()