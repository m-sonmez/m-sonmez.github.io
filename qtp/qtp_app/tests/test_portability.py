"""Taşınabilirlik, temiz klasör, PATH/HOME sıyırma, yerel ayar matrisi ve statik sıfır-bağımlılık taraması."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

QTP_APP_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = QTP_APP_DIR.parent
DIST_EXE = ROOT_DIR / "dist" / ("qtp.exe" if sys.platform == "win32" else "qtp.bin")

_FORBIDDEN_SYMBOLS = (
    "pyperclip",
    "xclip",
    "xsel",
    "xdotool",
    "wmctrl",
    "ydotool",
    "wtype",
    "win32clipboard",
    "pbcopy",
    "pbpaste",
)


def test_static_zero_dep_scan():
    """
    qtp_app/** içinde harici pano/otomasyon araçlarını tarar ve yalnızca izin verilen
    beyaz liste (EXTERNAL_CALLS.md, try/except ImportError pyperclip, stok pbcopy, isteğe bağlı wtype/ydotool) kabul eder.
    """
    violations: list[str] = []
    for path in QTP_APP_DIR.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix not in (".py", ".html", ".css", ".md"):
            continue
        rel = path.relative_to(QTP_APP_DIR).as_posix()
        if rel in (
            "core/EXTERNAL_CALLS.md",
            "tests/test_portability.py",
        ):
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for sym in _FORBIDDEN_SYMBOLS:
                if re.search(rf"\b{re.escape(sym)}\b", line):
                    # İzin verilen tek istisnalar:
                    allowed = False
                    if sym == "pyperclip" and rel in ("core/paster.py", "tests/test_paster.py", "build/qtp.spec"):
                        allowed = True
                    elif sym == "pbcopy" and rel in ("core/paster.py", "tests/test_paster.py"):
                        allowed = True
                    elif sym in ("wtype", "ydotool") and rel in (
                        "core/paster.py",
                        "core/operations.py",
                        "core/settings.py",
                        "tests/test_paster.py",
                    ):
                        allowed = True
                    if not allowed:
                        violations.append(f"{rel}:{lineno}: yasak bağımlılık referansı '{sym}' -> {line.strip()}")

    assert not violations, "Sıfır bağımlılık taraması başarısız:\n" + "\n".join(violations)


def _run_cli_matrix_subprocess(cmd_prefix: list[str], work_dir: Path, env: dict[str, str]) -> None:
    cmds = [
        ["--version"],
        ["--help"],
        ["--selftest"],
        ["--modes"],
        ["--list-categories", "--json"],
        ["--search", "şifre", "--json"],
        ["--export-ini", str(work_dir / "out.ini")],
        ["--import-ini", str(work_dir / "out.ini"), "--merge"],
        ["--backup"],
    ]
    for args in cmds:
        proc = subprocess.run(
            cmd_prefix + ["--work-dir", str(work_dir)] + args,
            cwd=str(work_dir),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert proc.returncode == 0, f"Komut başarısız {args}: rc={proc.returncode}\nERR={proc.stderr}\nOUT={proc.stdout}"


@pytest.mark.parametrize("locale_val", ["C", "tr_TR.UTF-8"])
def test_inprocess_path_home_stripped_and_locale_matrix(tmp_path: Path, locale_val: str):
    work = tmp_path / "clean_folder"
    work.mkdir()
    fake_home = tmp_path / "fresh_home"
    fake_home.mkdir()

    env = {
        "PATH": "" if sys.platform == "win32" else "/usr/bin:/bin",
        "HOME": str(fake_home),
        "USERPROFILE": str(fake_home),
        "APPDATA": str(fake_home / "AppData" / "Roaming"),
        "XDG_CONFIG_HOME": str(fake_home / ".config"),
        "LANG": locale_val,
        "LC_ALL": locale_val,
        "PYTHONIOENCODING": "utf-8",
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": str(ROOT_DIR),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
    }
    _run_cli_matrix_subprocess([sys.executable, "-m", "qtp_app.main"], work, env)

    # İlk çalıştırmada varsayılan dosyalar oluşmuş olmalı
    assert (work / "qtp_settings.json").is_file()
    assert (work / "qtp.log").is_file()
    assert (work / "QuickTextPaste.ini").is_file()
    assert (work / "data.json").is_file()


def test_built_binary_fresh_folder_zero_siblings_if_present(tmp_path: Path):
    if not DIST_EXE.is_file():
        pytest.skip(f"Derlenmiş ikili henüz üretilmedi: {DIST_EXE}")

    isolated = tmp_path / "isolated_bin"
    isolated.mkdir()
    copied_bin = isolated / DIST_EXE.name
    shutil.copy2(DIST_EXE, copied_bin)

    fake_home = tmp_path / "isolated_home"
    fake_home.mkdir()
    env = {
        "PATH": "" if sys.platform == "win32" else "/usr/bin:/bin",
        "HOME": str(fake_home),
        "USERPROFILE": str(fake_home),
        "APPDATA": str(fake_home / "AppData" / "Roaming"),
        "XDG_CONFIG_HOME": str(fake_home / ".config"),
        "LANG": "C",
        "PYTHONIOENCODING": "utf-8",
        "QT_QPA_PLATFORM": "offscreen",
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
    }
    _run_cli_matrix_subprocess([str(copied_bin)], isolated, env)
    assert (isolated / "qtp_settings.json").is_file()
    assert (isolated / "qtp.log").is_file()
    assert (isolated / "QuickTextPaste.ini").is_file()
    assert (isolated / "data.json").is_file()
