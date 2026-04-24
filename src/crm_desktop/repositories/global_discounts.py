from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class DiscountRule:
    id: int
    rule_type: str   # 'prepay' или 'volume'
    threshold: float
    discount_pct: float


def list_by_type(conn: sqlite3.Connection, rule_type: str) -> list[DiscountRule]:
    rows = conn.execute(
        "SELECT id, rule_type, threshold, discount_pct "
        "FROM global_discount_rules WHERE rule_type=? ORDER BY threshold",
        (rule_type,),
    ).fetchall()
    return [DiscountRule(id=r[0], rule_type=r[1], threshold=r[2], discount_pct=r[3]) for r in rows]


def set_rules(
    conn: sqlite3.Connection,
    rule_type: str,
    rules: list[tuple[float, float]],
) -> None:
    """Заменить все правила заданного типа новым списком (threshold, discount_pct)."""
    conn.execute("DELETE FROM global_discount_rules WHERE rule_type=?", (rule_type,))
    for threshold, discount_pct in rules:
        conn.execute(
            "INSERT INTO global_discount_rules(rule_type, threshold, discount_pct) VALUES (?, ?, ?)",
            (rule_type, threshold, discount_pct),
        )
    conn.commit()


def as_matrix_dict(conn: sqlite3.Connection) -> dict:
    """Вернуть словарь вида {'prepay_25': 2.0, 'volume_300': 6.0, ...}.

    Используется в quote_tab как единый источник скидок за предоплату и объём.
    """
    rows = conn.execute(
        "SELECT rule_type, threshold, discount_pct FROM global_discount_rules"
    ).fetchall()
    result: dict[str, float] = {}
    for rule_type, threshold, discount_pct in rows:
        key = f"{rule_type}_{int(threshold)}"
        result[key] = discount_pct
    return result
