from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QVBoxLayout,
)

from crm_desktop.repositories import audit, settings as settings_repo


class SettingsDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("Настройки SMTP")
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

        form = QFormLayout()
        form.addRow("Сервер:", self._host)
        form.addRow("Порт:", self._port)
        form.addRow("Логин:", self._user)
        form.addRow("Пароль:", self._password)
        form.addRow("От кого (email):", self._from)
        form.addRow(self._tls)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

    def _save(self) -> None:
        settings_repo.set_value(self._conn, "smtp_host", self._host.text().strip())
        settings_repo.set_value(self._conn, "smtp_port", self._port.text().strip() or "587")
        settings_repo.set_value(self._conn, "smtp_user", self._user.text().strip())
        settings_repo.set_value(self._conn, "smtp_password", self._password.text())
        settings_repo.set_value(self._conn, "smtp_from", self._from.text().strip())
        settings_repo.set_value(self._conn, "smtp_use_tls", "1" if self._tls.isChecked() else "0")
        audit.log(self._conn, "settings", "smtp", "updated")
        self.accept()
