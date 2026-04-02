from __future__ import annotations

from datetime import datetime


def ts_now() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")
