from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from crm_desktop.repositories._util import ts_now


@dataclass
class Product:
    id: int
    external_id: str | None
    name: str
    base_price: float
    box_barcode: str
    unit: str
    units_per_box: int
    regular_piece_price: float
    boxes_per_pallet: float
    gross_weight_kg: float
    volume_m3: float
    # ── новые логистические поля ──────────────────────────────
    boxes_in_row: int = 0        # коробов в ряде на паллете
    rows_per_pallet: int = 0     # рядов в паллете
    pallet_height_mm: int = 0    # высота с паллетой (мм)
    box_dimensions: str = ""     # размер короба д*ш*в, например "420*240*395"


_SELECT = """
    SELECT id, external_id, name, base_price, box_barcode, unit, units_per_box,
           regular_piece_price, boxes_per_pallet, gross_weight_kg, volume_m3,
           boxes_in_row, rows_per_pallet, pallet_height_mm, box_dimensions
    FROM products
"""


def _row(r: sqlite3.Row) -> Product:
    return Product(
        id=r["id"],
        external_id=r["external_id"],
        name=r["name"] or "",
        base_price=float(r["base_price"] or 0),
        box_barcode=r["box_barcode"] or "",
        unit=r["unit"] or "кор",
        units_per_box=int(r["units_per_box"] or 0),
        regular_piece_price=float(r["regular_piece_price"] or 0),
        boxes_per_pallet=float(r["boxes_per_pallet"] or 0),
        gross_weight_kg=float(r["gross_weight_kg"] or 0),
        volume_m3=float(r["volume_m3"] or 0),
        boxes_in_row=int(r["boxes_in_row"] or 0),
        rows_per_pallet=int(r["rows_per_pallet"] or 0),
        pallet_height_mm=int(r["pallet_height_mm"] or 0),
        box_dimensions=r["box_dimensions"] or "",
    )


def list_all(conn: sqlite3.Connection) -> list[Product]:
    rows = conn.execute(_SELECT + " ORDER BY id").fetchall()
    return [_row(r) for r in rows]


def get(conn: sqlite3.Connection, pid: int) -> Product | None:
    r = conn.execute(_SELECT + " WHERE id = ?", (pid,)).fetchone()
    return _row(r) if r else None


def by_external_id(conn: sqlite3.Connection, external_id: str) -> Product | None:
    r = conn.execute(_SELECT + " WHERE external_id = ?", (external_id,)).fetchone()
    return _row(r) if r else None


def insert(
    conn: sqlite3.Connection,
    *,
    external_id: str | None,
    name: str,
    base_price: float,
    box_barcode: str = "",
    unit: str = "кор",
    units_per_box: int = 0,
    regular_piece_price: float = 0.0,
    boxes_per_pallet: float = 0.0,
    gross_weight_kg: float = 0.0,
    volume_m3: float = 0.0,
    boxes_in_row: int = 0,
    rows_per_pallet: int = 0,
    pallet_height_mm: int = 0,
    box_dimensions: str = "",
) -> int:
    t = ts_now()
    cur = conn.execute(
        """INSERT INTO products(
               external_id, name, base_price, box_barcode, unit, units_per_box,
               regular_piece_price, boxes_per_pallet, gross_weight_kg, volume_m3,
               boxes_in_row, rows_per_pallet, pallet_height_mm, box_dimensions,
               imported_at, updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            external_id or None,
            name, base_price, box_barcode, unit, units_per_box,
            regular_piece_price, boxes_per_pallet, gross_weight_kg, volume_m3,
            boxes_in_row, rows_per_pallet, pallet_height_mm, box_dimensions,
            t, t,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def update(
    conn: sqlite3.Connection,
    pid: int,
    *,
    external_id: str | None,
    name: str,
    base_price: float,
    box_barcode: str | None = None,
    unit: str | None = None,
    units_per_box: int | None = None,
    regular_piece_price: float | None = None,
    boxes_per_pallet: float | None = None,
    gross_weight_kg: float | None = None,
    volume_m3: float | None = None,
    boxes_in_row: int | None = None,
    rows_per_pallet: int | None = None,
    pallet_height_mm: int | None = None,
    box_dimensions: str | None = None,
) -> None:
    prev = get(conn, pid)
    if prev is None:
        return
    conn.execute(
        """UPDATE products SET
               external_id=?, name=?, base_price=?, box_barcode=?, unit=?, units_per_box=?,
               regular_piece_price=?, boxes_per_pallet=?, gross_weight_kg=?, volume_m3=?,
               boxes_in_row=?, rows_per_pallet=?, pallet_height_mm=?, box_dimensions=?,
               updated_at=?
           WHERE id=?""",
        (
            external_id or None,
            name,
            base_price,
            box_barcode       if box_barcode       is not None else prev.box_barcode,
            unit              if unit              is not None else prev.unit,
            units_per_box     if units_per_box     is not None else prev.units_per_box,
            regular_piece_price if regular_piece_price is not None else prev.regular_piece_price,
            boxes_per_pallet  if boxes_per_pallet  is not None else prev.boxes_per_pallet,
            gross_weight_kg   if gross_weight_kg   is not None else prev.gross_weight_kg,
            volume_m3         if volume_m3         is not None else prev.volume_m3,
            boxes_in_row      if boxes_in_row      is not None else prev.boxes_in_row,
            rows_per_pallet   if rows_per_pallet   is not None else prev.rows_per_pallet,
            pallet_height_mm  if pallet_height_mm  is not None else prev.pallet_height_mm,
            box_dimensions    if box_dimensions    is not None else prev.box_dimensions,
            ts_now(),
            pid,
        ),
    )
    conn.commit()


def delete(conn: sqlite3.Connection, pid: int) -> None:
    conn.execute("DELETE FROM products WHERE id = ?", (pid,))
    conn.commit()