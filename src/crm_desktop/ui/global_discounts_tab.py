from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crm_desktop.repositories import global_discounts


class GlobalDiscountsTab(QWidget):
    """Вкладка «Скидки» (только для администратора).

    Здесь задаются глобальные правила скидок за предоплату и за объём заказа.
    Они применяются ко всему расчёту, независимо от конкретного товара.
    """

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn

        root = QVBoxLayout(self)
        root.setSpacing(16)

        info = QLabel(
            "<b>Глобальные скидки</b> применяются ко всему заказу:<br>"
            "• <b>За предоплату</b> — если клиент вносит предоплату ≥ порога, "
            "применяется указанная скидка.<br>"
            "• <b>За объём</b> — если суммарное кол-во коробок в заказе ≥ порога, "
            "применяется скидка."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        # ── Скидка за предоплату ──────────────────────────────────────
        gb_pre = QGroupBox("Скидки за предоплату")
        pre_lay = QVBoxLayout(gb_pre)
        pre_lay.addWidget(QLabel("Предоплата ≥ (%) → скидка (%)  [пример: 25 → 2]"))

        self._prepay_table = QTableWidget(0, 2)
        self._prepay_table.setHorizontalHeaderLabels(["Предоплата ≥ %", "Скидка %"])
        self._prepay_table.setMaximumHeight(180)
        self._prepay_table.horizontalHeader().setStretchLastSection(True)
        pre_lay.addWidget(self._prepay_table)

        btn_add_pre = QPushButton("+ Порог")
        btn_del_pre = QPushButton("− Удалить")
        btn_add_pre.setMaximumWidth(90)
        btn_del_pre.setMaximumWidth(90)
        btn_add_pre.clicked.connect(lambda: self._add_row(self._prepay_table, "25", "2"))
        btn_del_pre.clicked.connect(lambda: self._del_row(self._prepay_table))
        pre_btns = QHBoxLayout()
        pre_btns.addWidget(btn_add_pre)
        pre_btns.addWidget(btn_del_pre)
        pre_btns.addStretch()
        pre_lay.addLayout(pre_btns)
        root.addWidget(gb_pre)

        # ── Скидка за объём ───────────────────────────────────────────
        gb_vol = QGroupBox("Скидки за объём заказа")
        vol_lay = QVBoxLayout(gb_vol)
        vol_lay.addWidget(QLabel("Коробок в заказе ≥ → скидка (%)  [пример: 300 → 6]"))

        self._volume_table = QTableWidget(0, 2)
        self._volume_table.setHorizontalHeaderLabels(["Коробок ≥", "Скидка %"])
        self._volume_table.setMaximumHeight(180)
        self._volume_table.horizontalHeader().setStretchLastSection(True)
        vol_lay.addWidget(self._volume_table)

        btn_add_vol = QPushButton("+ Порог")
        btn_del_vol = QPushButton("− Удалить")
        btn_add_vol.setMaximumWidth(90)
        btn_del_vol.setMaximumWidth(90)
        btn_add_vol.clicked.connect(lambda: self._add_row(self._volume_table, "300", "6"))
        btn_del_vol.clicked.connect(lambda: self._del_row(self._volume_table))
        vol_btns = QHBoxLayout()
        vol_btns.addWidget(btn_add_vol)
        vol_btns.addWidget(btn_del_vol)
        vol_btns.addStretch()
        vol_lay.addLayout(vol_btns)
        root.addWidget(gb_vol)

        # ── Кнопка сохранения ─────────────────────────────────────────
        btn_save = QPushButton("💾  Сохранить")
        btn_save.setFixedHeight(36)
        btn_save.clicked.connect(self._save)
        root.addWidget(btn_save)
        root.addStretch()

        self.reload()

    # ── публичный метод для MainWindow ────────────────────────────────

    def reload(self) -> None:
        self._load_table(self._prepay_table, "prepay")
        self._load_table(self._volume_table, "volume")

    # ── внутренние методы ─────────────────────────────────────────────

    def _load_table(self, table: QTableWidget, rule_type: str) -> None:
        table.setRowCount(0)
        for rule in global_discounts.list_by_type(self._conn, rule_type):
            r = table.rowCount()
            table.insertRow(r)
            table.setItem(r, 0, QTableWidgetItem(str(int(rule.threshold))))
            table.setItem(r, 1, QTableWidgetItem(str(rule.discount_pct)))

    def _add_row(self, table: QTableWidget, thr: str, disc: str) -> None:
        r = table.rowCount()
        table.insertRow(r)
        table.setItem(r, 0, QTableWidgetItem(thr))
        table.setItem(r, 1, QTableWidgetItem(disc))

    def _del_row(self, table: QTableWidget) -> None:
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)

    def _collect_table(self, table: QTableWidget) -> list[tuple[float, float]] | None:
        rules: list[tuple[float, float]] = []
        for r in range(table.rowCount()):
            thr_it  = table.item(r, 0)
            disc_it = table.item(r, 1)
            thr_s  = thr_it.text().strip()  if thr_it  else ""
            disc_s = disc_it.text().strip() if disc_it else ""
            try:
                thr  = float(thr_s)
                disc = float(disc_s)
                if thr < 0 or disc < 0 or disc > 100:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(
                    self, "Ошибка",
                    f"Строка {r + 1}: введите корректные числа (порог ≥ 0, скидка 0–100)."
                )
                return None
            rules.append((thr, disc))
        return rules

    def _save(self) -> None:
        pre_rules = self._collect_table(self._prepay_table)
        if pre_rules is None:
            return
        vol_rules = self._collect_table(self._volume_table)
        if vol_rules is None:
            return
        global_discounts.set_rules(self._conn, "prepay", pre_rules)
        global_discounts.set_rules(self._conn, "volume", vol_rules)
        QMessageBox.information(self, "Сохранено", "Глобальные скидки сохранены.")
