"""PyInstaller tek dosya (onefile) QTP yapılandırması — Windows, Linux & macOS."""

from pathlib import Path
import os
import sys

SPEC_DIR = Path(SPECPATH).resolve()
PKG_DIR = SPEC_DIR.parent
ROOT_DIR = PKG_DIR.parent

datas = [
    (str(PKG_DIR / "assets" / "icon.svg"), "qtp_app/assets"),
    (str(PKG_DIR / "assets" / "icon-192.png"), "qtp_app/assets"),
    (str(PKG_DIR / "assets" / "icon-512.png"), "qtp_app/assets"),
    (str(PKG_DIR / "assets" / "fonts" / "*.ttf"), "qtp_app/assets/fonts"),
    (str(PKG_DIR / "assets" / "defaults" / "*"), "qtp_app/assets/defaults"),
    (str(PKG_DIR / "web" / "index.html"), "qtp_app/web"),
    (str(PKG_DIR / "web" / "theme.css"), "qtp_app/web"),
    (str(PKG_DIR / "tui" / "_win_console.py"), "qtp_app/tui"),
    (str(PKG_DIR / "core" / "EXTERNAL_CALLS.md"), "qtp_app/core"),
    (str(ROOT_DIR / "docs" / "KULLANIM.md"), "docs"),
    (str(ROOT_DIR / "docs" / "KISAYOLLAR.md"), "docs"),
    (str(ROOT_DIR / "docs" / "SSS.md"), "docs"),
]

hiddenimports = [
    "pynput.keyboard._win32",
    "pynput.keyboard._darwin",
    "pynput.keyboard._xorg",
    "pynput.mouse._win32",
    "pynput.mouse._darwin",
    "pynput.mouse._xorg",
    "PyQt6.QtGui",
    "PyQt6.QtSvg",
    "PyQt6.QtTest",
    "PyQt6.QtNetwork",
    "PyQt6.QtDBus",
    "qtp_app.core.engine",
    "qtp_app.core.hotkeys",
    "qtp_app.core.operations",
    "qtp_app.core.watcher",
    "qtp_app.cli",
    "qtp_app.tui",
    "qtp_app.tui.app",
    "qtp_app.tui._win_console",
    "qtp_app.web",
    "keyboard",
]

excludes = [
    "tkinter",
    "matplotlib",
    "numpy",
    "tests",
    "qtp_app.tests",
]

icon_path = str(PKG_DIR / "assets" / "icon-192.png")

a = Analysis(
    [str(PKG_DIR / "main.py")],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="QTP",
    debug=False,
    bootloader_ignore_signals=False,
    strip=(sys.platform not in ("win32", "darwin")),
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=os.environ.get("QTP_TARGET_ARCH") or None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
