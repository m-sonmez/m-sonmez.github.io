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


def _collect_annotation_node_ids(tree) -> set[int]:
    import ast

    ann_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                ann_ids.update(id(x) for x in ast.walk(node.returns))
            args = (
                list(node.args.posonlyargs)
                + list(node.args.args)
                + list(node.args.kwonlyargs)
                + ([node.args.vararg] if node.args.vararg else [])
                + ([node.args.kwarg] if node.args.kwarg else [])
            )
            for arg in args:
                if arg and arg.annotation is not None:
                    ann_ids.update(id(x) for x in ast.walk(arg.annotation))
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            ann_ids.update(id(x) for x in ast.walk(node.annotation))
    return ann_ids


def test_python38_runtime_compatibility_and_importlib_fallback(tmp_path: Path, monkeypatch):
    import ast
    import importlib.resources
    from unittest import mock

    target_dirs = [QTP_APP_DIR / "core", QTP_APP_DIR / "tui"]
    target_files = [
        QTP_APP_DIR / "cli.py",
        QTP_APP_DIR / "web.py",
        QTP_APP_DIR / "ui" / "search.py",
    ]
    for folder in target_dirs:
        target_files.extend(sorted(folder.rglob("*.py")))

    for py_file in target_files:
        src = py_file.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(py_file))
        rel = py_file.relative_to(QTP_APP_DIR).as_posix()

        has_future = any(
            isinstance(n, ast.ImportFrom)
            and n.module == "__future__"
            and any(a.name == "annotations" for a in n.names)
            for n in tree.body
        )
        assert has_future, f"{rel}: from __future__ import annotations eksik"

        ann_ids = _collect_annotation_node_ids(tree)
        for node in ast.walk(tree):
            if hasattr(ast, "Match") and isinstance(node, ast.Match):
                raise AssertionError(f"{rel}:{node.lineno}: Python 3.10 match/case yasak")
            if isinstance(node, ast.Attribute) and node.attr in ("removeprefix", "removesuffix"):
                raise AssertionError(f"{rel}:{node.lineno}: Python 3.9 str.{node.attr} yasak")
            if id(node) in ann_ids:
                continue
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("isinstance", "issubclass")
                and len(node.args) >= 2
            ):
                if any(isinstance(s, ast.BinOp) and isinstance(s.op, ast.BitOr) for s in ast.walk(node.args[1])):
                    raise AssertionError(f"{rel}:{node.lineno}: Python 3.10 runtime A|B isinstance yasak")
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                side_src = ast.unparse(node)
                if "{" in side_src or "to_dict" in side_src:
                    raise AssertionError(f"{rel}:{node.lineno}: Python 3.9 sözlük | birleşimi yasak: {side_src}")

    from qtp_app.core.engine import get_bundled_default_path, get_bundled_docs_dir
    from qtp_app.ui.theme import get_asset_path
    from qtp_app.web import _read_web_asset

    with mock.patch.object(importlib.resources, "files", None, create=True):
        assert get_bundled_default_path("QuickTextPaste.ini").is_file()
        assert get_bundled_docs_dir().is_dir()
        assert get_asset_path("icon.svg").is_file()
        assert len(_read_web_asset("qtp.html")) > 100


def test_headless_modes_zero_pyqt6_dependency(tmp_path: Path, capsys):
    import io
    from unittest import mock
    from qtp_app import cli

    work = tmp_path / "no_pyqt6"
    work.mkdir()

    blocked = {name: None for name in list(sys.modules) if name == "PyQt6" or name.startswith("PyQt6.")}
    blocked["PyQt6"] = None
    blocked["PyQt6.QtCore"] = None
    blocked["PyQt6.QtGui"] = None
    blocked["PyQt6.QtWidgets"] = None
    blocked["PyQt6.QtTest"] = None

    with mock.patch.dict("sys.modules", blocked):
        assert cli.run(["--version"]) == 0
        assert cli.run(["--selftest"]) == 0
        assert cli.run(["--work-dir", str(work), "--list-categories", "--json"]) == 0
        assert cli.run(["--work-dir", str(work), "--search", "şifre", "--json"]) == 0
        capsys.readouterr()

        fake_stdin = io.StringIO("cq")
        fake_stdin.isatty = lambda: False
        with mock.patch.object(sys, "stdin", fake_stdin), \
             mock.patch("qtp_app.core.engine.copy_to_clipboard", return_value=True):
            assert cli.run(["--work-dir", str(work), "--tui"]) == 0

        assert cli.run(["--work-dir", str(work), "--web", "--port", "0", "--shutdown-after", "0.1"]) == 0
        assert cli.run(["--work-dir", str(work), "--gui"]) == 1
        err_out = capsys.readouterr().err
        assert "PyQt6" in err_out


def test_win7_legacy_and_unix_build_configurations():
    from qtp_app.build import build_unix

    win7_req = ROOT_DIR / "requirements-win7.txt"
    win7_spec = ROOT_DIR / "qtp_app" / "build" / "qtp_win7.spec"
    assert win7_req.is_file() and "pyinstaller==5.13.2" in win7_req.read_text(encoding="utf-8")
    spec_txt = win7_spec.read_text(encoding="utf-8")
    assert '"PyQt6"' in spec_txt and 'name="qtp-win7"' in spec_txt and "upx=False" in spec_txt

    main_spec_txt = (ROOT_DIR / "qtp_app" / "build" / "qtp.spec").read_text(encoding="utf-8")
    assert '("win32", "darwin")' in main_spec_txt
    assert hasattr(build_unix, "build_unix")

