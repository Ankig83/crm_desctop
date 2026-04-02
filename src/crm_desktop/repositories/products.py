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


def list_all(conn: sqlite3.Connection) -> list[Product]:
    rows = conn.execute(
        """SELECT id, external_id, name, base_price, box_barcode, unit, units_per_box,
                  regular_piece_price, boxes_per_pallet, gross_weight_kg, volume_m3
           FROM products ORDER BY id"""
    ).fetchall()
    return [
        Product(
            id=r[0],
            external_id=r[1],
            name=r[2] or "",
            base_price=float(r[3] or 0),
            box_barcode=r[4] or "",
            unit=r[5] or "кор",
            units_per_box=int(r[6] or 0),
            regular_piece_price=float(r[7] or 0),
            boxes_per_pallet=float(r[8] or 0),
            gross_weight_kg=float(r[9] or 0),
            volume_m3=float(r[10] or 0),
        )
        for r in rows
    ]


def get(conn: sqlite3.Connection, pid: int) -> Product | None:
    r = conn.execute(
        """SELECT id, external_id, name, base_price, box_barcode, unit, units_per_box,
                  regular_piece_price, boxes_per_pallet, gross_weight_kg, volume_m3
           FROM products WHERE id = ?""",
        (pid,),
    ).fetchone()
    if not r:
        return None
    return Product(
        id=r[0],
        external_id=r[1],
        name=r[2] or "",
        base_price=float(r[3] or 0),
        box_barcode=r[4] or "",
        unit=r[5] or "кор",
        units_per_box=int(r[6] or 0),
        regular_piece_price=float(r[7] or 0),
        boxes_per_pallet=float(r[8] or 0),
        gross_weight_kg=float(r[9] or 0),
        volume_m3=float(r[10] or 0),
    )


def by_external_id(conn: sqlite3.Connection, external_id: str) -> Product | None:
    r = conn.execute(
        """SELECT id, external_id, name, base_price, box_barcode, unit, units_per_box,
                  regular_piece_price, boxes_per_pallet, gross_weight_kg, volume_m3
           FROM products WHERE external_id = ?""",
        (external_id,),
    ).fetchone()
    if not r:
        return None
    return Product(
        id=r[0],
        external_id=r[1],
        name=r[2] or "",
        base_price=float(r[3] or 0),
        box_barcode=r[4] or "",
        unit=r[5] or "кор",
        units_per_box=int(r[6] or 0),
        regular_piece_price=float(r[7] or 0),
        boxes_per_pallet=float(r[8] or 0),
        gross_weight_kg=float(r[9] or 0),
        volume_m3=float(r[10] or 0),
    )


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
) -> int:
    t = ts_now()
    cur = conn.execute(
        """INSERT INTO products(
               external_id, name, base_price, box_barcode, unit, units_per_box, regular_piece_price,
               boxes_per_pallet, gross_weight_kg, volume_m3, imported_at, updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            external_id or None,
            name,
            base_price,
            box_barcode,
            unit,
            units_per_box,
            regular_piece_price,
            boxes_per_pallet,
            gross_weight_kg,
            volume_m3,
            t,
            t,
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
) -> None:
    prev = get(conn, pid)
    if prev is None:
        return
    conn.execute(
        """UPDATE products SET
               external_id=?, name=?, base_price=?, box_barcode=?, unit=?, units_per_box=?,
               regular_piece_price=?, boxes_per_pallet=?, gross_weight_kg=?, volume_m3=?, updated_at=?
           WHERE id=?""",
        (
            external_id or None,
            name,
            base_price,
            box_barcode if box_barcode is not None else prev.box_barcode,
            unit if unit is not None else prev.unit,
            units_per_box if units_per_box is not None else prev.units_per_box,
            regular_piece_price if regular_piece_price is not None else prev.regular_piece_price,
            boxes_per_pallet if boxes_per_pallet is not None else prev.boxes_per_pallet,
            gross_weight_kg if gross_weight_kg is not None else prev.gross_weight_kg,
            volume_m3 if volume_m3 is not None else prev.volume_m3,
            ts_now(),
            pid,
        ),
    )
    conn.commit()


def delete(conn: sqlite3.Connection, pid: int) -> None:
    conn.execute("DELETE FROM products WHERE id = ?", (pid,))
    conn.commit()
