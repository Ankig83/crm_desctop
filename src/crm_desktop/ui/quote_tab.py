from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
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
from crm_desktop.repositories import audit, calculation_sessions, clients, products, promotions
from crm_desktop.services import email_send
from crm_desktop.services.pricing import line_total
from crm_desktop.utils.dates import iso, parse_dmY, parse_iso


class QuoteTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._block = False
        self._client = QComboBox()
        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("dd.MM.yyyy")
        self._date.setDate(QDate.currentDate())
        self._date.dateChanged.connect(lambda *_: self._recalc())

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["ID", "Товар", "Цена", "Кол-во", "Сумма"])
        self._table.hideColumn(0)
        self._table.cellChanged.connect(self._on_changed)

        self._total = QLabel("0.00")

        btn_line = QPushButton("Строка")
        btn_line.clicked.connect(self._add_line)
        btn_del = QPushButton("Удалить строку")
        btn_del.clicked.connect(self._del_line)
        btn_calc = QPushButton("Пересчитать")
        btn_calc.clicked.connect(self._recalc)
        btn_export = QPushButton("Сохранить расчёт (TXT)…")
        btn_export.clicked.connect(self._export_txt)
        btn_export_pdf = QPushButton("Сохранить расчёт (PDF)…")
        btn_export_pdf.clicked.connect(self._export_pdf)
        btn_export_rus = QPushButton("Сформировать RUS.xlsx…")
        btn_export_rus.clicked.connect(self._export_rus)
        btn_save_session = QPushButton("Сохранить в историю")
        btn_save_session.clicked.connect(self._save_session_action)
        btn_mail = QPushButton("Отправить на e-mail…")
        btn_mail.clicked.connect(self._send_mail)

        row = QHBoxLayout()
        for b in (btn_line, btn_del, btn_calc, btn_export, btn_export_pdf, btn_export_rus, btn_save_session, btn_mail):
            row.addWidget(b)
        row.addStretch()

        grid = QGridLayout()
        grid.addWidget(QLabel("Клиент:"), 0, 0)
        grid.addWidget(self._client, 0, 1)
        grid.addWidget(QLabel("Дата расчёта:"), 0, 2)
        grid.addWidget(self._date, 0, 3)

        lay = QVBoxLayout(self)
        lay.addLayout(grid)
        lay.addLayout(row)
        lay.addWidget(self._table)
        lay.addWidget(QLabel("Итого:"))
        lay.addWidget(self._total)
        self.reload_clients()
        self._add_line()

    def reload_clients(self) -> None:
        self._client.clear()
        for c in clients.list_all(self._conn):
            self._client.addItem(f"{c.name} (ИНН {c.inn or '—'})", c.id)

    def _add_line(self) -> None:
        self._block = True
        r = self._table.rowCount()
        self._table.insertRow(r)
        combo = QComboBox()
        for p in products.list_all(self._conn):
            combo.addItem(p.name, p.id)
        self._table.setCellWidget(r, 1, combo)
        combo.currentIndexChanged.connect(lambda *_: self._recalc())
        self._table.setItem(r, 0, QTableWidgetItem(""))
        self._table.setItem(r, 2, QTableWidgetItem("0"))
        self._table.setItem(r, 3, QTableWidgetItem("1"))
        self._table.setItem(r, 4, QTableWidgetItem("0"))
        self._sync_pid_for_row(r)
        self._block = False
        self._recalc()

    def _sync_pid_for_row(self, r: int) -> None:
        w = self._table.cellWidget(r, 1)
        if not isinstance(w, QComboBox):
            return
        pid = w.currentData()
        it = self._table.item(r, 0)
        if it is None:
            self._table.setItem(r, 0, QTableWidgetItem(str(pid or "")))
        else:
            it.setText(str(pid or ""))
        p = products.get(self._conn, int(pid)) if pid is not None else None
        price_it = self._table.item(r, 2)
        if price_it and p:
            price_it.setText(str(p.base_price))

    def _del_line(self) -> None:
        r = self._table.currentRow()
        if r >= 0:
            self._table.removeRow(r)
            self._recalc()

    def _on_changed(self, row: int, col: int) -> None:
        if self._block:
            return
        if col == 3:
            self._recalc()

    def _quote_date(self):
        q = self._date.date()
        return parse_dmY(f"{q.day():02d}.{q.month():02d}.{q.year():04d}")

    def _recalc(self) -> None:
        self._block = True
        qd = self._quote_date()
        total = 0.0
        for r in range(self._table.rowCount()):
            w = self._table.cellWidget(r, 1)
            if not isinstance(w, QComboBox):
                continue
            self._sync_pid_for_row(r)
            pid = w.currentData()
            p = products.get(self._conn, int(pid)) if pid is not None else None
            if not p:
                continue
            qty_it = self._table.item(r, 3)
            qty_s = qty_it.text().strip() if qty_it else "1"
            try:
                qty = float(qty_s.replace(",", "."))
            except ValueError:
                qty = 0.0
            promo = promotions.get_for_product(self._conn, p.id)
            vf = parse_iso(promo.valid_from_iso) if promo else None
            vt = parse_iso(promo.valid_to_iso) if promo else None
            disc = promo.discount_percent if promo else 0.0
            sub = line_total(p.base_price, qty, disc, qd, vf, vt)
            total += sub
            sum_it = self._table.item(r, 4)
            if sum_it:
                sum_it.setText(f"{sub:.2f}")
            pr_it = self._table.item(r, 2)
            if pr_it:
                pr_it.setText(str(p.base_price))
        self._total.setText(f"{total:.2f}")
        self._block = False

    def _build_text(self) -> str:
        lines: list[str] = []
        q = self._date.date()
        lines.append(f"Дата расчёта: {q.day():02d}.{q.month():02d}.{q.year():04d}")
        cid = self._client.currentData()
        c = clients.get(self._conn, int(cid)) if cid is not None else None
        lines.append(f"Клиент: {c.name if c else '—'}")
        lines.append(f"ИНН: {c.inn if c else '—'}")
        lines.append("")
        qd = self._quote_date()
        grand = 0.0
        for r in range(self._table.rowCount()):
            w = self._table.cellWidget(r, 1)
            if not isinstance(w, QComboBox):
                continue
            pid = w.currentData()
            p = products.get(self._conn, int(pid)) if pid is not None else None
            if not p:
                continue
            qty_it = self._table.item(r, 3)
            qty_s = qty_it.text().strip() if qty_it else "1"
            try:
                qty = float(qty_s.replace(",", "."))
            except ValueError:
                qty = 0.0
            promo = promotions.get_for_product(self._conn, p.id)
            vf = parse_iso(promo.valid_from_iso) if promo else None
            vt = parse_iso(promo.valid_to_iso) if promo else None
            disc = promo.discount_percent if promo else 0.0
            sub = line_total(p.base_price, qty, disc, qd, vf, vt)
            grand += sub
            lines.append(f"{p.name} × {qty} = {sub:.2f}")
        lines.append("")
        lines.append(f"Итого: {grand:.2f}")
        return "\n".join(lines)

    def _session_payload(self) -> tuple[float, list[calculation_sessions.SessionLine]]:
        qd = self._quote_date()
        total = 0.0
        payload: list[calculation_sessions.SessionLine] = []
        for r in range(self._table.rowCount()):
            w = self._table.cellWidget(r, 1)
            if not isinstance(w, QComboBox):
                continue
            pid = w.currentData()
            p = products.get(self._conn, int(pid)) if pid is not None else None
            if not p:
                continue
            qty_it = self._table.item(r, 3)
            qty_s = qty_it.text().strip() if qty_it else "1"
            try:
                qty = float(qty_s.replace(",", "."))
            except ValueError:
                qty = 0.0
            promo = promotions.get_for_product(self._conn, p.id)
            vf = parse_iso(promo.valid_from_iso) if promo else None
            vt = parse_iso(promo.valid_to_iso) if promo else None
            disc = promo.discount_percent if promo else 0.0
            applied_disc = disc if (vf and vt and vf <= qd <= vt and disc > 0) else 0.0
            sub = line_total(p.base_price, qty, disc, qd, vf, vt)
            total += sub
            payload.append(
                calculation_sessions.SessionLine(
                    product_id=p.id,
                    product_external_id=p.external_id or "",
                    product_name=p.name,
                    qty=qty,
                    base_price=p.base_price,
                    discount_percent=applied_disc,
                    line_total=sub,
                )
            )
        return total, payload

    def _save_session(self) -> int | None:
        total, lines = self._session_payload()
        if not lines:
            QMessageBox.warning(self, "История расчётов", "Нет строк расчёта для сохранения.")
            return None
        cid = self._client.currentData()
        sid = calculation_sessions.create(
            self._conn,
            quote_date_iso=iso(self._quote_date()),
            client_id=int(cid) if cid is not None else None,
            total=total,
            details={"total_rows": len(lines)},
            lines=lines,
        )
        audit.log(self._conn, "create", "calculation_session", str(sid))
        return sid

    def _save_session_action(self) -> None:
        sid = self._save_session()
        if sid is not None:
            QMessageBox.information(self, "История расчётов", f"Сессия сохранена: #{sid}")

    def _collect_rus_lines(self) -> list[RusLine]:
        qd = self._quote_date()
        out: list[RusLine] = []
        for r in range(self._table.rowCount()):
            w = self._table.cellWidget(r, 1)
            if not isinstance(w, QComboBox):
                continue
            pid = w.currentData()
            p = products.get(self._conn, int(pid)) if pid is not None else None
            if not p:
                continue
            qty_it = self._table.item(r, 3)
            qty_s = qty_it.text().strip() if qty_it else "1"
            try:
                qty = float(qty_s.replace(",", "."))
            except ValueError:
                qty = 0.0
            promo = promotions.get_for_product(self._conn, p.id)
            vf = parse_iso(promo.valid_from_iso) if promo else None
            vt = parse_iso(promo.valid_to_iso) if promo else None
            disc = promo.discount_percent if promo else 0.0
            sub = line_total(p.base_price, qty, disc, qd, vf, vt)
            matrix_rules: dict[str, str | int | float] = {}
            if promo and promo.matrix_rules_json:
                try:
                    raw_rules = json.loads(promo.matrix_rules_json)
                    if isinstance(raw_rules, dict):
                        matrix_rules = {str(k): v for k, v in raw_rules.items()}
                except Exception:  # noqa: BLE001
                    matrix_rules = {}
            out.append(
                RusLine(
                    external_id=p.external_id or "",
                    box_barcode=p.box_barcode,
                    name=p.name,
                    unit=p.unit or "кор",
                    qty=qty,
                    regular_price_per_box=p.base_price,
                    regular_price_per_piece=(
                        p.regular_piece_price
                        if p.regular_piece_price > 0
                        else (p.base_price / p.units_per_box if p.units_per_box > 0 else 0.0)
                    ),
                    units_per_box=p.units_per_box,
                    boxes_per_pallet=p.boxes_per_pallet,
                    gross_weight_kg=p.gross_weight_kg,
                    volume_m3=p.volume_m3,
                    base_price=p.base_price,
                    discount_percent=disc if (vf and vt and vf <= qd <= vt and disc > 0) else 0.0,
                    line_total=sub,
                    matrix_rules=matrix_rules,
                )
            )
        return out

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
        path, _ = QFileDialog.getSaveFileName(self, "Сформировать RUS.xlsx", "RUS.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        cid = self._client.currentData()
        client = clients.get(self._conn, int(cid)) if cid is not None else None
        try:
            export_rus_variant_a(
                Path(path),
                client=client,
                quote_date=self._quote_date(),
                lines=self._collect_rus_lines(),
            )
            self._save_session()
            audit.log(self._conn, "export", "rus_xlsx", path)
            QMessageBox.information(self, "Готово", "RUS.xlsx сформирован.")
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
                self._conn,
                [to_s.strip()],
                "Расчёт из CRM",
                body,
                tmp_path,
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
