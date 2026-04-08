from __future__ import annotations

import sqlite3
from typing import Literal

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from crm_desktop.repositories import settings as settings_repo

THEME_KEY = "ui_theme"
ThemeId = Literal["dark", "light"]


def get_stored_theme(conn: sqlite3.Connection) -> ThemeId:
    v = (settings_repo.get(conn, THEME_KEY, "dark") or "dark").strip().lower()
    return "light" if v == "light" else "dark"


def apply_saved_theme(app: QApplication, conn: sqlite3.Connection) -> None:
    apply_theme(app, get_stored_theme(conn))


def apply_theme(app: QApplication, theme: ThemeId) -> None:
    app.setStyle("Fusion")
    if theme == "light":
        app.setPalette(_light_palette())
        app.setStyleSheet(_light_stylesheet())
    else:
        app.setPalette(_dark_palette())
        app.setStyleSheet(_dark_stylesheet())


def _dark_palette() -> QPalette:
    p = QPalette()
    w = QColor(45, 45, 48)
    base = QColor(30, 30, 32)
    alt = QColor(42, 42, 45)
    text = QColor(230, 230, 235)
    dim = QColor(150, 150, 155)
    hi = QColor(64, 128, 255)
    p.setColor(QPalette.ColorRole.Window, w)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, alt)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, QColor(55, 55, 58))
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 80, 80))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(50, 50, 52))
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Highlight, hi)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Link, QColor(120, 170, 255))
    p.setColor(QPalette.ColorRole.PlaceholderText, dim)
    return p


def _light_palette() -> QPalette:
    p = QPalette()
    win = QColor(242, 242, 247)
    base = QColor(255, 255, 255)
    alt = QColor(249, 249, 250)
    text = QColor(28, 28, 30)
    secondary = QColor(60, 60, 67)
    hi = QColor(0, 122, 255)
    p.setColor(QPalette.ColorRole.Window, win)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, alt)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, base)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 59, 48))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Highlight, hi)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Link, hi)
    p.setColor(QPalette.ColorRole.PlaceholderText, secondary)
    return p


def _dark_stylesheet() -> str:
    return """
        QMainWindow { background-color: #2d2d30; }
        QTabWidget::pane {
            border: 1px solid #3f3f46;
            background: #2d2d30;
            border-radius: 6px;
            top: -1px;
        }
        QTabBar::tab {
            background: #3c3c40;
            color: #c8c8d0;
            padding: 8px 14px;
            margin-right: 2px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
        }
        QTabBar::tab:selected {
            background: #2d2d30;
            color: #f0f0f5;
            font-weight: 600;
        }
        QMenuBar {
            background-color: #2d2d30;
            color: #e8e8ed;
            padding: 2px;
        }
        QMenuBar::item:selected {
            background-color: #3d5afe;
        }
        QMenu {
            background-color: #3c3c40;
            color: #e8e8ed;
            border: 1px solid #555;
        }
        QScrollArea { border: none; background: transparent; }
        QComboBox, QDateEdit {
            background-color: #3a3a3e;
            border: 1px solid #555;
            border-radius: 6px;
            padding: 4px 8px;
            min-height: 20px;
        }
    """


def _light_stylesheet() -> str:
    return """
        QMainWindow { background-color: #F2F2F7; }
        QTabWidget::pane {
            border: none;
            background: #F2F2F7;
            border-radius: 10px;
            top: -1px;
        }
        QTabBar::tab {
            background: #E5E5EA;
            color: #3C3C43;
            padding: 8px 16px;
            margin-right: 3px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            min-width: 72px;
        }
        QTabBar::tab:selected {
            background: #FFFFFF;
            color: #000000;
            font-weight: 600;
        }
        QTabBar::tab:hover:!selected {
            background: #D1D1D6;
        }
        QTableWidget, QTableView {
            background-color: #FFFFFF;
            alternate-background-color: #FAFAFA;
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: 10px;
            gridline-color: rgba(0, 0, 0, 0.06);
        }
        QHeaderView::section {
            background-color: #F2F2F7;
            color: #3C3C43;
            padding: 6px;
            border: none;
            border-bottom: 1px solid rgba(0, 0, 0, 0.08);
        }
        QLineEdit, QPlainTextEdit, QListWidget {
            background-color: #FFFFFF;
            border: 1px solid rgba(0, 0, 0, 0.10);
            border-radius: 8px;
            padding: 4px 8px;
        }
        QListWidget::item:selected {
            background-color: #007AFF;
            color: #FFFFFF;
            border-radius: 4px;
        }
        QListWidget::item:hover:!selected {
            background-color: rgba(0, 122, 255, 0.08);
        }
        QGroupBox {
            background-color: #FFFFFF;
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 10px;
            margin-top: 12px;
            padding-top: 12px;
            font-weight: 600;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }
        QMenuBar {
            background-color: #F2F2F7;
            color: #000000;
            padding: 2px;
            border-bottom: 1px solid rgba(0, 0, 0, 0.08);
        }
        QMenuBar::item:selected {
            background-color: rgba(0, 122, 255, 0.12);
        }
        QMenu {
            background-color: #FFFFFF;
            color: #000000;
            border: 1px solid rgba(0, 0, 0, 0.10);
            border-radius: 8px;
            padding: 4px;
        }
        QMenu::item:selected {
            background-color: rgba(0, 122, 255, 0.12);
        }
        QScrollArea { border: none; background: transparent; }
        QCheckBox { color: #000000; }
        QDialog { background-color: #F2F2F7; }
        QPushButton {
            background-color: #FFFFFF;
            border: 1px solid rgba(0, 0, 0, 0.12);
            border-radius: 8px;
            padding: 6px 14px;
            min-height: 20px;
        }
        QPushButton:hover {
            background-color: #F2F2F7;
        }
        QPushButton:pressed {
            background-color: #E5E5EA;
        }
        QLabel { color: #000000; }
        QComboBox, QDateEdit {
            background-color: #FFFFFF;
            border: 1px solid rgba(0, 0, 0, 0.10);
            border-radius: 8px;
            padding: 4px 8px;
            min-height: 22px;
        }
        QComboBox::drop-down { border: none; width: 24px; }
    """
