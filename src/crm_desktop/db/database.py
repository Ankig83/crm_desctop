from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 7  # ← было 6

DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS clients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  external_id TEXT UNIQUE,
  name TEXT NOT NULL DEFAULT '',
  inn TEXT NOT NULL DEFAULT '',
  contacts TEXT NOT NULL DEFAULT '',
  addresses TEXT NOT NULL DEFAULT '',
  unload_points TEXT NOT NULL DEFAULT '',
  contact_person TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL DEFAULT '',
  city_region_zip TEXT NOT NULL DEFAULT '',
  consignee_name TEXT NOT NULL DEFAULT '',
  consignee_contact_person TEXT NOT NULL DEFAULT '',
  consignee_address TEXT NOT NULL DEFAULT '',
  consignee_city_region_zip TEXT NOT NULL DEFAULT '',
  consignee_phone TEXT NOT NULL DEFAULT '',
  consignee_email TEXT NOT NULL DEFAULT '',
  is_new INTEGER NOT NULL DEFAULT 0,
  client_type TEXT NOT NULL DEFAULT 'regular',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  external_id TEXT UNIQUE,
  name TEXT NOT NULL DEFAULT '',
  base_price REAL NOT NULL DEFAULT 0,
  box_barcode TEXT NOT NULL DEFAULT '',
  unit TEXT NOT NULL DEFAULT 'кор',
  units_per_box INTEGER NOT NULL DEFAULT 0,
  regular_piece_price REAL NOT NULL DEFAULT 0,
  boxes_per_pallet REAL NOT NULL DEFAULT 0,
  gross_weight_kg REAL NOT NULL DEFAULT 0,
  volume_m3 REAL NOT NULL DEFAULT 0,
  boxes_in_row INTEGER NOT NULL DEFAULT 0,
  rows_per_pallet INTEGER NOT NULL DEFAULT 0,
  pallet_height_mm INTEGER NOT NULL DEFAULT 0,
  box_dimensions TEXT NOT NULL DEFAULT '',
  imported_at TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promotions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL UNIQUE REFERENCES products(id) ON DELETE CASCADE,
  promo_type TEXT NOT NULL DEFAULT '',
  discount_percent REAL NOT NULL DEFAULT 0,
  valid_from TEXT NOT NULL,
  valid_to TEXT NOT NULL,
  bonus_other_product_ids TEXT NOT NULL DEFAULT '',
  matrix_rules_json TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calculation_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  quote_date TEXT NOT NULL,
  client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
  total REAL NOT NULL DEFAULT 0,
  details_json TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS calculation_session_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES calculation_sessions(id) ON DELETE CASCADE,
  product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
  product_external_id TEXT NOT NULL DEFAULT '',
  product_name TEXT NOT NULL DEFAULT '',
  qty REAL NOT NULL DEFAULT 0,
  base_price REAL NOT NULL DEFAULT 0,
  discount_percent REAL NOT NULL DEFAULT 0,
  line_total REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  action TEXT NOT NULL,
  entity TEXT,
  details TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clients_inn ON clients(inn);
CREATE INDEX IF NOT EXISTS idx_products_external ON products(external_id);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    from crm_desktop.config import db_path

    p = path or db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    _migrate_v2(conn)
    _migrate_v3(conn)
    _migrate_v4(conn)
    _migrate_v5(conn)
    _migrate_v6(conn)
    _migrate_v7(conn)  # ← новая
    row = conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
    ).fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (SCHEMA_VERSION,))
    elif int(row[0]) < SCHEMA_VERSION:
        conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column_sql: str, col_name: str
) -> None:
    if col_name not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_sql}")


def _migrate_v2(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "clients", "contact_person TEXT NOT NULL DEFAULT ''", "contact_person")
    _add_column_if_missing(conn, "clients", "email TEXT NOT NULL DEFAULT ''", "email")
    _add_column_if_missing(conn, "clients", "city_region_zip TEXT NOT NULL DEFAULT ''", "city_region_zip")
    _add_column_if_missing(conn, "clients", "consignee_name TEXT NOT NULL DEFAULT ''", "consignee_name")
    _add_column_if_missing(conn, "clients", "consignee_contact_person TEXT NOT NULL DEFAULT ''", "consignee_contact_person")
    _add_column_if_missing(conn, "clients", "consignee_address TEXT NOT NULL DEFAULT ''", "consignee_address")
    _add_column_if_missing(conn, "clients", "consignee_city_region_zip TEXT NOT NULL DEFAULT ''", "consignee_city_region_zip")
    _add_column_if_missing(conn, "clients", "consignee_phone TEXT NOT NULL DEFAULT ''", "consignee_phone")
    _add_column_if_missing(conn, "clients", "consignee_email TEXT NOT NULL DEFAULT ''", "consignee_email")
    _add_column_if_missing(conn, "products", "box_barcode TEXT NOT NULL DEFAULT ''", "box_barcode")
    _add_column_if_missing(conn, "products", "unit TEXT NOT NULL DEFAULT 'кор'", "unit")
    _add_column_if_missing(conn, "products", "units_per_box INTEGER NOT NULL DEFAULT 0", "units_per_box")
    _add_column_if_missing(conn, "products", "regular_piece_price REAL NOT NULL DEFAULT 0", "regular_piece_price")
    _add_column_if_missing(conn, "products", "boxes_per_pallet REAL NOT NULL DEFAULT 0", "boxes_per_pallet")
    _add_column_if_missing(conn, "products", "gross_weight_kg REAL NOT NULL DEFAULT 0", "gross_weight_kg")
    _add_column_if_missing(conn, "products", "volume_m3 REAL NOT NULL DEFAULT 0", "volume_m3")


def _migrate_v3(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "promotions", "bonus_other_product_ids TEXT NOT NULL DEFAULT ''", "bonus_other_product_ids")


def _migrate_v4(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "promotions", "matrix_rules_json TEXT NOT NULL DEFAULT ''", "matrix_rules_json")


def _migrate_v5(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS calculation_sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL,
          quote_date TEXT NOT NULL,
          client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
          total REAL NOT NULL DEFAULT 0,
          details_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS calculation_session_lines (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id INTEGER NOT NULL REFERENCES calculation_sessions(id) ON DELETE CASCADE,
          product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
          product_external_id TEXT NOT NULL DEFAULT '',
          product_name TEXT NOT NULL DEFAULT '',
          qty REAL NOT NULL DEFAULT 0,
          base_price REAL NOT NULL DEFAULT 0,
          discount_percent REAL NOT NULL DEFAULT 0,
          line_total REAL NOT NULL DEFAULT 0
        );
        """
    )


def _migrate_v6(conn: sqlite3.Connection) -> None:
    """Тип клиента: retail_chain / distributor / wholesaler / regular."""
    _add_column_if_missing(conn, "clients", "client_type TEXT NOT NULL DEFAULT 'regular'", "client_type")


def _migrate_v7(conn: sqlite3.Connection) -> None:
    """Логистические поля продукта для колонок ORDER в RUS.xlsx."""
    _add_column_if_missing(conn, "products", "boxes_in_row INTEGER NOT NULL DEFAULT 0", "boxes_in_row")
    _add_column_if_missing(conn, "products", "rows_per_pallet INTEGER NOT NULL DEFAULT 0", "rows_per_pallet")
    _add_column_if_missing(conn, "products", "pallet_height_mm INTEGER NOT NULL DEFAULT 0", "pallet_height_mm")
    _add_column_if_missing(conn, "products", "box_dimensions TEXT NOT NULL DEFAULT ''", "box_dimensions")