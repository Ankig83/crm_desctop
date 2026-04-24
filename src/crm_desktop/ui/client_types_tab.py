from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
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
from PySide6.QtCore import Qt

from crm_desktop.repositories import client_types


class ClientTypesTab(QWidget):
    """Вкладка «Типы клиентов» (только для администратора).

    Позволяет добавлять, редактировать и удалять типы клиентов
    с указанием скидки в процентах.
    """

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._current_id: int | None = None

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # ── Левая панель: список типов ────────────────────────────────
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.addWidget(QLabel("<b>Типы клиентов</b>"))

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        left_lay.addWidget(self._list)

        btn_new = QPushButton("+ Новый тип")
        btn_del = QPushButton("− Удалить")
        btn_new.clicked.connect(self._new_type)
        btn_del.clicked.connect(self._delete_type)
        btns = QHBoxLayout()
        btns.addWidget(btn_new)
        btns.addWidget(btn_del)
        btns.addStretch()
        left_lay.addLayout(btns)

        splitter.addWidget(left)

        # ── Правая панель: редактирование ─────────────────────────────
        right = QWidget()
        right_lay = QVBoxLayout(right)

        gb = QGroupBox("Параметры типа")
        form = QFormLayout(gb)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Например: Торговая сеть")
        form.addRow("Название:", self._name)

        self._disc = QDoubleSpinBox()
        self._disc.setRange(0, 100)
        self._disc.setDecimals(1)
        self._disc.setSuffix(" %")
        self._disc.setToolTip(
            "Скидка, которая автоматически применяется ко всем клиентам этого типа."
        )
        form.addRow("Скидка:", self._disc)

        right_lay.addWidget(gb)

        info = QLabel(
            "<i>Скидка типа клиента суммируется с другими скидками при расчёте заказа.</i>"
        )
        info.setWordWrap(True)
        right_lay.addWidget(info)

        btn_save = QPushButton("💾  Сохранить")
        btn_save.setFixedHeight(34)
        btn_save.clicked.connect(self._save)
        right_lay.addWidget(btn_save)
        right_lay.addStretch()

        splitter.addWidget(right)
        splitter.setSizes([220, 400])

        root = QVBoxLayout(self)
        root.addWidget(splitter)

        self.reload()

    # ── публичный метод ───────────────────────────────────────────────

    def reload(self) -> None:
        saved_id = self._current_id
        self._list.clear()
        for ct in client_types.list_all(self._conn):
            it = QListWidgetItem(
                f"{ct.name}  (−{ct.discount_pct:.1f}%)" if ct.discount_pct > 0 else ct.name
            )
            it.setData(Qt.ItemDataRole.UserRole, ct.id)
            self._list.addItem(it)

        # Восстанавливаем выбранный тип
        if saved_id is not None:
            for i in range(self._list.count()):
                if self._list.item(i).data(Qt.ItemDataRole.UserRole) == saved_id:
                    self._list.setCurrentRow(i)
                    return
        if self._list.count():
            self._list.setCurrentRow(0)

    # ── внутренние методы ─────────────────────────────────────────────

    def _on_select(self, row: int) -> None:
        if row < 0:
            self._current_id = None
            return
        it = self._list.item(row)
        if not it:
            return
        type_id = it.data(Qt.ItemDataRole.UserRole)
        ct = client_types.get(self._conn, type_id)
        if ct:
            self._current_id = ct.id
            self._name.setText(ct.name)
            self._disc.setValue(ct.discount_pct)

    def _new_type(self) -> None:
        self._current_id = None
        self._name.clear()
        self._disc.setValue(0.0)
        self._list.clearSelection()
        self._name.setFocus()

    def _save(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название типа.")
            self._name.setStyleSheet("border: 2px solid #e74c3c;")
            return
        self._name.setStyleSheet("")
        disc = self._disc.value()

        if self._current_id is None:
            client_types.add(self._conn, name, disc)
        else:
            client_types.update(self._conn, self._current_id, name, disc)

        self.reload()

    def _delete_type(self) -> None:
        if self._current_id is None:
            return
        ans = QMessageBox.question(
            self, "Удаление",
            "Удалить этот тип клиента?\n"
            "Клиенты с этим типом перейдут без типа (скидка 0%).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        client_types.delete(self._conn, self._current_id)
        self._current_id = None
        self.reload()
