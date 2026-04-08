from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QTabWidget

from crm_desktop.adapters import excel_io
from crm_desktop.repositories import audit
from crm_desktop.services.backup import copy_database_to
from crm_desktop.ui.clients_tab import ClientsTab
from crm_desktop.ui.history_tab import HistoryTab
from crm_desktop.ui.products_tab import ProductsTab
from crm_desktop.ui.promotions_tab import PromotionsTab
from crm_desktop.ui.quote_tab import QuoteTab
from crm_desktop.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__()
        self._conn = conn
        self.setWindowTitle("CRM — клиенты и товары")
        self.resize(1000, 640)

        tabs = QTabWidget()
        self._clients = ClientsTab(conn)
        self._products = ProductsTab(conn)
        self._promotions = PromotionsTab(conn)
        self._quote = QuoteTab(conn)
        self._history = HistoryTab(conn)
        tabs.addTab(self._clients, "Клиенты")
        tabs.addTab(self._products, "Товары")
        tabs.addTab(self._promotions, "Акции")
        tabs.addTab(self._quote, "Расчёт")
        tabs.addTab(self._history, "История")
        tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(tabs)
        self._tabs = tabs

        self._build_menu()

    def _on_tab_changed(self, index: int) -> None:
        w = self._tabs.widget(index)
        if w is self._quote:
            self._quote.reload_clients()
        elif w is self._clients:
            self._clients.reload()
        elif w is self._products:
            self._products.reload()
        elif w is self._promotions:
            self._promotions.reload()
        elif w is self._history:
            self._history.reload()

    def _build_menu(self) -> None:
        bar = self.menuBar()
        m_file = bar.addMenu("Файл")

        a_imp_c = QAction("Импорт клиентов (Excel)…", self)
        a_imp_c.triggered.connect(self._imp_clients)
        m_file.addAction(a_imp_c)

        a_imp_p = QAction("Импорт товаров (Excel)…", self)
        a_imp_p.triggered.connect(self._imp_products)
        m_file.addAction(a_imp_p)

        a_imp_r = QAction("Импорт акций (Excel)…", self)
        a_imp_r.triggered.connect(self._imp_promo)
        m_file.addAction(a_imp_r)

        m_file.addSeparator()

        a_exp_c = QAction("Экспорт клиентов…", self)
        a_exp_c.triggered.connect(self._exp_clients)
        m_file.addAction(a_exp_c)

        a_exp_p = QAction("Экспорт товаров…", self)
        a_exp_p.triggered.connect(self._exp_products)
        m_file.addAction(a_exp_p)

        a_exp_r = QAction("Экспорт акций…", self)
        a_exp_r.triggered.connect(self._exp_promo)
        m_file.addAction(a_exp_r)

        m_file.addSeparator()

        a_backup = QAction("Резервная копия базы…", self)
        a_backup.triggered.connect(self._backup)
        m_file.addAction(a_backup)

        m_file.addSeparator()

        a_set = QAction("Настройки…", self)
        a_set.triggered.connect(self._settings)
        m_file.addAction(a_set)

        a_exit = QAction("Выход", self)
        a_exit.triggered.connect(self.close)
        m_file.addAction(a_exit)

    def _imp_clients(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Клиенты", "", "Excel (*.xlsx)")
        if not path:
            return
        rep = excel_io.import_clients(self._conn, Path(path))
        self._show_import_report(rep)
        self._clients.reload()

    def _imp_products(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Товары", "", "Excel (*.xlsx)")
        if not path:
            return
        rep = excel_io.import_products(self._conn, Path(path))
        self._show_import_report(rep)
        self._products.reload()
        self._promotions.reload()
        self._quote.reload_clients()

    def _imp_promo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Акции", "", "Excel (*.xlsx)")
        if not path:
            return
        rep = excel_io.import_promotions(self._conn, Path(path))
        self._show_import_report(rep)
        self._promotions.reload()

    def _show_import_report(self, rep: excel_io.ImportReport) -> None:
        msg = (
            f"Клиентов: {rep.clients_rows}\nТоваров: {rep.products_rows}\nАкций: {rep.promotions_rows}\n"
        )
        if rep.errors:
            msg += "\nОшибки:\n" + "\n".join(rep.errors[:30])
            if len(rep.errors) > 30:
                msg += f"\n… и ещё {len(rep.errors) - 30}"
            QMessageBox.warning(self, "Импорт", msg)
        else:
            QMessageBox.information(self, "Импорт", msg)

    def _exp_clients(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт клиентов", "clients.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        excel_io.export_clients(self._conn, Path(path))
        QMessageBox.information(self, "Экспорт", "Готово.")

    def _exp_products(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт товаров", "products.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        excel_io.export_products(self._conn, Path(path))
        QMessageBox.information(self, "Экспорт", "Готово.")

    def _exp_promo(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт акций", "promotions.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        excel_io.export_promotions(self._conn, Path(path))
        QMessageBox.information(self, "Экспорт", "Готово.")

    def _backup(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Папка для копии базы")
        if not d:
            return
        p = copy_database_to(Path(d))
        audit.log(self._conn, "backup", "db", str(p))
        QMessageBox.information(self, "Резервная копия", f"Сохранено:\n{p}")

    def _settings(self) -> None:
        dlg = SettingsDialog(self._conn, self)
        dlg.exec()

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass
        event.accept()
