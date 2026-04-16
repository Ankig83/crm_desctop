from __future__ import annotations

import json
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
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

from crm_desktop.repositories import audit, products, promotions
from crm_desktop.utils.dates import format_dmY, parse_iso


# Колонки: 0=id (скрыта), далее — все поля продукта
# Порядок: Артикул → Баркод → Наименование → Ед. → Цена шт → Шт в кор → Базовая цена (авто)
_COL_EXT        = 1
_COL_BARCODE    = 2
_COL_NAME       = 3
_COL_UNIT       = 4
_COL_PIECE      = 5
_COL_UNITS_BOX  = 6
_COL_PRICE      = 7   # вычисляется автоматически: Цена шт × Шт в кор
_COL_PALLET     = 8
_COL_WEIGHT     = 9
_COL_VOL        = 10
_COL_BOX_ROW    = 11
_COL_ROWS_PAL   = 12
_COL_PAL_H      = 13
_COL_BOX_DIM    = 14


class ProductsTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._block = False

        self._table = QTableWidget()
        self._table.setColumnCount(15)
        self._table.setHorizontalHeaderLabels([
            "#",
            "Артикул",
            "Баркод коробки",
            "Наименование",
            "Ед. изм.",
            "Цена за штуку",
            "Штук в коробке",
            "Базовая цена\n(кор, авто)",
            "Кор на паллете",
            "Брутто кг",
            "Объём м³",
            "Кор в ряде",
            "Рядов в пал.",
            "Высота пал. мм",
            "Размер короба\nд*ш*в",
        ])
        self._table.hideColumn(0)
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.horizontalHeader().setDefaultSectionSize(100)
        self._table.setColumnWidth(_COL_NAME, 220)
        self._table.setColumnWidth(_COL_BARCODE, 140)
        self._table.setColumnWidth(_COL_BOX_DIM, 120)
        self._table.cellChanged.connect(self._on_cell_changed)
        self._table.currentItemChanged.connect(self._on_selection_changed)

        btn_add = QPushButton("Добавить товар")
        btn_add.clicked.connect(self._add_row)
        btn_del = QPushButton("Удалить строку")
        btn_del.clicked.connect(self._delete_row)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Поиск по названию или артикулу…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)

        # ── Панель «Акция для товара» ────────────────────────
        self._promo_frame = QFrame()
        self._promo_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._promo_frame.setStyleSheet(
            "QFrame { background: #EBF5FB; border: 1px solid #AED6F1; border-radius: 4px; }"
        )
        self._promo_label = QLabel("Выберите товар — здесь отобразятся его акции и скидки.")
        self._promo_label.setWordWrap(True)
        self._promo_label.setContentsMargins(8, 6, 8, 6)
        promo_frame_lay = QVBoxLayout(self._promo_frame)
        promo_frame_lay.setContentsMargins(0, 0, 0, 0)
        promo_frame_lay.addWidget(self._promo_label)

        top_row = QHBoxLayout()
        top_row.addWidget(btn_add)
        top_row.addWidget(btn_del)
        top_row.addStretch()

        lay = QVBoxLayout(self)
        lay.addLayout(top_row)
        lay.addWidget(self._search)
        lay.addWidget(self._table)
        lay.addWidget(self._promo_frame)
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

    def _make_auto_item(self, value: str) -> QTableWidgetItem:
        """Нередактируемая ячейка для автовычисляемых значений."""
        it = QTableWidgetItem(value)
        it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        it.setForeground(Qt.GlobalColor.darkGray)
        return it

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
            # поля в новом порядке
            self._table.setItem(r, _COL_EXT,       QTableWidgetItem(p.external_id or ""))
            self._table.setItem(r, _COL_BARCODE,   QTableWidgetItem(p.box_barcode))
            self._table.setItem(r, _COL_NAME,      QTableWidgetItem(p.name))
            self._table.setItem(r, _COL_UNIT,      QTableWidgetItem(p.unit or "кор"))
            self._table.setItem(r, _COL_PIECE,     QTableWidgetItem(str(p.regular_piece_price)))
            self._table.setItem(r, _COL_UNITS_BOX, QTableWidgetItem(str(p.units_per_box)))
            # базовая цена коробки — автовычисление
            auto_price = round(p.regular_piece_price * p.units_per_box, 2)
            self._table.setItem(r, _COL_PRICE, self._make_auto_item(str(auto_price)))
            # логистические поля
            self._table.setItem(r, _COL_PALLET,    QTableWidgetItem(str(p.boxes_per_pallet)))
            self._table.setItem(r, _COL_WEIGHT,    QTableWidgetItem(str(p.gross_weight_kg)))
            self._table.setItem(r, _COL_VOL,       QTableWidgetItem(str(p.volume_m3)))
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
        # Колонка цены — только для чтения, изменения игнорируем
        if col == _COL_PRICE:
            return
        pid = self._row_pid(row)
        if pid is None:
            return

        ext       = self._txt(row, _COL_EXT) or None
        name      = self._txt(row, _COL_NAME)
        barcode   = self._txt(row, _COL_BARCODE)
        unit      = self._txt(row, _COL_UNIT) or "кор"

        units_box = self._int(row, _COL_UNITS_BOX, "Штук в коробке")
        piece     = self._float(row, _COL_PIECE, "Цена за штуку")
        pallet    = self._float(row, _COL_PALLET, "Кор на паллете")
        weight    = self._float(row, _COL_WEIGHT, "Брутто кг")
        vol       = self._float(row, _COL_VOL, "Объём м³")
        box_row   = self._int(row, _COL_BOX_ROW, "Кор в ряде")
        rows_pal  = self._int(row, _COL_ROWS_PAL, "Рядов в паллете")
        pal_h     = self._int(row, _COL_PAL_H, "Высота паллеты мм")
        box_dim   = self._txt(row, _COL_BOX_DIM)

        if any(v is None for v in (units_box, piece, pallet, weight, vol, box_row, rows_pal, pal_h)):
            return

        # Базовая цена коробки вычисляется автоматически
        auto_price = round((piece or 0.0) * (units_box or 0), 2)

        # Обновляем отображение автовычисленной цены
        if col in (_COL_PIECE, _COL_UNITS_BOX):
            self._block = True
            self._table.setItem(row, _COL_PRICE, self._make_auto_item(str(auto_price)))
            self._block = False

        products.update(
            self._conn, pid,
            external_id=ext,
            name=name,
            base_price=auto_price,
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

    # ── Панель акции ─────────────────────────────────────────

    def _on_selection_changed(self) -> None:
        r = self._table.currentRow()
        if r < 0:
            self._promo_label.setText("Выберите товар — здесь отобразятся его акции и скидки.")
            return
        pid = self._row_pid(r)
        if pid is None:
            return
        self._show_promo_info(pid)

    def _show_promo_info(self, pid: int) -> None:
        promo = promotions.get_for_product(self._conn, pid)
        if not promo:
            self._promo_label.setText("Для этого товара акций не настроено.")
            return

        lines = []

        # Базовая скидка и период
        d1 = parse_iso(promo.valid_from_iso)
        d2 = parse_iso(promo.valid_to_iso)
        period = f"{format_dmY(d1)} — {format_dmY(d2)}" if d1 and d2 else "период не задан"
        if promo.discount_percent and float(promo.discount_percent) > 0:
            lines.append(f"Скидка: {promo.discount_percent}%  |  Период: {period}")
        else:
            lines.append(f"Период: {period}")

        # matrix_rules
        mr: dict = {}
        if promo.matrix_rules_json:
            try:
                mr = json.loads(promo.matrix_rules_json)
            except Exception:  # noqa: BLE001
                pass

        # Продуктовая скидка
        epct = float(mr.get("expiry_pct", 0) or 0)
        erub = float(mr.get("expiry_rub", 0) or 0)
        if epct > 0 or erub > 0:
            parts = []
            if epct > 0:
                parts.append(f"{epct:.1f}%")
            if erub > 0:
                parts.append(f"срок годности {erub:.1f}%")
            lines.append("Продуктовая скидка: " + " + ".join(parts))

        # Предоплата
        prepay_parts = []
        for k, v in sorted(mr.items()):
            if k.startswith("prepay_"):
                try:
                    thr = int(k.split("_")[1])
                    prepay_parts.append(f"≥{thr}% → −{v}%")
                except (ValueError, IndexError):
                    pass
        if prepay_parts:
            lines.append("Предоплата: " + ", ".join(prepay_parts))

        # Объём
        vol_parts = []
        for k, v in sorted(mr.items()):
            if k.startswith("volume_"):
                try:
                    thr = int(k.split("_")[1])
                    vol_parts.append(f"≥{thr} кор → −{v}%")
                except (ValueError, IndexError):
                    pass
        if vol_parts:
            lines.append("Скидка за объём: " + ", ".join(vol_parts))

        # Бонусные правила (новый формат)
        if "bonus_rules" in mr:
            try:
                bonus_list = json.loads(str(mr["bonus_rules"]))
                for rule in bonus_list:
                    thr = rule.get("threshold", 0)
                    same = int(rule.get("same_qty", 0))
                    fid  = str(rule.get("fixed_id", "")).strip()
                    fqty = int(rule.get("fixed_qty", 1))
                    cids = str(rule.get("choice_ids", "")).strip()
                    bonus_parts = []
                    if same > 0:
                        bonus_parts.append(f"+{same} кор того же")
                    if fid:
                        bonus_parts.append(f"+{fqty} кор [{fid}] (фикс.)")
                    if cids:
                        bonus_parts.append(f"+1 на выбор из [{cids}]")
                    if bonus_parts:
                        lines.append(f"Бонус при ≥{thr} кор: " + "; ".join(bonus_parts))
            except Exception:  # noqa: BLE001
                pass
        else:
            # Старый формат promo_*_qty
            bonus_names = sorted(
                k[len("promo_"):-len("_qty")]
                for k in mr if k.startswith("promo_") and k.endswith("_qty")
            )
            for name in bonus_names:
                try:
                    thr = name.split("_")[0]
                    same = int(float(mr.get(f"promo_{name}_qty", 0) or 0))
                    ids  = str(mr.get(f"promo_{name}_ids", "") or "")
                    bonus_parts = []
                    if same > 0:
                        bonus_parts.append(f"+{same} кор того же")
                    if ids:
                        bonus_parts.append(f"+1 на выбор из [{ids}]")
                    if bonus_parts:
                        lines.append(f"Бонус при ≥{thr} кор: " + "; ".join(bonus_parts))
                except Exception:  # noqa: BLE001
                    pass

        self._promo_label.setText("  |  ".join(lines) if lines else "Акция задана, но правила пусты.")