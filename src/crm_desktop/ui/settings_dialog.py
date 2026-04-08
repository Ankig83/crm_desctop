from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from crm_desktop.repositories import audit, settings as settings_repo
from crm_desktop.ui.app_theme import THEME_KEY, apply_theme, get_stored_theme


class SettingsDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("Настройки")
        self._host = QLineEdit()
        self._port = QLineEdit()
        self._user = QLineEdit()
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._from = QLineEdit()
        self._tls = QCheckBox("TLS (STARTTLS)")
        self._tls.setChecked(True)

        self._host.setText(settings_repo.get(conn, "smtp_host", "") or "")
        self._port.setText(settings_repo.get(conn, "smtp_port", "587") or "587")
        self._user.setText(settings_repo.get(conn, "smtp_user", "") or "")
        self._password.setText(settings_repo.get(conn, "smtp_password", "") or "")
        self._from.setText(settings_repo.get(conn, "smtp_from", "") or "")
        tls = settings_repo.get(conn, "smtp_use_tls", "1")
        self._tls.setChecked((tls or "1").lower() in ("1", "true", "yes"))

        self._theme = QComboBox()
        self._theme.addItem("Тёмная", "dark")
        self._theme.addItem("Светлая (как в iOS)", "light")
        cur = get_stored_theme(conn)
        idx = self._theme.findData(cur)
        if idx >= 0:
            self._theme.setCurrentIndex(idx)

        gb_mail = QGroupBox("Почта (SMTP)")
        form = QFormLayout(gb_mail)
        form.addRow("Сервер:", self._host)
        form.addRow("Порт:", self._port)
        form.addRow("Логин:", self._user)
        form.addRow("Пароль:", self._password)
        form.addRow("От кого (email):", self._from)
        form.addRow(self._tls)

        gb_ui = QGroupBox("Оформление")
        form_ui = QFormLayout(gb_ui)
        form_ui.addRow("Тема интерфейса:", self._theme)
        hint = QLabel("Светлая тема: белые панели на мягком фоне (#F2F2F7).")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid); font-size: 9pt;")
        form_ui.addRow(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(gb_ui)
        lay.addWidget(gb_mail)
        lay.addWidget(buttons)

    def _save(self) -> None:
        settings_repo.set_value(self._conn, "smtp_host", self._host.text().strip())
        settings_repo.set_value(self._conn, "smtp_port", self._port.text().strip() or "587")
        settings_repo.set_value(self._conn, "smtp_user", self._user.text().strip())
        settings_repo.set_value(self._conn, "smtp_password", self._password.text())
        settings_repo.set_value(self._conn, "smtp_from", self._from.text().strip())
        settings_repo.set_value(self._conn, "smtp_use_tls", "1" if self._tls.isChecked() else "0")
        t = self._theme.currentData()
        settings_repo.set_value(self._conn, THEME_KEY, t if t in ("dark", "light") else "dark")
        app = QApplication.instance()
        if app:
            apply_theme(app, get_stored_theme(self._conn))
        audit.log(self._conn, "settings", "smtp", "updated")
        self.accept()
