from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from crm_desktop.repositories import audit, clients
from crm_desktop.repositories.clients import CLIENT_TYPES, CLIENT_TYPE_DISCOUNT
from crm_desktop.utils.validation import inn_ok, normalize_inn


class ClientsTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._current_id: int | None = None
        self._loading = False

        # ── Список клиентов (левая панель) ───────────────────
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)

        # ── Поля формы ───────────────────────────────────────
        self._ext = QLineEdit()
        self._ext.setPlaceholderText("ID из Excel (необязательно)")
        self._ext.setToolTip("Внешний идентификатор для импорта/экспорта Excel.")

        self._name = QLineEdit()

        self._inn = QLineEdit()
        self._inn.setPlaceholderText("10 или 12 цифр")

        # ── Тип клиента ──────────────────────────────────────
        self._client_type = QComboBox()
        for key, label in CLIENT_TYPES.items():
            disc = CLIENT_TYPE_DISCOUNT[key]
            display = f"{label}  (−{disc:.0f}%)" if disc > 0 else label
            self._client_type.addItem(display, key)
        self._client_type.setToolTip(
            "Тип клиента определяет базовую скидку:\n"
            "Торговая сеть — 15%\n"
            "Дистрибутор  — 5%\n"
            "Оптовик      — 2%\n"
            "Обычный      — 0%"
        )

        self._contact_person = QLineEdit()
        self._contact_person.setPlaceholderText("ФИО контактного лица (покупатель)")
        self._contact_person.setToolTip("Для шаблона RUS: «Контактное лицо» покупателя.")

        self._email = QLineEdit()
        self._email.setPlaceholderText("email покупателя")

        self._city_region_zip = QLineEdit()
        self._city_region_zip.setPlaceholderText("Город, индекс (покупатель)")
        self._city_region_zip.setToolTip("Как в RUS: строка «Город/Штат/Почтовый индекс».")

        self._contacts = QPlainTextEdit()
        self._contacts.setPlaceholderText("Телефоны и прочие контакты (несколько — с новой строки)")

        self._addresses = QPlainTextEdit()
        self._addresses.setPlaceholderText("Адреса (несколько — с новой строки)")

        self._unload = QPlainTextEdit()
        self._unload.setPlaceholderText("Пункты разгрузки")

        self._is_new = QCheckBox("Новый клиент")

        # ── Грузополучатель ───────────────────────────────────
        self._c_name = QLineEdit()
        self._c_name.setPlaceholderText("Название компании грузополучателя")

        self._c_contact = QLineEdit()
        self._c_contact.setPlaceholderText("Контактное лицо грузополучателя")

        self._c_address = QPlainTextEdit()
        self._c_address.setPlaceholderText("Адрес грузополучателя")
        self._c_address.setMinimumHeight(96)

        self._c_city = QLineEdit()
        self._c_city.setPlaceholderText("Город / индекс грузополучателя")

        self._c_phone = QLineEdit()
        self._c_phone.setPlaceholderText("Телефон грузополучателя")

        self._c_email = QLineEdit()
        self._c_email.setPlaceholderText("Email грузополучателя")

        # ── Сигналы автосохранения ────────────────────────────
        for w in (self._ext, self._name, self._inn, self._contact_person,
                  self._email, self._city_region_zip):
            w.editingFinished.connect(self._save_current)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._save_current)
        for w in (self._contacts, self._addresses, self._unload, self._c_address):
            w.textChanged.connect(lambda: self._debounce.start(350))

        for w in (self._c_name, self._c_contact, self._c_city, self._c_phone, self._c_email):
            w.editingFinished.connect(self._save_current)

        self._is_new.toggled.connect(lambda _: self._save_current())
        self._client_type.currentIndexChanged.connect(lambda _: self._save_current())

        # ── Кнопки ───────────────────────────────────────────
        btn_new = QPushButton("Новый клиент")
        btn_new.clicked.connect(self._new_client)
        btn_del = QPushButton("Удалить")
        btn_del.clicked.connect(self._delete_current)

        # ── Группа «Грузополучатель» ──────────────────────────
        gb_con = QGroupBox("Грузополучатель (для RUS)")
        gb_con.setStyleSheet(
            "QGroupBox { font-size: 11pt; font-weight: 600; }"
            "QGroupBox QLabel { font-size: 10pt; font-weight: normal; }"
            "QGroupBox QLineEdit, QGroupBox QPlainTextEdit { font-size: 10pt; min-height: 1.4em; }"
        )
        gl = QVBoxLayout(gb_con)
        gl.setSpacing(6)
        gl.addWidget(QLabel("Название компании"))
        gl.addWidget(self._c_name)
        gl.addWidget(QLabel("Контактное лицо"))
        gl.addWidget(self._c_contact)
        gl.addWidget(QLabel("Адрес"))
        gl.addWidget(self._c_address)
        gl.addWidget(QLabel("Город / индекс"))
        gl.addWidget(self._c_city)
        gl.addWidget(QLabel("Телефон"))
        gl.addWidget(self._c_phone)
        gl.addWidget(QLabel("Электронная почта"))
        gl.addWidget(self._c_email)

        # ── Группа «Тип клиента / скидка» ────────────────────
        gb_type = QGroupBox("Тип клиента и скидка")
        gb_type.setStyleSheet(
            "QGroupBox { font-size: 11pt; font-weight: 600; }"
            "QGroupBox QLabel { font-size: 10pt; font-weight: normal; }"
            "QGroupBox QComboBox { font-size: 10pt; min-height: 1.6em; }"
        )
        gt = QVBoxLayout(gb_type)
        gt.setSpacing(6)
        self._type_hint = QLabel("")
        self._type_hint.setStyleSheet("color: #1a6b1a; font-style: italic; font-size: 9pt;")
        gt.addWidget(QLabel("Категория клиента"))
        gt.addWidget(self._client_type)
        gt.addWidget(self._type_hint)
        self._client_type.currentIndexChanged.connect(self._update_type_hint)
        self._update_type_hint()

        # ── Основная форма ────────────────────────────────────
        form = QVBoxLayout()
        form.setSpacing(6)

        title = QLabel("Редактирование")
        title_font = title.font()
        title_font.setPointSizeF(title_font.pointSizeF() + 1.0)
        title_font.setBold(True)
        title.setFont(title_font)

        form.addWidget(title)
        form.addWidget(gb_type)           # ← тип клиента сверху, хорошо заметен
        form.addWidget(QLabel("ID (внешний)"))
        form.addWidget(self._ext)
        form.addWidget(QLabel("Название"))
        form.addWidget(self._name)
        form.addWidget(QLabel("ИНН"))
        form.addWidget(self._inn)
        form.addWidget(QLabel("Контактное лицо"))
        form.addWidget(self._contact_person)
        form.addWidget(QLabel("Электронная почта"))
        form.addWidget(self._email)
        form.addWidget(QLabel("Город / индекс"))
        form.addWidget(self._city_region_zip)
        form.addWidget(QLabel("Контакты (телефоны и др.)"))
        form.addWidget(self._contacts)
        form.addWidget(QLabel("Адреса"))
        form.addWidget(self._addresses)
        form.addWidget(QLabel("Пункты разгрузки"))
        form.addWidget(self._unload)
        form.addWidget(gb_con)
        form.addWidget(self._is_new)

        row = QHBoxLayout()
        row.addWidget(btn_new)
        row.addWidget(btn_del)
        form.addLayout(row)

        _h_text = 100
        for te in (self._contacts, self._addresses, self._unload):
            te.setMinimumHeight(_h_text)
            te.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        form_root = QWidget()
        form_root.setMinimumWidth(340)
        form_root.setLayout(form)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(form_root)

        split = QSplitter()
        split.addWidget(self._list)
        split.addWidget(scroll)
        split.setStretchFactor(1, 1)

        lay = QVBoxLayout(self)
        lay.addWidget(split)
        self.reload()

    # ── Подсказка под выпадающим списком типа ─────────────────
    def _update_type_hint(self) -> None:
        key = self._client_type.currentData()
        disc = CLIENT_TYPE_DISCOUNT.get(key, 0.0)
        if disc > 0:
            self._type_hint.setText(f"Базовая скидка для этого типа: −{disc:.0f}% от цены")
        else:
            self._type_hint.setText("Базовая скидка не предусмотрена")

    # ── Список клиентов ───────────────────────────────────────
    def reload(self) -> None:
        self._list.clear()
        for c in clients.list_all(self._conn):
            label = f"{c.name or '(без названия)'}  [{c.client_type_label}]  ИНН {c.inn or '—'}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, c.id)
            self._list.addItem(item)
        if self._list.count() and self._current_id is None:
            self._list.setCurrentRow(0)

    # ── Загрузка данных в форму ───────────────────────────────
    def _load_form(self, c: clients.Client) -> None:
        self._loading = True
        self._current_id = c.id
        self._ext.setText(c.external_id or "")
        self._name.setText(c.name)
        self._inn.setText(c.inn)
        self._contact_person.setText(c.contact_person)
        self._email.setText(c.email)
        self._city_region_zip.setText(c.city_region_zip)
        self._contacts.setPlainText(c.contacts)
        self._addresses.setPlainText(c.addresses)
        self._unload.setPlainText(c.unload_points)
        self._c_name.setText(c.consignee_name)
        self._c_contact.setText(c.consignee_contact_person)
        self._c_address.setPlainText(c.consignee_address)
        self._c_city.setText(c.consignee_city_region_zip)
        self._c_phone.setText(c.consignee_phone)
        self._c_email.setText(c.consignee_email)
        self._is_new.setChecked(c.is_new)
        # тип клиента
        idx = self._client_type.findData(c.client_type)
        self._client_type.setCurrentIndex(idx if idx >= 0 else 0)
        self._loading = False
        self._update_type_hint()

    # ── Переключение между клиентами ─────────────────────────
    def _on_row_changed(self, row: int) -> None:
        if self._loading:
            return
        self._save_current()
        if row < 0:
            self._current_id = None
            return
        item = self._list.item(row)
        if not item:
            return
        cid = item.data(Qt.ItemDataRole.UserRole)
        if cid is None:
            return
        c = clients.get(self._conn, int(cid))
        if c:
            self._load_form(c)

    # ── Сохранение ───────────────────────────────────────────
    def _save_current(self) -> None:
        if self._loading:
            return
        cid = self._current_id
        if cid is None:
            return
        inn = normalize_inn(self._inn.text())
        if inn and not inn_ok(inn):
            QMessageBox.warning(self, "ИНН", "ИНН должен содержать 10 или 12 цифр.")
            return
        clients.update(
            self._conn,
            cid,
            external_id=self._ext.text().strip() or None,
            name=self._name.text().strip(),
            inn=inn,
            contacts=self._contacts.toPlainText(),
            addresses=self._addresses.toPlainText(),
            unload_points=self._unload.toPlainText(),
            contact_person=self._contact_person.text().strip(),
            email=self._email.text().strip(),
            city_region_zip=self._city_region_zip.text().strip(),
            consignee_name=self._c_name.text().strip(),
            consignee_contact_person=self._c_contact.text().strip(),
            consignee_address=self._c_address.toPlainText(),
            consignee_city_region_zip=self._c_city.text().strip(),
            consignee_phone=self._c_phone.text().strip(),
            consignee_email=self._c_email.text().strip(),
            is_new=self._is_new.isChecked(),
            client_type=self._client_type.currentData(),  # ← новое
        )
        # обновляем отображение в списке
        for i in range(self._list.count()):
            it = self._list.item(i)
            if it and it.data(Qt.ItemDataRole.UserRole) == cid:
                c = clients.get(self._conn, cid)
                if c:
                    it.setText(
                        f"{c.name or '(без названия)'}  [{c.client_type_label}]  ИНН {c.inn or '—'}"
                    )
                break

    # ── Создание нового клиента ───────────────────────────────
    def _new_client(self) -> None:
        nid = clients.insert(
            self._conn,
            external_id=None,
            name="",
            inn="",
            contacts="",
            addresses="",
            unload_points="",
            contact_person="",
            email="",
            city_region_zip="",
            consignee_name="",
            consignee_contact_person="",
            consignee_address="",
            consignee_city_region_zip="",
            consignee_phone="",
            consignee_email="",
            is_new=True,
            client_type="regular",  # ← новое
        )
        audit.log(self._conn, "create", "client", str(nid))
        self._current_id = nid
        self.reload()
        for i in range(self._list.count()):
            it = self._list.item(i)
            if it and it.data(Qt.ItemDataRole.UserRole) == nid:
                self._list.setCurrentRow(i)
                break

    # ── Удаление клиента ─────────────────────────────────────
    def _delete_current(self) -> None:
        cid = self._current_id
        if cid is None:
            return
        if QMessageBox.question(self, "Удалить", "Удалить клиента?") != QMessageBox.StandardButton.Yes:
            return
        clients.delete(self._conn, cid)
        audit.log(self._conn, "delete", "client", str(cid))
        self._current_id = None
        self.reload()