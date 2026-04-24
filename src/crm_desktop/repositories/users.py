from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass


@dataclass
class User:
    id: int
    name: str
    role: str          # 'admin' или 'manager'
    password_hash: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def list_all(conn: sqlite3.Connection) -> list[User]:
    rows = conn.execute(
        "SELECT id, name, role, password_hash FROM users ORDER BY role DESC, name"
    ).fetchall()
    return [User(id=r[0], name=r[1], role=r[2], password_hash=r[3]) for r in rows]


def get_by_name(conn: sqlite3.Connection, name: str) -> User | None:
    r = conn.execute(
        "SELECT id, name, role, password_hash FROM users WHERE name=?", (name,)
    ).fetchone()
    return User(id=r[0], name=r[1], role=r[2], password_hash=r[3]) if r else None


def check_password(user: User, password: str) -> bool:
    if not user.password_hash:
        return password == ""
    return user.password_hash == _hash(password)


def add(conn: sqlite3.Connection, name: str, role: str, password: str = "") -> None:
    ph = _hash(password) if password else ""
    conn.execute(
        "INSERT INTO users(name, role, password_hash) VALUES (?, ?, ?)",
        (name, role, ph),
    )
    conn.commit()


def update(
    conn: sqlite3.Connection,
    user_id: int,
    name: str,
    role: str,
    password: str | None = None,
) -> None:
    if password is not None:
        conn.execute(
            "UPDATE users SET name=?, role=?, password_hash=? WHERE id=?",
            (name, role, _hash(password), user_id),
        )
    else:
        conn.execute(
            "UPDATE users SET name=?, role=? WHERE id=?",
            (name, role, user_id),
        )
    conn.commit()


def delete(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
