from __future__ import annotations

import json
import sqlite3

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crm_desktop.repositories import audit, products, promotions
from crm_desktop.utils.bonus_ids import (
    missing_product_external_ids,
    normalize_product_external_ids_csv,
    parse_product_external_ids_csv,
)
from crm_desktop.utils.dates import format_dmY, iso, parse_dmY, parse_iso


class _ProductPickerDialog(QDialog):
    """Диалог выбора товаров по артикулу/названию.

    multi=False → одиночный выбор (для колонки «Конкретный»).
    multi=True  → множественный выбор (для колонки «На выбор»).
    preselected → список артикулов, которые нужно отметить сразу.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        multi: bool = False,
        preselected: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Выбор товара" if not multi else "Выбор товаров (можно несколько)")
        self.setMinimumSize(460, 400)

        self._all_products = products.list_all(conn)
        pre = set(preselected or [])

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Двойной клик или Enter — подтвердить выбор."
            if not multi else
            "Отмечайте товары кликом (Ctrl+клик для снятия). Затем нажмите OK."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Поиск по артикулу или названию…")
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection if multi
            else QListWidget.SelectionMode.SingleSelection
        )
        layout.addWidget(self._list)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._populate(self._all_products, pre)

        # Двойной клик по строке сразу подтверждает (удобно для одиночного выбора)
        if not multi:
            self._list.itemDoubleClicked.connect(lambda _: self.accept())

    # ── внутренние методы ──────────────────────────────────────────

    def _populate(self, prods: list, preselected: set[str]) -> None:
        self._list.clear()
        for p in prods:
            ext = p.external_id or ""
            label = f"{ext or '—':>10}   {p.name}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ext)
            self._list.addItem(item)
            if ext and ext in preselected:
                item.setSelected(True)
        # Прокручиваем к первому выделенному элементу
        sel = self._list.selectedItems()
        if sel:
            self._list.scrollToItem(sel[0])

    def _filter(self, text: str) -> None:
        txt = text.strip().lower()
        pre = {
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._list.selectedItems()
        }
        filtered = [
            p for p in self._all_products
            if txt in (p.name or "").lower() or txt in (p.external_id or "").lower()
        ] if txt else self._all_products
        self._populate(filtered, pre)

    # ── публичный результат ────────────────────────────────────────

    def selected_ids(self) -> list[str]:
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._list.selectedItems()
            if item.data(Qt.ItemDataRole.UserRole)
        ]


def _hsep() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


class PromotionsTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._loading = False
        self._current_product_id: int | None = None

        # ── Левая панель: список акций ────────────────────────
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)

        # ── Правая панель: редактирование ────────────────────

        # — Базовые поля —
        self._product = QComboBox()
        self._disc = QLineEdit()
        self._disc.setPlaceholderText("Процент, например 10")
        self._disc.setToolTip("Базовая скидка в % для этой акции (поле promotions.discount_percent).")
        self._d1 = QDateEdit()
        self._d2 = QDateEdit()
        for d in (self._d1, self._d2):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd.MM.yyyy")
            d.setDate(QDate.currentDate())

        self._no_d1 = QCheckBox("Бессрочно (без даты начала)")
        self._no_d1.setToolTip("Акция действует с самого начала, без ограничения по дате старта.")
        self._no_d1.toggled.connect(lambda v: self._d1.setEnabled(not v))

        self._no_d2 = QCheckBox("Бессрочно (без даты окончания)")
        self._no_d2.setToolTip("Акция действует бессрочно — без даты завершения.")
        self._no_d2.toggled.connect(lambda v: self._d2.setEnabled(not v))

        self._disc_err = QLabel("")
        self._disc_err.setStyleSheet("color:#c0392b; font-size:9pt;")
        self._disc_err.hide()
        self._disc.textChanged.connect(lambda _: self._clear_field_error(self._disc, self._disc_err))

        basic_form = QFormLayout()
        basic_form.addRow("Товар:", self._product)
        basic_form.addRow("Базовая скидка %:", self._disc)
        basic_form.addRow("", self._disc_err)
        basic_form.addRow("Дата начала:", self._d1)
        basic_form.addRow("", self._no_d1)
        basic_form.addRow("Дата окончания:", self._d2)
        basic_form.addRow("", self._no_d2)

        # ── QGroupBox: Продуктовая скидка ────────────────────
        self._expiry_pct = QDoubleSpinBox()
        self._expiry_pct.setRange(0, 100)
        self._expiry_pct.setDecimals(2)
        self._expiry_pct.setSuffix(" %")
        self._expiry_pct.setToolTip(
            "Продуктовая скидка в % (expiry_pct). Применяется к этому товару всегда при > 0, "
            "независимо от условий предоплаты или объёма."
        )
        self._expiry_rub = QDoubleSpinBox()
        self._expiry_rub.setRange(0, 100)
        self._expiry_rub.setDecimals(2)
        self._expiry_rub.setSuffix(" %")
        self._expiry_rub.setToolTip(
            "Скидка за срок годности в %. "
            "Применяется к товарам с коротким сроком годности. "
            "Отражается в колонке «Доп. скидка» файла RUS.xlsx."
        )
        self._floor_pct = QDoubleSpinBox()
        self._floor_pct.setRange(0, 100)
        self._floor_pct.setDecimals(1)
        self._floor_pct.setSuffix(" %")
        self._floor_pct.setToolTip(
            "Минимальная цена в % от базовой цены товара.\n"
            "Если после применения ВСЕХ скидок цена за штуку опускается ниже этого порога — "
            "программа автоматически поднимает её до указанного минимума.\n"
            "Пример: 80 → цена никогда не будет ниже 80% от базовой."
        )

        gb_expiry = QGroupBox("Продуктовая скидка")
        expiry_form = QFormLayout(gb_expiry)
        expiry_form.addRow("Скидка %:", self._expiry_pct)
        expiry_form.addRow("Срок годности %:", self._expiry_rub)
        expiry_form.addRow("Не ниже % от базовой:", self._floor_pct)

        # ── QGroupBox: Акционные бонусы (динамическая таблица) ──
        gb_promo = QGroupBox("Акционные бонусы (купи → получи бесплатно)")
        promo_lay = QVBoxLayout(gb_promo)
        promo_lay.addWidget(QLabel(
            "Задайте правила: порог покупки → что дать бесплатно.\n"
            "«Конкретный товар» добавляется автоматически. «На выбор» — менеджер выбирает в расчёте."
        ))

        self._bonus_table = QTableWidget(0, 5)
        self._bonus_table.setHorizontalHeaderLabels([
            "Порог (кор)", "Тот же +кор", "Конкретный (арт.)", "Кол-во", "На выбор (арт., запятая)",
        ])
        self._bonus_table.setMinimumHeight(130)
        self._bonus_table.setColumnWidth(0, 85)
        self._bonus_table.setColumnWidth(1, 85)
        self._bonus_table.setColumnWidth(2, 130)
        self._bonus_table.setColumnWidth(3, 60)
        self._bonus_table.horizontalHeader().setStretchLastSection(True)
        self._bonus_table.setToolTip(
            "Порог       — мин. кол-во коробок для активации бонуса.\n"
            "Тот же      — бесплатных кор. ТОГО ЖЕ товара.\n"
            "Конкретный  — двойной клик → выбрать товар из каталога.\n"
            "Кол-во      — сколько коробок конкретного товара.\n"
            "На выбор    — двойной клик → выбрать несколько товаров из каталога."
        )
        self._bonus_table.cellDoubleClicked.connect(self._on_bonus_cell_dblclick)

        btn_add_bonus = QPushButton("+ Правило")
        btn_del_bonus = QPushButton("− Удалить")
        btn_add_bonus.setMaximumWidth(90)
        btn_del_bonus.setMaximumWidth(90)
        btn_add_bonus.clicked.connect(self._bonus_add_row)
        btn_del_bonus.clicked.connect(lambda: self._table_del_row(self._bonus_table))

        bonus_btns = QHBoxLayout()
        bonus_btns.addWidget(btn_add_bonus)
        bonus_btns.addWidget(btn_del_bonus)
        bonus_btns.addStretch()

        promo_lay.addWidget(self._bonus_table)
        promo_lay.addLayout(bonus_btns)

        # Даты акционных бонусов
        promo_lay.addWidget(_hsep())
        promo_lay.addWidget(QLabel("Период действия бонусной акции:"))

        self._promo_date_from = QDateEdit()
        self._promo_date_from.setCalendarPopup(True)
        self._promo_date_from.setDisplayFormat("dd.MM.yyyy")
        self._promo_date_from.setDate(QDate.currentDate())
        self._promo_no_start = QCheckBox("Без даты начала (сразу активно)")
        self._promo_no_start.toggled.connect(lambda v: self._promo_date_from.setEnabled(not v))

        self._promo_date_to = QDateEdit()
        self._promo_date_to.setCalendarPopup(True)
        self._promo_date_to.setDisplayFormat("dd.MM.yyyy")
        self._promo_date_to.setDate(QDate(QDate.currentDate().year(), 12, 31))
        self._promo_no_end = QCheckBox("Бессрочно (без даты окончания)")
        self._promo_no_end.toggled.connect(lambda v: self._promo_date_to.setEnabled(not v))

        dates_form = QFormLayout()
        dates_form.addRow("Дата начала:", self._promo_date_from)
        dates_form.addRow("", self._promo_no_start)
        dates_form.addRow("Дата окончания:", self._promo_date_to)
        dates_form.addRow("", self._promo_no_end)
        promo_lay.addLayout(dates_form)

        # ── Кнопки ───────────────────────────────────────────
        btn_save = QPushButton("Сохранить акцию для выбранного товара")
        btn_save.setStyleSheet("font-weight: bold;")
        btn_save.clicked.connect(self._save)
        btn_new = QPushButton("Новая акция (выберите товар)")
        btn_new.clicked.connect(self._new_promo)
        btn_del = QPushButton("Удалить акцию")
        btn_del.clicked.connect(self._delete)

        btns_row = QHBoxLayout()
        btns_row.addWidget(btn_save)
        btns_row.addWidget(btn_new)
        btns_row.addWidget(btn_del)
        btns_row.addStretch()

        # ── Сборка правой панели со скроллом ─────────────────
        right_inner = QVBoxLayout()
        right_inner.setSpacing(8)
        title = QLabel("Редактирование акции")
        title.setStyleSheet("font-size: 11pt; font-weight: bold;")
        right_inner.addWidget(title)
        right_inner.addLayout(basic_form)
        right_inner.addWidget(_hsep())
        right_inner.addWidget(gb_expiry)
        right_inner.addWidget(gb_promo)
        right_inner.addLayout(btns_row)
        right_inner.addStretch()

        right_widget = QWidget()
        right_widget.setLayout(right_inner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(right_widget)

        split = QSplitter()
        split.addWidget(self._list)
        split.addWidget(scroll)
        split.setStretchFactor(1, 1)

        lay = QVBoxLayout(self)
        lay.addWidget(split)
        self.reload()

    # ─────────────────────────────────────────────────────────
    # Служебные: таблицы порогов
    # ─────────────────────────────────────────────────────────

    # ── подсветка ошибок ──────────────────────────────────────────────

    @staticmethod
    def _mark_field_error(widget: QWidget, label: QLabel, msg: str) -> None:
        widget.setStyleSheet("border: 2px solid #e74c3c; background:#fff5f5;")
        label.setText(msg)
        label.show()

    @staticmethod
    def _clear_field_error(widget: QWidget, label: QLabel) -> None:
        widget.setStyleSheet("")
        label.hide()

    def _table_del_row(self, table: QTableWidget) -> None:
        r = table.currentRow()
        if r >= 0:
            table.removeRow(r)

    # ─────────────────────────────────────────────────────────
    # Сбор / загрузка matrix_rules из/в UI
    # ─────────────────────────────────────────────────────────

    def _collect_matrix_rules(self) -> dict:
        mr: dict = {}

        # Продуктовая скидка
        epct = self._expiry_pct.value()
        erub = self._expiry_rub.value()
        floor_pct = self._floor_pct.value()
        if epct > 0:
            mr["expiry_pct"] = epct
        if erub > 0:
            mr["expiry_rub"] = erub
        if floor_pct > 0:
            mr["price_floor_pct"] = floor_pct

        # Акционные бонусы → JSON-массив правил
        bonus_rules = []
        for row in range(self._bonus_table.rowCount()):
            def _cell(col: int) -> str:
                it = self._bonus_table.item(row, col)
                return it.text().strip() if it else ""
            try:
                threshold = float(_cell(0) or 0)
            except ValueError:
                continue
            if threshold <= 0:
                continue
            try:
                same_qty = int(float(_cell(1) or 0))
            except ValueError:
                same_qty = 0
            fixed_id = _cell(2)
            try:
                fixed_qty = max(1, int(float(_cell(3) or 1)))
            except ValueError:
                fixed_qty = 1
            choice_ids = normalize_product_external_ids_csv(_cell(4))
            bonus_rules.append({
                "threshold": threshold,
                "same_qty": same_qty,
                "fixed_id": fixed_id,
                "fixed_qty": fixed_qty,
                "choice_ids": choice_ids,
            })
        if bonus_rules:
            mr["bonus_rules"] = json.dumps(bonus_rules, ensure_ascii=False)

        # Даты акционных бонусов
        if not self._promo_no_start.isChecked():
            q = self._promo_date_from.date()
            d_from = parse_dmY(f"{q.day():02d}.{q.month():02d}.{q.year():04d}")
            mr["promo_date_from"] = iso(d_from)

        if not self._promo_no_end.isChecked():
            q = self._promo_date_to.date()
            d_to = parse_dmY(f"{q.day():02d}.{q.month():02d}.{q.year():04d}")
            mr["promo_date_to"] = iso(d_to)

        return mr

    def _load_matrix_rules(self, mr: dict) -> None:
        """Загружает matrix_rules в поля UI."""
        # Продуктовая скидка
        try:
            self._expiry_pct.setValue(float(mr.get("expiry_pct", 0) or 0))
        except (ValueError, TypeError):
            self._expiry_pct.setValue(0.0)
        try:
            self._expiry_rub.setValue(float(mr.get("expiry_rub", 0) or 0))
        except (ValueError, TypeError):
            self._expiry_rub.setValue(0.0)
        try:
            self._floor_pct.setValue(float(mr.get("price_floor_pct", 0) or 0))
        except (ValueError, TypeError):
            self._floor_pct.setValue(0.0)

        # Акционные бонусы — новый формат bonus_rules, fallback на старый promo_*_qty
        self._bonus_table.setRowCount(0)
        if "bonus_rules" in mr:
            try:
                for rule in json.loads(str(mr["bonus_rules"])):
                    self._bonus_table_insert(
                        str(rule.get("threshold", "")),
                        str(rule.get("same_qty", "0")),
                        str(rule.get("fixed_id", "")),
                        str(rule.get("fixed_qty", "1")),
                        str(rule.get("choice_ids", "")),
                    )
            except Exception:  # noqa: BLE001
                pass
        else:
            # Старый формат: promo_N_M_qty
            for name in sorted(
                key[len("promo_"):-len("_qty")]
                for key in mr
                if key.startswith("promo_") and key.endswith("_qty")
            ):
                parts = name.split("_")
                try:
                    thr = str(int(float(parts[0])))
                except (ValueError, IndexError):
                    continue
                try:
                    same = str(int(float(mr.get(f"promo_{name}_qty", 0) or 0)))
                except (ValueError, TypeError):
                    same = "0"
                ids = str(mr.get(f"promo_{name}_ids", "") or "")
                self._bonus_table_insert(thr, same, "", "1", ids)

        # Даты акционных бонусов
        from_s = str(mr.get("promo_date_from", "") or "")
        to_s   = str(mr.get("promo_date_to",   "") or "")

        if from_s:
            self._promo_no_start.setChecked(False)
            try:
                d = parse_iso(from_s)
                self._promo_date_from.setDate(QDate(d.year, d.month, d.day))
                self._promo_date_from.setEnabled(True)
            except Exception:  # noqa: BLE001
                pass
        else:
            self._promo_no_start.setChecked(True)
            self._promo_date_from.setEnabled(False)

        if to_s:
            self._promo_no_end.setChecked(False)
            try:
                d = parse_iso(to_s)
                self._promo_date_to.setDate(QDate(d.year, d.month, d.day))
                self._promo_date_to.setEnabled(True)
            except Exception:  # noqa: BLE001
                pass
        else:
            self._promo_no_end.setChecked(True)
            self._promo_date_to.setEnabled(False)

    def _clear_matrix_rules_ui(self) -> None:
        self._expiry_pct.setValue(0.0)
        self._expiry_rub.setValue(0.0)
        self._floor_pct.setValue(0.0)
        self._bonus_table.setRowCount(0)
        self._promo_no_start.setChecked(True)
        self._promo_no_end.setChecked(True)
        self._promo_date_from.setEnabled(False)
        self._promo_date_to.setEnabled(False)

    def _bonus_add_row(self) -> None:
        self._bonus_table_insert("50", "0", "", "1", "")

    def _on_bonus_cell_dblclick(self, row: int, col: int) -> None:
        """Двойной клик по «Конкретный» (col 2) или «На выбор» (col 4) — открыть подборщик товаров."""
        if col not in (2, 4):
            return
        multi = col == 4
        it = self._bonus_table.item(row, col)
        existing_text = it.text().strip() if it else ""
        pre = [s.strip() for s in existing_text.split(",") if s.strip()] if existing_text else []

        dlg = _ProductPickerDialog(self._conn, multi=multi, preselected=pre, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        ids = dlg.selected_ids()
        if not ids:
            return

        if col == 2:
            # Конкретный артикул — один товар, берём первый выбранный
            self._bonus_table.setItem(row, col, QTableWidgetItem(ids[0]))
        else:
            # На выбор — несколько, через запятую
            self._bonus_table.setItem(row, col, QTableWidgetItem(", ".join(ids)))

    def _bonus_table_insert(
        self, threshold: str, same_qty: str, fixed_id: str, fixed_qty: str, choice_ids: str
    ) -> None:
        r = self._bonus_table.rowCount()
        self._bonus_table.insertRow(r)
        self._bonus_table.setItem(r, 0, QTableWidgetItem(threshold))
        self._bonus_table.setItem(r, 1, QTableWidgetItem(same_qty))
        self._bonus_table.setItem(r, 2, QTableWidgetItem(fixed_id))
        self._bonus_table.setItem(r, 3, QTableWidgetItem(fixed_qty))
        self._bonus_table.setItem(r, 4, QTableWidgetItem(choice_ids))

    # ─────────────────────────────────────────────────────────
    # Список акций
    # ─────────────────────────────────────────────────────────

    def reload(self) -> None:
        saved_pid = self._current_product_id
        # Если пользователь заполнял новую акцию (ещё не сохранял),
        # запоминаем выбранный товар в комбо, чтобы не потерять черновик
        draft_combo_pid = self._product.currentData() if saved_pid is None else None

        self._fill_product_combo(draft_combo_pid)
        self._list.clear()
        for r in promotions.list_all(self._conn):
            d1 = parse_iso(r.valid_from_iso)
            d2 = parse_iso(r.valid_to_iso)
            from_s = "∞" if (d1 and d1.year <= 1)    else format_dmY(d1)
            to_s   = "∞" if (d2 and d2.year >= 9999) else format_dmY(d2)
            label  = f"{r.product_name} — {r.discount_percent}%  ({from_s}—{to_s})"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, r.product_id)
            self._list.addItem(it)

        if saved_pid is None:
            # Черновик новой акции — не трогаем форму, список обновился в фоне
            return

        # Восстанавливаем выделение той же акции, что была открыта
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.ItemDataRole.UserRole) == saved_pid:
                self._list.setCurrentRow(i)
                return
        # Если акция была удалена — выбираем первую
        if self._list.count():
            self._list.setCurrentRow(0)

    def _fill_product_combo(self, select_pid: int | None) -> None:
        self._product.clear()
        for p in products.list_all(self._conn):
            label = f"{p.name} ({p.external_id or 'без ID'})"
            self._product.addItem(label, p.id)
        if select_pid is not None:
            idx = self._product.findData(select_pid)
            if idx >= 0:
                self._product.setCurrentIndex(idx)

    def _on_select(self, row: int) -> None:
        if self._loading:
            return
        if row < 0:
            self._current_product_id = None
            return
        it = self._list.item(row)
        if not it:
            return
        pid = it.data(Qt.ItemDataRole.UserRole)
        self._current_product_id = int(pid) if pid is not None else None
        self._load_promo(self._current_product_id)

    def _load_promo(self, product_id: int | None) -> None:
        self._loading = True
        self._fill_product_combo(product_id)
        if product_id is None:
            self._clear_matrix_rules_ui()
            self._loading = False
            return
        pr = promotions.get_for_product(self._conn, product_id)
        if pr:
            self._disc.setText(str(pr.discount_percent))
            d1 = parse_iso(pr.valid_from_iso)
            d2 = parse_iso(pr.valid_to_iso)
            # Sentinel «бессрочно»: год ≤ 1 = без даты начала, год ≥ 9999 = без окончания
            if d1 and d1.year <= 1:
                self._no_d1.setChecked(True)
                self._d1.setEnabled(False)
            else:
                self._no_d1.setChecked(False)
                self._d1.setEnabled(True)
                if d1:
                    self._d1.setDate(QDate(d1.year, d1.month, d1.day))
            if d2 and d2.year >= 9999:
                self._no_d2.setChecked(True)
                self._d2.setEnabled(False)
            else:
                self._no_d2.setChecked(False)
                self._d2.setEnabled(True)
                if d2:
                    self._d2.setDate(QDate(d2.year, d2.month, d2.day))
            # matrix_rules
            mr: dict = {}
            if pr.matrix_rules_json:
                try:
                    raw = json.loads(pr.matrix_rules_json)
                    if isinstance(raw, dict):
                        mr = {str(k): v for k, v in raw.items()}
                except Exception:  # noqa: BLE001
                    pass
            self._load_matrix_rules(mr)
        else:
            self._disc.clear()
            self._d1.setDate(QDate.currentDate())
            self._d2.setDate(QDate.currentDate())
            self._clear_matrix_rules_ui()
        self._loading = False

    # ─────────────────────────────────────────────────────────
    # Сохранение
    # ─────────────────────────────────────────────────────────

    def _save(self) -> None:
        if self._loading:
            return
        pid = self._product.currentData()
        if pid is None:
            return
        product_id = int(pid)

        self._clear_field_error(self._disc, self._disc_err)
        try:
            disc = float(self._disc.text().strip().replace(",", "."))
            if not (0 <= disc <= 100):
                raise ValueError
        except ValueError:
            self._mark_field_error(self._disc, self._disc_err, "Введите число от 0 до 100")
            self._disc.setFocus()
            return

        q1 = self._d1.date()
        q2 = self._d2.date()
        d1 = parse_dmY(f"{q1.day():02d}.{q1.month():02d}.{q1.year():04d}")
        d2 = parse_dmY(f"{q2.day():02d}.{q2.month():02d}.{q2.year():04d}")
        # Бессрочность: используем sentinel-даты
        if self._no_d1.isChecked():
            d1 = parse_dmY("01.01.0001") or d1
            valid_from = "0001-01-01"
        else:
            valid_from = iso(d1)
        if self._no_d2.isChecked():
            valid_to = "9999-12-31"
        else:
            valid_to = iso(d2)
            d2_check = d2
            if not self._no_d1.isChecked() and d1 > d2:
                QMessageBox.warning(self, "Период", "Дата начала не может быть позже окончания.")
                return

        # Проверяем ID бонусных товаров в таблице бонусов
        for row in range(self._bonus_table.rowCount()):
            for col in (2, 4):  # «Конкретный» и «На выбор»
                it = self._bonus_table.item(row, col)
                ids_text = it.text().strip() if it else ""
                if ids_text:
                    parsed = parse_product_external_ids_csv(ids_text)
                    if parsed:
                        miss = missing_product_external_ids(self._conn, parsed)
                        if miss:
                            col_name = "Конкретный" if col == 2 else "На выбор"
                            QMessageBox.warning(
                                self,
                                f"Бонусные товары (строка {row + 1}, {col_name})",
                                "Нет товаров с такими артикулами:\n" + ", ".join(miss),
                            )
                            return

        mr = self._collect_matrix_rules()
        mr_json = json.dumps(mr, ensure_ascii=False) if mr else ""

        promotions.upsert(
            self._conn,
            product_id,
            promo_type="",
            discount_percent=disc,
            valid_from_iso=valid_from,
            valid_to_iso=valid_to,
            bonus_other_product_ids="",
            matrix_rules_json=mr_json,
        )
        audit.log(self._conn, "upsert", "promotion", str(product_id))
        self._reload_list_only()

    # ─────────────────────────────────────────────────────────
    # Новая / удалить
    # ─────────────────────────────────────────────────────────

    def _reload_list_only(self) -> None:
        cur_pid = self._current_product_id
        self._loading = True
        self._list.clear()
        for r in promotions.list_all(self._conn):
            d1 = parse_iso(r.valid_from_iso)
            d2 = parse_iso(r.valid_to_iso)
            from_s = "∞" if (d1 and d1.year <= 1)    else format_dmY(d1)
            to_s   = "∞" if (d2 and d2.year >= 9999) else format_dmY(d2)
            label  = f"{r.product_name} — {r.discount_percent}%  ({from_s}—{to_s})"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, r.product_id)
            self._list.addItem(it)
        self._loading = False
        if cur_pid is not None:
            for i in range(self._list.count()):
                it = self._list.item(i)
                if it and it.data(Qt.ItemDataRole.UserRole) == cur_pid:
                    self._list.setCurrentRow(i)
                    break

    def _new_promo(self) -> None:
        self._loading = True
        self._list.clearSelection()
        self._current_product_id = None
        self._fill_product_combo(None)
        if self._product.count():
            self._product.setCurrentIndex(0)
        self._disc.clear()
        self._d1.setDate(QDate.currentDate())
        self._d2.setDate(QDate.currentDate())
        self._no_d1.setChecked(False)
        self._no_d2.setChecked(False)
        self._d1.setEnabled(True)
        self._d2.setEnabled(True)
        self._clear_matrix_rules_ui()
        self._loading = False

    def _delete(self) -> None:
        pid = self._product.currentData()
        if pid is None:
            return
        product_id = int(pid)
        if QMessageBox.question(
            self, "Удалить", "Удалить акцию для этого товара?"
        ) != QMessageBox.StandardButton.Yes:
            return
        promotions.delete_for_product(self._conn, product_id)
        audit.log(self._conn, "delete", "promotion", str(product_id))
        self.reload()
