from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from crm_desktop.config import db_path


def copy_database_to(dest_dir: Path) -> Path:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = dest_dir / f"crm_backup_{stamp}.db"
    shutil.copy2(db_path(), target)
    return target
