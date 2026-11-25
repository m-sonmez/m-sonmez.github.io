"""PyInstaller tek dosya (onefile) QTP yapılandırması — Windows, Linux & macOS."""

from pathlib import Path
import os
import sys

SPEC_DIR = Path(SPECPATH).resolve()
PKG_DIR = SPEC_DIR.parent
ROOT_DIR = PKG_DIR.parent
QTP_ROOT = ROOT_DIR.parent

datas = [
    (str(PKG_DIR / "assets" / "icon.svg"), "qtp_app/assets"),
    (str(PKG_DIR / "assets" / "icon-192.png"), "qtp_app/assets"),
    (str(PKG_DIR / "assets" / "icon-512.png"), "qtp_app/assets"),
    (str(PKG_DIR / "assets" / "fonts" / "*.ttf"), "qtp_app/assets/fonts"),
    (str(PKG_DIR / "assets" / "defaults" / "*"), "qtp_app/assets/defaults"),
    (str(PKG_DIR / "web" / "qtp.html"), "qtp_app/web"),
    (str(PKG_DIR / "web" / "theme.css"), "qtp_app/web"),
    (str(PKG_DIR / "tui" / "_win_console.py"), "qtp_app/tui"),
    (str(PKG_DIR / "core" / "EXTERNAL_CALLS.md"), "qtp_app/core"),
    (str(QTP_ROOT / "docs" / "KULLANIM.md"), "docs"),
    (str(QTP_ROOT / "docs" / "KURULUM.md"), "docs"),
    (str(QTP_ROOT / "docs" / "KISAYOLLAR.md"), "docs"),
    (str(QTP_ROOT / "docs" / "SSS.md"), "docs"),
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
    "qtp_app.core.i18n",
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
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineQuick",
    "PyQt6.QtQuick",
    "PyQt6.QtQuickWidgets",
    "PyQt6.QtQml",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtPdf",
    "PyQt6.QtPdfWidgets",
    "PyQt6.QtSql",
    "PyQt6.QtBluetooth",
    "PyQt6.QtNfc",
    "PyQt6.QtPositioning",
    "PyQt6.QtSensors",
    "PyQt6.QtSerialPort",
    "PyQt6.Qt3DCore",
    "PyQt6.Qt3DRender",
    "PyQt6.QtDesigner",
    "PyQt6.QtHelp",
    "PyQt6.QtWebSockets",
    "PyQt6.QtCharts",
    "PyQt6.QtDataVisualization",
    "PyQt6.QtWebChannel",
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

if sys.platform != "win32":
    _skip_bins = (
        "libqt6pdf",
        "libqpdf",
        "libqtiff",
        "libqwebp",
        "libqicns",
        "libqtga",
        "libqwbmp",
        "libqvnc",
        "libqvkkhrdisplay",
        "libqt6quick",
        "libqt6qml",
        "libqt6multimedia",
        "libqt6sql",
        "libqt6webengine",
        "libqt6charts",
        "libqt63d",
        "libqt6designer",
    )
    a.binaries = [
        item for item in a.binaries
        if not any(tok in item[0].lower().replace("\\", "/") for tok in _skip_bins)
    ]
    if sys.platform not in ("win32", "darwin"):
        _linux_sys_prefixes = (
            "libfontconfig.so",
            "libfreetype.so",
            "libharfbuzz.so",
            "libexpat.so",
            "libxkbcommon.so",
            "libxkbcommon-x11.so",
            "libegl.so",
            "libgl.so",
            "libgldispatch.so",
            "libglx.so",
            "libdrm.so",
            "libgbm.so",
            "libmesa",
            "libwayland-client.so",
            "libwayland-cursor.so",
            "libwayland-egl.so",
            "libwayland-server.so",
            "libx11",
            "libxcb",
            "libxau",
            "libxdmcp",
            "libxext",
            "libxfixes",
            "libxi.so",
            "libxrender",
            "libxcursor",
            "libxrandr",
            "libxcomposite",
            "libxdamage",
            "libxinerama",
            "libice.so",
            "libsm.so",
            "libglib-2.0.so",
            "libgobject-2.0.so",
            "libgio-2.0.so",
            "libgmodule-2.0.so",
            "libgthread-2.0.so",
            "libdbus-1.so",
            "libsystemd.so",
            "libudev.so",
            "libcap.so",
            "libz.so",
            "libstdc++.so",
            "libgcc_s.so",
            "libgpg-error.so",
            "libgcrypt.so",
            "liblz4.so",
            "liblzma.so",
            "libzstd.so",
            "libpcre2",
            "libffi.so",
            "libmount.so",
            "libblkid.so",
            "libselinux.so",
            "libqgtk3.so",
            "libgtk-",
            "libgdk-",
            "libgdk_pixbuf",
            "libcairo",
            "libpango",
            "libpixman",
            "libglycin",
            "libatk",
            "libatspi",
            "libepoxy",
            "libtinysparql",
            "libxml2.so",
            "libgraphite2.so",
            "libthai.so",
            "libdatrie.so",
            "libfribidi.so",
            "libseccomp.so",
            "libcloudproviders.so",
            "libjson-glib",
        )
        a.binaries = [
            item for item in a.binaries
            if not Path(item[0].replace("\\", "/")).name.lower().startswith(_linux_sys_prefixes)
            and not (
                Path(item[0].replace("\\", "/")).name.lower().startswith("libicu")
                and not item[0].replace("\\", "/").startswith("PyQt6/")
            )
        ]
    a.datas = [
        item for item in a.datas
        if "/translations/" not in item[0].lower().replace("\\", "/")
        or item[0].lower().endswith(("_tr.qm", "_en.qm"))
    ]

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
    version=str(SPEC_DIR / "version_info.txt") if sys.platform == "win32" else None,
)
