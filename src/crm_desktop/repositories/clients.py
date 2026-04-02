from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from crm_desktop.repositories._util import ts_now


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


def list_all(conn: sqlite3.Connection) -> list[Client]:
    rows = conn.execute(
        """SELECT id, external_id, name, inn, contacts, addresses, unload_points,
                  contact_person, email, city_region_zip, consignee_name, consignee_contact_person,
                  consignee_address, consignee_city_region_zip, consignee_phone, consignee_email, is_new
           FROM clients ORDER BY id"""
    ).fetchall()
    return [
        Client(
            id=r[0],
            external_id=r[1],
            name=r[2] or "",
            inn=r[3] or "",
            contacts=r[4] or "",
            addresses=r[5] or "",
            unload_points=r[6] or "",
            contact_person=r[7] or "",
            email=r[8] or "",
            city_region_zip=r[9] or "",
            consignee_name=r[10] or "",
            consignee_contact_person=r[11] or "",
            consignee_address=r[12] or "",
            consignee_city_region_zip=r[13] or "",
            consignee_phone=r[14] or "",
            consignee_email=r[15] or "",
            is_new=bool(r[16]),
        )
        for r in rows
    ]


def get(conn: sqlite3.Connection, cid: int) -> Client | None:
    r = conn.execute(
        """SELECT id, external_id, name, inn, contacts, addresses, unload_points,
                  contact_person, email, city_region_zip, consignee_name, consignee_contact_person,
                  consignee_address, consignee_city_region_zip, consignee_phone, consignee_email, is_new
           FROM clients WHERE id = ?""",
        (cid,),
    ).fetchone()
    if not r:
        return None
    return Client(
        id=r[0],
        external_id=r[1],
        name=r[2] or "",
        inn=r[3] or "",
        contacts=r[4] or "",
        addresses=r[5] or "",
        unload_points=r[6] or "",
        contact_person=r[7] or "",
        email=r[8] or "",
        city_region_zip=r[9] or "",
        consignee_name=r[10] or "",
        consignee_contact_person=r[11] or "",
        consignee_address=r[12] or "",
        consignee_city_region_zip=r[13] or "",
        consignee_phone=r[14] or "",
        consignee_email=r[15] or "",
        is_new=bool(r[16]),
    )


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
) -> int:
    t = ts_now()
    cur = conn.execute(
        """INSERT INTO clients(
               external_id, name, inn, contacts, addresses, unload_points,
               contact_person, email, city_region_zip, consignee_name, consignee_contact_person,
               consignee_address, consignee_city_region_zip, consignee_phone, consignee_email,
               is_new, created_at, updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            external_id or None,
            name,
            inn,
            contacts,
            addresses,
            unload_points,
            contact_person,
            email,
            city_region_zip,
            consignee_name,
            consignee_contact_person,
            consignee_address,
            consignee_city_region_zip,
            consignee_phone,
            consignee_email,
            1 if is_new else 0,
            t,
            t,
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
) -> None:
    prev = get(conn, cid)
    if prev is None:
        return
    conn.execute(
        """UPDATE clients SET
               external_id=?, name=?, inn=?, contacts=?, addresses=?, unload_points=?,
               contact_person=?, email=?, city_region_zip=?, consignee_name=?, consignee_contact_person=?,
               consignee_address=?, consignee_city_region_zip=?, consignee_phone=?, consignee_email=?,
               is_new=?, updated_at=?
           WHERE id=?""",
        (
            external_id or None,
            name,
            inn,
            contacts,
            addresses,
            unload_points,
            contact_person if contact_person is not None else prev.contact_person,
            email if email is not None else prev.email,
            city_region_zip if city_region_zip is not None else prev.city_region_zip,
            consignee_name if consignee_name is not None else prev.consignee_name,
            consignee_contact_person
            if consignee_contact_person is not None
            else prev.consignee_contact_person,
            consignee_address if consignee_address is not None else prev.consignee_address,
            consignee_city_region_zip
            if consignee_city_region_zip is not None
            else prev.consignee_city_region_zip,
            consignee_phone if consignee_phone is not None else prev.consignee_phone,
            consignee_email if consignee_email is not None else prev.consignee_email,
            1 if is_new else 0,
            ts_now(),
            cid,
        ),
    )
    conn.commit()


def delete(conn: sqlite3.Connection, cid: int) -> None:
    conn.execute("DELETE FROM clients WHERE id = ?", (cid,))
    conn.commit()
