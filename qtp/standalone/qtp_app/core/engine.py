"""Arayüzden bağımsız (Qt-free) QTP çekirdek motoru — --gui, --tui, --cli ve --web için tek kaynak."""

from __future__ import annotations

import contextlib
import copy
import importlib.resources
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from qtp_app import __build_date__, __display_name__, __version__
from qtp_app.core.hotkeys import (
    HOTKEY_PRESETS,
    HOTKEY_PRESET_LABELS,
    apply_modifier_combo,
    detect_hotkey_conflicts,
    resolve_preset_name,
)
from qtp_app.core.operations import OPERATIONS
from qtp_app.core.ini_parser import (
    DEFAULT_TERMINATOR,
    IniParseError,
    atomic_write_bytes,
    build_qtp_ini,
    decode_bytes_auto,
    parse_qtp_ini,
    read_text_auto,
    serialize_qtp_ini,
    write_qtp_ini,
)
from qtp_app.core.json_store import (
    JsonStoreError,
    create_backup,
    list_backups,
    load_data_json,
    load_state,
    parse_any_content,
    restore_backup,
    save_data_json,
    save_state,
    write_full_backup_file,
)
from qtp_app.core.logging_setup import (
    attach_stderr_handler,
    get_logger,
    setup_ephemeral_logging,
    setup_logging,
)
from qtp_app.core.paster import copy_to_clipboard, paste_into_active_app
from qtp_app.core.settings import (
    DEFAULT_HOTKEYS,
    DEFAULT_SETTINGS,
    SETTINGS_FILENAME,
    SettingValidationError,
    _sanitize_settings,
    get_app_dir,
    get_setting_value,
    is_dir_writable,
    load_settings,
    resolve_config_dir,
    resolve_data_path,
    save_settings,
    set_setting_value,
)
from qtp_app.core.watcher import ConfigFileWatcher, FileChange, ReloadEvent
from qtp_app.ui.search import FuzzyMatcher, tr_lower

_EMOJI_RE = re.compile(
    "["
    "\U0001F1E0-\U0001FAFF"
    "\u2600-\u27BF"
    "\u2B50\u2B55\u231A\u231B\u23E9-\u23F3\u23F8-\u23FA"
    "\ufe0e\ufe0f\u200d\u20e3"
    "]+",
    flags=re.UNICODE,
)


def _strip_unicode_emojis(text: str) -> str:
    cleaned = _EMOJI_RE.sub("", str(text or ""))
    lines = [re.sub(r"[ \t]{2,}", " ", ln).strip() for ln in cleaned.splitlines()]
    return "\n".join(lines).strip()


def strip_emojis(text: str) -> str:
    """Türkçe harfleri, noktalama ve satır sonlarını koruyarak Unicode emojileri metinden temizler."""
    return _strip_unicode_emojis(text)

CATEGORY_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("ALL", "Tümü", ""),
    ("A", "A · İş Ortağı", "L-Win+A"),
    ("Z", "Z · Kurye", "L-Win+Z"),
    ("X", "X · Canlı Yardım", "L-Win+X"),
    ("Q", "Q · Turkcell", "L-Win+Q"),
)


def format_hotkeys_toast(hotkeys: dict[str, str] | None = None) -> str:
    hk = hotkeys or DEFAULT_HOTKEYS
    ordered = []
    for k in ("all", "A", "Z", "X", "Q"):
        val = str(hk.get(k, "")).strip()
        if val:
            ordered.append(val)
    for k, val in hk.items():
        if k not in ("all", "A", "Z", "X", "Q") and str(val or "").strip():
            ordered.append(str(val).strip())
    return "QTP hazır. " + (" / ".join(ordered) if ordered else "Tepsi veya Ctrl+, ile kısayol atayın")


FIRST_RUN_TOAST = format_hotkeys_toast(DEFAULT_HOTKEYS)

_DEFAULT_CLI_FLAGS: tuple[str, ...] = (
    "--mode",
    "--gui",
    "--tui",
    "--cli",
    "--web",
    "-h",
    "--help",
    "-v",
    "--verbose",
    "-q",
    "--quiet",
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
    "--direction",
    "--toggle-favorite",
    "--bulk-edit",
    "--bulk-delete",
    "--rename-group",
    "--new-group",
    "--delete-group",
    "--undo",
    "--redo",
    "--item-keys",
    "--item-group",
    "--item-label",
    "--item-text",
    "--item-favorite",
    "--no-end-marker",
    "--find",
    "--ignore-case",
    "--prefix",
    "--suffix",
    "--strip-emojis",
    "--add-emoji",
    "--favorite-action",
    "--category",
    "--query",
    "--only-favorites",
    "--only-notes",
    "--group",
    "--sort",
    "--strip-emoji",
    "--selected-keys",
    "--encoding",
    "--skip-duplicates",
    "--json",
    "--work-dir",
    "--keep",
    "--merge",
    "--replace-all",
    "--replace",
    "--port",
    "--open-browser",
    "--shutdown-after",
)

SUPPORTED_SHELLS = ("powershell", "bash", "zsh", "fish")


@dataclass
class OperationResult:
    """Tüm modlarda aynı çıkış kodu, mesaj ve veri yapısını taşıyan işlem sonucu."""

    ok: bool
    exit_code: int
    message: str
    data: Any = None
    error: str | None = None
    warning: str | None = None

    def to_api_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "exit_code": self.exit_code,
            "message": self.message,
            "data": self.data,
            "error": self.error,
        }
        if self.warning:
            payload["warning"] = self.warning
        return payload


def _all_setting_keys() -> list[str]:
    keys: list[str] = []
    for k, v in DEFAULT_SETTINGS.items():
        if isinstance(v, dict):
            for sub in v:
                keys.append(f"{k}.{sub}")
        else:
            keys.append(k)
    return keys


def detect_target_shell(requested: str | None = None, *, platform_name: str | None = None, env: dict[str, str] | None = None) -> str:
    """Hedef kabuğu ('powershell', 'bash', 'zsh', 'fish') algılar veya doğrular."""
    raw = (requested or "auto").strip().lower()
    if raw and raw != "auto":
        return raw
    environ = env if env is not None else os.environ
    plat = platform_name or sys.platform
    shell_env = str(environ.get("SHELL", "")).lower()
    if "zsh" in shell_env:
        return "zsh"
    if "fish" in shell_env:
        return "fish"
    if "pwsh" in shell_env or "powershell" in shell_env:
        return "powershell"
    if "bash" in shell_env and plat != "win32":
        return "bash"
    if plat == "win32" or "PSModulePath" in environ:
        return "powershell"
    return "bash"


def build_completion_script(shell: str, option_strings: list[str] | tuple[str, ...] | None = None) -> str:
    """Canlı seçenekler, kategoriler, ayar anahtarları ve profillerden kabuk tamamlama betiği üretir."""
    flags = list(option_strings) if option_strings else list(_DEFAULT_CLI_FLAGS)
    modes = ["gui", "tui", "cli", "web"]
    cats = [c for c, _lbl, _p in CATEGORY_DEFINITIONS]
    presets = list(HOTKEY_PRESETS.keys())
    shells = ["powershell", "bash", "zsh", "fish", "auto"]
    skeys = _all_setting_keys()
    sorts = ["order", "usage", "alpha", "keys", "favorites"]
    dirs = ["up", "down"]
    fav_acts = ["keep", "add", "remove"]

    if shell == "powershell":
        flags_ps = ", ".join(f"'{f}'" for f in flags)
        modes_ps = ", ".join(f"'{m}'" for m in modes)
        cats_ps = ", ".join(f"'{c}'" for c in cats)
        presets_ps = ", ".join(f"'{p}'" for p in presets)
        shells_ps = ", ".join(f"'{s}'" for s in shells)
        skeys_ps = ", ".join(f"'{k}'" for k in skeys)
        sorts_ps = ", ".join(f"'{s}'" for s in sorts)
        dirs_ps = ", ".join(f"'{d}'" for d in dirs)
        fav_ps = ", ".join(f"'{a}'" for a in fav_acts)
        return (
            "Register-ArgumentCompleter -Native -CommandName qtp, qtp.exe, qtp.bin -ScriptBlock {\n"
            "    param($wordToComplete, $commandAst, $cursorPosition)\n"
            "    $tokens = $commandAst.CommandElements | ForEach-Object { $_.Extent.Text }\n"
            "    $prev = if ($tokens.Count -ge 2 -and $wordToComplete -ne '') { $tokens[$tokens.Count - 2] } elseif ($tokens.Count -ge 1 -and $wordToComplete -eq '') { $tokens[$tokens.Count - 1] } else { '' }\n"
            "    $map = @{\n"
            f"        '--mode' = @({modes_ps})\n"
            f"        '--category' = @({cats_ps})\n"
            f"        '--completion' = @({shells_ps})\n"
            f"        '--hotkey-preset' = @({presets_ps})\n"
            f"        '--sort' = @({sorts_ps})\n"
            f"        '--direction' = @({dirs_ps})\n"
            f"        '--favorite-action' = @({fav_ps})\n"
            f"        '--get' = @({skeys_ps})\n"
            f"        '--set' = @({skeys_ps})\n"
            "    }\n"
            "    $candidates = if ($map.ContainsKey($prev)) { $map[$prev] } else { @("
            + flags_ps
            + ") }\n"
            "    $candidates | Where-Object { $_ -like \"$wordToComplete*\" } | ForEach-Object {\n"
            "        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)\n"
            "    }\n"
            "}\n"
        )

    if shell == "bash":
        return (
            "_qtp_completions() {\n"
            "    local cur prev\n"
            "    COMPREPLY=()\n"
            "    cur=\"${COMP_WORDS[COMP_CWORD]}\"\n"
            "    prev=\"${COMP_WORDS[COMP_CWORD-1]}\"\n"
            "    case \"${prev}\" in\n"
            f"        --mode) COMPREPLY=( $(compgen -W \"{' '.join(modes)}\" -- \"${{cur}}\") ); return 0 ;;\n"
            f"        --category) COMPREPLY=( $(compgen -W \"{' '.join(cats)}\" -- \"${{cur}}\") ); return 0 ;;\n"
            f"        --completion) COMPREPLY=( $(compgen -W \"{' '.join(shells)}\" -- \"${{cur}}\") ); return 0 ;;\n"
            f"        --hotkey-preset) COMPREPLY=( $(compgen -W \"{' '.join(presets)}\" -- \"${{cur}}\") ); return 0 ;;\n"
            f"        --sort) COMPREPLY=( $(compgen -W \"{' '.join(sorts)}\" -- \"${{cur}}\") ); return 0 ;;\n"
            f"        --direction) COMPREPLY=( $(compgen -W \"{' '.join(dirs)}\" -- \"${{cur}}\") ); return 0 ;;\n"
            f"        --favorite-action) COMPREPLY=( $(compgen -W \"{' '.join(fav_acts)}\" -- \"${{cur}}\") ); return 0 ;;\n"
            f"        --get|--set) COMPREPLY=( $(compgen -W \"{' '.join(skeys)}\" -- \"${{cur}}\") ); return 0 ;;\n"
            "    esac\n"
            f"    COMPREPLY=( $(compgen -W \"{' '.join(flags)}\" -- \"${{cur}}\") )\n"
            "    return 0\n"
            "}\n"
            "complete -F _qtp_completions qtp qtp.bin qtp.exe\n"
        )

    if shell == "zsh":
        specs = [
            f"  '{f}[QTP seçeneği]'"
            if f not in ("--mode", "--category", "--completion", "--hotkey-preset", "--sort", "--direction", "--favorite-action", "--get", "--set")
            else (
                f"  '--mode[Çalışma modu]:mod:({' '.join(modes)})'"
                if f == "--mode"
                else f"  '--category[Kategori filtresi]:kategori:({' '.join(cats)})'"
                if f == "--category"
                else f"  '--completion[Kabuk tamamlama betiği]:kabuk:({' '.join(shells)})'"
                if f == "--completion"
                else f"  '--hotkey-preset[Kısayol profili]:profil:({' '.join(presets)})'"
                if f == "--hotkey-preset"
                else f"  '--sort[Sıralama ölçütü]:sıra:({' '.join(sorts)})'"
                if f == "--sort"
                else f"  '--direction[Taşıma yönü]:yön:({' '.join(dirs)})'"
                if f == "--direction"
                else f"  '--favorite-action[Favori işlemi]:eylem:({' '.join(fav_acts)})'"
                if f == "--favorite-action"
                else f"  '{f}[Ayar anahtarı]:anahtar:({' '.join(skeys)})'"
            )
            for f in flags
        ]
        return "#compdef qtp qtp.bin\n_qtp() {\n  _arguments -s \\\n" + " \\\n".join(specs) + "\n}\n_qtp \"$@\"\n"

    fish_lines = []
    for f in flags:
        if f.startswith("--"):
            long_name = f[2:]
            extra = ""
            if f == "--mode":
                extra = f" -xa \"{' '.join(modes)}\""
            elif f == "--category":
                extra = f" -xa \"{' '.join(cats)}\""
            elif f == "--completion":
                extra = f" -xa \"{' '.join(shells)}\""
            elif f == "--hotkey-preset":
                extra = f" -xa \"{' '.join(presets)}\""
            elif f == "--sort":
                extra = f" -xa \"{' '.join(sorts)}\""
            elif f == "--direction":
                extra = f" -xa \"{' '.join(dirs)}\""
            elif f == "--favorite-action":
                extra = f" -xa \"{' '.join(fav_acts)}\""
            elif f in ("--get", "--set"):
                extra = f" -xa \"{' '.join(skeys)}\""
            fish_lines.append(f"complete -c qtp -l {long_name}{extra} -d 'QTP'")
            fish_lines.append(f"complete -c qtp.bin -l {long_name}{extra} -d 'QTP'")
        elif len(f) == 2 and f.startswith("-"):
            short_name = f[1:]
            fish_lines.append(f"complete -c qtp -s {short_name} -d 'QTP'")
            fish_lines.append(f"complete -c qtp.bin -s {short_name} -d 'QTP'")
    return "\n".join(fish_lines) + "\n"


def get_bundled_default_path(filename: str) -> Path:
    """Paket içi varsayılan varlık (QuickTextPaste.ini / data.json) yolunu döndürür."""
    try:
        files_fn = getattr(importlib.resources, "files", None)
        if files_fn is not None:
            pkg_root = Path(str(files_fn("qtp_app")))
            candidate = pkg_root / "assets" / "defaults" / filename
            if candidate.is_file():
                return candidate
    except Exception:
        pass
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_candidate = Path(getattr(sys, "_MEIPASS")) / "qtp_app" / "assets" / "defaults" / filename
        if meipass_candidate.is_file():
            return meipass_candidate
    local = Path(__file__).resolve().parent.parent / "assets" / "defaults" / filename
    if local.is_file():
        return local
    standalone_cand = Path(__file__).resolve().parent.parent.parent / filename
    if standalone_cand.is_file():
        return standalone_cand
    return Path(__file__).resolve().parent.parent.parent.parent / filename


def get_bundled_docs_dir() -> Path:
    """Gömülü Türkçe dokümantasyon klasörünü döndürür."""
    try:
        files_fn = getattr(importlib.resources, "files", None)
        if files_fn is not None:
            pkg_root = Path(str(files_fn("qtp_app")))
            for candidate in (pkg_root / "docs", pkg_root.parent / "docs", pkg_root.parent.parent / "docs"):
                if candidate.is_dir():
                    return candidate
    except Exception:
        pass
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_docs = Path(getattr(sys, "_MEIPASS")) / "docs"
        if meipass_docs.is_dir():
            return meipass_docs
    standalone_docs = Path(__file__).resolve().parent.parent.parent / "docs"
    if standalone_docs.is_dir():
        return standalone_docs
    return Path(__file__).resolve().parent.parent.parent.parent / "docs"


def read_doc_text(filename: str) -> str:
    docs_dir = get_bundled_docs_dir()
    path = docs_dir / filename
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return f"# {filename}\n\nBelge dosyası bulunamadı: `{path}`"


def item_matches_category(item: dict[str, Any], category_code: str) -> bool:
    code = (category_code or "ALL").strip().upper()
    if code in ("", "ALL"):
        return True
    keys = str(item.get("keys", item.get("hotkey_prefix", ""))).strip().upper()
    return keys.endswith(f"+{code}") or keys == code


def is_note_item(item: dict[str, Any]) -> bool:
    """Kısayolsuz kayıtları ve [DAHİLİ NOT] ön ekli dahili notları tanımlar."""
    keys = str(item.get("keys", item.get("hotkey_prefix", ""))).strip()
    text = str(item.get("text", ""))
    return (not keys) or text.startswith("[DAHİLİ NOT]")


def format_ini_preview(item: dict[str, Any], index: int) -> str:
    """Seçili kaydın [list_text], [list_order] ve [list_label] ham INI önizlemesini oluşturur."""
    tid = str(item.get("raw_key") or f"text_{index:03d}")
    keys = str(item.get("keys", ""))
    term = str(item.get("terminator", DEFAULT_TERMINATOR))
    text_enc = str(item.get("text", "")).replace("\r\n", "\n").replace("\n", "\\n")
    grp = str(item.get("group", "Genel"))
    lbl = str(item.get("label", ""))
    full_label = f"{grp}/{lbl}" if grp and grp != "Genel" else lbl
    return (
        f"[list_text]\n{tid}={keys}={text_enc}{term}\n\n"
        f"[list_order]\n{tid}={index + 1}\n\n"
        f"[list_label]\n{tid}={full_label}"
    )


def build_cli_help_text(*, verbose: bool = False) -> str:
    """Tüm modlar (--cli, --web, --tui, --gui) ve Yardım pencereleri için kanonsal Türkçe yardım metni."""
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
        "  --category KOD                         --gui/--tui/--web ve --list-items/--search kategori filtresi (ALL/A/Z/X/Q)\n"
        "  --query METIN                          --gui/--tui/--web ve --list-items için arama süzgeci\n"
        "  --only-favorites / --only-notes        Yalnızca favori veya [DAHİLİ NOT] kayıtlarını süzer\n"
        "  --group GRUP / --sort OLCUT            Grup filtresi ve sıralama (order, usage, alpha, keys, favorites)\n"
        "  --strip-emoji                          Kopyalama/yapıştırma sırasında emojileri temizler\n"
        "  --selected-keys CSV / --skip-duplicates Seçili kayıt dışa aktarma ve içe aktarmada tekrar atlama\n"
        "  --merge / --replace                    --import-ini ve --restore için birleştir/değiştir modu\n"
        "  --keep N                               --backup için tutulacak maksimum yedek sayısı\n"
        "  --port N                               --web için 127.0.0.1 bağlantı noktası (varsayılan: 8765)\n"
        "  --open-browser                         --web başlatıldığında tarayıcıyı açar\n"
        "  --shutdown-after SN                    --web sunucusunu belirtilen saniye sonra zarifçe kapatır\n"
        "  --item-keys TUS / --item-group GRUP    Ekleme/güncelleme/toplu düzenleme için kısayol, grup, etiket ve metin\n"
        "  --item-label ETIKET / --item-text METIN / --no-end-marker\n"
        "                                         Yeni veya güncellenen kaydın alanlarını ve <E<N<D| son ekini belirler\n"
        "  --find ARA --replace YENI [--ignore-case] [--prefix ON] [--suffix SON] [--strip-emojis] [--add-emoji EMOJI]\n"
        "  --favorite-action {keep,add,remove}    --bulk-edit için toplu metin ve favori seçenekleri\n"
        "  --direction {up,down} / --new-group GRUP --move-item ve --rename-group alt parametreleri\n"
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


def _get_git_short_sha() -> str | None:
    try:
        root = Path(__file__).resolve().parent.parent.parent
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=2,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception:
        pass
    return None


class QtpEngine:
    """--gui, --tui, --cli ve --web modlarının tamamına hizmet eden tek motor."""

    def __init__(
        self,
        work_dir: str | Path | None = None,
        *,
        seed_defaults: bool = True,
        ephemeral: bool = False,
        verbose: int = 0,
        quiet: bool = False,
        clipboard_fn: Callable[[str], bool] | None = None,
        paste_fn: Callable[..., Any] | None = None,
    ):
        requested_dir = Path(work_dir).resolve() if work_dir else get_app_dir()
        self.ephemeral = bool(ephemeral)
        self.verbose: int = max(0, int(verbose))
        self.quiet: bool = bool(quiet) and self.verbose <= 0
        self._diag_emitted: bool = False
        self.startup_warning: str | None = None
        self._corrupt_backup_created: bool = False
        self._applied_log_level: str = "info"
        if self.ephemeral:
            self.config_dir = requested_dir
            self.portable = True
            self.work_dir = requested_dir
            self.first_run = False
            setup_ephemeral_logging(verbose=self.verbose)
            self.logger = get_logger("engine")
            self.settings = copy.deepcopy(DEFAULT_SETTINGS)
            self.settings_path = self.config_dir / SETTINGS_FILENAME
            if self.settings_path.is_file():
                try:
                    raw = json.loads(self.settings_path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        self.settings = _sanitize_settings(raw)
                except Exception:
                    pass
            self.settings_warning = None
        else:
            self.config_dir, self.portable = resolve_config_dir(requested_dir)
            self.work_dir = requested_dir if is_dir_writable(requested_dir) else self.config_dir
            self.first_run = not (self.config_dir / SETTINGS_FILENAME).is_file()

            setup_logging(self.config_dir, level="info", verbose=self.verbose)
            self._applied_log_level = "info"
            self.logger = get_logger("engine")

            self.settings, self.settings_path, self.settings_warning = load_settings(self.config_dir)
            cfg_level = str(self.settings.get("log_level", "info"))
            if cfg_level != self._applied_log_level:
                setup_logging(
                    self.config_dir,
                    level=cfg_level,
                    verbose=self.verbose,
                )
                self._applied_log_level = cfg_level

        self._matcher = FuzzyMatcher()
        self._clipboard_fn = clipboard_fn
        self._paste_fn = paste_fn
        self.items: list[dict[str, Any]] = []
        self.program_meta: dict[str, str] = {}
        self.extra_sections: list[dict[str, Any]] = []
        self.ini_path: Path = resolve_data_path(self.settings, self.work_dir)
        self._watcher: ConfigFileWatcher | None = None
        self._on_reload_cb: Callable[[ReloadEvent], None] | None = None
        self._reload_lock = threading.RLock()
        self.revision: int = 0
        self.last_reload_event: ReloadEvent | None = None
        self._undo_stack: list[tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]] = []
        self._redo_stack: list[tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]] = []

        self._seed_defaults_if_empty(seed_defaults and not self.ephemeral)
        self.reload_data()
        self._load_history()

    def configure_verbosity(self, verbose: int = 0, quiet: bool = False) -> None:
        """Çalışma zamanında ayrıntı (-v/-vv) ve sessiz (-q) akışlarını birleştirir."""
        self.verbose = max(self.verbose, max(0, int(verbose)))
        self.quiet = bool(quiet) and self.verbose <= 0
        if self.verbose >= 1:
            if self.ephemeral:
                setup_ephemeral_logging(verbose=self.verbose)
            else:
                attach_stderr_handler(verbose=self.verbose)

    def emit_startup_diagnostics(self, mode: str, started_at: float | None = None) -> None:
        """Tüm 4 mod için tek tip [INFO] / [DEBUG] başlangıç tanılama satırlarını stderr ve günlüğe yazar."""
        if self.verbose <= 0 or self._diag_emitted:
            return
        self._diag_emitted = True
        self.logger.info(
            "mod=%s çalışma_dizini=%s yapılandırma=%s taşınabilir=%s kayıt=%d",
            mode,
            self.work_dir,
            self.config_dir,
            self.portable,
            len(self.items),
        )
        if self.verbose >= 2:
            conflicts = self.op_check_hotkeys().data["conflicts"]
            dur_ms = int((time.monotonic() - started_at) * 1000) if started_at is not None else 0
            self.logger.debug(
                "ini_yolu=%s ayarlar_yolu=%s tema=%s otomatik_yenileme=%s aralik_ms=%s kısayol_uyarısı=%d süre_ms=%d",
                self.ini_path,
                self.settings_path,
                self.settings.get("theme"),
                self.settings.get("auto_reload"),
                self.settings.get("auto_reload_interval_ms"),
                len(conflicts),
                dur_ms,
            )

    @contextlib.contextmanager
    def _suppress_write(self, *paths: str | Path) -> Iterator[None]:
        if self._watcher is None:
            yield
            return
        with contextlib.ExitStack() as stack:
            for p in paths:
                stack.enter_context(self._watcher.suppress_write(p))
            yield

    def mark_internal_write(self, *paths: str | Path) -> None:
        if self._watcher is not None:
            for p in paths:
                self._watcher.mark_internal_write(p)

    def _watcher_targets(self) -> dict[str, Path]:
        return {
            "settings": self.settings_path,
            "ini": self.ini_path,
            "json": self.work_dir / "data.json",
        }

    def start_watcher(
        self,
        on_reload: Callable[[ReloadEvent], None] | None = None,
        *,
        debounce_ms: int = 250,
    ) -> ConfigFileWatcher | None:
        """Harici dosya değişiklikleri için canlı izleyici iş parçacığını başlatır."""
        if self.ephemeral:
            return None
        self._on_reload_cb = on_reload
        if not bool(self.settings.get("auto_reload", True)):
            return None
        interval_ms = int(self.settings.get("auto_reload_interval_ms", 500))
        if self._watcher is None:
            self._watcher = ConfigFileWatcher(
                self._watcher_targets(),
                self._handle_watched_changes,
                interval_ms=interval_ms,
                debounce_ms=debounce_ms,
            )
        else:
            self._watcher.update_paths(self._watcher_targets())
            self._watcher.set_interval(interval_ms)
        self._watcher.start()
        self.logger.info("Canlı dosya izleyici başlatıldı (aralık=%d ms).", interval_ms)
        self.logger.debug("İzlenen yollar: %s", {k: str(v) for k, v in self._watcher_targets().items()})
        return self._watcher

    def stop_watcher(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None
            self.logger.info("Canlı dosya izleyici durduruldu.")

    def _read_json_with_retry(self, path: Path) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("Kök JSON nesnesi sözlük değil.")
                return raw
            except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(0.15)
        raise ValueError(str(last_exc))

    def _validate_data_source_with_retry(self, source_kind: str) -> None:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                if source_kind == "ini" and self.ini_path.is_file():
                    parse_qtp_ini(read_text_auto(self.ini_path))
                elif source_kind == "json" and (self.work_dir / "data.json").is_file():
                    load_data_json(self.work_dir / "data.json")
                return
            except (OSError, IniParseError, JsonStoreError, UnicodeDecodeError, ValueError) as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(0.15)
        raise ValueError(str(last_exc))

    def _handle_watched_changes(self, changes: list[FileChange]) -> None:
        with self._reload_lock:
            self.logger.debug("Dosya değişikliği algılandı: %s", [c.kind for c in changes])
            kinds = {c.kind: c for c in changes}
            ev = ReloadEvent(item_count=len(self.items))
            reload_data_kind: str | None = None

            if "settings" in kinds and kinds["settings"].exists:
                try:
                    raw = self._read_json_with_retry(self.settings_path)
                    new_settings = _sanitize_settings(raw)
                    old = self.settings
                    if new_settings != old:
                        ev.settings_changed = True
                        ev.hotkeys_changed = new_settings.get("hotkeys") != old.get("hotkeys")
                        ev.theme_changed = new_settings.get("theme") != old.get("theme")
                        ev.window_size_changed = new_settings.get("window_size") != old.get("window_size")
                        ev.data_path_changed = new_settings.get("data_path") != old.get("data_path")
                        ev.log_level_changed = new_settings.get("log_level") != old.get("log_level")
                        ev.tray_changed = new_settings.get("tray_icon") != old.get("tray_icon")
                        ev.auto_reload_changed = (
                            new_settings.get("auto_reload") != old.get("auto_reload")
                            or new_settings.get("auto_reload_interval_ms") != old.get("auto_reload_interval_ms")
                        )
                        self.settings = new_settings
                        if ev.log_level_changed:
                            new_level = str(new_settings.get("log_level", "info"))
                            setup_logging(
                                self.config_dir,
                                level=new_level,
                                verbose=self.verbose,
                            )
                            self._applied_log_level = new_level
                        if ev.data_path_changed:
                            self.ini_path = resolve_data_path(self.settings, self.work_dir)
                            if self._watcher is not None:
                                self._watcher.update_paths(self._watcher_targets())
                            reload_data_kind = "ini"
                        if ev.auto_reload_changed and self._watcher is not None:
                            if not bool(new_settings.get("auto_reload", True)):
                                self._watcher.stop()
                            else:
                                self._watcher.set_interval(int(new_settings.get("auto_reload_interval_ms", 500)))
                        self.logger.info("Ayarlar dosya değişikliğinden otomatik yenilendi.")
                except Exception as exc:
                    warn = f"Otomatik ayar yenileme başarısız (mevcut ayarlar korundu): {exc}"
                    self.logger.warning("%s", warn)
                    ev.warning = warn

            if "ini" in kinds:
                reload_data_kind = "ini"
            elif "json" in kinds and reload_data_kind is None:
                reload_data_kind = "json"

            if reload_data_kind is not None:
                try:
                    self._validate_data_source_with_retry(reload_data_kind)
                    res = self.reload_data(prefer_source=reload_data_kind)
                    if res.ok:
                        ev.items_changed = True
                        ev.item_count = len(self.items)
                        ev.source = str((res.data or {}).get("source", reload_data_kind))
                    else:
                        warn = f"Otomatik veri yenileme başarısız (önceki geçerli kayıtlar korundu): {res.error or res.message}"
                        self.logger.warning("%s", warn)
                        ev.warning = warn
                except Exception as exc:
                    warn = f"Otomatik veri yenileme başarısız (önceki geçerli kayıtlar korundu): {exc}"
                    self.logger.warning("%s", warn)
                    ev.warning = warn

            if (
                ev.settings_changed
                or ev.items_changed
                or ev.hotkeys_changed
                or ev.theme_changed
                or ev.window_size_changed
                or ev.warning is not None
            ):
                self.revision += 1
                self.last_reload_event = ev
                if self._on_reload_cb is not None:
                    try:
                        self._on_reload_cb(ev)
                    except Exception:
                        pass

    def _seed_defaults_if_empty(self, seed_defaults: bool) -> None:
        if not seed_defaults:
            return
        ini_exists = self.ini_path.is_file()
        json_exists = (self.work_dir / "data.json").is_file()
        if ini_exists or json_exists:
            return

        bundled_ini = get_bundled_default_path("QuickTextPaste.ini")
        bundled_json = get_bundled_default_path("data.json")
        try:
            self.work_dir.mkdir(parents=True, exist_ok=True)
            if bundled_ini.is_file() and not self.ini_path.exists():
                self.ini_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(bundled_ini, self.ini_path)
            if bundled_json.is_file() and not (self.work_dir / "data.json").exists():
                shutil.copy2(bundled_json, self.work_dir / "data.json")
            self.logger.info("İlk çalıştırma varsayılan veri dosyaları oluşturuldu: %s", self.work_dir)
        except OSError as exc:
            self.logger.warning("Varsayılan veri dosyaları kopyalanamadı: %s", exc)

    def save_current_settings(self, new_settings: dict[str, Any]) -> Path:
        """Ayarları diske yazar ve kendi yazımını izleyici yankısından hariç tutar."""
        old_auto = bool(self.settings.get("auto_reload", True))
        old_data = self.settings.get("data_path")
        with self._suppress_write(self.settings_path):
            saved = save_settings(new_settings, self.settings_path)
        self.settings = _sanitize_settings(new_settings)
        new_level = str(self.settings.get("log_level", "info"))
        if not self.ephemeral and new_level != getattr(self, "_applied_log_level", None):
            setup_logging(
                self.config_dir,
                level=new_level,
                verbose=self.verbose,
            )
            self._applied_log_level = new_level
        if self.settings.get("data_path") != old_data:
            self.ini_path = resolve_data_path(self.settings, self.work_dir)
        if self._watcher is not None:
            self._watcher.update_paths(self._watcher_targets())
            self._watcher.set_interval(int(self.settings.get("auto_reload_interval_ms", 500)))
            if not bool(self.settings.get("auto_reload", True)):
                self._watcher.stop()
        elif not old_auto and bool(self.settings.get("auto_reload", True)) and self._on_reload_cb is not None:
            self.start_watcher(self._on_reload_cb)
        self.revision += 1
        return saved

    def reload_data(self, *, prefer_source: str | None = None) -> OperationResult:
        """Diskten QuickTextPaste.ini / data.json verisini yeniden yükler."""
        self.ini_path = resolve_data_path(self.settings, self.work_dir)
        has_disk_file = self.ini_path.is_file() or (self.work_dir / "data.json").is_file()
        try:
            if has_disk_file:
                state = load_state(self.work_dir, ini_path=self.ini_path, prefer_source=prefer_source)
                if state.get("source") == "empty":
                    detail = "; ".join(state.get("errors") or []) or "geçerli kayıt kaynağı okunamadı"
                    err = f"HATA: Kayıtlar yeniden yüklenemedi: {detail}"
                    self.logger.error(err)
                    if not self.ephemeral and not getattr(self, "_corrupt_backup_created", False):
                        try:
                            create_backup(
                                self.work_dir,
                                reason="corrupt_load",
                                max_keep=int(self.settings.get("backup_count", 15)),
                            )
                        except Exception as bak_exc:
                            self.logger.warning("Bozuk veri yedeği oluşturulamadı: %s", bak_exc)
                        self._corrupt_backup_created = True
                    self.startup_warning = err
                    return OperationResult(ok=False, exit_code=1, message=err, error=err)

                self.items = state["items"]
                self.program_meta = state.get("program") or {}
                self.extra_sections = state.get("extraSections") or []
                for idx, it in enumerate(self.items):
                    it.setdefault("raw_key", f"text_{idx:03d}")
                    it.setdefault("terminator", DEFAULT_TERMINATOR)
                self.startup_warning = None
                self._corrupt_backup_created = False
                self.logger.info("INI yeniden yüklendi: %d kayıt (%s).", len(self.items), self.ini_path)
                return OperationResult(
                    ok=True,
                    exit_code=0,
                    message=f"INI yeniden yüklendi: {len(self.items)} kayıt ({self.ini_path}).",
                    data={"count": len(self.items), "source": state.get("source"), "ini_path": str(self.ini_path)},
                )

            bundled_ini = get_bundled_default_path("QuickTextPaste.ini")
            if bundled_ini.is_file():
                doc = parse_qtp_ini(read_text_auto(bundled_ini))
                self.items = [
                    {
                        **it.to_dict(include_meta=False),
                        "terminator": it.terminator,
                        "raw_key": it.raw_key,
                    }
                    for it in doc.items
                ]
                self.program_meta = dict(doc.program)
                self.extra_sections = list(doc.extra_sections)
                self.startup_warning = None
                self._corrupt_backup_created = False
                self.logger.info("Gömülü varsayılan INI yüklendi: %d kayıt.", len(self.items))
                return OperationResult(
                    ok=True,
                    exit_code=0,
                    message=f"INI yeniden yüklendi: {len(self.items)} kayıt (gömülü varsayılan).",
                    data={"count": len(self.items), "source": "bundled", "ini_path": str(self.ini_path)},
                )
        except Exception as exc:
            err = f"HATA: Kayıtlar yeniden yüklenemedi: {exc}"
            self.logger.error(err)
            self.startup_warning = err
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

        self.items = []
        self.startup_warning = None
        self._corrupt_backup_created = False
        return OperationResult(
            ok=True,
            exit_code=0,
            message="INI yeniden yüklendi: 0 kayıt.",
            data={"count": 0, "source": "empty", "ini_path": str(self.ini_path)},
        )

    def op_version(self) -> OperationResult:
        sha = _get_git_short_sha()
        sha_part = f" ({sha})" if sha else ""
        msg = f"{__display_name__} v{__version__} — Derleme: {__build_date__}{sha_part}"
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={
                "app": __display_name__,
                "version": __version__,
                "build_date": __build_date__,
                "git_sha": sha,
            },
        )

    def op_modes(self) -> OperationResult:
        modes = ["gui", "tui", "cli", "web"]
        return OperationResult(
            ok=True,
            exit_code=0,
            message="Desteklenen çalışma modları: gui, tui, cli, web.",
            data={"modes": modes},
        )

    def op_completion(
        self,
        shell: str = "auto",
        *,
        option_strings: list[str] | tuple[str, ...] | None = None,
    ) -> OperationResult:
        target = detect_target_shell(shell)
        if target not in SUPPORTED_SHELLS:
            err = (
                f"Desteklenmeyen kabuk türü: '{shell}' (desteklenenler: {', '.join(SUPPORTED_SHELLS)})."
            )
            return OperationResult(ok=False, exit_code=2, message=err, error=err)
        script = build_completion_script(target, option_strings=option_strings)
        return OperationResult(
            ok=True,
            exit_code=0,
            message="Otomatik tamamlama betiği üretildi.",
            data={"shell": target, "script": script},
        )

    def op_help(self, help_text: str = "", *, verbose: bool = False) -> OperationResult:
        usage = build_cli_help_text(verbose=False)
        usage_verbose = build_cli_help_text(verbose=True)
        chosen_usage = help_text or (usage_verbose if verbose else usage)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=chosen_usage,
            data={
                "usage": usage,
                "usage_verbose": usage_verbose,
                "kullanim": read_doc_text("KULLANIM.md"),
                "kurulum": read_doc_text("KURULUM.md"),
                "kisayollar": read_doc_text("KISAYOLLAR.md"),
                "sss": read_doc_text("SSS.md"),
                "verbose": bool(verbose),
            },
        )

    def op_selftest(self, *, run_ui_smoke: bool = True) -> OperationResult:
        """Gömülü QuickTextPaste.ini gidiş-dönüş ve isteğe bağlı offscreen PyQt6 duman testini çalıştırır."""
        bundled_ini = get_bundled_default_path("QuickTextPaste.ini")
        if not bundled_ini.is_file():
            err = f"HATA: Paketlenmiş INI örneği bulunamadı: {bundled_ini}"
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

        try:
            raw_bytes = bundled_ini.read_bytes()
            decoded_text, detected_enc = decode_bytes_auto(raw_bytes)
            doc = parse_qtp_ini(decoded_text)
            reserialized = serialize_qtp_ini(doc, update_test_ini=False)
            if reserialized != decoded_text:
                err = "HATA: Paketlenmiş QuickTextPaste.ini gidiş-dönüş (round-trip) doğrulaması başarısız."
                return OperationResult(ok=False, exit_code=1, message=err, error=err)
            reparsed = parse_qtp_ini(reserialized)
            if len(reparsed.items) != len(doc.items) or len(doc.items) == 0:
                err = f"HATA: Öğe sayısı uyuşmuyor ({len(reparsed.items)} != {len(doc.items)})."
                return OperationResult(ok=False, exit_code=1, message=err, error=err)

            with tempfile.TemporaryDirectory() as _tmp_dir:
                tmp_ini = Path(_tmp_dir) / "selftest_roundtrip.ini"
                write_qtp_ini(tmp_ini, reserialized, encoding="utf-16-le-bom", create_bak=False)
                disk_doc = parse_qtp_ini(read_text_auto(tmp_ini))
                if len(disk_doc.items) != len(doc.items):
                    err = f"HATA: Öğe sayısı uyuşmuyor ({len(disk_doc.items)} != {len(doc.items)})."
                    return OperationResult(ok=False, exit_code=1, message=err, error=err)

            if run_ui_smoke:
                prev_qpa = os.environ.get("QT_QPA_PLATFORM")
                try:
                    from PyQt6.QtCore import Qt
                    from PyQt6.QtTest import QTest
                    from PyQt6.QtWidgets import QApplication
                    from qtp_app.ui.overlay import OverlayWindow

                    app = QApplication.instance()
                    if app is None:
                        if not prev_qpa:
                            os.environ["QT_QPA_PLATFORM"] = "offscreen"
                        app = QApplication([sys.argv[0]])

                    items_dicts = [
                        {
                            **it.to_dict(include_meta=False),
                            "terminator": it.terminator,
                            "raw_key": it.raw_key,
                        }
                        for it in doc.items
                    ]
                    pasted: list[dict[str, Any]] = []
                    overlay = OverlayWindow(
                        items_dicts,
                        on_paste=lambda item, _prev: pasted.append(item),
                    )
                    try:
                        overlay.show_overlay(category="ALL", animate=False, previous_app=None)
                        app.processEvents()
                        if overlay.list_model.rowCount() != len(doc.items):
                            err = f"HATA: Katman beklenen {len(doc.items)} yerine {overlay.list_model.rowCount()} satır listeledi."
                            return OperationResult(ok=False, exit_code=1, message=err, error=err)
                        if not overlay.search_input.hasFocus():
                            err = "HATA: Arama kutusu otomatik odaklanamadı."
                            return OperationResult(ok=False, exit_code=1, message=err, error=err)
                        QTest.keyClick(overlay.search_input, Qt.Key.Key_Return)
                        app.processEvents()
                        if len(pasted) != 1:
                            err = "HATA: Enter tuşu yapıştırma geri çağrısını tetiklemedi."
                            return OperationResult(ok=False, exit_code=1, message=err, error=err)
                    finally:
                        overlay.close()
                        overlay.deleteLater()
                        app.processEvents()
                except ImportError:
                    self._matcher.filter_items("şifre", [it.to_dict(include_meta=False) for it in doc.items])
                finally:
                    if prev_qpa is None and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
                        os.environ.pop("QT_QPA_PLATFORM", None)

            msg = f"Otomatik test başarılı: {len(doc.items)} kayıt doğrulandı (kodlama={detected_enc})."
            return OperationResult(
                ok=True,
                exit_code=0,
                message=msg,
                data={"count": len(doc.items), "encoding": detected_enc},
            )
        except Exception as exc:
            err = f"HATA: Otomatik test sırasında beklenmeyen hata: {exc}"
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

    def op_list_categories(self) -> OperationResult:
        categories = [
            {
                "code": code,
                "label": label,
                "hotkey_prefix": prefix,
                "count": sum(1 for it in self.items if item_matches_category(it, code)),
            }
            for code, label, prefix in CATEGORY_DEFINITIONS
        ]
        return OperationResult(
            ok=True,
            exit_code=0,
            message="Kategoriler listelendi.",
            data={"categories": categories, "total": len(self.items)},
        )

    def _history_path(self) -> Path:
        return self.work_dir / ".qtp_history.json"

    def _load_history(self) -> None:
        if self.ephemeral:
            return
        hp = self._history_path()
        if not hp.is_file():
            return
        try:
            raw = json.loads(hp.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                undo_raw = raw.get("undo")
                redo_raw = raw.get("redo")
                if isinstance(undo_raw, list):
                    self._undo_stack = [
                        (list(e.get("items") or []), dict(e.get("program") or {}), list(e.get("extra_sections") or []))
                        for e in undo_raw[-30:]
                        if isinstance(e, dict)
                    ]
                if isinstance(redo_raw, list):
                    self._redo_stack = [
                        (list(e.get("items") or []), dict(e.get("program") or {}), list(e.get("extra_sections") or []))
                        for e in redo_raw[-30:]
                        if isinstance(e, dict)
                    ]
        except Exception:
            pass

    def _save_history(self) -> None:
        if self.ephemeral:
            return
        try:
            payload = {
                "undo": [
                    {"items": items, "program": prog, "extra_sections": extra}
                    for items, prog, extra in self._undo_stack[-30:]
                ],
                "redo": [
                    {"items": items, "program": prog, "extra_sections": extra}
                    for items, prog, extra in self._redo_stack[-30:]
                ],
            }
            atomic_write_bytes(
                self._history_path(),
                (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"),
            )
        except Exception as exc:
            self.logger.warning("Geri alma geçmişi diske yazılamadı: %s", exc)

    def _push_undo(self) -> None:
        snap = (
            copy.deepcopy(self.items),
            copy.deepcopy(self.program_meta),
            copy.deepcopy(self.extra_sections),
        )
        self._undo_stack.append(snap)
        if len(self._undo_stack) > 30:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._save_history()

    def _persist_copy_count(self) -> None:
        if self.ephemeral:
            return
        try:
            with self._suppress_write(self.work_dir / "data.json"):
                save_state(
                    self.work_dir,
                    self.items,
                    program=self.program_meta,
                    extra_sections=self.extra_sections,
                    create_backup_flag=False,
                    backup_reason="copy_count",
                    max_backups=int(self.settings.get("backup_count", 15)),
                    ini_path=self.ini_path,
                    update_ini=False,
                )
        except Exception as exc:
            self.logger.warning("Kopyalama sayacı diske yazılamadı: %s", exc)

    def op_list_items(
        self,
        *,
        category: str = "ALL",
        query: str = "",
        only_favorites: bool = False,
        only_notes: bool = False,
        group: str = "",
        sort_by: str | None = None,
    ) -> OperationResult:
        cat = (category or "ALL").strip().upper()
        grp_filter = (group or "").strip()
        filtered_cat: list[dict[str, Any]] = []
        for idx, it in enumerate(self.items):
            if not item_matches_category(it, cat):
                continue
            if only_favorites and not bool(it.get("favorite", False)):
                continue
            if only_notes and not is_note_item(it):
                continue
            if grp_filter and (str(it.get("group") or "Genel").strip() != grp_filter):
                continue
            entry = dict(it)
            entry.setdefault("raw_key", f"text_{idx:03d}")
            filtered_cat.append(entry)

        matched = self._matcher.filter_items(query or "", filtered_cat)
        eff_sort = (sort_by if sort_by is not None else str(self.settings.get("sort_by", "order"))).strip().lower()
        if eff_sort == "usage":
            matched = sorted(matched, key=lambda r: (-int(r[1].get("copyCount") or 0), r[0]))
        elif eff_sort == "alpha":
            matched = sorted(
                matched,
                key=lambda r: (tr_lower(str(r[1].get("label") or r[1].get("text") or "")), r[0]),
            )
        elif eff_sort == "keys":
            matched = sorted(matched, key=lambda r: (str(r[1].get("keys", "")).lower(), r[0]))
        elif eff_sort == "favorites":
            matched = sorted(matched, key=lambda r: (0 if r[1].get("favorite") else 1, r[0]))

        out_items: list[dict[str, Any]] = []
        for orig_idx, it, indices in matched:
            row: dict[str, Any] = {
                "raw_key": str(it.get("raw_key") or f"text_{orig_idx:03d}"),
                "keys": str(it.get("keys", "")),
                "group": str(it.get("group", "Genel")),
                "label": str(it.get("label", "")),
                "text": str(it.get("text", "")),
                "terminator": str(it.get("terminator", DEFAULT_TERMINATOR)),
                "matched_indices": list(indices),
            }
            if it.get("favorite"):
                row["favorite"] = True
            cc = int(it.get("copyCount") or 0)
            if cc > 0:
                row["copyCount"] = cc
            out_items.append(row)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=f"Hazır cevaplar listelendi: {len(out_items)} kayıt.",
            data={"items": out_items, "count": len(out_items), "category": cat, "query": query},
        )

    def op_search(
        self,
        query: str,
        *,
        category: str = "ALL",
        only_favorites: bool = False,
        only_notes: bool = False,
        group: str = "",
        sort_by: str | None = None,
    ) -> OperationResult:
        res = self.op_list_items(
            category=category,
            query=query,
            only_favorites=only_favorites,
            only_notes=only_notes,
            group=group,
            sort_by=sort_by,
        )
        res.message = f"Arama tamamlandı: {res.data['count']} eşleşme."
        return res

    def resolve_item(self, target: str) -> tuple[int, dict[str, Any]] | None:
        """raw_key (text_000), id (qtp_000) veya tam/kısmi metin ile kayıt arar."""
        needle = (target or "").strip()
        if not needle:
            return None
        needle_low = needle.lower()

        for idx, it in enumerate(self.items):
            rk = str(it.get("raw_key") or f"text_{idx:03d}")
            iid = str(it.get("id") or f"qtp_{idx:03d}")
            if rk.lower() == needle_low or iid.lower() == needle_low:
                return idx, it

        for idx, it in enumerate(self.items):
            if str(it.get("text", "")) == needle:
                return idx, it

        for idx, it in enumerate(self.items):
            if needle_low in str(it.get("text", "")).lower() or needle_low in str(it.get("label", "")).lower():
                return idx, it
        return None

    def op_show_ini(self, target: str) -> OperationResult:
        found = self.resolve_item(target)
        if found is None:
            err = f"Öğe bulunamadı: {target}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)
        idx, item = found
        tid = str(item.get("raw_key") or f"text_{idx:03d}")
        preview = format_ini_preview(item, idx)
        return OperationResult(
            ok=True,
            exit_code=0,
            message="INI kaydı görüntülendi.",
            data={"raw_key": tid, "ini_path": str(self.ini_path), "preview": preview},
        )

    def op_copy(self, target: str, *, strip_emoji: bool | None = None) -> OperationResult:
        found = self.resolve_item(target)
        if found is None:
            err = f"Öğe bulunamadı: {target}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)
        idx, item = found
        raw_text = str(item.get("text", ""))
        use_strip = bool(self.settings.get("strip_emoji", False)) if strip_emoji is None else bool(strip_emoji)
        text = _strip_unicode_emojis(raw_text) if use_strip else raw_text
        raw_key = str(item.get("raw_key") or f"text_{idx:03d}")

        ok = self._clipboard_fn(text) if self._clipboard_fn is not None else copy_to_clipboard(text)
        if not ok:
            err = "Pano erişimi başarısız: grafik oturumu veya pano desteği bulunamadı."
            return OperationResult(ok=False, exit_code=3, message=err, error=err)

        item["copyCount"] = int(item.get("copyCount", 0) or 0) + 1
        self._persist_copy_count()
        self.logger.info("Panoya kopyalandı: kategori=%s anahtar=%s", item.get("keys", ""), raw_key)
        return OperationResult(
            ok=True,
            exit_code=0,
            message="Panoya kopyalandı ✔",
            data={
                "raw_key": raw_key,
                "keys": item.get("keys", ""),
                "text": text,
                "copyCount": item["copyCount"],
                "strip_emoji": use_strip,
            },
        )

    def op_paste(
        self,
        target: str,
        *,
        previous_app: Any = None,
        strip_emoji: bool | None = None,
        already_copied: bool = False,
    ) -> OperationResult:
        found = self.resolve_item(target)
        if found is None:
            err = f"Öğe bulunamadı: {target}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)
        idx, item = found
        raw_text = str(item.get("text", ""))
        use_strip = bool(self.settings.get("strip_emoji", False)) if strip_emoji is None else bool(strip_emoji)
        text = _strip_unicode_emojis(raw_text) if use_strip else raw_text
        raw_key = str(item.get("raw_key") or f"text_{idx:03d}")
        has_end = str(item.get("terminator", DEFAULT_TERMINATOR)) == DEFAULT_TERMINATOR

        if self._paste_fn is not None:
            fn_kwargs: dict[str, Any] = {
                "has_end_marker": has_end,
                "enter_after_paste": bool(self.settings.get("enter_after_paste", True)),
                "paste_method": str(self.settings.get("paste_method", "auto")),
                "previous_app": previous_app,
            }
            if already_copied:
                fn_kwargs["already_copied"] = True
            res = self._paste_fn(text, **fn_kwargs)
        else:
            res = paste_into_active_app(
                text,
                has_end_marker=has_end,
                enter_after_paste=bool(self.settings.get("enter_after_paste", True)),
                paste_method=str(self.settings.get("paste_method", "auto")),
                previous_app=previous_app,
                already_copied=already_copied,
            )

        if not res.ok:
            code = getattr(res, "exit_code", 4 if res.copied else 3)
            err = res.warning or "Tuş simülasyonu başarısız (yalnızca panoya kopyalandı)."
            return OperationResult(
                ok=False,
                exit_code=code,
                message=err,
                error=err,
                warning=res.warning,
                data={"raw_key": raw_key, "copied": res.copied, "pasted": res.pasted, "method": res.method},
            )

        item["copyCount"] = int(item.get("copyCount", 0) or 0) + 1
        self._persist_copy_count()
        self.logger.info(
            "Yapıştırıldı: kategori=%s anahtar=%s yöntem=%s enter=%s",
            item.get("keys", ""),
            raw_key,
            res.method,
            res.enter_sent,
        )
        return OperationResult(
            ok=True,
            exit_code=0,
            message="Yapıştırıldı ✔",
            data={
                "raw_key": raw_key,
                "keys": item.get("keys", ""),
                "text": text,
                "method": res.method,
                "enter_sent": res.enter_sent,
                "copyCount": item["copyCount"],
                "strip_emoji": use_strip,
            },
            warning=res.warning,
        )

    def op_export_ini(
        self,
        target_path: str | Path,
        *,
        raw_keys: list[str] | None = None,
        encoding: str = "utf-16-le-bom",
    ) -> OperationResult:
        export_items = self.items
        if raw_keys is not None:
            want = {str(k).strip().lower() for k in raw_keys if str(k).strip()}
            export_items = [
                it
                for idx, it in enumerate(self.items)
                if str(it.get("raw_key") or f"text_{idx:03d}").lower() in want
                or str(it.get("id") or "").lower() in want
            ]
        if not export_items:
            err = "HATA: Dışa aktarılacak hazır cevap kaydı bulunamadı."
            return OperationResult(ok=False, exit_code=1, message=err, error=err)
        try:
            dest = Path(target_path)
            ini_text = build_qtp_ini(
                export_items,
                program=self.program_meta,
                extra_sections=[] if raw_keys is not None else self.extra_sections,
                preserve_test_ini=True,
            )
            with self._suppress_write(dest):
                write_qtp_ini(dest, ini_text, encoding=encoding, create_bak=True)
            msg = f"INI dışa aktarıldı: {dest} ({len(export_items)} kayıt)."
            self.logger.info(msg)
            return OperationResult(ok=True, exit_code=0, message=msg, data={"path": str(dest), "count": len(export_items)})
        except Exception as exc:
            err = f"HATA: INI dışa aktarılamadı: {exc}"
            self.logger.error(err)
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

    def _apply_imported_records(
        self,
        incoming: list[dict[str, Any]],
        *,
        program: dict[str, str] | None = None,
        extra_sections: list[dict[str, Any]] | None = None,
        mode: str = "merge",
        skip_duplicates: bool = False,
    ) -> tuple[int, int]:
        self._push_undo()
        if mode == "replace":
            if skip_duplicates:
                merged: list[dict[str, Any]] = []
                seen_texts: set[str] = set()
                for it in incoming:
                    txt_norm = str(it.get("text", "")).strip()
                    if txt_norm in seen_texts:
                        continue
                    seen_texts.add(txt_norm)
                    merged.append(it)
            else:
                merged = list(incoming)
            added = len(merged)
            if program:
                self.program_meta = dict(program)
            if extra_sections:
                self.extra_sections = list(extra_sections)
        else:
            merged = list(self.items)
            seen = {(str(it.get("keys", "")), str(it.get("group", "")), str(it.get("text", ""))) for it in merged}
            seen_texts = {str(it.get("text", "")).strip() for it in merged}
            added = 0
            for it in incoming:
                sig = (str(it.get("keys", "")), str(it.get("group", "")), str(it.get("text", "")))
                txt_norm = str(it.get("text", "")).strip()
                if skip_duplicates and txt_norm in seen_texts:
                    continue
                if sig not in seen:
                    merged.append(it)
                    seen.add(sig)
                    seen_texts.add(txt_norm)
                    added += 1
            if not self.program_meta and program:
                self.program_meta = dict(program)
            if not self.extra_sections and extra_sections:
                self.extra_sections = list(extra_sections)

        for idx, it in enumerate(merged):
            it["raw_key"] = f"text_{idx:03d}"
            it.setdefault("terminator", DEFAULT_TERMINATOR)

        with self._suppress_write(self.ini_path, self.work_dir / "data.json"):
            save_state(
                self.work_dir,
                merged,
                program=self.program_meta,
                extra_sections=self.extra_sections,
                backup_reason=f"import_{mode}",
                max_backups=int(self.settings.get("backup_count", 15)),
                ini_path=self.ini_path,
            )
        self.items = merged
        self.revision += 1
        return added, len(merged)

    def op_import_ini(
        self,
        source_path: str | Path,
        *,
        mode: str = "merge",
        skip_duplicates: bool = False,
    ) -> OperationResult:
        src = Path(source_path)
        if not src.is_file():
            err = f"HATA: İçe aktarılacak INI dosyası bulunamadı: {src}"
            return OperationResult(ok=False, exit_code=1, message=err, error=err)
        try:
            doc = parse_qtp_ini(read_text_auto(src))
        except IniParseError as exc:
            err = str(exc)
            return OperationResult(ok=False, exit_code=2, message=err, error=err)
        except Exception as exc:
            err = f"HATA: INI okunamadı: {exc}"
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

        incoming = [
            {**it.to_dict(include_meta=False), "terminator": it.terminator}
            for it in doc.items
        ]
        added, total = self._apply_imported_records(
            incoming,
            program=doc.program,
            extra_sections=doc.extra_sections,
            mode=mode,
            skip_duplicates=skip_duplicates,
        )
        msg = f"INI içe aktarıldı: {added} yeni kayıt eklendi (toplam {total} kayıt korundu)."
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={"added": added, "count": total, "mode": mode},
        )

    def op_import_content(
        self,
        content: str,
        *,
        filename: str = "import.ini",
        mode: str = "merge",
        skip_duplicates: bool = False,
    ) -> OperationResult:
        try:
            parsed = parse_any_content(str(content or ""), filename)
        except (JsonStoreError, IniParseError, json.JSONDecodeError) as exc:
            err = str(exc)
            return OperationResult(ok=False, exit_code=2, message=err, error=err)
        except Exception as exc:
            err = f"HATA: İçe aktarılan içerik okunamadı: {exc}"
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

        incoming = [dict(it) for it in (parsed.get("items") or [])]
        added, total = self._apply_imported_records(
            incoming,
            program=parsed.get("program") or {},
            extra_sections=parsed.get("extra_sections") or [],
            mode=mode,
            skip_duplicates=skip_duplicates,
        )
        msg = f"İçe aktarıldı: {added} yeni kayıt eklendi (toplam {total} kayıt)."
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={"added": added, "count": total, "mode": mode, "kind": parsed.get("kind")},
        )

    def op_backup(self, *, keep: int | None = None) -> OperationResult:
        try:
            if not (self.work_dir / "data.json").is_file() and self.items:
                with self._suppress_write(self.work_dir / "data.json"):
                    save_data_json(self.work_dir / "data.json", self.items)
            max_keep = int(keep if keep is not None else self.settings.get("backup_count", 15))
            meta = create_backup(self.work_dir, reason="cli_backup", max_keep=max_keep)
            if not meta:
                err = "HATA: Yedek oluşturulamadı: yedeklenecek veri dosyası bulunamadı."
                return OperationResult(ok=False, exit_code=1, message=err, error=err)
            msg = f"Anlık yedek alındı: {meta['id']} ({meta['count']} kayıt)."
            self.logger.info(msg)
            return OperationResult(ok=True, exit_code=0, message=msg, data=meta)
        except Exception as exc:
            err = f"HATA: Yedek oluşturulamadı: {exc}"
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

    def op_export_backup(self, target_path: str | Path) -> OperationResult:
        try:
            dest = write_full_backup_file(
                Path(target_path),
                self.items,
                settings=self.settings,
                program=self.program_meta,
                extra_sections=self.extra_sections,
            )
            msg = f"Tam yedek dışa aktarıldı: {dest} ({len(self.items)} kayıt)."
            self.logger.info(msg)
            return OperationResult(ok=True, exit_code=0, message=msg, data={"path": str(dest), "count": len(self.items)})
        except Exception as exc:
            err = f"HATA: Tam yedek dışa aktarılamadı: {exc}"
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

    def op_restore(self, target: str | Path, *, mode: str = "replace") -> OperationResult:
        raw_str = str(target or "").strip()
        if not raw_str:
            err = "Yedek bulunamadı: boş hedef."
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

        as_path = Path(raw_str)
        if as_path.is_file():
            try:
                parsed = parse_any_content(read_text_auto(as_path), as_path.name)
            except (JsonStoreError, IniParseError, json.JSONDecodeError) as exc:
                err = str(exc)
                return OperationResult(ok=False, exit_code=2, message=err, error=err)
            except Exception as exc:
                err = f"HATA: Yedek okunamadı: {exc}"
                return OperationResult(ok=False, exit_code=1, message=err, error=err)

            self._push_undo()
            incoming = parsed["items"]
            if mode == "merge":
                merged = list(self.items)
                seen = {(str(it.get("keys", "")), str(it.get("group", "")), str(it.get("text", ""))) for it in merged}
                for it in incoming:
                    sig = (str(it.get("keys", "")), str(it.get("group", "")), str(it.get("text", "")))
                    if sig not in seen:
                        merged.append(it)
                        seen.add(sig)
            else:
                merged = incoming
                if parsed.get("program"):
                    self.program_meta = dict(parsed["program"])
                if parsed.get("extra_sections"):
                    self.extra_sections = list(parsed["extra_sections"])

            for idx, it in enumerate(merged):
                it["raw_key"] = f"text_{idx:03d}"
                it.setdefault("terminator", DEFAULT_TERMINATOR)

            with self._suppress_write(self.ini_path, self.work_dir / "data.json"):
                save_state(
                    self.work_dir,
                    merged,
                    program=self.program_meta,
                    extra_sections=self.extra_sections,
                    backup_reason="pre_restore",
                    max_backups=int(self.settings.get("backup_count", 15)),
                    ini_path=self.ini_path,
                )
            self.items = merged
            self.revision += 1
            msg = f"Yedek geri yüklendi ✔ ({len(merged)} kayıt, mod={mode})"
            self.logger.info(msg)
            return OperationResult(ok=True, exit_code=0, message=msg, data={"count": len(merged), "mode": mode})

        if "/" in raw_str or "\\" in raw_str or raw_str.endswith((".json", ".ini")):
            err = f"Yedek bulunamadı: {raw_str}"
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

        try:
            self._push_undo()
            with self._suppress_write(self.ini_path, self.work_dir / "data.json"):
                res = restore_backup(self.work_dir, raw_str)
            st = res["state"]
            self.items = st["items"]
            self.program_meta = st.get("program") or {}
            self.extra_sections = st.get("extraSections") or []
            for idx, it in enumerate(self.items):
                it.setdefault("raw_key", f"text_{idx:03d}")
            self.revision += 1
            msg = f"Yedek geri yüklendi ✔ ({res['restored']}, {len(self.items)} kayıt)"
            self.logger.info(msg)
            return OperationResult(
                ok=True,
                exit_code=0,
                message=msg,
                data={"restored": res["restored"], "count": len(self.items)},
            )
        except FileNotFoundError as exc:
            if self._undo_stack:
                self._undo_stack.pop()
                self._save_history()
            err = str(exc)
            return OperationResult(ok=False, exit_code=1, message=err, error=err)
        except Exception as exc:
            if self._undo_stack:
                self._undo_stack.pop()
                self._save_history()
            err = f"HATA: Yedek geri yüklenemedi: {exc}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

    def op_list_backups(self) -> OperationResult:
        return OperationResult(
            ok=True,
            exit_code=0,
            message="Yedek listesi alındı.",
            data={"backups": list_backups(self.work_dir)},
        )

    def op_get_setting(self, key: str | None = None) -> OperationResult:
        if not key:
            return OperationResult(ok=True, exit_code=0, message="Ayar okundu.", data={"settings": dict(self.settings)})
        try:
            val = get_setting_value(self.settings, key)
            return OperationResult(ok=True, exit_code=0, message="Ayar okundu.", data={"key": key, "value": val})
        except SettingValidationError as exc:
            err = str(exc)
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

    def op_set_setting(self, key: str, value: Any) -> OperationResult:
        try:
            updated = set_setting_value(self.settings, key, value)
            self.save_current_settings(updated)
            stored = self.settings.get("hotkeys", {}) if key.startswith("hotkeys.") else None
            if stored is not None:
                sub = key.split(".", 1)[1].strip()
                val_out = stored.get(sub, "")
            else:
                val_out = get_setting_value(self.settings, key)
            return OperationResult(
                ok=True,
                exit_code=0,
                message="Ayarlar kaydedildi ✔",
                data={"key": key, "value": val_out, "revision": self.revision},
            )
        except SettingValidationError as exc:
            err = str(exc)
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

    def op_check_hotkeys(self) -> OperationResult:
        hk = dict(self.settings.get("hotkeys") or DEFAULT_HOTKEYS)
        conflicts = detect_hotkey_conflicts(hk)
        count = sum(len(v) for v in conflicts.values())
        msg = (
            "Kısayol çakışma denetimi tamamlandı: çakışma yok ✔"
            if count == 0
            else f"Kısayol çakışma denetimi tamamlandı: {count} uyarı bulundu."
        )
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={"hotkeys": hk, "conflicts": conflicts, "conflict_count": count, "clean": count == 0},
        )

    def op_apply_hotkey_preset(self, preset_name: str = "recommended") -> OperationResult:
        try:
            canon = resolve_preset_name(preset_name)
        except ValueError as exc:
            err = str(exc)
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        updated = copy.deepcopy(self.settings)
        merged_hk = dict(updated.get("hotkeys") or DEFAULT_HOTKEYS)
        merged_hk.update(HOTKEY_PRESETS[canon])
        updated["hotkeys"] = merged_hk
        self.save_current_settings(updated)

        conflicts = detect_hotkey_conflicts(self.settings["hotkeys"])
        warn = None
        if conflicts:
            warn = "; ".join(f"{k}: {v[0]}" for k, v in conflicts.items())
        return OperationResult(
            ok=True,
            exit_code=0,
            message=f"Kısayol profili uygulandı ✔ ({canon})",
            data={"preset": canon, "hotkeys": dict(self.settings["hotkeys"]), "conflicts": conflicts},
            warning=warn,
        )

    def op_apply_hotkey_modifiers(self, modifiers: str = "Win+Alt") -> OperationResult:
        try:
            new_hk = apply_modifier_combo(self.settings.get("hotkeys") or DEFAULT_HOTKEYS, modifiers)
        except ValueError as exc:
            err = str(exc)
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        updated = copy.deepcopy(self.settings)
        updated["hotkeys"] = new_hk
        self.save_current_settings(updated)
        conflicts = detect_hotkey_conflicts(self.settings["hotkeys"])
        warn = "; ".join(f"{k}: {v[0]}" for k, v in conflicts.items()) if conflicts else None
        return OperationResult(
            ok=True,
            exit_code=0,
            message="Değiştirici bileşimi tüm kısayollara uygulandı ✔",
            data={"modifiers": modifiers, "hotkeys": dict(self.settings["hotkeys"]), "conflicts": conflicts},
            warning=warn,
        )

    def _persist_items_change(
        self,
        items: list[dict[str, Any]],
        reason: str,
        *,
        create_backup_flag: bool = False,
    ) -> None:
        normalized: list[dict[str, Any]] = []
        for idx, raw in enumerate(items):
            entry = dict(raw)
            entry["keys"] = str(entry.get("keys", "")).strip()
            entry["group"] = str(entry.get("group", "Genel")).strip() or "Genel"
            entry["label"] = str(entry.get("label", "")).strip()
            entry["text"] = str(entry.get("text", ""))
            if "terminator" not in entry or entry["terminator"] is None:
                entry["terminator"] = DEFAULT_TERMINATOR
            entry["raw_key"] = f"text_{idx:03d}"
            normalized.append(entry)

        with self._suppress_write(self.ini_path, self.work_dir / "data.json"):
            save_state(
                self.work_dir,
                normalized,
                program=self.program_meta,
                extra_sections=self.extra_sections,
                create_backup_flag=create_backup_flag,
                backup_reason=reason,
                max_backups=int(self.settings.get("backup_count", 15)),
                ini_path=self.ini_path,
            )
        self.items = normalized
        self.revision += 1

    def op_add_item(
        self,
        text: str,
        *,
        keys: str = "",
        group: str = "Genel",
        label: str = "",
        terminator: str = DEFAULT_TERMINATOR,
        favorite: bool = False,
    ) -> OperationResult:
        raw_text = str(text or "")
        if not raw_text.strip():
            err = "Metin alanı boş olamaz."
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        self._push_undo()
        new_item: dict[str, Any] = {
            "keys": str(keys or "").strip(),
            "group": str(group or "Genel").strip() or "Genel",
            "label": str(label or "").strip(),
            "text": raw_text,
            "terminator": DEFAULT_TERMINATOR if terminator is None else str(terminator),
        }
        if favorite:
            new_item["favorite"] = True
        updated_list = [dict(it) for it in self.items] + [new_item]
        self._persist_items_change(updated_list, "add_item", create_backup_flag=False)
        created = dict(self.items[-1])
        msg = f"Yeni cevap eklendi ✔ ({created['raw_key']})"
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={"item": created, "count": len(self.items), "revision": self.revision},
        )

    def op_update_item(
        self,
        target: str,
        *,
        keys: str | None = None,
        group: str | None = None,
        label: str | None = None,
        text: str | None = None,
        terminator: str | None = None,
        favorite: bool | None = None,
    ) -> OperationResult:
        found = self.resolve_item(target)
        if found is None:
            err = f"Öğe bulunamadı: {target}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        idx, _existing = found
        updated_list = [dict(it) for it in self.items]
        item = updated_list[idx]
        if text is not None:
            if not str(text).strip():
                err = "Metin alanı boş olamaz."
                return OperationResult(ok=False, exit_code=2, message=err, error=err)
            item["text"] = str(text)
        elif not str(item.get("text", "")).strip():
            err = "Metin alanı boş olamaz."
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        self._push_undo()
        if keys is not None:
            item["keys"] = str(keys).strip()
        if group is not None:
            item["group"] = str(group).strip() or "Genel"
        if label is not None:
            item["label"] = str(label).strip()
        if terminator is not None:
            item["terminator"] = str(terminator)
        if favorite is not None:
            item["favorite"] = bool(favorite)

        self._persist_items_change(updated_list, "update_item", create_backup_flag=False)
        saved_item = dict(self.items[idx])
        msg = f"Kayıt güncellendi ✔ ({saved_item['raw_key']})"
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={"item": saved_item, "count": len(self.items), "revision": self.revision},
        )

    def op_delete_item(self, target: str) -> OperationResult:
        found = self.resolve_item(target)
        if found is None:
            err = f"Öğe bulunamadı: {target}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        idx, existing = found
        self._push_undo()
        deleted_item = dict(existing)
        remaining = [dict(it) for i, it in enumerate(self.items) if i != idx]
        self._persist_items_change(remaining, "delete_item", create_backup_flag=True)
        msg = f"Kayıt silindi ✔ ({deleted_item.get('raw_key', target)})"
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={"deleted": deleted_item, "count": len(self.items), "revision": self.revision},
        )

    def op_save_all(self) -> OperationResult:
        try:
            self.save_current_settings(self.settings)
            self._persist_items_change([dict(it) for it in self.items], "manual_save", create_backup_flag=True)
            msg = "Tüm kayıtlar ve ayarlar kaydedildi ✔"
            self.logger.info(msg)
            return OperationResult(
                ok=True,
                exit_code=0,
                message=msg,
                data={
                    "count": len(self.items),
                    "ini_path": str(self.ini_path),
                    "settings_path": str(self.settings_path),
                    "revision": self.revision,
                },
            )
        except Exception as exc:
            err = f"HATA: Kayıt ve ayarlar diske yazılamadı: {exc}"
            self.logger.error(err)
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

    def op_duplicate_item(self, target: str) -> OperationResult:
        found = self.resolve_item(target)
        if found is None:
            err = f"Öğe bulunamadı: {target}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        idx, existing = found
        self._push_undo()
        clone = copy.deepcopy(existing)
        lbl = str(clone.get("label", "")).strip()
        if lbl:
            clone["label"] = f"{lbl} (Kopya)"
        clone["copyCount"] = 0
        clone.pop("id", None)
        clone.pop("raw_key", None)
        updated_list = [dict(it) for it in self.items]
        updated_list.insert(idx + 1, clone)
        self._persist_items_change(updated_list, "duplicate_item", create_backup_flag=False)
        created = dict(self.items[idx + 1])
        msg = f"Kayıt çoğaltıldı ✔ ({created['raw_key']})"
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={"item": created, "count": len(self.items), "revision": self.revision},
        )

    def op_move_item(self, target: str, direction: str = "up") -> OperationResult:
        dir_norm = str(direction or "").strip().lower()
        if dir_norm not in ("up", "down"):
            err = f"Geçersiz taşıma yönü: '{direction}' (up veya down bekleniyor)."
            return OperationResult(ok=False, exit_code=2, message=err, error=err)
        found = self.resolve_item(target)
        if found is None:
            err = f"Öğe bulunamadı: {target}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        idx, _ = found
        new_idx = idx - 1 if dir_norm == "up" else idx + 1
        if new_idx < 0 or new_idx >= len(self.items):
            err = "Kayıt zaten sınırda, taşınamadı."
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        self._push_undo()
        updated_list = [dict(it) for it in self.items]
        updated_list[idx], updated_list[new_idx] = updated_list[new_idx], updated_list[idx]
        for pos, entry in enumerate(updated_list, start=1):
            entry["order"] = pos
        self._persist_items_change(updated_list, "move_item", create_backup_flag=False)
        moved = dict(self.items[new_idx])
        msg = f"Kayıt sırası güncellendi ✔ ({moved['raw_key']})"
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={
                "item": moved,
                "old_index": idx,
                "new_index": new_idx,
                "count": len(self.items),
                "revision": self.revision,
            },
        )

    def op_toggle_favorite(self, target: str, *, favorite: bool | None = None) -> OperationResult:
        found = self.resolve_item(target)
        if found is None:
            err = f"Öğe bulunamadı: {target}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        idx, existing = found
        self._push_undo()
        updated_list = [dict(it) for it in self.items]
        new_fav = (not bool(existing.get("favorite", False))) if favorite is None else bool(favorite)
        updated_list[idx]["favorite"] = new_fav
        self._persist_items_change(updated_list, "toggle_favorite", create_backup_flag=False)
        saved = dict(self.items[idx])
        msg = f"Favori durumu güncellendi ✔ ({saved['raw_key']})"
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={"item": saved, "favorite": new_fav, "revision": self.revision},
        )

    def _resolve_targets(self, targets: list[str] | str) -> tuple[list[int] | None, OperationResult | None]:
        if isinstance(targets, str):
            raw_list = [t.strip() for t in targets.split(",") if t.strip()]
        elif isinstance(targets, (list, tuple, set)):
            raw_list = [str(t).strip() for t in targets if str(t).strip()]
        else:
            raw_list = []

        if not raw_list:
            err = "Toplu işlem için en az bir hedef kayıt seçilmelidir."
            return None, OperationResult(ok=False, exit_code=2, message=err, error=err)

        indices: list[int] = []
        seen_idx: set[int] = set()
        for t in raw_list:
            found = self.resolve_item(t)
            if found is None:
                err = f"Öğe bulunamadı: {t}"
                return None, OperationResult(ok=False, exit_code=2, message=err, error=err)
            if found[0] not in seen_idx:
                indices.append(found[0])
                seen_idx.add(found[0])
        return indices, None

    def op_bulk_edit(
        self,
        targets: list[str] | str,
        *,
        keys: str | None = None,
        group: str | None = None,
        find: str | None = None,
        replace: str = "",
        ignore_case: bool = False,
        prefix: str = "",
        suffix: str = "",
        strip_emojis: bool = False,
        add_emoji: str = "",
        favorite_action: str = "keep",
    ) -> OperationResult:
        indices, err_res = self._resolve_targets(targets)
        if err_res is not None or indices is None:
            return err_res

        fav_act = str(favorite_action or "keep").strip().lower()
        has_change = any(
            (
                keys is not None,
                group is not None and bool(str(group).strip()),
                bool(find),
                bool(prefix),
                bool(suffix),
                bool(strip_emojis),
                bool(str(add_emoji or "").strip()),
                fav_act in ("add", "remove"),
            )
        )
        if not has_change:
            err = "Toplu düzenleme için en az bir değişiklik seçeneği belirtilmelidir."
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        self._push_undo()
        updated_list = [dict(it) for it in self.items]
        pattern = None
        if find:
            flags = re.IGNORECASE if ignore_case else 0
            pattern = re.compile(re.escape(str(find)), flags)

        emoji_tok = str(add_emoji or "").strip()
        updated_keys: list[str] = []
        for idx in indices:
            item = updated_list[idx]
            if keys is not None:
                item["keys"] = str(keys).strip()
            if group is not None and str(group).strip():
                item["group"] = str(group).strip()
            txt = str(item.get("text", ""))
            if pattern is not None:
                txt = pattern.sub(str(replace or ""), txt)
            if prefix or suffix:
                txt = f"{prefix}{txt}{suffix}"
            if strip_emojis:
                txt = _strip_unicode_emojis(txt)
            if emoji_tok:
                sep = " " if txt and not txt.endswith((" ", "\n")) else ""
                txt = f"{txt}{sep}{emoji_tok}"
            item["text"] = txt
            if fav_act == "add":
                item["favorite"] = True
            elif fav_act == "remove":
                item["favorite"] = False
            updated_keys.append(str(item.get("raw_key") or f"text_{idx:03d}"))

        self._persist_items_change(updated_list, "bulk_edit", create_backup_flag=True)
        msg = f"Toplu düzenleme tamamlandı ✔ ({len(indices)} kayıt güncellendi)"
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={
                "updated_count": len(indices),
                "raw_keys": updated_keys,
                "count": len(self.items),
                "revision": self.revision,
            },
        )

    def op_bulk_delete(self, targets: list[str] | str) -> OperationResult:
        indices, err_res = self._resolve_targets(targets)
        if err_res is not None or indices is None:
            return err_res

        self._push_undo()
        idx_set = set(indices)
        deleted_keys = [
            str(it.get("raw_key") or f"text_{i:03d}")
            for i, it in enumerate(self.items)
            if i in idx_set
        ]
        remaining = [dict(it) for i, it in enumerate(self.items) if i not in idx_set]
        self._persist_items_change(remaining, "bulk_delete", create_backup_flag=True)
        msg = f"Seçili kayıtlar silindi ✔ ({len(idx_set)} kayıt)"
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={
                "deleted_count": len(idx_set),
                "deleted_keys": deleted_keys,
                "count": len(self.items),
                "revision": self.revision,
            },
        )

    def op_list_groups(self) -> OperationResult:
        counts: dict[str, int] = {}
        hotkeys_map: dict[str, list[str]] = {}
        for it in self.items:
            grp = str(it.get("group") or "Genel").strip() or "Genel"
            counts[grp] = counts.get(grp, 0) + 1
            hk = str(it.get("keys", "")).strip()
            lst = hotkeys_map.setdefault(grp, [])
            if hk and hk not in lst:
                lst.append(hk)
        groups = [
            {"name": name, "count": cnt, "hotkeys": hotkeys_map.get(name, [])}
            for name, cnt in counts.items()
        ]
        return OperationResult(
            ok=True,
            exit_code=0,
            message=f"Gruplar listelendi ({len(groups)} grup).",
            data={"groups": groups, "count": len(groups)},
        )

    def op_rename_group(self, old_group: str, new_group: str) -> OperationResult:
        old_g = str(old_group or "").strip()
        new_g = str(new_group or "").strip()
        if not old_g or not new_g:
            err = "Eski ve yeni grup adı boş olamaz."
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        matches = [i for i, it in enumerate(self.items) if (str(it.get("group") or "Genel").strip() == old_g)]
        if not matches:
            err = f"Grup bulunamadı: {old_g}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        self._push_undo()
        updated_list = [dict(it) for it in self.items]
        for idx in matches:
            updated_list[idx]["group"] = new_g
        self._persist_items_change(updated_list, "rename_group", create_backup_flag=True)
        msg = f"Grup yeniden adlandırıldı ✔ ({old_g} → {new_g}, {len(matches)} kayıt)"
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={
                "old_group": old_g,
                "new_group": new_g,
                "updated_count": len(matches),
                "count": len(self.items),
                "revision": self.revision,
            },
        )

    def op_delete_group(self, group_name: str) -> OperationResult:
        grp = str(group_name or "").strip()
        if not grp:
            err = "Grup adı boş olamaz."
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        remaining = [dict(it) for it in self.items if (str(it.get("group") or "Genel").strip() != grp)]
        deleted_count = len(self.items) - len(remaining)
        if deleted_count == 0:
            err = f"Grup bulunamadı: {grp}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        self._push_undo()
        self._persist_items_change(remaining, "delete_group", create_backup_flag=True)
        msg = f"Grup silindi ✔ ({grp}, {deleted_count} kayıt)"
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={
                "group": grp,
                "deleted_count": deleted_count,
                "count": len(self.items),
                "revision": self.revision,
            },
        )

    def op_undo(self) -> OperationResult:
        if not self._undo_stack:
            err = "Geri alınacak işlem yok."
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        current_snap = (
            copy.deepcopy(self.items),
            copy.deepcopy(self.program_meta),
            copy.deepcopy(self.extra_sections),
        )
        self._redo_stack.append(current_snap)
        if len(self._redo_stack) > 30:
            self._redo_stack.pop(0)

        prev_items, prev_prog, prev_extra = self._undo_stack.pop()
        self.program_meta = prev_prog
        self.extra_sections = prev_extra
        self._persist_items_change(prev_items, "undo", create_backup_flag=False)
        self._save_history()
        msg = f"Son işlem geri alındı ✔ ({len(self.items)} kayıt)"
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={
                "count": len(self.items),
                "revision": self.revision,
                "can_undo": bool(self._undo_stack),
                "can_redo": bool(self._redo_stack),
            },
        )

    def op_redo(self) -> OperationResult:
        if not self._redo_stack:
            err = "Yinelenecek işlem yok."
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        current_snap = (
            copy.deepcopy(self.items),
            copy.deepcopy(self.program_meta),
            copy.deepcopy(self.extra_sections),
        )
        self._undo_stack.append(current_snap)
        if len(self._undo_stack) > 30:
            self._undo_stack.pop(0)

        next_items, next_prog, next_extra = self._redo_stack.pop()
        self.program_meta = next_prog
        self.extra_sections = next_extra
        self._persist_items_change(next_items, "redo", create_backup_flag=False)
        self._save_history()
        msg = f"İşlem yinelendi ✔ ({len(self.items)} kayıt)"
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={
                "count": len(self.items),
                "revision": self.revision,
                "can_undo": bool(self._undo_stack),
                "can_redo": bool(self._redo_stack),
            },
        )
