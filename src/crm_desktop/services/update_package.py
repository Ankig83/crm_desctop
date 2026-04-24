"""Создание и применение подписанных пакетов обновлений (.crmpack).

Формат пакета — ZIP-архив с расширением .crmpack:
  products.xlsx    — актуальный каталог товаров
  promotions.xlsx  — актуальные акции
  discounts.xlsx   — глобальные правила скидок
  manifest.json    — мета-данные (версия, дата, автор)
  .sig             — HMAC-SHA256 подпись всего содержимого

Секретный ключ вшит в приложение. Менеджер не может создать валидный
пакет, не зная ключа, — любая подмена файлов обнаруживается при проверке.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from crm_desktop.adapters import excel_io
from crm_desktop.repositories import audit

# ── Ключ подписи (обфусцирован разбиением) ───────────────────
_K = (
    b"\x63\x72\x6d"   # crm
    b"\x5f\x75\x70"   # _up
    b"\x64\x5f\x53"   # d_S
    b"\x65\x63\x52"   # ecR
    b"\x65\x54\x5f"   # eT_
    b"\x78\x4b\x39"   # xK9
    b"\x5f\x32\x30"   # _20
    b"\x32\x35\x21"   # 25!
)

_MANIFEST_VER = 1
_SIG_FILE     = ".sig"
_MANIFEST_FILE = "manifest.json"


def _sign(data: bytes) -> str:
    return hmac.new(_K, data, hashlib.sha256).hexdigest()


def _verify(data: bytes, sig: str) -> bool:
    expected = _sign(data)
    return hmac.compare_digest(expected, sig)


def _collect_bytes(conn: sqlite3.Connection) -> dict[str, bytes]:
    """Экспортировать товары/акции/скидки в память, вернуть {filename: bytes}."""
    files: dict[str, bytes] = {}
    for fname, export_fn in (
        ("products.xlsx",   excel_io.export_products),
        ("promotions.xlsx", excel_io.export_promotions),
        ("discounts.xlsx",  excel_io.export_global_discounts),
    ):
        buf = io.BytesIO()
        export_fn(conn, buf)   # type: ignore[call-arg]
        files[fname] = buf.getvalue()
    return files


def create_package(
    conn: sqlite3.Connection,
    dest_path: Path,
    created_by: str = "admin",
) -> None:
    """Создать подписанный пакет обновлений и сохранить в dest_path (.crmpack).

    Raises:
        RuntimeError — если не удалось экспортировать или записать файл.
    """
    files = _collect_bytes(conn)

    manifest = json.dumps(
        {
            "version": _MANIFEST_VER,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "created_by": created_by,
            "files": list(files.keys()),
        },
        ensure_ascii=False,
    ).encode()
    files[_MANIFEST_FILE] = manifest

    # Подпись — HMAC от конкатенации всех файлов в строго фиксированном порядке
    sign_order = ["products.xlsx", "promotions.xlsx", "discounts.xlsx", _MANIFEST_FILE]
    combined = b"".join(files[k] for k in sign_order)
    sig = _sign(combined)

    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, data in files.items():
            zf.writestr(fname, data)
        zf.writestr(_SIG_FILE, sig)

    audit.log(conn, "export", "update_package", str(dest_path))


@dataclass
class ApplyResult:
    ok: bool
    message: str
    products_rows: int = 0
    promotions_rows: int = 0
    discounts_rows: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def apply_package(conn: sqlite3.Connection, src_path: Path) -> ApplyResult:
    """Проверить подпись и применить пакет обновлений.

    Returns:
        ApplyResult с ok=True при успехе, иначе ok=False и описание ошибки.
    """
    src_path = Path(src_path)
    try:
        zf = zipfile.ZipFile(src_path, "r")
    except (zipfile.BadZipFile, OSError) as e:
        return ApplyResult(ok=False, message=f"Не удалось открыть файл: {e}")

    with zf:
        names = set(zf.namelist())
        required = {"products.xlsx", "promotions.xlsx", "discounts.xlsx",
                    _MANIFEST_FILE, _SIG_FILE}
        missing = required - names
        if missing:
            return ApplyResult(
                ok=False,
                message=f"Файл повреждён — отсутствуют: {', '.join(sorted(missing))}",
            )

        # Проверка подписи
        sig_stored = zf.read(_SIG_FILE).decode().strip()
        sign_order = ["products.xlsx", "promotions.xlsx", "discounts.xlsx", _MANIFEST_FILE]
        combined = b"".join(zf.read(k) for k in sign_order)
        if not _verify(combined, sig_stored):
            return ApplyResult(
                ok=False,
                message=(
                    "Подпись пакета недействительна.\n\n"
                    "Файл был изменён или создан не администратором.\n"
                    "Обновление отклонено."
                ),
            )

        # Мета-данные
        try:
            manifest = json.loads(zf.read(_MANIFEST_FILE).decode())
        except (json.JSONDecodeError, KeyError):
            manifest = {}

        # Применяем данные
        result = ApplyResult(ok=True, message="")

        prod_bytes = io.BytesIO(zf.read("products.xlsx"))
        promo_bytes = io.BytesIO(zf.read("promotions.xlsx"))
        disc_bytes  = io.BytesIO(zf.read("discounts.xlsx"))

    rep_prod  = excel_io.import_products(conn, prod_bytes)    # type: ignore[arg-type]
    rep_promo = excel_io.import_promotions(conn, promo_bytes) # type: ignore[arg-type]
    rep_disc  = excel_io.import_global_discounts(conn, disc_bytes)  # type: ignore[arg-type]

    result.products_rows   = rep_prod.products_rows
    result.promotions_rows = rep_promo.promotions_rows
    result.discounts_rows  = rep_disc.discounts_rows
    result.errors          = rep_prod.errors + rep_promo.errors + rep_disc.errors

    created_at = manifest.get("created_at", "—")
    created_by = manifest.get("created_by", "—")
    result.message = (
        f"Пакет применён успешно!\n\n"
        f"Автор: {created_by}\n"
        f"Дата создания: {created_at}\n\n"
        f"Товаров обновлено: {result.products_rows}\n"
        f"Акций обновлено: {result.promotions_rows}\n"
        f"Правил скидок: {result.discounts_rows}"
    )
    if result.errors:
        result.message += f"\n\nПредупреждения ({len(result.errors)}):\n" + "\n".join(result.errors[:15])

    audit.log(conn, "import", "update_package", str(src_path))
    return result
