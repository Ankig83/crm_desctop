from __future__ import annotations

import re
from datetime import date, datetime

_DATE_RE = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*$")


def parse_dmY(s: str) -> date:
    s = (s or "").strip()
    m = _DATE_RE.match(s)
    if not m:
        raise ValueError("Ожидается дата в формате ДД.ММ.ГГГГ")
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return date(y, mo, d)


def format_dmY(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}.{d.year:04d}"


def iso(d: date) -> str:
    return d.isoformat()


def parse_iso(s: str) -> date:
    return date.fromisoformat(s)


def today_dmY() -> str:
    return format_dmY(date.today())
