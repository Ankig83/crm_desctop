from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

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
    """Диалог с прокручиваемым текстом руководства пользователя."""

    def __init__(self, markdown_text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Руководство пользователя")
        self.resize(820, 620)

        # Конвертируем Markdown в простой читаемый HTML
        html = _md_to_simple_html(markdown_text)

        label = QLabel()
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setText(html)
        label.setWordWrap(True)
        label.setOpenExternalLinks(False)
        label.setContentsMargins(12, 8, 12, 8)

        scroll = QScrollArea()
        scroll.setWidget(label)
        scroll.setWidgetResizable(True)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(scroll)
        lay.addWidget(btns)


def _md_to_simple_html(md: str) -> str:
    """Минимальный конвертер Markdown → HTML для отображения в QLabel."""
    import html as _html
    lines = md.split("\n")
    result: list[str] = []
    in_table = False
    in_code = False

    for line in lines:
        # Блок кода
        if line.startswith("```"):
            if in_code:
                result.append("</pre>")
                in_code = False
            else:
                result.append("<pre style='background:#f5f5f5;padding:8px;"
                              "border-radius:4px;font-family:Consolas,monospace;"
                              "font-size:12px;'>")
                in_code = True
            continue
        if in_code:
            result.append(_html.escape(line))
            continue

        # Разделитель таблицы (строка из |---|)
        if line.strip().startswith("|") and set(line.replace("|", "").replace(" ", "")) <= set("-:"):
            continue

        # Строка таблицы
        if line.strip().startswith("|") and line.strip().endswith("|"):
            cells = [c.strip() for c in line.strip()[1:-1].split("|")]
            if not in_table:
                result.append("<table border='1' cellpadding='5' cellspacing='0' "
                              "style='border-collapse:collapse;margin:8px 0;"
                              "font-size:13px;'>")
                in_table = True
                # первая строка = заголовок
                result.append("<tr style='background:#D9E1F2;'>" +
                               "".join(f"<th>{_html.escape(c)}</th>" for c in cells) +
                               "</tr>")
            else:
                result.append("<tr>" +
                               "".join(f"<td>{_html.escape(c)}</td>" for c in cells) +
                               "</tr>")
            continue
        else:
            if in_table:
                result.append("</table>")
                in_table = False

        # Горизонтальная линия
        if line.strip() in ("---", "***", "___"):
            result.append("<hr/>")
            continue

        escaped = _html.escape(line)
        # Inline code
        import re
        escaped = re.sub(r"`([^`]+)`",
                         r"<code style='background:#f0f0f0;padding:1px 4px;"
                         r"border-radius:3px;font-family:Consolas;'>\1</code>",
                         escaped)
        # Bold
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
        # Italic
        escaped = re.sub(r"\*(.+?)\*", r"<i>\1</i>", escaped)

        # Заголовки
        if escaped.startswith("### "):
            result.append(f"<h3 style='margin:10px 0 4px;color:#1F3864;'>{escaped[4:]}</h3>")
        elif escaped.startswith("## "):
            result.append(f"<h2 style='margin:14px 0 6px;color:#1F3864;"
                          f"border-bottom:2px solid #BDD7EE;padding-bottom:4px;'>{escaped[3:]}</h2>")
        elif escaped.startswith("# "):
            result.append(f"<h1 style='color:#1F3864;'>{escaped[2:]}</h1>")
        elif escaped.startswith("&gt; "):
            result.append(f"<blockquote style='border-left:4px solid #BDD7EE;"
                          f"margin:4px 0;padding:4px 12px;background:#EBF5FB;"
                          f"color:#555;'>{escaped[5:]}</blockquote>")
        elif escaped.startswith("- ") or escaped.startswith("* "):
            result.append(f"<li style='margin:2px 0;'>{escaped[2:]}</li>")
        elif escaped.strip() == "":
            result.append("<br/>")
        else:
            result.append(f"<p style='margin:3px 0;'>{escaped}</p>")

    if in_table:
        result.append("</table>")
    if in_code:
        result.append("</pre>")

    return "".join(result)
