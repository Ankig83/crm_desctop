from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from crm_desktop.adapters import excel_io
from crm_desktop.repositories import audit
from crm_desktop.services.backup import copy_database_to
from PySide6.QtWidgets import (
    QAbstractSpinBox, QCheckBox, QComboBox, QDateEdit,
    QLineEdit, QPlainTextEdit, QPushButton, QTableWidget,
)
from crm_desktop.repositories import users as users_repo
from crm_desktop.ui.client_types_tab import ClientTypesTab
from crm_desktop.ui.clients_tab import ClientsTab
from crm_desktop.ui.global_discounts_tab import GlobalDiscountsTab
from crm_desktop.ui.history_tab import HistoryTab
from crm_desktop.ui.products_tab import ProductsTab
from crm_desktop.ui.promotions_tab import PromotionsTab
from crm_desktop.ui.quote_tab import QuoteTab
from crm_desktop.ui.settings_dialog import SettingsDialog
from crm_desktop.ui.users_tab import UsersTab


def _apply_readonly(widget: "QWidget") -> None:
    """Перевести вкладку в режим «только чтение» для менеджеров.

    Списки (QListWidget) остаются кликабельными — можно листать и читать.
    Поля ввода, кнопки сохранения/удаления блокируются.
    """
    from PySide6.QtWidgets import QListWidget, QWidget as _W
    for child in widget.findChildren(_W):
        if isinstance(child, (QLineEdit, QPlainTextEdit)):
            child.setReadOnly(True)
        elif isinstance(child, QTableWidget):
            child.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        elif isinstance(child, QPushButton):
            child.setEnabled(False)
        elif isinstance(child, (QComboBox, QAbstractSpinBox, QDateEdit, QCheckBox)):
            # Не трогаем вспомогательные комбо внутри QListWidget (полосы прокрутки)
            parent = child.parent()
            if not isinstance(parent, QListWidget):
                child.setEnabled(False)


class MainWindow(QMainWindow):
    def __init__(
        self,
        conn: sqlite3.Connection,
        role: str = "admin",
        user_name: str = "",
        user_id: int | None = None,
    ) -> None:
        super().__init__()
        self._conn = conn
        self._role = role
        self._user_name = user_name
        self._user_id = user_id
        is_admin = (role == "admin")

        title = f"CRM — {user_name}" if user_name else "CRM — клиенты и товары"
        self.setWindowTitle(title)
        self.resize(1100, 660)

        tabs = QTabWidget()

        # Все вкладки доступны всем; менеджер — только просмотр в data-вкладках
        self._clients = ClientsTab(conn)
        self._products = ProductsTab(conn)
        self._promotions = PromotionsTab(conn)
        self._quote = QuoteTab(conn, user_name=user_name)
        self._history = HistoryTab(conn)
        self._global_disc = GlobalDiscountsTab(conn)
        self._client_types = ClientTypesTab(conn)
        self._users = UsersTab(conn, current_user_name=user_name)

        tabs.addTab(self._clients, "Клиенты")
        tabs.addTab(self._quote, "Расчёт")
        tabs.addTab(self._history, "История")
        tabs.addTab(self._products, "Товары")
        tabs.addTab(self._promotions, "Акции")
        tabs.addTab(self._global_disc, "Скидки")
        tabs.addTab(self._client_types, "Типы клиентов")
        if is_admin:
            tabs.addTab(self._users, "Пользователи")

        # Менеджер — просмотр без редактирования во всех data-вкладках
        if not is_admin:
            for w in (
                self._clients,
                self._products,
                self._promotions,
                self._global_disc,
                self._client_types,
            ):
                _apply_readonly(w)

        tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(tabs)
        self._tabs = tabs

        self._build_menu(role)

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
        elif w is self._global_disc:
            self._global_disc.reload()
        elif w is self._client_types:
            self._client_types.reload()
            self._clients._reload_type_combo()
        elif w is self._users:
            self._users.reload()

    def _build_menu(self, role: str = "admin") -> None:
        bar = self.menuBar()
        m_file = bar.addMenu("Файл")
        is_admin = (role == "admin")

        # ── Импорт (доступно всем) ────────────────────────────
        m_import = m_file.addMenu("Импорт")

        a_imp_c = QAction("Клиенты (Excel)…", self)
        a_imp_c.triggered.connect(self._imp_clients)
        m_import.addAction(a_imp_c)

        a_imp_p = QAction("Товары (Excel)…", self)
        a_imp_p.triggered.connect(self._imp_products)
        m_import.addAction(a_imp_p)

        a_imp_r = QAction("Акции (Excel)…", self)
        a_imp_r.triggered.connect(self._imp_promo)
        m_import.addAction(a_imp_r)

        # Импорт скидок — только для администратора
        if is_admin:
            a_imp_d = QAction("Скидки (Excel)…", self)
            a_imp_d.triggered.connect(self._imp_discounts)
            m_import.addAction(a_imp_d)

        # ── Экспорт (доступно всем) ───────────────────────────
        m_export = m_file.addMenu("Экспорт")

        a_exp_c = QAction("Клиенты…", self)
        a_exp_c.triggered.connect(self._exp_clients)
        m_export.addAction(a_exp_c)

        a_exp_p = QAction("Товары…", self)
        a_exp_p.triggered.connect(self._exp_products)
        m_export.addAction(a_exp_p)

        a_exp_r = QAction("Акции…", self)
        a_exp_r.triggered.connect(self._exp_promo)
        m_export.addAction(a_exp_r)

        a_exp_d = QAction("Скидки…", self)
        a_exp_d.triggered.connect(self._exp_discounts)
        m_export.addAction(a_exp_d)

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

        # ── Меню «Справка» ───────────────────────────────────
        m_help = bar.addMenu("Справка")

        a_guide = QAction("Руководство пользователя", self)
        a_guide.setShortcut("F1")
        a_guide.triggered.connect(self._show_user_guide)
        m_help.addAction(a_guide)

        m_help.addSeparator()

        a_about = QAction("О программе", self)
        a_about.triggered.connect(self._show_about)
        m_help.addAction(a_about)

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
        parts = []
        if rep.clients_rows:
            parts.append(f"Клиентов: {rep.clients_rows}")
        if rep.products_rows:
            parts.append(f"Товаров: {rep.products_rows}")
        if rep.promotions_rows:
            parts.append(f"Акций: {rep.promotions_rows}")
        if rep.discounts_rows:
            parts.append(f"Правил скидок: {rep.discounts_rows}")
        msg = "\n".join(parts) if parts else "Импортировано: 0 строк"
        if rep.errors:
            msg += "\n\nОшибки:\n" + "\n".join(rep.errors[:30])
            if len(rep.errors) > 30:
                msg += f"\n… и ещё {len(rep.errors) - 30}"
            QMessageBox.warning(self, "Импорт", msg)
        else:
            QMessageBox.information(self, "Импорт завершён", msg)

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

    def _imp_discounts(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Импорт скидок", "", "Excel (*.xlsx)")
        if not path:
            return
        rep = excel_io.import_global_discounts(self._conn, Path(path))
        self._show_import_report(rep)
        self._global_disc.reload()

    def _exp_discounts(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт скидок", "discounts.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        excel_io.export_global_discounts(self._conn, Path(path))
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

    def _show_user_guide(self) -> None:
        import sys
        # Порядок поиска файла:
        # 1. Внутри PyInstaller-бандла (--add-data встроил файл в EXE)
        # 2. Рядом с EXE в папке docs/ (onedir-режим или ручная раскладка)
        # 3. Папка проекта при запуске из исходников
        candidates = [
            Path(getattr(sys, "_MEIPASS", "")) / "docs" / "USER_GUIDE.md",
            Path(sys.executable).parent / "docs" / "USER_GUIDE.md",
            Path(__file__).resolve().parents[4] / "docs" / "USER_GUIDE.md",
        ]
        guide_path = next((p for p in candidates if p.exists()), None)
        if guide_path is None:
            QMessageBox.information(
                self, "Справка",
                "Файл руководства не найден.\n"
                "Ожидается: docs/USER_GUIDE.md рядом с программой."
            )
            return
        try:
            text = guide_path.read_text(encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, "Справка", f"Не удалось открыть файл:\n{e}")
            return
        _GuideDialog(text, self).exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "О программе",
            "<b>CRM Desktop</b><br>"
            "Версия 1.0<br><br>"
            "Программа для учёта клиентов и товаров,<br>"
            "расчёта заказов и выгрузки в 1С (RUS.xlsx).<br><br>"
            "По вопросам: PyBotStudio",
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass
        event.accept()


class _GuideDialog(QDialog):
    """Диалог со справкой — рендерит Markdown через встроенный Qt-движок."""

    def __init__(self, markdown_text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Руководство пользователя")
        self.resize(900, 680)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        font = QFont("Segoe UI", 10)
        browser.setFont(font)
        browser.setMarkdown(markdown_text)
        browser.setReadOnly(True)
        browser.document().setDefaultStyleSheet(
            "h1 { color: #1F3864; }"
            "h2 { color: #1F3864; border-bottom: 1px solid #BDD7EE; padding-bottom: 4px; }"
            "h3 { color: #2E75B6; }"
            "h4, h5 { color: #2E75B6; }"
            "table { border-collapse: collapse; margin: 6px 0; }"
            "th { background: #D9E1F2; padding: 4px 8px; border: 1px solid #ADB9CA; }"
            "td { padding: 4px 8px; border: 1px solid #D0D0D0; }"
            "blockquote { border-left: 4px solid #BDD7EE; margin: 4px 0;"
            "             padding: 4px 12px; background: #EBF5FB; color: #444; }"
            "code { background: #F0F0F0; padding: 1px 4px; font-family: Consolas, monospace; }"
            "pre  { background: #F5F5F5; padding: 8px; font-family: Consolas, monospace;"
            "       font-size: 12px; }"
            "li { margin: 2px 0; }"
        )

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(browser)
        lay.addWidget(btns)
