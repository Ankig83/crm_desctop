from __future__ import annotations

import sqlite3

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from crm_desktop.repositories import audit, products, promotions
from crm_desktop.utils.dates import format_dmY, iso, parse_dmY, parse_iso


class PromotionsTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._loading = False
        self._current_product_id: int | None = None

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)

        self._product = QComboBox()
        self._ptype = QLineEdit()
        self._ptype.setPlaceholderText("Тип акции (по ТЗ)")
        self._disc = QLineEdit()
        self._disc.setPlaceholderText("Процент, например 10")
        self._d1 = QDateEdit()
        self._d2 = QDateEdit()
        for d in (self._d1, self._d2):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd.MM.yyyy")
            d.setDate(QDate.currentDate())

        btn_save = QPushButton("Сохранить акцию для выбранного товара")
        btn_save.clicked.connect(self._save)
        btn_new = QPushButton("Новая акция (выберите товар)")
        btn_new.clicked.connect(self._new_promo)
        btn_del = QPushButton("Удалить акцию")
        btn_del.clicked.connect(self._delete)

        form = QFormLayout()
        form.addRow("Товар:", self._product)
        form.addRow("Тип акции:", self._ptype)
        form.addRow("Скидка %:", self._disc)
        form.addRow("Дата начала:", self._d1)
        form.addRow("Дата окончания:", self._d2)
        btns = QHBoxLayout()
        btns.addWidget(btn_save)
        btns.addWidget(btn_new)
        btns.addWidget(btn_del)

        right = QVBoxLayout()
        right.addWidget(QLabel("Редактирование акции"))
        right.addLayout(form)
        right.addLayout(btns)
        right.addStretch()
        rw = QWidget()
        rw.setLayout(right)

        split = QSplitter()
        split.addWidget(self._list)
        split.addWidget(rw)
        split.setStretchFactor(1, 1)

        lay = QVBoxLayout(self)
        lay.addWidget(split)
        self.reload()

    def reload(self) -> None:
        self._fill_product_combo(None)
        self._list.clear()
        for r in promotions.list_all(self._conn):
            label = f"{r.product_name} — {r.discount_percent}% ({format_dmY(parse_iso(r.valid_from_iso))}—{format_dmY(parse_iso(r.valid_to_iso))})"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, r.product_id)
            self._list.addItem(it)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _fill_product_combo(self, select_pid: int | None) -> None:
        self._product.clear()
        for p in products.list_all(self._conn):
            label = f"{p.name} ({p.external_id or 'без ID'})"
            self._product.addItem(label, p.id)
        if select_pid is not None:
            idx = self._product.findData(select_pid)
            if idx >= 0:
                self._product.setCurrentIndex(idx)

    def _on_select(self, row: int) -> None:
        if self._loading:
            return
        if row < 0:
            self._current_product_id = None
            return
        it = self._list.item(row)
        if not it:
            return
        pid = it.data(Qt.ItemDataRole.UserRole)
        self._current_product_id = int(pid) if pid is not None else None
        self._load_promo(self._current_product_id)

    def _load_promo(self, product_id: int | None) -> None:
        self._loading = True
        self._fill_product_combo(product_id)
        if product_id is None:
            self._loading = False
            return
        pr = promotions.get_for_product(self._conn, product_id)
        if pr:
            self._ptype.setText(pr.promo_type)
            self._disc.setText(str(pr.discount_percent))
            d1 = parse_iso(pr.valid_from_iso)
            d2 = parse_iso(pr.valid_to_iso)
            self._d1.setDate(QDate(d1.year, d1.month, d1.day))
            self._d2.setDate(QDate(d2.year, d2.month, d2.day))
        else:
            self._ptype.clear()
            self._disc.clear()
            self._d1.setDate(QDate.currentDate())
            self._d2.setDate(QDate.currentDate())
        self._loading = False

    def _save(self) -> None:
        if self._loading:
            return
        pid = self._product.currentData()
        if pid is None:
            return
        product_id = int(pid)
        try:
            disc = float(self._disc.text().strip().replace(",", "."))
        except ValueError:
            QMessageBox.warning(self, "Скидка", "Укажите число процента.")
            return
        q1 = self._d1.date()
        q2 = self._d2.date()
        d1 = parse_dmY(f"{q1.day():02d}.{q1.month():02d}.{q1.year():04d}")
        d2 = parse_dmY(f"{q2.day():02d}.{q2.month():02d}.{q2.year():04d}")
        if d1 > d2:
            QMessageBox.warning(self, "Период", "Дата начала не может быть позже окончания.")
            return
        promotions.upsert(
            self._conn,
            product_id,
            promo_type=self._ptype.text().strip(),
            discount_percent=disc,
            valid_from_iso=iso(d1),
            valid_to_iso=iso(d2),
        )
        audit.log(self._conn, "upsert", "promotion", str(product_id))
        self._reload_list_only()

    def _reload_list_only(self) -> None:
        cur_pid = self._current_product_id
        self._loading = True
        self._list.clear()
        for r in promotions.list_all(self._conn):
            label = f"{r.product_name} — {r.discount_percent}% ({format_dmY(parse_iso(r.valid_from_iso))}—{format_dmY(parse_iso(r.valid_to_iso))})"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, r.product_id)
            self._list.addItem(it)
        self._loading = False
        if cur_pid is not None:
            for i in range(self._list.count()):
                it = self._list.item(i)
                if it and it.data(Qt.ItemDataRole.UserRole) == cur_pid:
                    self._list.setCurrentRow(i)
                    break

    def _new_promo(self) -> None:
        self._loading = True
        self._list.clearSelection()
        self._current_product_id = None
        self._fill_product_combo(None)
        if self._product.count():
            self._product.setCurrentIndex(0)
        self._ptype.clear()
        self._disc.clear()
        self._d1.setDate(QDate.currentDate())
        self._d2.setDate(QDate.currentDate())
        self._loading = False

    def _delete(self) -> None:
        pid = self._product.currentData()
        if pid is None:
            return
        product_id = int(pid)
        if QMessageBox.question(self, "Удалить", "Удалить акцию для этого товара?") != QMessageBox.StandardButton.Yes:
            return
        promotions.delete_for_product(self._conn, product_id)
        audit.log(self._conn, "delete", "promotion", str(product_id))
        self.reload()
