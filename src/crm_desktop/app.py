from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from crm_desktop.db.database import connect, init_db
from crm_desktop.services.trial import check_trial
from crm_desktop.ui.app_theme import apply_saved_theme
from crm_desktop.ui.login_dialog import LoginDialog
from crm_desktop.ui.main_window import MainWindow


def main() -> None:
    conn = connect()
    init_db(conn)
    app = QApplication(sys.argv)
    app.setApplicationName("CRM Desktop")
    apply_saved_theme(app, conn)

    # ── Проверка пробного периода ──────────────────────────────
    from PySide6.QtWidgets import QMessageBox
    ok, days_left = check_trial(conn)
    if not ok:
        QMessageBox.critical(
            None,
            "Срок действия истёк",
            "Пробный период программы завершён.\n\n"
            "Для продолжения работы обратитесь к разработчику.",
        )
        raise SystemExit(1)

    login = LoginDialog(conn)
    if login.exec() != LoginDialog.DialogCode.Accepted:
        raise SystemExit(0)

    from crm_desktop.repositories import users as users_repo
    u = users_repo.get_by_name(conn, login.user_name)
    user_id = u.id if u else None

    w = MainWindow(conn, role=login.role, user_name=login.user_name, user_id=user_id)
    w.show()
    raise SystemExit(app.exec())
