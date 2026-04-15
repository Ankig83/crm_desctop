from __future__ import annotations

import json
import sqlite3

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
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
        self._ptype = QLineEdit()
        self._ptype.setPlaceholderText("Тип акции (по ТЗ)")
        self._disc = QLineEdit()
        self._disc.setPlaceholderText("Процент, например 10")
        self._disc.setToolTip("Базовая скидка в % для этой акции (поле promotions.discount_percent).")
        self._bonus_ids = QLineEdit()
        self._bonus_ids.setPlaceholderText("Например: 4,5,12 — внешние ID товаров из каталога")
        self._bonus_ids.setToolTip(
            "Товары, которые клиент может получить бонусом по акции «другой товар». "
            "Те же ID, что в колонке «ID товара» в Excel товаров. Через запятую."
        )
        self._d1 = QDateEdit()
        self._d2 = QDateEdit()
        for d in (self._d1, self._d2):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd.MM.yyyy")
            d.setDate(QDate.currentDate())

        basic_form = QFormLayout()
        basic_form.addRow("Товар:", self._product)
        basic_form.addRow("Тип акции:", self._ptype)
        basic_form.addRow("Базовая скидка %:", self._disc)
        basic_form.addRow("ID товаров-бонусов:", self._bonus_ids)
        basic_form.addRow("Дата начала:", self._d1)
        basic_form.addRow("Дата окончания:", self._d2)

        # ── QGroupBox: Скидка за предоплату ──────────────────
        self._prepay_table = QTableWidget(0, 2)
        self._prepay_table.setHorizontalHeaderLabels(["Порог предоплаты %", "Скидка %"])
        self._prepay_table.setMaximumHeight(130)
        self._prepay_table.horizontalHeader().setStretchLastSection(True)
        self._prepay_table.setToolTip(
            "Если клиент вносит предоплату ≥ порогу, применяется скидка.\n"
            "Пример: порог 25 → скидка 2% при предоплате от 25%."
        )
        btn_add_prepay = QPushButton("+ Порог")
        btn_del_prepay = QPushButton("− Удалить")
        btn_add_prepay.setMaximumWidth(90)
        btn_del_prepay.setMaximumWidth(90)
        btn_add_prepay.clicked.connect(self._prepay_add_row)
        btn_del_prepay.clicked.connect(lambda: self._table_del_row(self._prepay_table))
        prepay_btns = QHBoxLayout()
        prepay_btns.addWidget(btn_add_prepay)
        prepay_btns.addWidget(btn_del_prepay)
        prepay_btns.addStretch()

        gb_prepay = QGroupBox("Скидки за предоплату")
        prepay_lay = QVBoxLayout(gb_prepay)
        prepay_lay.addWidget(QLabel("Предоплата ≥ (%) → скидка (%)  [пример: 25 → 2]"))
        prepay_lay.addWidget(self._prepay_table)
        prepay_lay.addLayout(prepay_btns)

        # ── QGroupBox: Скидка за объём ────────────────────────
        self._volume_table = QTableWidget(0, 2)
        self._volume_table.setHorizontalHeaderLabels(["Порог (коробок)", "Скидка %"])
        self._volume_table.setMaximumHeight(130)
        self._volume_table.horizontalHeader().setStretchLastSection(True)
        self._volume_table.setToolTip(
            "Суммарное кол-во коробок в заказе ≥ порогу → применяется скидка.\n"
            "Пример: 300 кор → −6%, 500 кор → −8%."
        )
        btn_add_vol = QPushButton("+ Порог")
        btn_del_vol = QPushButton("− Удалить")
        btn_add_vol.setMaximumWidth(90)
        btn_del_vol.setMaximumWidth(90)
        btn_add_vol.clicked.connect(self._volume_add_row)
        btn_del_vol.clicked.connect(lambda: self._table_del_row(self._volume_table))
        vol_btns = QHBoxLayout()
        vol_btns.addWidget(btn_add_vol)
        vol_btns.addWidget(btn_del_vol)
        vol_btns.addStretch()

        gb_volume = QGroupBox("Скидки за объём заказа")
        vol_lay = QVBoxLayout(gb_volume)
        vol_lay.addWidget(QLabel("Коробок в заказе ≥ (шт) → скидка (%)  [пример: 300 → 6]"))
        vol_lay.addWidget(self._volume_table)
        vol_lay.addLayout(vol_btns)

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
        self._expiry_rub.setRange(0, 999_999)
        self._expiry_rub.setDecimals(2)
        self._expiry_rub.setSuffix(" руб")
        self._expiry_rub.setToolTip(
            "Дополнительная скидка в рублях (expiry_rub). "
            "Отражается в колонке «Доп. скидка (РУБ)*» файла RUS.xlsx."
        )

        gb_expiry = QGroupBox("Продуктовая скидка")
        expiry_form = QFormLayout(gb_expiry)
        expiry_form.addRow("Скидка %:", self._expiry_pct)
        expiry_form.addRow("Доп. скидка руб:", self._expiry_rub)

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
            "Конкретный  — артикул другого товара (добавляется автоматически).\n"
            "Кол-во      — сколько коробок конкретного товара.\n"
            "На выбор    — артикулы через запятую; менеджер выберет 1 в расчёте."
        )

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
        right_inner.addWidget(gb_prepay)
        right_inner.addWidget(gb_volume)
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

    def _prepay_add_row(self) -> None:
        r = self._prepay_table.rowCount()
        self._prepay_table.insertRow(r)
        self._prepay_table.setItem(r, 0, QTableWidgetItem("25"))
        self._prepay_table.setItem(r, 1, QTableWidgetItem("2"))

    def _volume_add_row(self) -> None:
        r = self._volume_table.rowCount()
        self._volume_table.insertRow(r)
        self._volume_table.setItem(r, 0, QTableWidgetItem("300"))
        self._volume_table.setItem(r, 1, QTableWidgetItem("6"))

    def _table_del_row(self, table: QTableWidget) -> None:
        r = table.currentRow()
        if r >= 0:
            table.removeRow(r)

    # ─────────────────────────────────────────────────────────
    # Сбор / загрузка matrix_rules из/в UI
    # ─────────────────────────────────────────────────────────

    def _collect_matrix_rules(self) -> dict:
        mr: dict = {}

        # Скидки за предоплату
        for r in range(self._prepay_table.rowCount()):
            thr_it = self._prepay_table.item(r, 0)
            disc_it = self._prepay_table.item(r, 1)
            if not thr_it or not disc_it:
                continue
            try:
                thr = int(float(thr_it.text().replace(",", ".").strip()))
                disc = float(disc_it.text().replace(",", ".").strip())
            except ValueError:
                continue
            if thr > 0 and disc > 0:
                mr[f"prepay_{thr}"] = disc

        # Скидки за объём
        for r in range(self._volume_table.rowCount()):
            thr_it = self._volume_table.item(r, 0)
            disc_it = self._volume_table.item(r, 1)
            if not thr_it or not disc_it:
                continue
            try:
                thr = int(float(thr_it.text().replace(",", ".").strip()))
                disc = float(disc_it.text().replace(",", ".").strip())
            except ValueError:
                continue
            if thr > 0 and disc > 0:
                mr[f"volume_{thr}"] = disc

        # Продуктовая скидка
        epct = self._expiry_pct.value()
        erub = self._expiry_rub.value()
        if epct > 0:
            mr["expiry_pct"] = epct
        if erub > 0:
            mr["expiry_rub"] = erub

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
        # Таблицы порогов
        self._prepay_table.setRowCount(0)
        self._volume_table.setRowCount(0)

        for key in sorted(mr.keys()):
            if key.startswith("prepay_"):
                try:
                    thr = float(key.split("_", 1)[1])
                    disc = float(mr[key] or 0)
                except (ValueError, IndexError):
                    continue
                r = self._prepay_table.rowCount()
                self._prepay_table.insertRow(r)
                self._prepay_table.setItem(r, 0, QTableWidgetItem(str(int(thr))))
                self._prepay_table.setItem(r, 1, QTableWidgetItem(str(disc)))

            elif key.startswith("volume_"):
                try:
                    thr = float(key.split("_", 1)[1])
                    disc = float(mr[key] or 0)
                except (ValueError, IndexError):
                    continue
                r = self._volume_table.rowCount()
                self._volume_table.insertRow(r)
                self._volume_table.setItem(r, 0, QTableWidgetItem(str(int(thr))))
                self._volume_table.setItem(r, 1, QTableWidgetItem(str(disc)))

        # Продуктовая скидка
        try:
            self._expiry_pct.setValue(float(mr.get("expiry_pct", 0) or 0))
        except (ValueError, TypeError):
            self._expiry_pct.setValue(0.0)
        try:
            self._expiry_rub.setValue(float(mr.get("expiry_rub", 0) or 0))
        except (ValueError, TypeError):
            self._expiry_rub.setValue(0.0)

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
        self._prepay_table.setRowCount(0)
        self._volume_table.setRowCount(0)
        self._expiry_pct.setValue(0.0)
        self._expiry_rub.setValue(0.0)
        self._bonus_table.setRowCount(0)
        self._promo_no_start.setChecked(True)
        self._promo_no_end.setChecked(True)
        self._promo_date_from.setEnabled(False)
        self._promo_date_to.setEnabled(False)

    def _bonus_add_row(self) -> None:
        self._bonus_table_insert("50", "0", "", "1", "")

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
        self._fill_product_combo(None)
        self._list.clear()
        for r in promotions.list_all(self._conn):
            label = (
                f"{r.product_name} — {r.discount_percent}% "
                f"({format_dmY(parse_iso(r.valid_from_iso))}—{format_dmY(parse_iso(r.valid_to_iso))})"
            )
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, r.product_id)
            self._list.addItem(it)
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
            self._ptype.setText(pr.promo_type)
            self._disc.setText(str(pr.discount_percent))
            self._bonus_ids.setText(pr.bonus_other_product_ids.replace(",", ", "))
            d1 = parse_iso(pr.valid_from_iso)
            d2 = parse_iso(pr.valid_to_iso)
            self._d1.setDate(QDate(d1.year, d1.month, d1.day))
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
            self._ptype.clear()
            self._disc.clear()
            self._bonus_ids.clear()
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

        try:
            disc = float(self._disc.text().strip().replace(",", "."))
        except ValueError:
            QMessageBox.warning(self, "Скидка", "Укажите число процента.")
            return

        q1 = self._d1.date()
        q2 = self._d2.date()
        d1 = parse_dmY(f"{q1.day():02d}.{q1.month():02d}.{q1.year():04d}")
        d2 = parse_dmY(f"{q2.day():02d}.{q2.month():02d}.{q2.year():04d}")
        if d1 > d2:
            QMessageBox.warning(self, "Период", "Дата начала не может быть позже окончания.")
            return

        bonus_norm = normalize_product_external_ids_csv(self._bonus_ids.text())
        parsed_bonus = parse_product_external_ids_csv(self._bonus_ids.text())
        if parsed_bonus:
            miss = missing_product_external_ids(self._conn, parsed_bonus)
            if miss:
                QMessageBox.warning(
                    self,
                    "Бонусные товары",
                    "Нет товаров с такими внешними ID в каталоге:\n" + ", ".join(miss),
                )
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
            promo_type=self._ptype.text().strip(),
            discount_percent=disc,
            valid_from_iso=iso(d1),
            valid_to_iso=iso(d2),
            bonus_other_product_ids=bonus_norm,
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
            label = (
                f"{r.product_name} — {r.discount_percent}% "
                f"({format_dmY(parse_iso(r.valid_from_iso))}—{format_dmY(parse_iso(r.valid_to_iso))})"
            )
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
        self._ptype.clear()
        self._disc.clear()
        self._bonus_ids.clear()
        self._d1.setDate(QDate.currentDate())
        self._d2.setDate(QDate.currentDate())
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
