r"""
Сборка CRM_Desktop.exe одной командой:

    python build.py           -- обычная сборка (папка dist/CRM_Desktop/)
    python build.py --onefile -- один .exe файл (медленнее стартует)
    python build.py --clean   -- удалить build/ dist/ перед сборкой

Результат: dist\CRM_Desktop\CRM_Desktop.exe (или dist\CRM_Desktop.exe при --onefile)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# ─── Настройки ────────────────────────────────────────────────────────────────
APP_NAME    = "CRM_Desktop"
APP_VERSION = "1.0.0"
ENTRY_POINT = "run.py"          # относительно корня проекта
ICON_PATH   = None              # например: "assets/icon.ico" (или None — без иконки)

# Hidden imports — модули, которые PyInstaller не обнаруживает автоматически
HIDDEN_IMPORTS: list[str] = [
    "crm_desktop.db.database",
    "crm_desktop.config",
    "crm_desktop.app",
    "crm_desktop.repositories.clients",
    "crm_desktop.repositories.products",
    "crm_desktop.repositories.promotions",
    "crm_desktop.repositories.calculation_sessions",
    "crm_desktop.repositories.audit",
    "crm_desktop.repositories.settings",
    "crm_desktop.services.pricing",
    "crm_desktop.services.email_send",
    "crm_desktop.services.backup",
    "crm_desktop.adapters.rus_export",
    "crm_desktop.adapters.excel_io",
    "crm_desktop.adapters.quote_pdf",
    "crm_desktop.ui.main_window",
    "crm_desktop.ui.quote_tab",
    "crm_desktop.ui.clients_tab",
    "crm_desktop.ui.products_tab",
    "crm_desktop.ui.promotions_tab",
    "crm_desktop.ui.history_tab",
    "crm_desktop.ui.settings_dialog",
    "crm_desktop.ui.app_theme",
    "crm_desktop.utils.dates",
    "crm_desktop.utils.validation",
    "crm_desktop.utils.bonus_ids",
    # Стандартные, но иногда пропускаемые
    "sqlite3",
    "email.mime.text",
    "email.mime.multipart",
    "email.mime.base",
    "smtplib",
]

# Пакеты, которые нужно включить целиком (с данными)
COLLECT_ALL: list[str] = [
    "openpyxl",
    "reportlab",
]

# ──────────────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent


def _python() -> str:
    """Возвращает путь к текущему Python-интерпретатору."""
    return sys.executable


def _ensure_pyinstaller() -> None:
    """Устанавливает PyInstaller если его нет."""
    try:
        import PyInstaller  # noqa: F401
        import importlib.metadata
        ver = importlib.metadata.version("pyinstaller")
        print(f"[build] PyInstaller {ver} уже установлен.")
    except ImportError:
        print("[build] PyInstaller не найден — устанавливаю...")
        subprocess.run(
            [_python(), "-m", "pip", "install", "pyinstaller>=6.0"],
            check=True,
        )
        print("[build] PyInstaller установлен.")


def _clean() -> None:
    """Удаляет старые артефакты сборки."""
    for folder in ("build", "dist"):
        p = ROOT / folder
        if p.exists():
            shutil.rmtree(p)
            print(f"[build] Удалена папка: {folder}/")
    spec_file = ROOT / f"{APP_NAME}.spec"
    if spec_file.exists():
        spec_file.unlink()
        print(f"[build] Удалён файл: {APP_NAME}.spec")


def _build(onefile: bool = False) -> None:
    """Запускает PyInstaller с нужными аргументами."""
    src_path = str(ROOT / "src")

    cmd: list[str] = [
        _python(), "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", APP_NAME,
        "--windowed",               # без консольного окна (GUI-приложение)
        "--paths", src_path,        # чтобы находились модули из src/
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    if ICON_PATH:
        icon = ROOT / ICON_PATH
        if icon.exists():
            cmd += ["--icon", str(icon)]
        else:
            print(f"[build] Предупреждение: иконка не найдена: {icon}")

    for imp in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", imp]

    for pkg in COLLECT_ALL:
        cmd += ["--collect-all", pkg]

    # Версионная информация для Windows (отображается в свойствах .exe)
    version_file = ROOT / "_version_info.txt"
    _write_version_file(version_file)
    cmd += ["--version-file", str(version_file)]

    cmd.append(ENTRY_POINT)

    print(f"\n[build] Запускаю PyInstaller{'  (onefile)' if onefile else '  (onedir)'}...")
    print(f"[build] Команда: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=ROOT)

    version_file.unlink(missing_ok=True)

    if result.returncode != 0:
        print("\n[build] ❌  Сборка завершилась с ошибкой.")
        sys.exit(result.returncode)

    # Показываем итог
    if onefile:
        exe = ROOT / "dist" / f"{APP_NAME}.exe"
        size_mb = exe.stat().st_size / 1024 / 1024 if exe.exists() else 0
        print(f"\n[build] === ГОТОВО! ===")
        print(f"[build]    Файл: {exe}")
        print(f"[build]    Размер: {size_mb:.1f} МБ")
    else:
        folder = ROOT / "dist" / APP_NAME
        exe = folder / f"{APP_NAME}.exe"
        size_mb = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / 1024 / 1024
        print(f"\n[build] === ГОТОВО! ===")
        print(f"[build]    Папка: {folder}")
        print(f"[build]    Размер папки: {size_mb:.0f} МБ")
        print(f"[build]    Запуск: {exe}")
    print()
    print("[build]    База данных хранится отдельно:")
    print(r"[build]    %LOCALAPPDATA%\CRM_Desktop\crm.db")
    print("[build]    При обновлении приложения данные сохраняются.")


def _write_version_file(path: Path) -> None:
    """Генерирует файл версии для Windows (.exe свойства)."""
    parts = APP_VERSION.split(".")
    while len(parts) < 4:
        parts.append("0")
    v_tuple = ", ".join(parts[:4])
    v_str   = ".".join(parts[:4])

    content = f"""\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({v_tuple}),
    prodvers=({v_tuple}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName',      u''),
         StringStruct(u'FileDescription',  u'{APP_NAME}'),
         StringStruct(u'FileVersion',      u'{v_str}'),
         StringStruct(u'InternalName',     u'{APP_NAME}'),
         StringStruct(u'LegalCopyright',   u''),
         StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),
         StringStruct(u'ProductName',      u'{APP_NAME}'),
         StringStruct(u'ProductVersion',   u'{v_str}'),
        ])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    path.write_text(content, encoding="utf-8")


def main() -> None:
    args = sys.argv[1:]
    do_clean   = "--clean"   in args
    do_onefile = "--onefile" in args
    do_help    = "--help"    in args or "-h" in args

    if do_help:
        print(__doc__)
        return

    print("=" * 60)
    print(f"  Сборка {APP_NAME} v{APP_VERSION}")
    print(f"  Python: {_python()}")
    print(f"  Режим: {'onefile (.exe)' if do_onefile else 'onedir (папка)'}")
    print("=" * 60)

    _ensure_pyinstaller()

    if do_clean:
        _clean()

    _build(onefile=do_onefile)


if __name__ == "__main__":
    main()
