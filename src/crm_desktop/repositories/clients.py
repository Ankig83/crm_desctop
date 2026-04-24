from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from crm_desktop.repositories._util import ts_now

# ---------------------------------------------------------------------------
# Устаревшие константы — оставлены для обратной совместимости с импортом
# ---------------------------------------------------------------------------

CLIENT_TYPES: dict[str, str] = {
    "retail_chain": "Торговая сеть",
    "distributor":  "Дистрибьютор",
    "wholesaler":   "Оптовик",
    "regular":      "Обычный клиент",
}

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
    client_type: str = "regular"
    client_type_id: int | None = None
    owner_user_id: int | None = None
    # Заполняется через JOIN с client_types при загрузке
    type_name: str = field(default="")
    type_disc: float = field(default=0.0)

    @property
    def client_type_label(self) -> str:
        if self.type_name:
            return self.type_name
        return CLIENT_TYPES.get(self.client_type, "Обычный клиент")

    @property
    def type_discount_pct(self) -> float:
        if self.client_type_id is not None:
            return self.type_disc
        return CLIENT_TYPE_DISCOUNT.get(self.client_type, 0.0)


# ---------------------------------------------------------------------------
# Вспомогательная функция построения объекта из строки БД
# ---------------------------------------------------------------------------

def _row_to_client(r: sqlite3.Row) -> Client:
    keys = r.keys()
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
        client_type_id=r["client_type_id"] if "client_type_id" in keys else None,
        owner_user_id=r["owner_user_id"] if "owner_user_id" in keys else None,
        type_name=r["type_name"] if "type_name" in keys and r["type_name"] else "",
        type_disc=float(r["type_disc"]) if "type_disc" in keys and r["type_disc"] is not None else 0.0,
    )


_SELECT = """
    SELECT c.id, c.external_id, c.name, c.inn, c.contacts, c.addresses, c.unload_points,
           c.contact_person, c.email, c.city_region_zip,
           c.consignee_name, c.consignee_contact_person,
           c.consignee_address, c.consignee_city_region_zip,
           c.consignee_phone, c.consignee_email,
           c.is_new, c.client_type, c.client_type_id, c.owner_user_id,
           ct.name AS type_name, ct.discount_pct AS type_disc
    FROM clients c
    LEFT JOIN client_types ct ON ct.id = c.client_type_id
"""


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def list_all(
    conn: sqlite3.Connection,
    owner_user_id: int | None = None,
) -> list[Client]:
    """Вернуть клиентов.

    Если owner_user_id задан (менеджер), возвращает только его клиентов.
    Если None (администратор), возвращает всех.
    """
    if owner_user_id is not None:
        rows = conn.execute(
            _SELECT + " WHERE c.owner_user_id = ? ORDER BY c.id", (owner_user_id,)
        ).fetchall()
    else:
        rows = conn.execute(_SELECT + " ORDER BY c.id").fetchall()
    return [_row_to_client(r) for r in rows]


def get(conn: sqlite3.Connection, cid: int) -> Client | None:
    r = conn.execute(_SELECT + " WHERE c.id = ?", (cid,)).fetchone()
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
    client_type: str = "regular",
    client_type_id: int | None = None,
    owner_user_id: int | None = None,
) -> int:
    t = ts_now()
    cur = conn.execute(
        """INSERT INTO clients(
               external_id, name, inn, contacts, addresses, unload_points,
               contact_person, email, city_region_zip, consignee_name, consignee_contact_person,
               consignee_address, consignee_city_region_zip, consignee_phone, consignee_email,
               is_new, client_type, client_type_id, owner_user_id, created_at, updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            external_id or None,
            name, inn, contacts, addresses, unload_points,
            contact_person, email, city_region_zip,
            consignee_name, consignee_contact_person, consignee_address,
            consignee_city_region_zip, consignee_phone, consignee_email,
            1 if is_new else 0,
            client_type,
            client_type_id,
            owner_user_id,
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
    client_type: str | None = None,
    client_type_id: int | None = None,
    owner_user_id: int | None = None,
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
               is_new=?, client_type=?, client_type_id=?, owner_user_id=?, updated_at=?
           WHERE id=?""",
        (
            external_id or None,
            name, inn, contacts, addresses, unload_points,
            contact_person           if contact_person           is not None else prev.contact_person,
            email                    if email                    is not None else prev.email,
            city_region_zip          if city_region_zip          is not None else prev.city_region_zip,
            consignee_name           if consignee_name           is not None else prev.consignee_name,
            consignee_contact_person if consignee_contact_person is not None else prev.consignee_contact_person,
            consignee_address        if consignee_address        is not None else prev.consignee_address,
            consignee_city_region_zip if consignee_city_region_zip is not None else prev.consignee_city_region_zip,
            consignee_phone          if consignee_phone          is not None else prev.consignee_phone,
            consignee_email          if consignee_email          is not None else prev.consignee_email,
            1 if is_new else 0,
            client_type    if client_type    is not None else prev.client_type,
            client_type_id if client_type_id is not None else prev.client_type_id,
            owner_user_id  if owner_user_id  is not None else prev.owner_user_id,
            ts_now(),
            cid,
        ),
    )
    conn.commit()


def delete(conn: sqlite3.Connection, cid: int) -> None:
    conn.execute("DELETE FROM clients WHERE id = ?", (cid,))
    conn.commit()
