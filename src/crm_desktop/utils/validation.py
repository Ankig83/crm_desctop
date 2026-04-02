from __future__ import annotations

import re

_INN_RE = re.compile(r"^\d{10}$|^\d{12}$")


def inn_ok(inn: str) -> bool:
    s = re.sub(r"\s+", "", inn or "")
    return bool(_INN_RE.match(s))


def normalize_inn(inn: str) -> str:
    return re.sub(r"\s+", "", inn or "")
