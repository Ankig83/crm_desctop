from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crm_desktop.repositories import audit, products


# Колонки: 0=id (скрыта), далее — поля для RUS / каталога
_COL_EXT = 1
_COL_NAME = 2
_COL_PRICE = 3
_COL_BARCODE = 4
_COL_UNIT = 5
_COL_UNITS_BOX = 6
_COL_PIECE = 7
_COL_PALLET = 8
_COL_WEIGHT = 9
_COL_VOL = 10


class ProductsTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._block = False
        self._table = QTableWidget()
        self._table.setColumnCount(11)
        self._table.setHorizontalHeaderLabels(
            [
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
            ]
        )
        self._table.hideColumn(0)
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.cellChanged.connect(self._on_cell_changed)

        btn_add = QPushButton("Добавить товар")
        btn_add.clicked.connect(self._add_row)
        btn_del = QPushButton("Удалить строку")
        btn_del.clicked.connect(self._delete_row)

        row = QHBoxLayout()
        row.addWidget(btn_add)
        row.addWidget(btn_del)
        row.addStretch()

        lay = QVBoxLayout(self)
        lay.addLayout(row)
        lay.addWidget(self._table)
        self.reload()

    def reload(self) -> None:
        self._block = True
        self._table.setRowCount(0)
        for p in products.list_all(self._conn):
            r = self._table.rowCount()
            self._table.insertRow(r)
            id_it = QTableWidgetItem(str(p.id))
            id_it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(r, 0, id_it)
            self._table.setItem(r, _COL_EXT, QTableWidgetItem(p.external_id or ""))
            self._table.setItem(r, _COL_NAME, QTableWidgetItem(p.name))
            self._table.setItem(r, _COL_PRICE, QTableWidgetItem(str(p.base_price)))
            self._table.setItem(r, _COL_BARCODE, QTableWidgetItem(p.box_barcode))
            self._table.setItem(r, _COL_UNIT, QTableWidgetItem(p.unit or "кор"))
            self._table.setItem(r, _COL_UNITS_BOX, QTableWidgetItem(str(p.units_per_box)))
            self._table.setItem(r, _COL_PIECE, QTableWidgetItem(str(p.regular_piece_price)))
            self._table.setItem(r, _COL_PALLET, QTableWidgetItem(str(p.boxes_per_pallet)))
            self._table.setItem(r, _COL_WEIGHT, QTableWidgetItem(str(p.gross_weight_kg)))
            self._table.setItem(r, _COL_VOL, QTableWidgetItem(str(p.volume_m3)))
        self._block = False

    def _row_pid(self, row: int) -> int | None:
        it = self._table.item(row, 0)
        if not it:
            return None
        try:
            return int(it.text())
        except ValueError:
            return None

    def _item_txt(self, row: int, col: int) -> str:
        it = self._table.item(row, col)
        return it.text().strip() if it else ""

    def _parse_float(self, row: int, col: int, field_label: str) -> float | None:
        s = self._item_txt(row, col).replace(",", ".")
        if s == "":
            return 0.0
        try:
            return float(s)
        except ValueError:
            QMessageBox.warning(self, "Число", f"Введите число: «{field_label}».")
            return None

    def _parse_int_nonneg(self, row: int, col: int, field_label: str) -> int | None:
        s = self._item_txt(row, col)
        if s == "":
            return 0
        try:
            v = int(float(s.replace(",", ".")))
            if v < 0:
                raise ValueError
            return v
        except ValueError:
            QMessageBox.warning(self, "Число", f"Введите целое неотрицательное число: «{field_label}».")
            return None

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._block or col == 0:
            return
        pid = self._row_pid(row)
        if pid is None:
            return
        ext = self._item_txt(row, _COL_EXT) or None
        name = self._item_txt(row, _COL_NAME)
        price = self._parse_float(row, _COL_PRICE, "Базовая цена")
        if price is None:
            return
        barcode = self._item_txt(row, _COL_BARCODE)
        unit = self._item_txt(row, _COL_UNIT) or "кор"
        units_box = self._parse_int_nonneg(row, _COL_UNITS_BOX, "Шт в кор")
        if units_box is None:
            return
        piece = self._parse_float(row, _COL_PIECE, "Цена шт")
        if piece is None:
            return
        pallet = self._parse_float(row, _COL_PALLET, "Кор на паллете")
        if pallet is None:
            return
        weight = self._parse_float(row, _COL_WEIGHT, "Брутто кг")
        if weight is None:
            return
        vol = self._parse_float(row, _COL_VOL, "Объём м³")
        if vol is None:
            return
        products.update(
            self._conn,
            pid,
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
        if QMessageBox.question(self, "Удалить", "Удалить товар и связанную акцию?") != QMessageBox.StandardButton.Yes:
            return
        products.delete(self._conn, pid)
        audit.log(self._conn, "delete", "product", str(pid))
        self.reload()
