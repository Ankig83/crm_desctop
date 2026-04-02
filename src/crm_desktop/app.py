from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from crm_desktop.db.database import connect, init_db
from crm_desktop.ui.main_window import MainWindow


def main() -> None:
    conn = connect()
    init_db(conn)
    app = QApplication(sys.argv)
    app.setApplicationName("CRM Desktop")
    w = MainWindow(conn)
    w.show()
    raise SystemExit(app.exec())
