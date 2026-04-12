# Руководство разработчика — CRM Desktop

**Стек:** Python 3.11+, PySide6, SQLite, openpyxl, reportlab  
**Платформа:** Windows 10/11

---

## Структура проекта

```
CRM_DESCTOP/
├── run.py                        # Точка входа — запускает приложение
├── build.py                      # Сборка EXE через PyInstaller
├── src/
│   └── crm_desktop/
│       ├── app.py                # Инициализация БД и запуск главного окна
│       ├── config.py             # Пути к файлам (AppData, база данных)
│       ├── db/
│       │   └── database.py       # Создание таблиц, миграции схемы БД
│       ├── repositories/         # Работа с БД (CRUD-операции)
│       │   ├── clients.py
│       │   ├── products.py
│       │   ├── promotions.py
│       │   ├── calculation_sessions.py
│       │   ├── audit.py
│       │   └── settings.py
│       ├── services/             # Бизнес-логика
│       │   ├── pricing.py        # Расчёт цен, скидок
│       │   ├── email_send.py     # Отправка e-mail
│       │   └── backup.py         # Резервное копирование базы
│       ├── adapters/             # Ввод/вывод данных
│       │   ├── excel_io.py       # Импорт/экспорт clients/products/promotions
│       │   ├── rus_export.py     # Генерация RUS.xlsx для 1С
│       │   └── quote_pdf.py      # Генерация PDF расчёта
│       ├── ui/                   # Интерфейс (PySide6)
│       │   ├── main_window.py    # Главное окно, меню
│       │   ├── clients_tab.py    # Вкладка «Клиенты»
│       │   ├── products_tab.py   # Вкладка «Товары»
│       │   ├── promotions_tab.py # Вкладка «Акции»
│       │   ├── quote_tab.py      # Вкладка «Расчёт»
│       │   ├── history_tab.py    # Вкладка «История»
│       │   ├── settings_dialog.py# Диалог настроек SMTP
│       │   └── app_theme.py      # Стили (цвета, шрифты)
│       └── utils/
│           ├── dates.py          # Парсинг и форматирование дат
│           ├── validation.py     # Проверка ИНН и других полей
│           └── bonus_ids.py      # Работа со списком ID бонусных товаров
├── docs/                         # Документация
├── tests/                        # Тесты (pytest)
└── .venv/                        # Виртуальное окружение Python
```

---

## Архитектура: слои приложения

```
UI (PySide6 виджеты)
       ↓  вызывает
Services (бизнес-логика)
       ↓  вызывает
Repositories (SQL-запросы к SQLite)
       ↑
   database.py (создание/миграция таблиц)

Adapters (Excel, PDF, e-mail) ← вызываются из UI напрямую
```

**Правило:** UI не пишет SQL напрямую. Всё идёт через репозитории.

---

## База данных

Файл: `%LOCALAPPDATA%\CRM_Desktop\crm.db` (SQLite)

### Таблицы

#### `clients`
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | Внутренний ID |
| external_id | TEXT | ID из 1С / Excel |
| name | TEXT | Название компании |
| inn | TEXT | ИНН (10 или 12 цифр) |
| client_type | TEXT | `regular` / `distributor` / `wholesaler` / `retail_chain` |
| contacts | TEXT | Телефоны (строки через \n) |
| addresses | TEXT | Адреса (строки через \n) |
| unload_points | TEXT | Пункты разгрузки |
| contact_person | TEXT | Контактное лицо |
| email | TEXT | E-mail |
| city_region_zip | TEXT | Город/регион/индекс |
| consignee_* | TEXT | Поля грузополучателя (6 полей) |
| is_new | INTEGER | 1 = новый клиент |

#### `products`
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | Внутренний ID |
| external_id | TEXT | Артикул (ID из 1С) |
| name | TEXT | Наименование |
| base_price | REAL | Базовая цена (руб) |
| units_per_box | INTEGER | Штук в коробке |
| regular_piece_price | REAL | Цена за штуку |
| boxes_per_pallet | REAL | Коробок на паллете |
| gross_weight_kg | REAL | Масса брутто (кг) |
| volume_m3 | REAL | Объём (м³) |
| boxes_in_row | INTEGER | Коробов в ряду |
| rows_per_pallet | INTEGER | Рядов в паллете |
| pallet_height_mm | INTEGER | Высота паллеты (мм) |
| box_dimensions | TEXT | Размеры короба |

#### `promotions`
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | |
| product_id | INTEGER FK | Ссылка на products.id |
| promo_type | TEXT | Тип акции (строка) |
| discount_percent | REAL | Скидка в % |
| valid_from_iso | TEXT | Дата начала (ISO: YYYY-MM-DD) |
| valid_to_iso | TEXT | Дата окончания (ISO) |
| bonus_other_product_ids | TEXT | CSV артикулов бонусных товаров |
| matrix_rules_json | TEXT | JSON со сложными правилами скидок |

#### `calculation_sessions`
История расчётов — снимок заказа на момент сохранения.

#### `audit_log`
Журнал всех действий пользователя (импорт, экспорт, резервная копия).

#### `app_settings`
Ключ-значение для хранения настроек (SMTP, счётчик заказов).

---

## Миграции базы данных

Файл: `src/crm_desktop/db/database.py`

При каждом запуске вызывается `init_db(conn)`. Функция:
1. Создаёт таблицы если их нет (`CREATE TABLE IF NOT EXISTS`).
2. Проверяет текущую версию схемы (таблица `schema_version`).
3. Последовательно применяет миграции `_migrate_v1()`, `_migrate_v2()` и т.д.

**Как добавить новое поле в таблицу:**
```python
def _migrate_v8(conn):
    conn.execute("ALTER TABLE clients ADD COLUMN new_field TEXT DEFAULT ''")
    conn.commit()
```
И добавить вызов в `init_db()`:
```python
if version < 8:
    _migrate_v8(conn)
    conn.execute("UPDATE schema_version SET version = 8")
```

---

## Как работает расчёт цены

Файл: `src/crm_desktop/services/pricing.py`

Функция `line_total(product, promo, qty, prepay_pct, calc_date)` возвращает `DiscountResult`:

```python
@dataclass
class DiscountResult:
    unit_price: float       # итоговая цена за коробку
    total: float            # итого строки (qty × unit_price)
    client_disc: float      # скидка за тип клиента, %
    prepay_disc: float      # скидка за предоплату, %
    volume_disc: float      # скидка за объём, %
    product_disc: float     # продуктовая скидка, %
    applied_bonuses: list   # список бонусных товаров
```

**Порядок применения скидок:**
1. Берём базовую цену товара.
2. Применяем скидку за тип клиента (из `CLIENT_TYPES` в `clients.py`).
3. Применяем скидку за предоплату (из `matrix_rules_json`, если prepay_pct >= порога).
4. Применяем скидку за объём (из `matrix_rules_json`, если qty >= порога).
5. Применяем продуктовую скидку `expiry_pct`.
6. Если сегодня в диапазоне `[valid_from; valid_to]` — применяем `discount_percent` акции.
7. Вычисляем бонусы.

---

## matrix_rules_json — формат

Это JSON-строка в поле `promotions.matrix_rules_json`. Пример:
```json
{
  "prepay_25": "2",
  "prepay_50": "3",
  "volume_300": "6",
  "volume_500": "8",
  "expiry_pct": "5",
  "expiry_rub": "0",
  "promo_15_2_qty": "2",
  "promo_10_3_qty": "3",
  "promo_date_from": "01.04.2026",
  "promo_date_to": "30.04.2026"
}
```

**Расшифровка ключей:**

| Ключ | Значение |
|------|----------|
| `prepay_25` | При предоплате ≥25% — скидка 2% |
| `prepay_50` | При предоплате ≥50% — скидка 3% |
| `volume_300` | При заказе ≥300 кор — скидка 6% |
| `volume_500` | При заказе ≥500 кор — скидка 8% |
| `expiry_pct` | Продуктовая скидка в % |
| `expiry_rub` | Продуктовая скидка в рублях (на коробку) |
| `promo_15_2_qty` | Акция «15+2»: при покупке 15 кор — 2 бесплатно |
| `promo_10_3_qty` | Акция «10+3»: при покупке 10 кор — 3 бесплатно |
| `promo_date_from` | Начало акционного периода бонусов |
| `promo_date_to` | Конец акционного периода бонусов |

Любые дополнительные ключи (импортированные из Excel) тоже сохраняются.

---

## Как работает RUS.xlsx

Файл: `src/crm_desktop/adapters/rus_export.py`

Функция `export_rus_variant_a(path, *, client, quote_date, lines, delivery_date, order_no)`.

### Структура файла (соответствует шаблону заказчика):

```
R1   No: {номер заказа}
R2   Информация о Покупателе
R3   Название компании        [H3 = тип клиента и скидка]
R4   ИНН
R5   Контактное лицо
R6   Адрес
R7   Город/Штат/Почтовый индекс
R8   Телефон
R9   Электронная почта
R10  Информация о Грузополучателе
R11–R16  Данные грузополучателя
R17  ДАТА ЗАКАЗА  ← читается 1С по номеру строки!
R18  ДАТА ДОСТАВКИ ← читается 1С по номеру строки!
R19  Подсказки (не читается 1С)
R20  Заголовки колонок
R21  Нумерация
R22+ Строки товаров
```

### Колонки в строках товаров:

| Колонка | Содержимое |
|---------|-----------|
| C1 | Артикул |
| C2 | Баркод коробки |
| C3 | Наименование |
| C4 | Ед. измерения |
| C5 | Кол-во (коробок) |
| **C6** | **Итого строки** (qty × цена) |
| **C7** | **Цена за штуку** после скидки |
| C8 | Регулярная цена за штуку |
| C9 | Коэффициент предоплаты (0.98 = -2%) |
| C10 | Коэффициент объём 300 (0.94 = -6%) |
| C11 | Коэффициент объём 500 (0.92 = -8%) |
| C12 | Коэффициент акции 15+2 |
| C13 | Количество бонусных коробок акции 10+3 |
| C14 | Штук в коробке |
| C15–C18 | Цена коробки при разных скидках |
| C19 | Доп. скидка в рублях |
| C20 | Коробок на паллете |
| C21 | Итого паллет |
| C22 | Масса брутто |
| C23 | Объём м³ |
| C24 | Регулярная сумма строки |
| C25 | Акционная сумма строки |

### Бонусные строки:
Для бесплатных товаров создаётся отдельная строка с `is_bonus=True`. В ней C6=0, C7=0. Строка выделяется жёлтым фоном.

---

## Как работает импорт Excel

Файл: `src/crm_desktop/adapters/excel_io.py`

1. Открывает файл через `openpyxl` (fallback — `pandas+calamine`).
2. Ищет строку заголовков по ключевым словам (`_find_header_row`).
3. Для каждой строки данных — парсит, валидирует, пишет в БД через репозиторий.
4. Собирает `ImportReport` с числом загруженных строк и списком ошибок.

**Нормализация заголовков:** регистр, лишние пробелы и буква «ё» игнорируются при сопоставлении.

**Для акций:** все нестандартные колонки (которые не входят в список известных полей) сохраняются в `matrix_rules_json` автоматически.

---

## Как запустить в режиме разработки

```powershell
# Активировать виртуальное окружение
.\.venv\Scripts\Activate.ps1

# Запустить приложение
$env:PYTHONPATH="src"
python run.py

# Запустить тесты
python -m pytest tests/ -v
```

---

## Как собрать EXE

```powershell
python build.py          # Папка dist/CRM_Desktop/
python build.py --onefile  # Один файл dist/CRM_Desktop.exe
python build.py --clean    # Очистить и пересобрать
```

Результат: `dist\CRM_Desktop\CRM_Desktop.exe`

**База данных НЕ входит в EXE** — она живёт в `%LOCALAPPDATA%\CRM_Desktop\crm.db`.  
При обновлении EXE данные сохраняются.

---

## Тесты

Файлы: `tests/`

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/ -v
```

Тесты покрывают:
- расчёт скидок (`test_pricing.py`)
- работу с бонусными ID (`test_bonus_ids.py`)
- импорт акций из Excel (`test_promotions_import_headers.py`)
- генерацию RUS.xlsx (`test_rus_export_matrix_columns.py`)

---

## Частые задачи при разработке

### Добавить новое поле в таблицу clients

1. В `database.py` — добавить новую миграцию `_migrate_vN`.
2. В `repositories/clients.py` — добавить поле в dataclass `Client` и в SQL-запросы.
3. В `ui/clients_tab.py` — добавить поле в форму.
4. В `adapters/excel_io.py` — добавить в `import_clients()` и `export_clients()`.

### Добавить новый тип скидки

1. В `services/pricing.py` — добавить расчёт в функцию `line_total()`.
2. В `ui/promotions_tab.py` — добавить UI-поля, обновить `_collect_matrix_rules()` и `_load_matrix_rules()`.
3. В `adapters/rus_export.py` — отразить в нужной колонке (если нужно в 1С).

### Изменить внешний вид

- Цвета и шрифты интерфейса: `ui/app_theme.py`
- Цвета ячеек в RUS.xlsx: константы `_C_*` в `adapters/rus_export.py`

---

## Зависимости (requirements)

```
PySide6>=6.6
openpyxl>=3.1
reportlab>=4.0
```

Опциональные (для fallback-импорта):
```
pandas
python-calamine
```

Для сборки EXE:
```
pyinstaller>=6.0
```

---

## Важные решения и ограничения

- **Один клиент = одна строка** в БД. Несколько контактов — через `\n` в поле.
- **Одна акция на товар** — ограничение по ТЗ. Попытка создать вторую — ошибка.
- **Даты в БД** хранятся в ISO-формате (`YYYY-MM-DD`), в UI и Excel показываются как `ДД.ММ.ГГГГ`.
- **Строки R17/R18** в RUS.xlsx (даты заказа и доставки) — фиксированные позиции, которые читает 1С. Нельзя добавлять строки выше без сдвига этих позиций.
- **Номер заказа** — простой счётчик в `app_settings`. Инкрементируется при каждом экспорте RUS.xlsx.
