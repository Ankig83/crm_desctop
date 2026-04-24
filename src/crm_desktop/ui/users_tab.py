from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
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

from crm_desktop.repositories import users


class UsersTab(QWidget):
    """Вкладка управления пользователями (только для администратора).

    Позволяет добавлять менеджеров, менять пароль администратора,
    удалять пользователей.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        current_user_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._current_user_name = current_user_name
        self._selected_id: int | None = None

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # ── Левая панель: список пользователей ───────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel("<b>Пользователи</b>"))

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        ll.addWidget(self._list)

        btn_new = QPushButton("+ Новый менеджер")
        btn_del = QPushButton("− Удалить")
        btn_new.clicked.connect(self._new_user)
        btn_del.clicked.connect(self._delete_user)
        row = QHBoxLayout()
        row.addWidget(btn_new)
        row.addWidget(btn_del)
        row.addStretch()
        ll.addLayout(row)
        splitter.addWidget(left)

        # ── Правая панель: редактирование ────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)

        gb = QGroupBox("Данные пользователя")
        form = QFormLayout(gb)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Имя, отображаемое при входе")
        form.addRow("Имя:", self._name_edit)

        self._is_admin = QCheckBox("Администратор")
        self._is_admin.setToolTip(
            "Администратор имеет полный доступ: редактирование товаров, "
            "акций, скидок, типов клиентов и пользователей."
        )
        form.addRow("Роль:", self._is_admin)

        rl.addWidget(gb)

        gb_pwd = QGroupBox("Пароль")
        pwd_form = QFormLayout(gb_pwd)

        self._pwd1 = QLineEdit()
        self._pwd1.setEchoMode(QLineEdit.EchoMode.Password)
        self._pwd1.setPlaceholderText("Новый пароль (оставьте пустым, чтобы не менять)")
        pwd_form.addRow("Пароль:", self._pwd1)

        self._pwd2 = QLineEdit()
        self._pwd2.setEchoMode(QLineEdit.EchoMode.Password)
        self._pwd2.setPlaceholderText("Повторите пароль")
        pwd_form.addRow("Повтор:", self._pwd2)

        pwd_hint = QLabel(
            "<i>Менеджеры входят без пароля — поле можно оставить пустым.<br>"
            "Для администратора пароль обязателен.</i>"
        )
        pwd_hint.setWordWrap(True)
        pwd_form.addRow("", pwd_hint)
        rl.addWidget(gb_pwd)

        btn_save = QPushButton("💾  Сохранить")
        btn_save.setFixedHeight(34)
        btn_save.clicked.connect(self._save)
        rl.addWidget(btn_save)
        rl.addStretch()

        splitter.addWidget(right)
        splitter.setSizes([220, 420])

        root = QVBoxLayout(self)
        root.addWidget(splitter)

        self.reload()

    # ── публичный метод ───────────────────────────────────────────────

    def reload(self) -> None:
        saved = self._selected_id
        self._list.clear()
        for u in users.list_all(self._conn):
            role_tag = " [адм.]" if u.is_admin else " [менеджер]"
            it = QListWidgetItem(f"{u.name}{role_tag}")
            it.setData(Qt.ItemDataRole.UserRole, u.id)
            self._list.addItem(it)
        # Восстанавливаем выделение
        if saved is not None:
            for i in range(self._list.count()):
                if self._list.item(i).data(Qt.ItemDataRole.UserRole) == saved:
                    self._list.setCurrentRow(i)
                    return
        if self._list.count():
            self._list.setCurrentRow(0)

    # ── внутренние методы ─────────────────────────────────────────────

    def _on_select(self, row: int) -> None:
        if row < 0:
            self._selected_id = None
            return
        it = self._list.item(row)
        if not it:
            return
        uid = it.data(Qt.ItemDataRole.UserRole)
        u = next((x for x in users.list_all(self._conn) if x.id == uid), None)
        if u:
            self._selected_id = u.id
            self._name_edit.setText(u.name)
            self._is_admin.setChecked(u.is_admin)
            self._pwd1.clear()
            self._pwd2.clear()

    def _new_user(self) -> None:
        self._selected_id = None
        self._name_edit.clear()
        self._is_admin.setChecked(False)
        self._pwd1.clear()
        self._pwd2.clear()
        self._list.clearSelection()
        self._name_edit.setFocus()

    def _save(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите имя пользователя.")
            return

        role = "admin" if self._is_admin.isChecked() else "manager"
        pwd1 = self._pwd1.text()
        pwd2 = self._pwd2.text()

        if pwd1 or pwd2:
            if pwd1 != pwd2:
                QMessageBox.warning(self, "Ошибка", "Пароли не совпадают.")
                self._pwd2.clear()
                return
            if role == "admin" and len(pwd1) < 4:
                QMessageBox.warning(self, "Ошибка", "Пароль администратора должен быть не менее 4 символов.")
                return
            new_pwd: str | None = pwd1
        else:
            if role == "admin" and self._selected_id is None:
                QMessageBox.warning(self, "Ошибка", "Задайте пароль для нового администратора.")
                return
            new_pwd = None  # не меняем существующий пароль

        if self._selected_id is None:
            users.add(self._conn, name, role, new_pwd or "")
        else:
            users.update(self._conn, self._selected_id, name, role, new_pwd)

        self.reload()

    def _delete_user(self) -> None:
        if self._selected_id is None:
            return
        # Нельзя удалить самого себя
        u = next((x for x in users.list_all(self._conn) if x.id == self._selected_id), None)
        if u and u.name == self._current_user_name:
            QMessageBox.warning(self, "Нельзя", "Нельзя удалить текущего пользователя.")
            return
        # Нельзя удалить последнего администратора
        all_admins = [x for x in users.list_all(self._conn) if x.is_admin]
        if u and u.is_admin and len(all_admins) <= 1:
            QMessageBox.warning(self, "Нельзя", "Нельзя удалить единственного администратора.")
            return
        ans = QMessageBox.question(
            self, "Удаление",
            f"Удалить пользователя «{u.name if u else ''}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        users.delete(self._conn, self._selected_id)
        self._selected_id = None
        self.reload()
