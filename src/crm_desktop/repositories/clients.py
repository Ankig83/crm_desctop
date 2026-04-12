from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from crm_desktop.repositories._util import ts_now

# ---------------------------------------------------------------------------
# Константы типов клиентов
# ---------------------------------------------------------------------------

CLIENT_TYPES: dict[str, str] = {
    "retail_chain": "Торговая сеть",
    "distributor":  "Дистрибьютор",
    "wholesaler":   "Оптовик",
    "regular":      "Обычный клиент",
}

# Скидка по типу клиента в процентах
CLIENT_TYPE_DISCOUNT: dict[str, float] = {
    "retail_chain": 15.0,
    "distributor":  5.0,
    "wholesaler":   2.0,
    "regular":      0.0,
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class Client:
    id: int
    external_id: str | None
    name: str
    inn: str
    contacts: str
    addresses: str
    unload_points: str
    contact_person: str
    email: str
    city_region_zip: str
    consignee_name: str
    consignee_contact_person: str
    consignee_address: str
    consignee_city_region_zip: str
    consignee_phone: str
    consignee_email: str
    is_new: bool
    client_type: str = "regular"  # ← новое поле

    @property
    def client_type_label(self) -> str:
        """Читаемое название типа клиента."""
        return CLIENT_TYPES.get(self.client_type, "Обычный клиент")

    @property
    def type_discount_pct(self) -> float:
        """Скидка клиента по его типу (%)."""
        return CLIENT_TYPE_DISCOUNT.get(self.client_type, 0.0)


# ---------------------------------------------------------------------------
# Вспомогательная функция построения объекта из строки БД
# ---------------------------------------------------------------------------

def _row_to_client(r: sqlite3.Row) -> Client:
    return Client(
        id=r["id"],
        external_id=r["external_id"],
        name=r["name"] or "",
        inn=r["inn"] or "",
        contacts=r["contacts"] or "",
        addresses=r["addresses"] or "",
        unload_points=r["unload_points"] or "",
        contact_person=r["contact_person"] or "",
        email=r["email"] or "",
        city_region_zip=r["city_region_zip"] or "",
        consignee_name=r["consignee_name"] or "",
        consignee_contact_person=r["consignee_contact_person"] or "",
        consignee_address=r["consignee_address"] or "",
        consignee_city_region_zip=r["consignee_city_region_zip"] or "",
        consignee_phone=r["consignee_phone"] or "",
        consignee_email=r["consignee_email"] or "",
        is_new=bool(r["is_new"]),
        client_type=r["client_type"] or "regular",
    )


_SELECT = """
    SELECT id, external_id, name, inn, contacts, addresses, unload_points,
           contact_person, email, city_region_zip, consignee_name, consignee_contact_person,
           consignee_address, consignee_city_region_zip, consignee_phone, consignee_email,
           is_new, client_type
    FROM clients
"""


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def list_all(conn: sqlite3.Connection) -> list[Client]:
    rows = conn.execute(_SELECT + " ORDER BY id").fetchall()
    return [_row_to_client(r) for r in rows]


def get(conn: sqlite3.Connection, cid: int) -> Client | None:
    r = conn.execute(_SELECT + " WHERE id = ?", (cid,)).fetchone()
    return _row_to_client(r) if r else None


def insert(
    conn: sqlite3.Connection,
    *,
    external_id: str | None,
    name: str,
    inn: str,
    contacts: str,
    addresses: str,
    unload_points: str,
    contact_person: str = "",
    email: str = "",
    city_region_zip: str = "",
    consignee_name: str = "",
    consignee_contact_person: str = "",
    consignee_address: str = "",
    consignee_city_region_zip: str = "",
    consignee_phone: str = "",
    consignee_email: str = "",
    is_new: bool = False,
    client_type: str = "regular",  # ← новый параметр
) -> int:
    t = ts_now()
    cur = conn.execute(
        """INSERT INTO clients(
               external_id, name, inn, contacts, addresses, unload_points,
               contact_person, email, city_region_zip, consignee_name, consignee_contact_person,
               consignee_address, consignee_city_region_zip, consignee_phone, consignee_email,
               is_new, client_type, created_at, updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            external_id or None,
            name, inn, contacts, addresses, unload_points,
            contact_person, email, city_region_zip,
            consignee_name, consignee_contact_person, consignee_address,
            consignee_city_region_zip, consignee_phone, consignee_email,
            1 if is_new else 0,
            client_type,
            t, t,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def update(
    conn: sqlite3.Connection,
    cid: int,
    *,
    external_id: str | None,
    name: str,
    inn: str,
    contacts: str,
    addresses: str,
    unload_points: str,
    contact_person: str | None = None,
    email: str | None = None,
    city_region_zip: str | None = None,
    consignee_name: str | None = None,
    consignee_contact_person: str | None = None,
    consignee_address: str | None = None,
    consignee_city_region_zip: str | None = None,
    consignee_phone: str | None = None,
    consignee_email: str | None = None,
    is_new: bool = False,
    client_type: str | None = None,  # ← новый параметр
) -> None:
    prev = get(conn, cid)
    if prev is None:
        return
    conn.execute(
        """UPDATE clients SET
               external_id=?, name=?, inn=?, contacts=?, addresses=?, unload_points=?,
               contact_person=?, email=?, city_region_zip=?,
               consignee_name=?, consignee_contact_person=?,
               consignee_address=?, consignee_city_region_zip=?,
               consignee_phone=?, consignee_email=?,
               is_new=?, client_type=?, updated_at=?
           WHERE id=?""",
        (
            external_id or None,
            name, inn, contacts, addresses, unload_points,
            contact_person          if contact_person          is not None else prev.contact_person,
            email                   if email                   is not None else prev.email,
            city_region_zip         if city_region_zip         is not None else prev.city_region_zip,
            consignee_name          if consignee_name          is not None else prev.consignee_name,
            consignee_contact_person if consignee_contact_person is not None else prev.consignee_contact_person,
            consignee_address       if consignee_address       is not None else prev.consignee_address,
            consignee_city_region_zip if consignee_city_region_zip is not None else prev.consignee_city_region_zip,
            consignee_phone         if consignee_phone         is not None else prev.consignee_phone,
            consignee_email         if consignee_email         is not None else prev.consignee_email,
            1 if is_new else 0,
            client_type             if client_type             is not None else prev.client_type,
            ts_now(),
            cid,
        ),
    )
    conn.commit()


def delete(conn: sqlite3.Connection, cid: int) -> None:
    conn.execute("DELETE FROM clients WHERE id = ?", (cid,))
    conn.commit()