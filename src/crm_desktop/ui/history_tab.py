from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crm_desktop.repositories import calculation_sessions


class HistoryTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._sessions = QListWidget()
        self._sessions.currentRowChanged.connect(self._on_session_select)
        self._lines = QTableWidget()
        self._lines.setColumnCount(5)
        self._lines.setHorizontalHeaderLabels(["ID товара", "Товар", "Кол-во", "Скидка %", "Сумма"])
        self._summary = QLabel("Выберите сохранённый расчёт.")

        right = QVBoxLayout()
        right.addWidget(self._summary)
        right.addWidget(self._lines)
        right_w = QWidget()
        right_w.setLayout(right)

        lay = QHBoxLayout(self)
        lay.addWidget(self._sessions, 2)
        lay.addWidget(right_w, 5)
        self.reload()

    def reload(self) -> None:
        self._sessions.clear()
        self._lines.setRowCount(0)
        self._summary.setText("Выберите сохранённый расчёт.")
        for s in calculation_sessions.list_recent(self._conn):
            qd = s.quote_date or "—"
            client = s.client_name or "—"
            label = f"#{s.id} | {qd} | {client} | {s.total:.2f}"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, s.id)
            self._sessions.addItem(it)
        if self._sessions.count():
            self._sessions.setCurrentRow(0)

    def _on_session_select(self, row: int) -> None:
        self._lines.setRowCount(0)
        if row < 0:
            self._summary.setText("Выберите сохранённый расчёт.")
            return
        it = self._sessions.item(row)
        if not it:
            return
        sid = it.data(Qt.ItemDataRole.UserRole)
        lines = calculation_sessions.list_lines(self._conn, int(sid))
        self._summary.setText(f"Сессия #{sid}, строк: {len(lines)}")
        for ln in lines:
            r = self._lines.rowCount()
            self._lines.insertRow(r)
            self._lines.setItem(r, 0, QTableWidgetItem(ln.product_external_id))
            self._lines.setItem(r, 1, QTableWidgetItem(ln.product_name))
            self._lines.setItem(r, 2, QTableWidgetItem(f"{ln.qty:g}"))
            self._lines.setItem(r, 3, QTableWidgetItem(f"{ln.discount_percent:g}"))
            self._lines.setItem(r, 4, QTableWidgetItem(f"{ln.line_total:.2f}"))
