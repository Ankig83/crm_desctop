from __future__ import annotations

import re
import sqlite3

from crm_desktop.repositories import products


def parse_product_external_ids_csv(raw: str | None) -> list[str]:
    """Разбор списка внешних ID товаров из ячейки Excel или поля UI (запятая/точка с запятой)."""
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    if re.match(r"^id\s*[-–—]\s*", text, re.IGNORECASE):
        text = re.sub(r"^id\s*[-–—]\s*", "", text, flags=re.IGNORECASE).strip()
    parts = re.split(r"[,;]\s*", text)
    return [p.strip() for p in parts if p.strip()]


def normalize_product_external_ids_csv(raw: str | None) -> str:
    return ",".join(parse_product_external_ids_csv(raw))


def missing_product_external_ids(conn: sqlite3.Connection, ids: list[str]) -> list[str]:
    """Возвращает те id из списка, для которых нет товара с таким external_id."""
    missing: list[str] = []
    for x in ids:
        if not products.by_external_id(conn, x):
            missing.append(x)
    return missing
