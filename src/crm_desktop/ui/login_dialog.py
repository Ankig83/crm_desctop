from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crm_desktop.repositories import users


class LoginDialog(QDialog):
    """Диалог входа. Менеджер выбирает имя и входит без пароля.
    Администратор вводит пароль. После accept() читать .user_name и .role."""

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self.user_name: str = ""
        self.role: str = "manager"

        self.setWindowTitle("Вход в CRM")
        self.setFixedWidth(380)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

        lay = QVBoxLayout(self)
        lay.setSpacing(14)

        title = QLabel("CRM — вход в систему")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(self._on_user_changed)
        form.addRow("Пользователь:", self._combo)

        self._pwd_label = QLabel("Пароль:")
        self._pwd = QLineEdit()
        self._pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._pwd.setPlaceholderText("Пароль администратора")
        self._pwd.returnPressed.connect(self._do_login)
        form.addRow(self._pwd_label, self._pwd)

        lay.addLayout(form)

        self._err = QLabel("")
        self._err.setStyleSheet("color:#c0392b; font-style:italic;")
        self._err.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._err.hide()
        lay.addWidget(self._err)

        btn_ok = QPushButton("Войти")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._do_login)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        box = QDialogButtonBox()
        box.addButton(btn_ok, QDialogButtonBox.ButtonRole.AcceptRole)
        box.addButton(btn_cancel, QDialogButtonBox.ButtonRole.RejectRole)
        lay.addWidget(box)

        self._load_users()

    def _load_users(self) -> None:
        self._combo.clear()
        for u in users.list_all(self._conn):
            tag = " [адм.]" if u.is_admin else ""
            self._combo.addItem(f"{u.name}{tag}", u)
        self._on_user_changed(0)

    def _on_user_changed(self, _: int) -> None:
        u = self._combo.currentData()
        is_admin = isinstance(u, users.User) and u.is_admin
        self._pwd_label.setVisible(is_admin)
        self._pwd.setVisible(is_admin)
        self._pwd.clear()
        self._err.hide()

    def _do_login(self) -> None:
        u = self._combo.currentData()
        if not isinstance(u, users.User):
            self._show_err("Выберите пользователя.")
            return
        if u.is_admin:
            if not users.check_password(u, self._pwd.text()):
                self._show_err("Неверный пароль.")
                self._pwd.clear()
                self._pwd.setFocus()
                return
        self.user_name = u.name
        self.role = u.role
        self.accept()

    def _show_err(self, msg: str) -> None:
        self._err.setText(msg)
        self._err.show()
