from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class ClientType:
    id: int
    name: str
    discount_pct: float


def list_all(conn: sqlite3.Connection) -> list[ClientType]:
    rows = conn.execute(
        "SELECT id, name, discount_pct FROM client_types ORDER BY discount_pct DESC, name"
    ).fetchall()
    return [ClientType(id=r[0], name=r[1], discount_pct=r[2]) for r in rows]


def get(conn: sqlite3.Connection, type_id: int) -> ClientType | None:
    r = conn.execute(
        "SELECT id, name, discount_pct FROM client_types WHERE id=?", (type_id,)
    ).fetchone()
    return ClientType(id=r[0], name=r[1], discount_pct=r[2]) if r else None


def add(conn: sqlite3.Connection, name: str, discount_pct: float) -> int:
    cur = conn.execute(
        "INSERT INTO client_types(name, discount_pct) VALUES (?, ?)", (name, discount_pct)
    )
    conn.commit()
    return cur.lastrowid


def update(conn: sqlite3.Connection, type_id: int, name: str, discount_pct: float) -> None:
    conn.execute(
        "UPDATE client_types SET name=?, discount_pct=? WHERE id=?",
        (name, discount_pct, type_id),
    )
    conn.commit()


def delete(conn: sqlite3.Connection, type_id: int) -> None:
    conn.execute("DELETE FROM client_types WHERE id=?", (type_id,))
    conn.commit()
