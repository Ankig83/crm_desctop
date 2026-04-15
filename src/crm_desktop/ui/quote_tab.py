from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import date as date_type
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from crm_desktop.adapters.quote_pdf import export_quote_pdf
from crm_desktop.adapters.rus_export import RusLine, export_rus_variant_a
from crm_desktop.repositories import audit, calculation_sessions, clients, products, promotions, settings as settings_repo
from crm_desktop.services import email_send
from crm_desktop.services.bonus import (
    BonusRule,
    collect_bonus_thresholds,
    find_best_threshold,
    promo_bonus_active,
)
from crm_desktop.services.pricing import line_total
from crm_desktop.utils.dates import iso, parse_dmY, parse_iso

# ── Индексы колонок таблицы ───────────────────────────────────
_C_PID   = 0   # скрытый product_id
_C_NAME  = 1   # название (QComboBox или QLabel для бонуса)
_C_PRICE = 2   # цена
_C_QTY   = 3   # количество
_C_SUM   = 4   # сумма
_C_BONUS = 5   # скрытый флаг: "1" = бонусная строка

_BONUS_BG = "#FFF2CC"


class _BonusPickerDialog(QDialog):
    """Диалог выбора бонусного товара когда вариантов > 1."""

    def __init__(self, parent, candidates: list[tuple[str, str]]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Выберите бонусный товар")
        self.setMinimumWidth(400)
        self._selected: str | None = None

        label = QLabel("Клиент выбирает один бонусный товар:")
        label.setStyleSheet("font-weight: bold;")

        self._list = QListWidget()
        for ext_id, name in candidates:
            it = QListWidgetItem(f"{name}  (ID: {ext_id})")
            it.setData(Qt.ItemDataRole.UserRole, ext_id)
            self._list.addItem(it)
        if self._list.count():
            self._list.setCurrentRow(0)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(label)
        lay.addWidget(self._list)
        lay.addWidget(btns)

    def _on_ok(self) -> None:
        it = self._list.currentItem()
        if it:
            self._selected = it.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def selected_external_id(self) -> str | None:
        return self._selected


class QuoteTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._block = False
        self._recalcing = False          # защита от рекурсивного вызова _recalc
        self._bonus_choices: dict[int, str] = {}

        # ── Клиент ───────────────────────────────────────────
        self._client = QComboBox()
        self._client.currentIndexChanged.connect(lambda *_: self._recalc())
        self._client_discount_label = QLabel("")
        self._client_discount_label.setStyleSheet("color: #1a6b1a; font-style: italic;")

        # ── Дата расчёта ─────────────────────────────────────
        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("dd.MM.yyyy")
        self._date.setDate(QDate.currentDate())
        self._date.dateChanged.connect(lambda *_: self._recalc())

        # ── Дата доставки ─────────────────────────────────────
        self._delivery_date = QDateEdit()
        self._delivery_date.setCalendarPopup(True)
        self._delivery_date.setDisplayFormat("dd.MM.yyyy")
        self._delivery_date.setDate(QDate.currentDate().addDays(3))
        self._delivery_date.setToolTip(
            "Дата доставки — записывается в строку 18 файла RUS.xlsx.\n"
            "Используется 1С при автоматическом чтении заказа."
        )

        # ── Номер заказа ──────────────────────────────────────
        _next_no = settings_repo.get(conn, "next_order_no", "1") or "1"
        self._order_no = QLineEdit(_next_no)
        self._order_no.setMaximumWidth(80)
        self._order_no.setToolTip(
            "Номер заказа — проставляется автоматически.\n"
            "Можно исправить вручную перед экспортом."
        )

        # ── Предоплата % ─────────────────────────────────────
        self._prepay = QDoubleSpinBox()
        self._prepay.setRange(0, 100)
        self._prepay.setSingleStep(5)
        self._prepay.setDecimals(0)
        self._prepay.setSuffix(" %")
        self._prepay.setValue(0)
        self._prepay.setToolTip(
            "Процент предоплаты от суммы заказа.\n"
            "Если у товара прописана скидка за предоплату\n"
            "и процент достигает порога — скидка применяется."
        )
        self._prepay.valueChanged.connect(lambda *_: self._recalc())
        self._prepay_label = QLabel("")
        self._prepay_label.setStyleSheet("color: #1a5276; font-style: italic;")

        # ── Инфо о скидках за объём ───────────────────────────
        self._volume_label = QLabel("")
        self._volume_label.setStyleSheet("color: #7D4E00; font-style: italic;")

        # ── Таблица ───────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Товар", "Цена", "Кол-во", "Сумма", "_bonus"]
        )
        self._table.hideColumn(_C_PID)
        self._table.hideColumn(_C_BONUS)
        self._table.cellChanged.connect(self._on_changed)

        self._total = QLabel("0.00")
        self._total.setStyleSheet("font-size: 14pt; font-weight: bold;")
        self._total_with_prepay = QLabel("")
        self._total_with_prepay.setStyleSheet("color: #1a5276; font-style: italic;")

        # ── Кнопки ───────────────────────────────────────────
        btn_line         = QPushButton("+ Добавить товар")
        btn_del          = QPushButton("Удалить строку")
        btn_calc         = QPushButton("Пересчитать")
        btn_export       = QPushButton("Сохранить расчёт (TXT)…")
        btn_export_pdf   = QPushButton("Сохранить расчёт (PDF)…")
        btn_export_rus   = QPushButton("Сформировать RUS.xlsx…")
        btn_save_session = QPushButton("Сохранить в историю")
        btn_mail         = QPushButton("Отправить на e-mail…")

        btn_line.clicked.connect(self._add_line)
        btn_del.clicked.connect(self._del_line)
        btn_calc.clicked.connect(self._recalc)
        btn_export.clicked.connect(self._export_txt)
        btn_export_pdf.clicked.connect(self._export_pdf)
        btn_export_rus.clicked.connect(self._export_rus)
        btn_save_session.clicked.connect(self._save_session_action)
        btn_mail.clicked.connect(self._send_mail)

        btn_row = QHBoxLayout()
        for b in (btn_line, btn_del, btn_calc, btn_export, btn_export_pdf,
                  btn_export_rus, btn_save_session, btn_mail):
            btn_row.addWidget(b)
        btn_row.addStretch()

        grid = QGridLayout()
        grid.addWidget(QLabel("Клиент:"),           0, 0)
        grid.addWidget(self._client,                0, 1)
        grid.addWidget(self._client_discount_label, 0, 2)
        grid.addWidget(QLabel("Дата расчёта:"),     0, 3)
        grid.addWidget(self._date,                  0, 4)
        grid.addWidget(QLabel("Дата доставки:"),    0, 5)
        grid.addWidget(self._delivery_date,         0, 6)
        grid.addWidget(QLabel("№ заказа:"),         0, 7)
        grid.addWidget(self._order_no,              0, 8)
        grid.addWidget(QLabel("Предоплата:"),       1, 0)
        grid.addWidget(self._prepay,                1, 1)
        grid.addWidget(self._prepay_label,          1, 2)
        grid.addWidget(self._volume_label,          1, 3, 1, 2)

        total_row = QHBoxLayout()
        total_row.addWidget(QLabel("Итого:"))
        total_row.addWidget(self._total)
        total_row.addWidget(self._total_with_prepay)
        total_row.addStretch()

        lay = QVBoxLayout(self)
        lay.addLayout(grid)
        lay.addLayout(btn_row)
        lay.addWidget(self._table)
        lay.addLayout(total_row)

        self.reload_clients()
        self._add_line()

    # ─────────────────────────────────────────────────────────
    # Клиент
    # ─────────────────────────────────────────────────────────

    def _current_client(self) -> clients.Client | None:
        cid = self._client.currentData()
        return clients.get(self._conn, int(cid)) if cid is not None else None

    def _client_type_pct(self) -> float:
        c = self._current_client()
        return c.type_discount_pct if c else 0.0

    def _prepay_pct(self) -> float:
        return float(self._prepay.value())

    def reload_clients(self) -> None:
        self._client.clear()
        for c in clients.list_all(self._conn):
            label = f"{c.name} [{c.client_type_label}] (ИНН {c.inn or '—'})"
            self._client.addItem(label, c.id)
        self._update_client_discount_label()

    def _update_client_discount_label(self) -> None:
        pct = self._client_type_pct()
        self._client_discount_label.setText(
            f"Скидка клиента: −{pct:.0f}%" if pct > 0 else ""
        )

    # ─────────────────────────────────────────────────────────
    # Скидки — вспомогательные
    # ─────────────────────────────────────────────────────────

    def _get_matrix_rules(self, promo) -> dict:
        if not promo or not promo.matrix_rules_json:
            return {}
        try:
            raw = json.loads(promo.matrix_rules_json)
            if isinstance(raw, dict):
                return {str(k): v for k, v in raw.items()}
        except Exception:  # noqa: BLE001
            pass
        return {}

    def _prepay_discount_for(self, matrix_rules: dict) -> float:
        """Скидка за предоплату: ищет наибольший подходящий порог prepay_<N>."""
        prepay = self._prepay_pct()
        if prepay <= 0:
            return 0.0
        best = 0.0
        for key, val in matrix_rules.items():
            if not key.startswith("prepay_"):
                continue
            try:
                threshold = float(key.split("_", 1)[1])
                disc = float(val or 0)
            except (ValueError, IndexError):
                continue
            if prepay >= threshold and disc > best:
                best = disc
        return best

    def _volume_discount_for(self, matrix_rules: dict, total_boxes: float) -> float:
        """
        Скидка за объём: ищет наибольший подходящий порог volume_<N>.
        total_boxes — суммарное кол-во коробок по всем обычным строкам заказа.
        """
        if total_boxes <= 0:
            return 0.0
        best = 0.0
        for key, val in matrix_rules.items():
            if not key.startswith("volume_"):
                continue
            try:
                threshold = float(key.split("_", 1)[1])
                disc = float(val or 0)
            except (ValueError, IndexError):
                continue
            if total_boxes >= threshold and disc > best:
                best = disc
        return best

    def _product_discount_for(self, matrix_rules: dict) -> float:
        """
        Продуктовая скидка: берёт expiry_pct если задана.
        Применяется всегда если > 0 (не зависит от условий).
        """
        try:
            return float(matrix_rules.get("expiry_pct", 0) or 0)
        except (ValueError, TypeError):
            return 0.0

    def _update_prepay_label(self, total_no_prepay: float, total_with_prepay: float) -> None:
        prepay = self._prepay_pct()
        if prepay <= 0:
            self._prepay_label.setText("")
            self._total_with_prepay.setText("")
            return
        saved = total_no_prepay - total_with_prepay
        self._prepay_label.setText("Скидка за предоплату применена")
        if saved > 0:
            self._total_with_prepay.setText(
                f"  → с предоплатой {prepay:.0f}%: {total_with_prepay:.2f}  "
                f"(экономия {saved:.2f})"
            )

    # ─────────────────────────────────────────────────────────
    # Подсчёт суммарного кол-ва коробок (для скидки за объём)
    # ─────────────────────────────────────────────────────────

    def _calc_total_boxes(self) -> float:
        """Суммирует кол-во коробок по всем обычным (не бонусным) строкам."""
        total = 0.0
        for r in range(self._table.rowCount()):
            if self._is_bonus_row(r):
                continue
            w = self._table.cellWidget(r, _C_NAME)
            if not isinstance(w, QComboBox):
                continue
            qty_it = self._table.item(r, _C_QTY)
            qty_s = qty_it.text().strip() if qty_it else "0"
            try:
                total += float(qty_s.replace(",", "."))
            except ValueError:
                pass
        return total

    # ─────────────────────────────────────────────────────────
    # Акционные бонусы
    # ─────────────────────────────────────────────────────────

    def _is_bonus_row(self, r: int) -> bool:
        it = self._table.item(r, _C_BONUS)
        return it is not None and it.text() == "1"

    def _promo_active(self, matrix_rules: dict, qd: date_type) -> bool:
        return promo_bonus_active(matrix_rules, qd)

    def _collect_bonus_thresholds(self, matrix_rules: dict) -> list[BonusRule]:
        return collect_bonus_thresholds(matrix_rules)

    def _find_best_threshold(
        self, thresholds: list[BonusRule], qty: float
    ) -> BonusRule | None:
        return find_best_threshold(thresholds, qty)

    def _remove_bonus_rows_after(self, main_row: int) -> None:
        while True:
            nxt = main_row + 1
            if nxt >= self._table.rowCount():
                break
            if self._is_bonus_row(nxt):
                self._table.removeRow(nxt)
            else:
                break

    def _add_bonus_row(self, after_row: int, p: object, qty: float, suffix: str = "") -> int:
        ins = after_row + 1
        new_ch = {(k if k < ins else k + 1): v for k, v in self._bonus_choices.items()}
        self._bonus_choices = new_ch

        self._table.insertRow(ins)

        lbl = QLabel(f"  🎁 БОНУС: {p.name}{suffix}")
        lbl.setStyleSheet(
            f"background-color:{_BONUS_BG}; color:#1F4E79; font-style:italic; padding:2px;"
        )
        self._table.setCellWidget(ins, _C_NAME, lbl)

        def _bi(val: str) -> QTableWidgetItem:
            it = QTableWidgetItem(val)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            it.setBackground(Qt.GlobalColor.yellow)
            return it

        self._table.setItem(ins, _C_PID,   _bi(str(getattr(p, "id", ""))))
        self._table.setItem(ins, _C_PRICE, _bi("0"))
        self._table.setItem(ins, _C_QTY,   _bi(str(qty)))
        self._table.setItem(ins, _C_SUM,   _bi("0"))
        self._table.setItem(ins, _C_BONUS, _bi("1"))
        return ins

    def _ask_bonus_choice(self, other_ids: list[str]) -> str | None:
        candidates: list[tuple[str, str]] = []
        for eid in other_ids:
            bp = products.by_external_id(self._conn, eid)
            candidates.append((eid, bp.name if bp else f"Товар ID {eid}"))
        dlg = _BonusPickerDialog(self, candidates)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.selected_external_id()
        return None

    # ─────────────────────────────────────────────────────────
    # Таблица
    # ─────────────────────────────────────────────────────────

    def _add_line(self) -> None:
        self._block = True
        r = self._table.rowCount()
        self._table.insertRow(r)
        combo = QComboBox()
        for p in products.list_all(self._conn):
            combo.addItem(p.name, p.id)
        self._table.setCellWidget(r, _C_NAME, combo)
        combo.currentIndexChanged.connect(lambda *_: self._recalc())
        self._table.setItem(r, _C_PID,   QTableWidgetItem(""))
        self._table.setItem(r, _C_PRICE, QTableWidgetItem("0"))
        self._table.setItem(r, _C_QTY,   QTableWidgetItem("1"))
        self._table.setItem(r, _C_SUM,   QTableWidgetItem("0"))
        self._table.setItem(r, _C_BONUS, QTableWidgetItem(""))
        self._sync_pid_for_row(r)
        self._block = False
        self._recalc()

    def _sync_pid_for_row(self, r: int) -> None:
        w = self._table.cellWidget(r, _C_NAME)
        if not isinstance(w, QComboBox):
            return
        pid = w.currentData()
        it = self._table.item(r, _C_PID)
        if it is None:
            self._table.setItem(r, _C_PID, QTableWidgetItem(str(pid or "")))
        else:
            it.setText(str(pid or ""))
        p = products.get(self._conn, int(pid)) if pid is not None else None
        pr = self._table.item(r, _C_PRICE)
        if pr and p:
            pr.setText(str(p.base_price))

    def _del_line(self) -> None:
        r = self._table.currentRow()
        if r < 0:
            return
        if self._is_bonus_row(r):
            QMessageBox.information(
                self, "Бонусная строка",
                "Бонусные строки удаляются автоматически при изменении количества товара."
            )
            return
        self._remove_bonus_rows_after(r)
        self._table.removeRow(r)
        self._bonus_choices.pop(r, None)
        self._recalc()

    def _on_changed(self, row: int, col: int) -> None:
        if self._block or self._recalcing:
            return
        if col == _C_QTY and not self._is_bonus_row(row):
            self._recalc()

    def _quote_date(self) -> date_type:
        q = self._date.date()
        return parse_dmY(f"{q.day():02d}.{q.month():02d}.{q.year():04d}")

    def _delivery_date_value(self) -> date_type:
        q = self._delivery_date.date()
        return parse_dmY(f"{q.day():02d}.{q.month():02d}.{q.year():04d}")

    # ─────────────────────────────────────────────────────────
    # Пересчёт
    # ─────────────────────────────────────────────────────────

    def _recalc(self) -> None:
        if self._recalcing:
            return
        self._recalcing = True
        self._block = True
        try:
            self._recalc_impl()
        finally:
            self._recalcing = False
            self._block = False

    def _recalc_impl(self) -> None:
        self._update_client_discount_label()
        qd = self._quote_date()
        client_pct = self._client_type_pct()

        # ── Шаг 1: считаем суммарное кол-во коробок для скидки за объём
        total_boxes = self._calc_total_boxes()

        # ── Шаг 2: показываем инфо об объёме
        if total_boxes > 0:
            self._volume_label.setText(f"Всего коробок в заказе: {total_boxes:.0f}")
        else:
            self._volume_label.setText("")

        total_no_prepay   = 0.0
        total_with_prepay = 0.0

        r = 0
        while r < self._table.rowCount():
            if self._is_bonus_row(r):
                r += 1
                continue

            w = self._table.cellWidget(r, _C_NAME)
            if not isinstance(w, QComboBox):
                r += 1
                continue

            self._sync_pid_for_row(r)
            pid = w.currentData()
            p = products.get(self._conn, int(pid)) if pid is not None else None
            if not p:
                r += 1
                continue

            qty_it = self._table.item(r, _C_QTY)
            qty_s  = qty_it.text().strip() if qty_it else "1"
            try:
                qty = float(qty_s.replace(",", "."))
            except ValueError:
                qty = 0.0

            promo = promotions.get_for_product(self._conn, p.id)
            vf    = parse_iso(promo.valid_from_iso) if promo else None
            vt    = parse_iso(promo.valid_to_iso)   if promo else None
            disc  = promo.discount_percent           if promo else 0.0
            matrix_rules = self._get_matrix_rules(promo)

            # ── Все скидки для этого товара ──────────────────
            prepay_disc  = self._prepay_discount_for(matrix_rules)
            volume_disc  = self._volume_discount_for(matrix_rules, total_boxes)  # ← Этап 2
            product_disc = self._product_discount_for(matrix_rules)              # ← Этап 3

            sub_no_prepay = line_total(
                p.base_price, qty, disc, qd, vf, vt,
                client_type_pct=client_pct,
                prepay_pct=0.0,
            )
            sub_full = line_total(
                p.base_price, qty, disc, qd, vf, vt,
                client_type_pct=client_pct,
                prepay_pct=prepay_disc,
                volume_pct=volume_disc,
                product_pct=product_disc,
            )

            total_no_prepay   += sub_no_prepay
            total_with_prepay += sub_full

            if s := self._table.item(r, _C_SUM):
                s.setText(f"{sub_full:.2f}")
            if pr := self._table.item(r, _C_PRICE):
                pr.setText(str(p.base_price))

            # ── Бонусные строки ───────────────────────────────
            self._remove_bonus_rows_after(r)

            if self._promo_active(matrix_rules, qd):
                thresholds = self._collect_bonus_thresholds(matrix_rules)
                best = self._find_best_threshold(thresholds, qty)

                if best:
                    threshold, same_qty, fixed_id, fixed_qty, choice_ids = best
                    ins = r

                    # 1) Бесплатные коробки того же товара
                    if same_qty > 0:
                        ins = self._add_bonus_row(
                            ins, p, same_qty,
                            f"  ×{same_qty} (купи {threshold:.0f} → получи {same_qty} бесплатно)"
                        )

                    # 2) Конкретный другой товар (фиксированный, автоматически)
                    if fixed_id:
                        bp_fixed = products.by_external_id(self._conn, fixed_id)
                        if bp_fixed:
                            ins = self._add_bonus_row(
                                ins, bp_fixed, fixed_qty,
                                f"  ×{fixed_qty} (бонус: {bp_fixed.name})"
                            )

                    # 3) Товар на выбор из списка (менеджер выбирает)
                    if choice_ids:
                        chosen = self._bonus_choices.get(r)
                        if len(choice_ids) == 1:
                            chosen = choice_ids[0]
                            self._bonus_choices[r] = chosen
                        elif chosen not in choice_ids:
                            chosen = self._ask_bonus_choice(choice_ids)
                            if chosen:
                                self._bonus_choices[r] = chosen

                        if chosen:
                            bp = products.by_external_id(self._conn, chosen)
                            if bp:
                                self._add_bonus_row(
                                    ins, bp, 1,
                                    f"  (бонус на выбор)"
                                )

            r += 1

        self._total.setText(f"{total_with_prepay:.2f}")
        self._update_prepay_label(total_no_prepay, total_with_prepay)
        # _block сбрасывается в finally блоке _recalc

    # ─────────────────────────────────────────────────────────
    # Текстовый расчёт
    # ─────────────────────────────────────────────────────────

    def _build_text(self) -> str:
        lines: list[str] = []
        q = self._date.date()
        lines.append(f"Дата расчёта: {q.day():02d}.{q.month():02d}.{q.year():04d}")
        c = self._current_client()
        lines.append(f"Клиент: {c.name if c else '—'}")
        lines.append(f"ИНН: {c.inn if c else '—'}")
        if c and c.type_discount_pct > 0:
            lines.append(f"Скидка клиента ({c.client_type_label}): −{c.type_discount_pct:.0f}%")
        prepay = self._prepay_pct()
        if prepay > 0:
            lines.append(f"Предоплата: {prepay:.0f}%")
        total_boxes = self._calc_total_boxes()
        if total_boxes > 0:
            lines.append(f"Всего коробок в заказе: {total_boxes:.0f}")
        lines.append("")

        qd = self._quote_date()
        client_pct = self._client_type_pct()
        grand = 0.0

        for r in range(self._table.rowCount()):
            if self._is_bonus_row(r):
                w = self._table.cellWidget(r, _C_NAME)
                name = w.text() if isinstance(w, QLabel) else "БОНУС"
                qty_it = self._table.item(r, _C_QTY)
                lines.append(f"  {name.strip()} × {qty_it.text() if qty_it else 0} = 0.00 (бесплатно)")
                continue
            w = self._table.cellWidget(r, _C_NAME)
            if not isinstance(w, QComboBox):
                continue
            pid = w.currentData()
            p = products.get(self._conn, int(pid)) if pid is not None else None
            if not p:
                continue
            qty_it = self._table.item(r, _C_QTY)
            try:
                qty = float((qty_it.text().strip() if qty_it else "1").replace(",", "."))
            except ValueError:
                qty = 0.0
            promo = promotions.get_for_product(self._conn, p.id)
            vf    = parse_iso(promo.valid_from_iso) if promo else None
            vt    = parse_iso(promo.valid_to_iso)   if promo else None
            disc  = promo.discount_percent           if promo else 0.0
            mr    = self._get_matrix_rules(promo)
            pd    = self._prepay_discount_for(mr)
            vd    = self._volume_discount_for(mr, total_boxes)
            prd   = self._product_discount_for(mr)

            sub = line_total(
                p.base_price, qty, disc, qd, vf, vt,
                client_type_pct=client_pct,
                prepay_pct=pd, volume_pct=vd, product_pct=prd,
            )
            grand += sub
            discounts = []
            if pd > 0:  discounts.append(f"предоплата −{pd:.0f}%")
            if vd > 0:  discounts.append(f"объём −{vd:.0f}%")
            if prd > 0: discounts.append(f"продуктовая −{prd:.0f}%")
            suffix = f" ({', '.join(discounts)})" if discounts else ""
            lines.append(f"{p.name} × {qty} = {sub:.2f}{suffix}")

        lines.append("")
        lines.append(f"Итого: {grand:.2f}")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────
    # Сессия
    # ─────────────────────────────────────────────────────────

    def _session_payload(self) -> tuple[float, list[calculation_sessions.SessionLine]]:
        qd = self._quote_date()
        client_pct = self._client_type_pct()
        total_boxes = self._calc_total_boxes()
        total = 0.0
        payload: list[calculation_sessions.SessionLine] = []

        for r in range(self._table.rowCount()):
            if self._is_bonus_row(r):
                pid_it = self._table.item(r, _C_PID)
                qty_it = self._table.item(r, _C_QTY)
                try:
                    bp = products.get(self._conn, int(pid_it.text())) if pid_it else None
                    bqty = float(qty_it.text()) if qty_it else 0.0
                except (ValueError, TypeError):
                    bp, bqty = None, 0.0
                if bp:
                    payload.append(calculation_sessions.SessionLine(
                        product_id=bp.id,
                        product_external_id=bp.external_id or "",
                        product_name=f"🎁 БОНУС: {bp.name}",
                        qty=bqty, base_price=0.0,
                        discount_percent=100.0, line_total=0.0,
                    ))
                continue

            w = self._table.cellWidget(r, _C_NAME)
            if not isinstance(w, QComboBox):
                continue
            pid = w.currentData()
            p = products.get(self._conn, int(pid)) if pid is not None else None
            if not p:
                continue
            qty_it = self._table.item(r, _C_QTY)
            try:
                qty = float((qty_it.text().strip() if qty_it else "1").replace(",", "."))
            except ValueError:
                qty = 0.0
            promo = promotions.get_for_product(self._conn, p.id)
            vf    = parse_iso(promo.valid_from_iso) if promo else None
            vt    = parse_iso(promo.valid_to_iso)   if promo else None
            disc  = promo.discount_percent           if promo else 0.0
            mr    = self._get_matrix_rules(promo)
            pd    = self._prepay_discount_for(mr)
            vd    = self._volume_discount_for(mr, total_boxes)
            prd   = self._product_discount_for(mr)
            applied = disc if (vf and vt and vf <= qd <= vt and disc > 0) else 0.0
            sub = line_total(
                p.base_price, qty, disc, qd, vf, vt,
                client_type_pct=client_pct,
                prepay_pct=pd, volume_pct=vd, product_pct=prd,
            )
            total += sub
            payload.append(calculation_sessions.SessionLine(
                product_id=p.id,
                product_external_id=p.external_id or "",
                product_name=p.name, qty=qty, base_price=p.base_price,
                discount_percent=applied + client_pct + pd + vd + prd,
                line_total=sub,
            ))
        return total, payload

    def _save_session(self) -> int | None:
        total, lines = self._session_payload()
        if not lines:
            QMessageBox.warning(self, "История расчётов", "Нет строк для сохранения.")
            return None
        cid = self._client.currentData()
        sid = calculation_sessions.create(
            self._conn,
            quote_date_iso=iso(self._quote_date()),
            client_id=int(cid) if cid is not None else None,
            total=total,
            details={
                "total_rows": len(lines),
                "prepay_pct": self._prepay_pct(),
                "total_boxes": self._calc_total_boxes(),
            },
            lines=lines,
        )
        audit.log(self._conn, "create", "calculation_session", str(sid))
        return sid

    def _save_session_action(self) -> None:
        sid = self._save_session()
        if sid is not None:
            QMessageBox.information(self, "История расчётов", f"Сессия сохранена: #{sid}")

    # ─────────────────────────────────────────────────────────
    # Сбор строк для RUS.xlsx
    # ─────────────────────────────────────────────────────────

    def _collect_rus_lines(self) -> list[RusLine]:
        qd = self._quote_date()
        client_pct = self._client_type_pct()
        total_boxes = self._calc_total_boxes()
        out: list[RusLine] = []

        for r in range(self._table.rowCount()):
            if self._is_bonus_row(r):
                pid_it = self._table.item(r, _C_PID)
                qty_it = self._table.item(r, _C_QTY)
                try:
                    bp   = products.get(self._conn, int(pid_it.text())) if pid_it else None
                    bqty = float(qty_it.text()) if qty_it else 0.0
                except (ValueError, TypeError):
                    bp, bqty = None, 0.0
                if bp:
                    out.append(RusLine(
                        external_id=bp.external_id or "",
                        box_barcode=bp.box_barcode,
                        name=bp.name, unit=bp.unit or "кор",
                        qty=bqty, base_price=0.0,
                        regular_price_per_box=0.0, regular_price_per_piece=0.0,
                        discount_percent=0.0, line_total=0.0,
                        units_per_box=bp.units_per_box,
                        boxes_per_pallet=bp.boxes_per_pallet,
                        gross_weight_kg=bp.gross_weight_kg,
                        volume_m3=bp.volume_m3,
                        boxes_in_row=getattr(bp, "boxes_in_row", 0),
                        rows_per_pallet=getattr(bp, "rows_per_pallet", 0),
                        pallet_height_mm=getattr(bp, "pallet_height_mm", 0),
                        box_dimensions=getattr(bp, "box_dimensions", ""),
                        is_bonus=True,
                    ))
                continue

            w = self._table.cellWidget(r, _C_NAME)
            if not isinstance(w, QComboBox):
                continue
            pid = w.currentData()
            p = products.get(self._conn, int(pid)) if pid is not None else None
            if not p:
                continue
            qty_it = self._table.item(r, _C_QTY)
            try:
                qty = float((qty_it.text().strip() if qty_it else "1").replace(",", "."))
            except ValueError:
                qty = 0.0
            promo = promotions.get_for_product(self._conn, p.id)
            vf    = parse_iso(promo.valid_from_iso) if promo else None
            vt    = parse_iso(promo.valid_to_iso)   if promo else None
            disc  = promo.discount_percent           if promo else 0.0
            mr    = self._get_matrix_rules(promo)
            pd    = self._prepay_discount_for(mr)
            vd    = self._volume_discount_for(mr, total_boxes)
            prd   = self._product_discount_for(mr)
            promo_disc = disc if (vf and vt and vf <= qd <= vt and disc > 0) else 0.0
            total_disc = min(promo_disc + client_pct + pd + vd + prd, 100.0)

            sub = line_total(
                p.base_price, qty, disc, qd, vf, vt,
                client_type_pct=client_pct,
                prepay_pct=pd, volume_pct=vd, product_pct=prd,
            )

            export_mr = dict(mr)
            if pd  > 0: export_mr["_applied_prepay_pct"]  = pd
            if vd  > 0: export_mr["_applied_volume_pct"]  = vd
            if prd > 0: export_mr["_applied_product_pct"] = prd

            out.append(RusLine(
                external_id=p.external_id or "",
                box_barcode=p.box_barcode,
                name=p.name, unit=p.unit or "кор",
                qty=qty,
                regular_price_per_box=p.base_price,
                regular_price_per_piece=(
                    p.regular_piece_price if p.regular_piece_price > 0
                    else (p.base_price / p.units_per_box if p.units_per_box > 0 else 0.0)
                ),
                units_per_box=p.units_per_box,
                boxes_per_pallet=p.boxes_per_pallet,
                gross_weight_kg=p.gross_weight_kg,
                volume_m3=p.volume_m3,
                boxes_in_row=getattr(p, "boxes_in_row", 0),
                rows_per_pallet=getattr(p, "rows_per_pallet", 0),
                pallet_height_mm=getattr(p, "pallet_height_mm", 0),
                box_dimensions=getattr(p, "box_dimensions", ""),
                base_price=p.base_price,
                discount_percent=total_disc,
                line_total=sub,
                matrix_rules=export_mr,
            ))
        return out

    # ─────────────────────────────────────────────────────────
    # Экспорт
    # ─────────────────────────────────────────────────────────

    def _export_txt(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить", "", "Текст (*.txt)")
        if not path:
            return
        Path(path).write_text(self._build_text(), encoding="utf-8")
        self._save_session()
        audit.log(self._conn, "export", "quote_txt", path)
        QMessageBox.information(self, "Готово", "Файл сохранён.")

    def _export_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить PDF", "quote.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            export_quote_pdf(Path(path), self._build_text())
            self._save_session()
            audit.log(self._conn, "export", "quote_pdf", path)
            QMessageBox.information(self, "Готово", "PDF сохранён.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Ошибка", str(e))

    def _export_rus(self) -> None:
        order_no = self._order_no.text().strip() or "1"
        path, _ = QFileDialog.getSaveFileName(
            self, "Сформировать RUS.xlsx", f"RUS{order_no}.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            export_rus_variant_a(
                Path(path),
                client=self._current_client(),
                quote_date=self._quote_date(),
                delivery_date=self._delivery_date_value(),
                lines=self._collect_rus_lines(),
                order_no=order_no,
            )
            self._save_session()
            audit.log(self._conn, "export", "rus_xlsx", path)
            # Инкрементируем счётчик заказов
            try:
                next_no = str(int(order_no) + 1)
            except ValueError:
                next_no = order_no
            settings_repo.set_value(self._conn, "next_order_no", next_no)
            self._order_no.setText(next_no)
            QMessageBox.information(self, "Готово", f"RUS{order_no}.xlsx сформирован.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Ошибка", str(e))

    def _send_mail(self) -> None:
        to_s, ok = QInputDialog.getText(self, "E-mail", "Адрес получателя:")
        if not ok or not to_s.strip():
            return
        body = self._build_text()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(body)
            tmp_path = Path(f.name)
        try:
            email_send.send_with_attachment(
                self._conn, [to_s.strip()], "Расчёт из CRM", body, tmp_path,
            )
            self._save_session()
            audit.log(self._conn, "email", "quote", to_s.strip())
            QMessageBox.information(self, "Готово", "Письмо отправлено.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Ошибка", str(e))
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass