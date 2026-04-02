from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from crm_desktop.repositories._util import ts_now


@dataclass
class PromotionRow:
    id: int
    product_id: int
    product_name: str
    product_external_id: str | None
    promo_type: str
    discount_percent: float
    valid_from_iso: str
    valid_to_iso: str


def list_all(conn: sqlite3.Connection) -> list[PromotionRow]:
    rows = conn.execute(
        """
        SELECT p.id, p.product_id, pr.name, pr.external_id, p.promo_type, p.discount_percent, p.valid_from, p.valid_to
        FROM promotions p
        JOIN products pr ON pr.id = p.product_id
        ORDER BY p.id
        """
    ).fetchall()
    return [
        PromotionRow(
            id=r[0],
            product_id=r[1],
            product_name=r[2] or "",
            product_external_id=r[3],
            promo_type=r[4] or "",
            discount_percent=float(r[5] or 0),
            valid_from_iso=r[6],
            valid_to_iso=r[7],
        )
        for r in rows
    ]


def get_for_product(conn: sqlite3.Connection, product_id: int) -> PromotionRow | None:
    r = conn.execute(
        """
        SELECT p.id, p.product_id, pr.name, pr.external_id, p.promo_type, p.discount_percent, p.valid_from, p.valid_to
        FROM promotions p
        JOIN products pr ON pr.id = p.product_id
        WHERE p.product_id = ?
        """,
        (product_id,),
    ).fetchone()
    if not r:
        return None
    return PromotionRow(
        id=r[0],
        product_id=r[1],
        product_name=r[2] or "",
        product_external_id=r[3],
        promo_type=r[4] or "",
        discount_percent=float(r[5] or 0),
        valid_from_iso=r[6],
        valid_to_iso=r[7],
    )


def upsert(
    conn: sqlite3.Connection,
    product_id: int,
    *,
    promo_type: str,
    discount_percent: float,
    valid_from_iso: str,
    valid_to_iso: str,
) -> None:
    t = ts_now()
    row = conn.execute("SELECT id FROM promotions WHERE product_id = ?", (product_id,)).fetchone()
    if row:
        conn.execute(
            """UPDATE promotions SET promo_type=?, discount_percent=?, valid_from=?, valid_to=?, updated_at=?
               WHERE product_id=?""",
            (promo_type, discount_percent, valid_from_iso, valid_to_iso, t, product_id),
        )
    else:
        conn.execute(
            """INSERT INTO promotions(product_id, promo_type, discount_percent, valid_from, valid_to, updated_at)
               VALUES (?,?,?,?,?,?)""",
            (product_id, promo_type, discount_percent, valid_from_iso, valid_to_iso, t),
        )
    conn.commit()


def delete_for_product(conn: sqlite3.Connection, product_id: int) -> None:
    conn.execute("DELETE FROM promotions WHERE product_id = ?", (product_id,))
    conn.commit()
