"""Tüm QTP çalışma modları (--gui, --tui, --cli, --web) için birleşik komut satırı ayrıştırıcısı ve çalıştırıcı."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
from pathlib import Path
from typing import Any

from qtp_app import __display_name__, __version__
from qtp_app.core.engine import QtpEngine
from qtp_app.core.operations import OPERATIONS


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def attach_windows_console_if_needed(mode: str) -> None:
    """
    Windows tek-dosya (console=False) ikilisinde --cli / --tui çalıştırılırken
    stdout/stderr bağlı değilse üst konsola (AttachConsole) veya yeni konsola (AllocConsole) bağlanır.
    Alt süreç (pipe) yakalamasına dokunmaz.
    """
    if sys.platform != "win32" or mode not in ("cli", "tui"):
        return
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        k32 = ctypes.windll.kernel32
        attached = bool(k32.AttachConsole(-1))
        if not attached and mode == "tui":
            attached = bool(k32.AllocConsole())
        if attached:
            if sys.stdout is None:
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
            if sys.stderr is None:
                sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
            if sys.stdin is None:
                sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
    except Exception:
        pass


def format_help_text() -> str:
    op_lines = []
    for op in OPERATIONS:
        flag_disp = f"{op.cli_flag} {op.args_spec}".strip()
        op_lines.append(f"  {flag_disp:<34} {op.label_tr}")
    return (
        f"{__display_name__} v{__version__} — Komut Satırı Kullanımı\n\n"
        "Kullanım:\n"
        "  qtp [--mode {gui,tui,cli,web} | --gui | --tui | --cli | --web] [SEÇENEK]\n\n"
        "Çalışma Modları:\n"
        "  --mode {gui,tui,cli,web}           Çalışma modunu seçer (kısayol: --gui, --tui, --cli, --web).\n"
        "  --work-dir DIZIN                   Veri ve ayarlar için çalışma dizini belirler.\n"
        "  --json                             Salt-okunur CLI çıktılarını UTF-8 JSON biçiminde basar.\n\n"
        "İşlemler (Operation Registry):\n"
        + "\n".join(op_lines)
        + "\n\nEk Seçenekler:\n"
        "  --category KOD                     --list-items / --search için kategori filtresi (ALL/A/Z/X/Q)\n"
        "  --query METIN                      --list-items için arama süzgeci\n"
        "  --merge / --replace                --import-ini ve --restore için birleştir/değiştir modu\n"
        "  --keep N                           --backup için tutulacak maksimum yedek sayısı\n"
        "  --port N                           --web için 127.0.0.1 bağlantı noktası (varsayılan: 8765)\n"
        "  --open-browser                     --web başlatıldığında tarayıcıyı açar\n"
        "  --shutdown-after SN                --web sunucusunu belirtilen saniye sonra zarifçe kapatır\n"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False, prog="qtp")
    parser.add_argument("--mode", choices=["gui", "tui", "cli", "web"], default=None)
    parser.add_argument("--gui", action="store_const", const="gui", dest="mode_shorthand")
    parser.add_argument("--tui", action="store_const", const="tui", dest="mode_shorthand")
    parser.add_argument("--cli", action="store_const", const="cli", dest="mode_shorthand")
    parser.add_argument("--web", action="store_const", const="web", dest="mode_shorthand")

    parser.add_argument("-h", "--help", action="store_true", dest="show_help")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--modes", action="store_true")
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


def _has_cli_action(args: argparse.Namespace) -> bool:
    return any(
        (
            args.show_help,
            args.version,
            args.selftest,
            args.modes,
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


def _print_result(result: Any, *, as_json: bool = False, raw_formatter: Any = None) -> int:
    if as_json:
        out = sys.stdout if result.ok else sys.stdout
        print(json.dumps(result.to_api_dict(), ensure_ascii=False, indent=2), file=out)
        return result.exit_code

    stream = sys.stdout if result.ok else sys.stderr
    if result.ok and raw_formatter is not None:
        print(raw_formatter(result), file=stream)
    else:
        print(result.message, file=stream)
    return result.exit_code


def execute_cli(engine: QtpEngine, args: argparse.Namespace) -> int:
    as_json = bool(args.as_json)

    if args.show_help:
        txt = format_help_text()
        if as_json:
            return _print_result(engine.op_help(txt), as_json=True)
        print(txt)
        return 0

    if args.version:
        return _print_result(engine.op_version(), as_json=as_json)

    if args.selftest:
        return _print_result(engine.op_selftest(run_ui_smoke=True), as_json=as_json)

    if args.modes:
        return _print_result(engine.op_modes(), as_json=as_json)

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
        return _print_result(engine.op_copy(args.copy), as_json=as_json)

    if args.paste is not None:
        return _print_result(engine.op_paste(args.paste), as_json=as_json)

    if args.export_ini is not None:
        return _print_result(engine.op_export_ini(Path(args.export_ini)), as_json=as_json)

    if args.import_ini is not None:
        imp_mode = "replace" if args.replace else "merge"
        return _print_result(engine.op_import_ini(Path(args.import_ini), mode=imp_mode), as_json=as_json)

    if args.export_backup is not None:
        return _print_result(engine.op_export_backup(Path(args.export_backup)), as_json=as_json)

    if args.restore is not None:
        rest_mode = "merge" if args.merge else "replace"
        return _print_result(engine.op_restore(args.restore, mode=rest_mode), as_json=as_json)

    if args.backup:
        return _print_result(engine.op_backup(keep=args.keep), as_json=as_json)

    if args.reload:
        return _print_result(engine.reload_data(), as_json=as_json)

    if args.get is not None:
        return _print_result(
            engine.op_get_setting(args.get),
            as_json=as_json,
            raw_formatter=lambda r: f"{r.data['key']}={r.data['value']}",
        )

    if args.set is not None:
        return _print_result(engine.op_set_setting(args.set[0], args.set[1]), as_json=as_json)

    print(format_help_text())
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args, unknown = parser.parse_known_args(argv)
    mode, mode_err = determine_mode(args)
    attach_windows_console_if_needed(mode or "cli")
    configure_stdio()

    if unknown:
        print(f"HATA: Bilinmeyen komut satırı seçeneği: {' '.join(unknown)}", file=sys.stderr)
        print(format_help_text(), file=sys.stderr)
        return 2

    if mode_err:
        print(mode_err, file=sys.stderr)
        return 2

    work_dir = Path(args.work_dir).resolve() if args.work_dir else None

    if mode == "cli" and args.show_help and not args.as_json:
        print(format_help_text())
        return 0

    engine = QtpEngine(work_dir=work_dir)

    if mode == "cli":
        return execute_cli(engine, args)

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
        )

    # mode == "gui"
    from qtp_app.main import launch_gui

    return launch_gui(engine)


if __name__ == "__main__":
    raise SystemExit(run())
