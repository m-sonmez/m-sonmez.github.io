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

from qtp_app.core.engine import QtpEngine, build_cli_help_text
from qtp_app.core.i18n import resolve_language
from qtp_app.core.operations import OPERATIONS
from qtp_app.core.settings import SETTINGS_FILENAME

TH32CS_SNAPPROCESS = 0x00000002
_CONSOLE_ATTACHED_EXISTING = False

_CLI_ACTION_FLAGS = frozenset(
    {
        "--version",
        "--selftest",
        "--modes",
        "--completion",
        "--list-categories",
        "--list-items",
        "--search",
        "--show-ini",
        "--copy",
        "--paste",
        "--export-ini",
        "--import-ini",
        "--export-backup",
        "--restore",
        "--backup",
        "--reload",
        "--save",
        "--get",
        "--set",
        "--check-hotkeys",
        "--hotkey-preset",
        "--hotkey-modifiers",
        "--add-item",
        "--update-item",
        "--delete-item",
        "--duplicate-item",
        "--move-item",
        "--toggle-favorite",
        "--bulk-edit",
        "--bulk-delete",
        "--rename-group",
        "--delete-group",
        "--undo",
        "--redo",
    }
)


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


def attach_windows_console_if_needed(mode: str, *, allow_gui_console: bool = False) -> bool:
    """
    Windows tek-dosya (console=False) ikilisinde konsol akışları None ise ata süreç zincirini
    yürüyerek PowerShell/cmd/Terminal konsoluna (AttachConsole) veya TUI için yeni konsola bağlanır.
    Sessiz/çift-tık GUI açılışında konsol penceresi açmaz ve boru hatlarını bozmaz.
    """
    global _CONSOLE_ATTACHED_EXISTING
    _CONSOLE_ATTACHED_EXISTING = False

    if sys.platform != "win32":
        return False
    allowed = mode in ("cli", "tui", "web") or (mode == "gui" and allow_gui_console)
    if not allowed:
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


def _detect_pre_mode(raw_args: list[str]) -> str | None:
    mode: str | None = None
    i = 0
    while i < len(raw_args):
        tok = raw_args[i]
        if tok in ("--gui", "--tui", "--cli", "--web"):
            mode = tok[2:]
        elif tok == "--mode" and i + 1 < len(raw_args):
            cand = raw_args[i + 1].strip().lower()
            if cand in ("gui", "tui", "cli", "web"):
                mode = cand
            i += 1
        elif tok.startswith("--mode="):
            cand = tok.split("=", 1)[1].strip().lower()
            if cand in ("gui", "tui", "cli", "web"):
                mode = cand
        i += 1
    return mode


def _has_explicit_flag(raw_args: list[str], flag_name: str) -> bool:
    prefix = flag_name + "="
    return any(tok == flag_name or tok.startswith(prefix) for tok in raw_args)


def _attach_windows_console_before_argparse(raw_args: list[str]) -> bool:
    """
    argparse öncesinde Windows üst konsolunu bağlar:
    --help, --verbose, --cli, --tui, --web için ebeveyn konsoluna bağlanır;
    boş argümanlı çift tık veya sessiz/düz --gui açılışında konsol bağlamaz veya açmaz.
    """
    if not raw_args or (sys.stdout is not None and sys.stderr is not None):
        return False

    wants_help = any(tok in ("-h", "--help") for tok in raw_args)
    wants_verbose = any(
        tok == "--verbose" or (tok.startswith("-") and not tok.startswith("--") and "v" in tok[1:])
        for tok in raw_args
    )
    wants_cli_action = any(tok.split("=", 1)[0] in _CLI_ACTION_FLAGS for tok in raw_args)
    pre_mode = _detect_pre_mode(raw_args)

    if wants_help:
        return attach_windows_console_if_needed("cli")
    if pre_mode == "tui":
        return attach_windows_console_if_needed("tui")
    if pre_mode == "web":
        return attach_windows_console_if_needed("web")
    if pre_mode == "gui":
        if wants_verbose or wants_cli_action:
            return attach_windows_console_if_needed("gui", allow_gui_console=True)
        return False
    if pre_mode == "cli" or wants_verbose or wants_cli_action:
        return attach_windows_console_if_needed("cli")
    return False


def _resolve_cli_help_language(work_dir: Path | None = None) -> str:
    lang_setting = "auto"
    if work_dir is not None:
        cfg_file = work_dir / SETTINGS_FILENAME
        if cfg_file.is_file():
            try:
                raw = json.loads(cfg_file.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and raw.get("language"):
                    lang_setting = str(raw["language"])
            except Exception:
                pass
    return resolve_language(lang_setting, work_dir)


def format_help_text(
    *,
    verbose: bool = False,
    lang: str | None = None,
    config_dir: Path | None = None,
) -> str:
    eff_lang = lang if lang else _resolve_cli_help_language(config_dir)
    return build_cli_help_text(verbose=verbose, lang=eff_lang, config_dir=config_dir)


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
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--get", metavar="ANAHTAR")
    parser.add_argument("--set", nargs=2, metavar=("ANAHTAR", "DEGER"))
    parser.add_argument("--check-hotkeys", action="store_true")
    parser.add_argument("--hotkey-preset", metavar="PROFIL")
    parser.add_argument("--hotkey-modifiers", metavar="DEGISTIRICILER")
    parser.add_argument("--add-item", metavar="METIN")
    parser.add_argument("--update-item", metavar="HEDEF")
    parser.add_argument("--delete-item", metavar="HEDEF")
    parser.add_argument("--duplicate-item", metavar="HEDEF")
    parser.add_argument("--move-item", metavar="HEDEF")
    parser.add_argument("--direction", default="up", choices=["up", "down"])
    parser.add_argument("--toggle-favorite", metavar="HEDEF")
    parser.add_argument("--bulk-edit", metavar="HEDEFLER")
    parser.add_argument("--bulk-delete", metavar="HEDEFLER")
    parser.add_argument("--rename-group", metavar="ESKI")
    parser.add_argument("--new-group", default="", metavar="YENI")
    parser.add_argument("--delete-group", metavar="GRUP")
    parser.add_argument("--undo", action="store_true")
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--item-keys", default=None, metavar="TUS")
    parser.add_argument("--item-group", default=None, metavar="GRUP")
    parser.add_argument("--item-label", default=None, metavar="ETIKET")
    parser.add_argument("--item-text", default=None, metavar="METIN")
    parser.add_argument("--item-favorite", default=None, choices=["true", "false"])
    parser.add_argument("--no-end-marker", action="store_true")

    parser.add_argument("--find", default=None, metavar="ARANAN")
    parser.add_argument("--ignore-case", action="store_true")
    parser.add_argument("--prefix", default="", metavar="ONEK")
    parser.add_argument("--suffix", default="", metavar="SONEK")
    parser.add_argument("--strip-emojis", action="store_true")
    parser.add_argument("--add-emoji", default="", metavar="EMOJI")
    parser.add_argument("--favorite-action", default="keep", choices=["keep", "add", "remove"])

    parser.add_argument("--category", default="ALL")
    parser.add_argument("--query", default="")
    parser.add_argument("--only-favorites", action="store_true")
    parser.add_argument("--only-notes", action="store_true")
    parser.add_argument("--group", default="", metavar="GRUP")
    parser.add_argument("--sort", default=None, choices=["order", "usage", "alpha", "keys", "favorites"])
    parser.add_argument("--strip-emoji", action="store_true")
    parser.add_argument("--selected-keys", default="", metavar="ANAHTARLAR")
    parser.add_argument("--encoding", default="utf-16-le-bom")
    parser.add_argument("--skip-duplicates", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--work-dir", metavar="DIZIN")
    parser.add_argument("--keep", type=int, default=None)

    merge_group = parser.add_mutually_exclusive_group()
    merge_group.add_argument("--merge", action="store_true")
    merge_group.add_argument("--replace-all", action="store_true")
    merge_group.add_argument("--replace", nargs="?", const="__FLAG_TRUE__", default=None, metavar="YENI")

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
            args.save,
            args.get is not None,
            args.set is not None,
            args.check_hotkeys,
            args.hotkey_preset is not None,
            args.hotkey_modifiers is not None,
            args.add_item is not None,
            args.update_item is not None,
            args.delete_item is not None,
            args.duplicate_item is not None,
            args.move_item is not None,
            args.toggle_favorite is not None,
            args.bulk_edit is not None,
            args.bulk_delete is not None,
            args.rename_group is not None,
            args.delete_group is not None,
            args.undo,
            args.redo,
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
    engine.configure_verbosity(verbose_level, False)
    engine.emit_startup_diagnostics(mode, started_at)


def _dispatch_cli_action(
    engine: QtpEngine,
    args: argparse.Namespace,
    *,
    as_json: bool,
    verbose: int,
    quiet: bool,
    option_strings: list[str] | None,
) -> int:
    if args.show_help:
        txt = format_help_text(
            verbose=verbose > 0,
            lang=engine.resolved_language(),
            config_dir=engine.config_dir,
        )
        if as_json:
            return _print_result(engine.op_help(txt, verbose=verbose > 0), as_json=True)
        print(txt)
        return 0

    if args.version:
        return _print_result(engine.op_version(), as_json=as_json)

    if args.selftest:
        return _print_result(
            engine.op_selftest(run_ui_smoke=True),
            as_json=as_json,
            quiet=quiet,
            suppress_ok_if_quiet=True,
        )

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
            engine.op_list_items(
                category=args.category,
                query=args.query,
                only_favorites=bool(getattr(args, "only_favorites", False)),
                only_notes=bool(getattr(args, "only_notes", False)),
                group=str(getattr(args, "group", "") or ""),
                sort_by=getattr(args, "sort", None),
            ),
            as_json=as_json,
            raw_formatter=lambda r: "\n".join(
                f"{it['raw_key']} [{it['keys']}] {it['text']}" for it in r.data["items"]
            ),
        )

    if args.search is not None:
        return _print_result(
            engine.op_search(
                args.search,
                category=args.category,
                only_favorites=bool(getattr(args, "only_favorites", False)),
                only_notes=bool(getattr(args, "only_notes", False)),
                group=str(getattr(args, "group", "") or ""),
                sort_by=getattr(args, "sort", None),
            ),
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
        strip_opt = True if getattr(args, "strip_emoji", False) else None
        return _print_result(
            engine.op_copy(args.copy, strip_emoji=strip_opt),
            as_json=as_json,
            quiet=quiet,
            suppress_ok_if_quiet=True,
        )

    if args.paste is not None:
        strip_opt = True if getattr(args, "strip_emoji", False) else None
        return _print_result(
            engine.op_paste(args.paste, strip_emoji=strip_opt),
            as_json=as_json,
            quiet=quiet,
            suppress_ok_if_quiet=True,
        )

    if args.export_ini is not None:
        sel_csv = str(getattr(args, "selected_keys", "") or "")
        raw_keys = [k.strip() for k in sel_csv.split(",") if k.strip()] or None
        enc = str(getattr(args, "encoding", "utf-16-le-bom") or "utf-16-le-bom")
        return _print_result(
            engine.op_export_ini(Path(args.export_ini), raw_keys=raw_keys, encoding=enc),
            as_json=as_json,
            quiet=quiet,
            suppress_ok_if_quiet=True,
        )

    if args.import_ini is not None:
        imp_mode = "replace" if (getattr(args, "replace_all", False) or getattr(args, "replace", None) == "__FLAG_TRUE__") else "merge"
        skip_dup = bool(getattr(args, "skip_duplicates", False))
        return _print_result(
            engine.op_import_ini(Path(args.import_ini), mode=imp_mode, skip_duplicates=skip_dup),
            as_json=as_json,
            quiet=quiet,
            suppress_ok_if_quiet=True,
        )

    if args.export_backup is not None:
        return _print_result(engine.op_export_backup(Path(args.export_backup)), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if args.restore is not None:
        rest_mode = "merge" if args.merge else "replace"
        return _print_result(engine.op_restore(args.restore, mode=rest_mode), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if args.backup:
        return _print_result(engine.op_backup(keep=args.keep), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if args.reload:
        return _print_result(engine.reload_data(), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "save", False):
        return _print_result(engine.op_save_all(), as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

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

    if getattr(args, "add_item", None) is not None:
        term = "" if args.no_end_marker else "<E<N<D|"
        fav_flag = str(getattr(args, "item_favorite", "") or "").lower() == "true"
        res = engine.op_add_item(
            args.add_item,
            keys=args.item_keys or "",
            group=args.item_group or "Genel",
            label=args.item_label or "",
            terminator=term,
            favorite=fav_flag,
        )
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "update_item", None) is not None:
        term = "" if args.no_end_marker else None
        fav_arg = getattr(args, "item_favorite", None)
        fav_opt = None if fav_arg is None else (str(fav_arg).lower() == "true")
        res = engine.op_update_item(
            args.update_item,
            keys=args.item_keys,
            group=args.item_group,
            label=args.item_label,
            text=args.item_text,
            terminator=term,
            favorite=fav_opt,
        )
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "delete_item", None) is not None:
        res = engine.op_delete_item(args.delete_item)
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "duplicate_item", None) is not None:
        res = engine.op_duplicate_item(args.duplicate_item)
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "move_item", None) is not None:
        res = engine.op_move_item(args.move_item, direction=getattr(args, "direction", "up"))
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "toggle_favorite", None) is not None:
        fav_arg = getattr(args, "item_favorite", None)
        fav_opt = None if fav_arg is None else (str(fav_arg).lower() == "true")
        res = engine.op_toggle_favorite(args.toggle_favorite, favorite=fav_opt)
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "bulk_edit", None) is not None:
        raw_repl = getattr(args, "replace", None)
        repl_val = "" if raw_repl in (None, "__FLAG_TRUE__") else str(raw_repl)
        res = engine.op_bulk_edit(
            args.bulk_edit,
            keys=args.item_keys,
            group=args.item_group,
            find=getattr(args, "find", None),
            replace=repl_val,
            ignore_case=bool(getattr(args, "ignore_case", False)),
            prefix=str(getattr(args, "prefix", "") or ""),
            suffix=str(getattr(args, "suffix", "") or ""),
            strip_emojis=bool(getattr(args, "strip_emojis", False)),
            add_emoji=str(getattr(args, "add_emoji", "") or ""),
            favorite_action=str(getattr(args, "favorite_action", "keep") or "keep"),
        )
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "bulk_delete", None) is not None:
        res = engine.op_bulk_delete(args.bulk_delete)
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "rename_group", None) is not None:
        res = engine.op_rename_group(args.rename_group, getattr(args, "new_group", ""))
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "delete_group", None) is not None:
        res = engine.op_delete_group(args.delete_group)
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "undo", False):
        res = engine.op_undo()
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if getattr(args, "redo", False):
        res = engine.op_redo()
        return _print_result(res, as_json=as_json, quiet=quiet, suppress_ok_if_quiet=True)

    if (
        str(getattr(args, "category", "ALL")).strip().upper() != "ALL"
        or str(getattr(args, "query", ""))
        or bool(getattr(args, "only_favorites", False))
        or bool(getattr(args, "only_notes", False))
        or str(getattr(args, "group", "") or "")
    ):
        return _print_result(
            engine.op_list_items(
                category=args.category,
                query=args.query,
                only_favorites=bool(getattr(args, "only_favorites", False)),
                only_notes=bool(getattr(args, "only_notes", False)),
                group=str(getattr(args, "group", "") or ""),
                sort_by=getattr(args, "sort", None),
            ),
            as_json=as_json,
            raw_formatter=lambda r: "\n".join(
                f"{it['raw_key']} [{it['keys']}] {it['text']}" for it in r.data["items"]
            ),
        )

    print(format_help_text(verbose=verbose > 0, lang=engine.resolved_language(), config_dir=engine.config_dir))
    return 0


def execute_cli(
    engine: QtpEngine,
    args: argparse.Namespace,
    *,
    option_strings: list[str] | None = None,
    verbose: int | None = None,
    quiet: bool | None = None,
) -> int:
    as_json = bool(args.as_json)
    eff_verbose = int(verbose if verbose is not None else (getattr(args, "verbose", 0) or 0))
    raw_quiet = bool(quiet if quiet is not None else getattr(args, "quiet", False))
    eff_quiet = raw_quiet and eff_verbose <= 0
    started_at = time.monotonic()

    if eff_verbose > 0:
        engine.configure_verbosity(eff_verbose, eff_quiet)
        engine.emit_startup_diagnostics("cli", started_at)

    rc = _dispatch_cli_action(
        engine,
        args,
        as_json=as_json,
        verbose=eff_verbose,
        quiet=eff_quiet,
        option_strings=option_strings,
    )
    if eff_verbose > 0:
        dur_ms = int((time.monotonic() - started_at) * 1000)
        engine.logger.info("CLI işlemi tamamlandı (çıkış=%d, süre_ms=%d).", rc, dur_ms)
    return rc


def run(argv: list[str] | None = None) -> int:
    started_at = time.monotonic()
    raw_args = list(sys.argv[1:] if argv is None else argv)
    _attach_windows_console_before_argparse(raw_args)
    configure_stdio()

    try:
        parser = build_arg_parser()
        args, unknown = parser.parse_known_args(argv)
        verbose = int(getattr(args, "verbose", 0) or 0)
        raw_quiet = bool(getattr(args, "quiet", False))
        effective_quiet = raw_quiet and verbose <= 0

        if unknown or args.show_help or verbose > 0:
            attach_windows_console_if_needed("cli")
            configure_stdio()

        if unknown:
            print(f"HATA: Bilinmeyen komut satırı seçeneği: {' '.join(unknown)}", file=sys.stderr)
            print(format_help_text(verbose=verbose > 0), file=sys.stderr)
            return 2

        mode, mode_err = determine_mode(args)
        if mode_err:
            attach_windows_console_if_needed("cli")
            configure_stdio()
            print(mode_err, file=sys.stderr)
            return 2

        if mode in ("cli", "tui", "web") or (mode == "gui" and verbose > 0):
            attach_mode = "cli" if args.show_help else (mode or "cli")
            attach_windows_console_if_needed(attach_mode, allow_gui_console=verbose > 0)
            configure_stdio()

        work_dir = Path(args.work_dir).resolve() if args.work_dir else None

        if args.show_help and not args.as_json:
            print(format_help_text(verbose=verbose > 0, config_dir=work_dir))
            return 0

        ephemeral = bool(
            args.show_help
            or (
                mode == "cli"
                and (
                    args.version
                    or args.modes
                    or args.selftest
                    or args.completion is not None
                    or args.check_hotkeys
                )
            )
        )
        engine = QtpEngine(
            work_dir=work_dir,
            seed_defaults=not ephemeral,
            ephemeral=ephemeral,
            verbose=verbose,
            quiet=effective_quiet,
        )
        opt_strings = collect_option_strings(parser)

        if args.show_help:
            return execute_cli(
                engine,
                args,
                option_strings=opt_strings,
                verbose=verbose,
                quiet=effective_quiet,
            )

        if mode == "cli":
            return execute_cli(
                engine,
                args,
                option_strings=opt_strings,
                verbose=verbose,
                quiet=effective_quiet,
            )

        if verbose > 0:
            engine.emit_startup_diagnostics(mode or "gui", started_at)

        explicit_category = str(args.category).strip().upper() if _has_explicit_flag(raw_args, "--category") else None
        initial_query = str(getattr(args, "query", "") or "")

        if mode == "tui":
            from qtp_app.tui import run_tui

            return run_tui(
                engine,
                verbose=verbose,
                quiet=effective_quiet,
                initial_category=explicit_category,
                initial_query=initial_query,
            )

        if mode == "web":
            from qtp_app.web import run_web_server

            return run_web_server(
                engine,
                port=args.port,
                open_browser=bool(args.open_browser),
                shutdown_after=args.shutdown_after,
                quiet=effective_quiet,
                verbose=verbose,
                initial_category=explicit_category or "ALL",
                initial_query=initial_query,
            )

        from qtp_app.main import launch_gui

        return launch_gui(
            engine,
            verbose=verbose,
            quiet=effective_quiet,
            initial_category=explicit_category,
            initial_query=initial_query,
        )
    finally:
        for stream in (sys.stdout, sys.stderr):
            try:
                if stream is not None:
                    stream.flush()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(run())
