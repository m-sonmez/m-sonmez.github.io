"""Tüm QTP çalışma modları (--gui, --tui, --cli, --web) için birleşik komut satırı ayrıştırıcısı ve çalıştırıcı."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from qtp_app import __display_name__, __version__
from qtp_app.core.engine import QtpEngine
from qtp_app.core.hotkeys import HOTKEY_PRESETS, HOTKEY_PRESET_LABELS
from qtp_app.core.operations import OPERATIONS
from qtp_app.core.settings import DEFAULT_SETTINGS

TH32CS_SNAPPROCESS = 0x00000002
_CONSOLE_ATTACHED_EXISTING = False


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("cntUsage", ctypes.c_uint32),
        ("th32ProcessID", ctypes.c_uint32),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", ctypes.c_uint32),
        ("cntThreads", ctypes.c_uint32),
        ("th32ParentProcessID", ctypes.c_uint32),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_uint32),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def configure_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            if stream is not None and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _iter_windows_ancestor_pids(kernel32: Any, max_depth: int = 6) -> list[int]:
    """Win32 süreç ağacında üst süreç kimliklerini yürür (PyInstaller --onefile önyükleyicisini aşar)."""
    try:
        kernel32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
        kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
        kernel32.Process32FirstW.restype = ctypes.c_int
        kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
        kernel32.Process32NextW.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
    except Exception:
        return []

    invalid = ctypes.c_void_p(-1).value
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not isinstance(snap, int) or not snap or snap == invalid:
        return []

    ppid_map: dict[int, int] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        count = 0
        while isinstance(ok, (int, bool)) and ok and count < 50000:
            pid = int(entry.th32ProcessID)
            ppid = int(entry.th32ParentProcessID)
            if pid > 0:
                ppid_map[pid] = ppid
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
            count += 1
    except Exception:
        return []
    finally:
        try:
            kernel32.CloseHandle(snap)
        except Exception:
            pass

    ancestors: list[int] = []
    cur = os.getpid()
    seen: set[int] = {cur}
    for _ in range(max(1, max_depth)):
        parent = ppid_map.get(cur, 0)
        if parent <= 0 or parent in seen:
            break
        ancestors.append(parent)
        seen.add(parent)
        cur = parent
    return ancestors


def attach_windows_console_if_needed(mode: str) -> bool:
    """
    Windows tek-dosya (console=False) ikilisinde konsol akışları None ise ata süreç zincirini
    yürüyerek PowerShell/cmd/Terminal konsoluna (AttachConsole) veya TUI için yeni konsola bağlanır.
    Boru hatlarını (pipe) kesinlikle bozmaz.
    """
    global _CONSOLE_ATTACHED_EXISTING
    _CONSOLE_ATTACHED_EXISTING = False

    if sys.platform != "win32" or mode not in ("cli", "tui"):
        return False
    if sys.stdout is not None and sys.stderr is not None:
        return False
    try:
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return False
        k32 = windll.kernel32
        k32.AttachConsole.argtypes = [ctypes.c_int32]
        k32.AttachConsole.restype = ctypes.c_int
        k32.AllocConsole.argtypes = []
        k32.AllocConsole.restype = ctypes.c_int
        k32.FreeConsole.argtypes = []
        k32.FreeConsole.restype = ctypes.c_int
        k32.SetConsoleOutputCP.argtypes = [ctypes.c_uint]
        k32.SetConsoleOutputCP.restype = ctypes.c_int
        k32.SetConsoleCP.argtypes = [ctypes.c_uint]
        k32.SetConsoleCP.restype = ctypes.c_int

        attached_existing = bool(k32.AttachConsole(-1))
        if not attached_existing:
            for apid in _iter_windows_ancestor_pids(k32, max_depth=6):
                if k32.AttachConsole(int(apid)):
                    attached_existing = True
                    break

        attached = attached_existing
        if mode == "tui":
            if attached_existing:
                k32.FreeConsole()
                attached_existing = False
            attached = bool(k32.AllocConsole())

        if attached:
            k32.SetConsoleOutputCP(65001)
            k32.SetConsoleCP(65001)
            if sys.stdout is None:
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
            if sys.stderr is None:
                sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
            if sys.stdin is None:
                sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
            _CONSOLE_ATTACHED_EXISTING = attached_existing
            if attached_existing and sys.stdout is not None:
                sys.stdout.write("\n")
                sys.stdout.flush()
        return attached
    except Exception:
        return False


def format_help_text(*, verbose: bool = False) -> str:
    op_lines = []
    for op in OPERATIONS:
        flag_disp = f"{op.cli_flag} {op.args_spec}".strip()
        op_lines.append(f"  {flag_disp:<38} {op.label_tr}")
    base = (
        f"{__display_name__} v{__version__} — Komut Satırı Kullanımı\n\n"
        "Kullanım:\n"
        "  qtp [--mode {gui,tui,cli,web} | --gui | --tui | --cli | --web] [SEÇENEK]\n\n"
        "Çalışma Modları:\n"
        "  --mode {gui,tui,cli,web}               Çalışma modunu seçer (kısayol: --gui, --tui, --cli, --web).\n"
        "  --work-dir DIZIN                       Veri ve ayarlar için çalışma dizini belirler.\n"
        "  --json                                 Salt-okunur CLI çıktılarını UTF-8 JSON biçiminde basar.\n"
        "  -v, --verbose / -vv                    Ayrıntılı yardım ve stderr tanılama günlüğü (-vv hata ayıklama).\n"
        "  -q, --quiet                            Yalnızca veri veya hata çıktılarını basar; bilgi başlıklarını gizler.\n\n"
        "İşlemler (Operation Registry):\n"
        + "\n".join(op_lines)
        + "\n\nEk Seçenekler:\n"
        "  --category KOD                         --list-items / --search için kategori filtresi (ALL/A/Z/X/Q)\n"
        "  --query METIN                          --list-items için arama süzgeci\n"
        "  --merge / --replace                    --import-ini ve --restore için birleştir/değiştir modu\n"
        "  --keep N                               --backup için tutulacak maksimum yedek sayısı\n"
        "  --port N                               --web için 127.0.0.1 bağlantı noktası (varsayılan: 8765)\n"
        "  --open-browser                         --web başlatıldığında tarayıcıyı açar\n"
        "  --shutdown-after SN                    --web sunucusunu belirtilen saniye sonra zarifçe kapatır\n"
    )
    if not verbose:
        return base

    preset_lines = [
        f"  {pid:<16} {', '.join(f'{k}={v}' for k, v in pmap.items())}  [{HOTKEY_PRESET_LABELS.get(pid, pid)}]"
        for pid, pmap in HOTKEY_PRESETS.items()
    ]
    setting_keys = []
    for k, v in DEFAULT_SETTINGS.items():
        if isinstance(v, dict):
            for sub in v:
                setting_keys.append(f"{k}.{sub}")
        else:
            setting_keys.append(k)
    setting_keys.extend(["hotkeys.all", "hotkeys.A", "hotkeys.Z", "hotkeys.X", "hotkeys.Q", "hotkeys.<özel>"])
    return (
        base
        + "\nAyrıntılı Başvuru (--verbose):\n"
        + "\nKısayol Profilleri (--hotkey-preset):\n"
        + "\n".join(preset_lines)
        + "\n\nGeçerli Ayar Anahtarları (--get / --set):\n  "
        + ", ".join(setting_keys)
        + "\n\nÇıkış Kodları:\n"
        "  0  Başarılı\n"
        "  1  Genel G/Ç, derleme veya Web port hatası\n"
        "  2  Geçersiz CLI argümanı, ayar anahtarı/değeri veya bulunamayan kayıt/kabuk\n"
        "  3  Pano erişimi başarısız (başsız grafik oturumu yok)\n"
        "  4  Tuş simülasyonu başarısız (pano kopyalandı, Wayland/pencere odak kısıtı)\n"
        + "\nTaşınabilir ve Salt-Okunur Yapılandırma Yolları:\n"
        "  Taşınabilir : <ikili_klasörü>/{qtp_settings.json, qtp.log, backups/, QuickTextPaste.ini, data.json}\n"
        "  Windows     : %APPDATA%\\QTP\\\n"
        "  Linux/BSD   : $XDG_CONFIG_HOME/qtp/ (varsayılan ~/.config/qtp/)\n"
        "  macOS       : ~/Library/Application Support/QTP/\n"
        + "\nKabuk Otomatik Tamamlama (--completion) Kurulumu:\n"
        "  PowerShell  : qtp.exe --completion powershell | Out-String | Invoke-Expression\n"
        "  Bash        : eval \"$(./qtp.bin --completion bash)\"\n"
        "  Zsh         : eval \"$(./qtp.bin --completion zsh)\"\n"
        "  Fish        : ./qtp.bin --completion fish | source\n"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False, prog="qtp")
    parser.add_argument("--mode", choices=["gui", "tui", "cli", "web"], default=None)
    parser.add_argument("--gui", action="store_const", const="gui", dest="mode_shorthand")
    parser.add_argument("--tui", action="store_const", const="tui", dest="mode_shorthand")
    parser.add_argument("--cli", action="store_const", const="cli", dest="mode_shorthand")
    parser.add_argument("--web", action="store_const", const="web", dest="mode_shorthand")

    parser.add_argument("-h", "--help", action="store_true", dest="show_help")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--modes", action="store_true")
    parser.add_argument("--completion", nargs="?", const="auto", default=None, metavar="KABUK")
    parser.add_argument("--list-categories", action="store_true")
    parser.add_argument("--list-items", action="store_true")
    parser.add_argument("--search", metavar="SORGU")
    parser.add_argument("--show-ini", metavar="HEDEF")
    parser.add_argument("--copy", metavar="HEDEF")
    parser.add_argument("--paste", metavar="HEDEF")
    parser.add_argument("--export-ini", metavar="YOL")
    parser.add_argument("--import-ini", metavar="YOL")
    parser.add_argument("--export-backup", metavar="YOL")
    parser.add_argument("--restore", metavar="HEDEF")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--get", metavar="ANAHTAR")
    parser.add_argument("--set", nargs=2, metavar=("ANAHTAR", "DEGER"))
    parser.add_argument("--check-hotkeys", action="store_true")
    parser.add_argument("--hotkey-preset", metavar="PROFIL")
    parser.add_argument("--hotkey-modifiers", metavar="DEGISTIRICILER")

    parser.add_argument("--category", default="ALL")
    parser.add_argument("--query", default="")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--work-dir", metavar="DIZIN")
    parser.add_argument("--keep", type=int, default=None)

    merge_group = parser.add_mutually_exclusive_group()
    merge_group.add_argument("--merge", action="store_true")
    merge_group.add_argument("--replace", action="store_true")

    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--shutdown-after", type=float, default=None)
    return parser


def collect_option_strings(parser: argparse.ArgumentParser) -> list[str]:
    seen: list[str] = []
    for action in parser._actions:
        for opt in action.option_strings:
            if opt not in seen:
                seen.append(opt)
    return seen


def _has_cli_action(args: argparse.Namespace) -> bool:
    return any(
        (
            args.show_help,
            args.version,
            args.selftest,
            args.modes,
            args.completion is not None,
            args.list_categories,
            args.list_items,
            args.search is not None,
            args.show_ini is not None,
            args.copy is not None,
            args.paste is not None,
            args.export_ini is not None,
            args.import_ini is not None,
            args.export_backup is not None,
            args.restore is not None,
            args.backup,
            args.reload,
            args.get is not None,
            args.set is not None,
            args.check_hotkeys,
            args.hotkey_preset is not None,
            args.hotkey_modifiers is not None,
        )
    )


def determine_mode(args: argparse.Namespace) -> tuple[str | None, str | None]:
    """Çalışma modunu belirler; CI/non-TTY durumunda açık --mode gerektirir."""
    explicit = args.mode or args.mode_shorthand
    if explicit:
        return explicit, None
    if _has_cli_action(args):
        return "cli", None

    is_ci = bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))
    non_tty = sys.stdin is not None and not sys.stdin.isatty()
    if is_ci or non_tty:
        return None, (
            "HATA: Etkileşimsiz ortamda/CI içinde açıkça --mode {gui,tui,cli,web} belirtilmelidir."
        )
    return "gui", None


def _print_result(
    result: Any,
    *,
    as_json: bool = False,
    quiet: bool = False,
    raw_formatter: Any = None,
    suppress_ok_if_quiet: bool = False,
) -> int:
    if as_json:
        print(json.dumps(result.to_api_dict(), ensure_ascii=False, indent=2), file=sys.stdout)
        return result.exit_code

    stream = sys.stdout if result.ok else sys.stderr
    if result.ok and quiet and suppress_ok_if_quiet:
        return result.exit_code
    if result.ok and raw_formatter is not None:
        print(raw_formatter(result), file=stream)
    else:
        print(result.message, file=stream)
    return result.exit_code


def _emit_verbose_diagnostics(
    engine: QtpEngine,
    verbose_level: int,
    mode: str,
    started_at: float | None = None,
) -> None:
    if verbose_level <= 0:
        return
    print(
        f"[INFO] mod={mode} çalışma_dizini={engine.work_dir} yapılandırma={engine.config_dir} taşınabilir={engine.portable} kayıt={len(engine.items)}",
        file=sys.stderr,
    )
    if verbose_level >= 2:
        conflicts = engine.op_check_hotkeys().data["conflicts"]
        dur_ms = int((time.monotonic() - started_at) * 1000) if started_at is not None else 0
        print(
            f"[DEBUG] ini_yolu={engine.ini_path} ayarlar_yolu={engine.settings_path} tema={engine.settings.get('theme')} otomatik_yenileme={engine.settings.get('auto_reload')} aralik_ms={engine.settings.get('auto_reload_interval_ms')} kısayol_uyarısı={len(conflicts)} süre_ms={dur_ms}",
            file=sys.stderr,
        )


def execute_cli(
    engine: QtpEngine,
    args: argparse.Namespace,
    *,
    option_strings: list[str] | None = None,
) -> int:
    as_json = bool(args.as_json)
    verbose = int(getattr(args, "verbose", 0) or 0)
    quiet = bool(getattr(args, "quiet", False))
    started_at = time.monotonic()

    if verbose > 0 and not quiet:
        _emit_verbose_diagnostics(engine, verbose, "cli", started_at)

    if args.show_help:
        txt = format_help_text(verbose=verbose > 0)
        if as_json:
            return _print_result(engine.op_help(txt), as_json=True)
        print(txt)
        return 0

    if args.version:
        return _print_result(engine.op_version(), as_json=as_json)

    if args.selftest:
        return _print_result(engine.op_selftest(run_ui_smoke=True), as_json=as_json, quiet=quiet)

    if args.modes:
        return _print_result(engine.op_modes(), as_json=as_json)

    if getattr(args, "completion", None) is not None:
        return _print_result(
            engine.op_completion(args.completion, option_strings=option_strings),
            as_json=as_json,
            raw_formatter=lambda r: r.data["script"].rstrip("\n"),
        )

    if args.list_categories:
        return _print_result(
            engine.op_list_categories(),
            as_json=as_json,
            raw_formatter=lambda r: "\n".join(
                f"{c['code']:<4} {c['label']} ({c['count']})" for c in r.data["categories"]
            ),
        )

    if args.list_items:
        return _print_result(
            engine.op_list_items(category=args.category, query=args.query),
            as_json=as_json,
            raw_formatter=lambda r: "\n".join(
                f"{it['raw_key']} [{it['keys']}] {it['text']}" for it in r.data["items"]
            ),
        )

    if args.search is not None:
        return _print_result(
            engine.op_search(args.search, category=args.category),
            as_json=as_json,
            raw_formatter=lambda r: "\n".join(
                f"{it['raw_key']} [{it['keys']}] {it['text']}" for it in r.data["items"]
            ),
        )

    if args.show_ini is not None:
        return _print_result(
            engine.op_show_ini(args.show_ini),
            as_json=as_json,
            raw_formatter=lambda r: r.data["preview"],
        )

    if args.copy is not None:
        return _print_result(engine.op_copy(args.copy), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if args.paste is not None:
        return _print_result(engine.op_paste(args.paste), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if args.export_ini is not None:
        return _print_result(engine.op_export_ini(Path(args.export_ini)), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if args.import_ini is not None:
        imp_mode = "replace" if args.replace else "merge"
        return _print_result(engine.op_import_ini(Path(args.import_ini), mode=imp_mode), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if args.export_backup is not None:
        return _print_result(engine.op_export_backup(Path(args.export_backup)), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if args.restore is not None:
        rest_mode = "merge" if args.merge else "replace"
        return _print_result(engine.op_restore(args.restore, mode=rest_mode), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if args.backup:
        return _print_result(engine.op_backup(keep=args.keep), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if args.reload:
        return _print_result(engine.reload_data(), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if args.get is not None:
        return _print_result(
            engine.op_get_setting(args.get),
            as_json=as_json,
            raw_formatter=lambda r: f"{r.data['key']}={r.data['value']}",
        )

    if args.set is not None:
        return _print_result(engine.op_set_setting(args.set[0], args.set[1]), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "check_hotkeys", False):
        def _fmt_check(res: Any) -> str:
            hk_lines = [f"  {k:<6} -> {v}" for k, v in res.data["hotkeys"].items()]
            cdict = res.data["conflicts"]
            if not cdict:
                return res.message + "\n" + "\n".join(hk_lines)
            wlines = [f"  [!] {k}: {'; '.join(msgs)}" for k, msgs in cdict.items()]
            return res.message + "\n" + "\n".join(hk_lines) + "\nUyarılar:\n" + "\n".join(wlines)

        return _print_result(engine.op_check_hotkeys(), as_json=as_json, raw_formatter=_fmt_check)

    if getattr(args, "hotkey_preset", None) is not None:
        res = engine.op_apply_hotkey_preset(args.hotkey_preset)
        if res.warning and not as_json and not quiet:
            print(f"UYARI: {res.warning}", file=sys.stderr)
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "hotkey_modifiers", None) is not None:
        res = engine.op_apply_hotkey_modifiers(args.hotkey_modifiers)
        if res.warning and not as_json and not quiet:
            print(f"UYARI: {res.warning}", file=sys.stderr)
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    print(format_help_text(verbose=verbose > 0))
    return 0


def run(argv: list[str] | None = None) -> int:
    started_at = time.monotonic()
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and (sys.stdout is None or sys.stderr is None):
        pre_mode = "tui" if "--tui" in raw_args else "cli"
        attach_windows_console_if_needed(pre_mode)
    configure_stdio()

    try:
        parser = build_arg_parser()
        args, unknown = parser.parse_known_args(argv)
        mode, mode_err = determine_mode(args)
        attach_windows_console_if_needed(mode or "cli")
        configure_stdio()

        if unknown:
            print(f"HATA: Bilinmeyen komut satırı seçeneği: {' '.join(unknown)}", file=sys.stderr)
            print(format_help_text(verbose=bool(args.verbose)), file=sys.stderr)
            return 2

        if mode_err:
            print(mode_err, file=sys.stderr)
            return 2

        work_dir = Path(args.work_dir).resolve() if args.work_dir else None

        if mode == "cli" and args.show_help and not args.as_json:
            print(format_help_text(verbose=bool(args.verbose)))
            return 0

        ephemeral = bool(
            mode == "cli"
            and (
                args.show_help
                or args.version
                or args.modes
                or args.selftest
                or args.completion is not None
                or args.check_hotkeys
            )
        )
        engine = QtpEngine(work_dir=work_dir, seed_defaults=not ephemeral, ephemeral=ephemeral)
        opt_strings = collect_option_strings(parser)

        if mode == "cli":
            return execute_cli(engine, args, option_strings=opt_strings)

        if int(args.verbose or 0) > 0 and not bool(args.quiet):
            _emit_verbose_diagnostics(engine, int(args.verbose), mode or "gui", started_at)

        if mode == "tui":
            from qtp_app.tui import run_tui

            return run_tui(engine)

        if mode == "web":
            from qtp_app.web import run_web_server

            return run_web_server(
                engine,
                port=args.port,
                open_browser=bool(args.open_browser),
                shutdown_after=args.shutdown_after,
                quiet=bool(args.quiet),
            )

        from qtp_app.main import launch_gui

        return launch_gui(engine)
    finally:
        for stream in (sys.stdout, sys.stderr):
            try:
                if stream is not None:
                    stream.flush()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(run())
