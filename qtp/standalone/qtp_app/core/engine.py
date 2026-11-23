"""Arayüzden bağımsız (Qt-free) QTP çekirdek motoru — --gui, --tui, --cli ve --web için tek kaynak."""

from __future__ import annotations

import contextlib
import copy
import importlib.resources
import json
import os
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
from qtp_app.ui.search import FuzzyMatcher

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
    "--get",
    "--set",
    "--check-hotkeys",
    "--hotkey-preset",
    "--hotkey-modifiers",
    "--add-item",
    "--update-item",
    "--delete-item",
    "--item-keys",
    "--item-group",
    "--item-label",
    "--item-text",
    "--no-end-marker",
    "--category",
    "--query",
    "--json",
    "--work-dir",
    "--keep",
    "--merge",
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

    if shell == "powershell":
        flags_ps = ", ".join(f"'{f}'" for f in flags)
        modes_ps = ", ".join(f"'{m}'" for m in modes)
        cats_ps = ", ".join(f"'{c}'" for c in cats)
        presets_ps = ", ".join(f"'{p}'" for p in presets)
        shells_ps = ", ".join(f"'{s}'" for s in shells)
        skeys_ps = ", ".join(f"'{k}'" for k in skeys)
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
            if f not in ("--mode", "--category", "--completion", "--hotkey-preset", "--get", "--set")
            else (
                f"  '--mode[Çalışma modu]:mod:({' '.join(modes)})'"
                if f == "--mode"
                else f"  '--category[Kategori filtresi]:kategori:({' '.join(cats)})'"
                if f == "--category"
                else f"  '--completion[Kabuk tamamlama betiği]:kabuk:({' '.join(shells)})'"
                if f == "--completion"
                else f"  '--hotkey-preset[Kısayol profili]:profil:({' '.join(presets)})'"
                if f == "--hotkey-preset"
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
        "  --merge / --replace                    --import-ini ve --restore için birleştir/değiştir modu\n"
        "  --keep N                               --backup için tutulacak maksimum yedek sayısı\n"
        "  --port N                               --web için 127.0.0.1 bağlantı noktası (varsayılan: 8765)\n"
        "  --open-browser                         --web başlatıldığında tarayıcıyı açar\n"
        "  --shutdown-after SN                    --web sunucusunu belirtilen saniye sonra zarifçe kapatır\n"
        "  --item-keys TUS / --item-group GRUP    --add-item / --update-item için kısayol, grup, etiket ve metin alanları\n"
        "  --item-label ETIKET / --item-text METIN / --no-end-marker\n"
        "                                         Yeni veya güncellenen kaydın alanlarını ve <E<N<D| son ekini belirler\n"
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
            self.logger = get_logger("engine")

            self.settings, self.settings_path, self.settings_warning = load_settings(self.config_dir)
            setup_logging(
                self.config_dir,
                level=str(self.settings.get("log_level", "info")),
                verbose=self.verbose,
            )

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

        self._seed_defaults_if_empty(seed_defaults and not self.ephemeral)
        self.reload_data()

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
                            setup_logging(
                                self.config_dir,
                                level=str(new_settings.get("log_level", "info")),
                                verbose=self.verbose,
                            )
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
        setup_logging(
            self.config_dir,
            level=str(self.settings.get("log_level", "info")),
            verbose=self.verbose,
        )
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
        try:
            if self.ini_path.is_file() or (self.work_dir / "data.json").is_file():
                state = load_state(self.work_dir, ini_path=self.ini_path, prefer_source=prefer_source)
                if state["items"]:
                    self.items = state["items"]
                    self.program_meta = state.get("program") or {}
                    self.extra_sections = state.get("extraSections") or []
                    for idx, it in enumerate(self.items):
                        it.setdefault("raw_key", f"text_{idx:03d}")
                        it.setdefault("terminator", DEFAULT_TERMINATOR)
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
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

        self.items = []
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

    def op_list_items(self, *, category: str = "ALL", query: str = "") -> OperationResult:
        cat = (category or "ALL").strip().upper()
        filtered_cat = [it for it in self.items if item_matches_category(it, cat)]
        matched = self._matcher.filter_items(query or "", filtered_cat)
        out_items = [
            {
                "raw_key": str(it.get("raw_key") or f"text_{orig_idx:03d}"),
                "keys": str(it.get("keys", "")),
                "group": str(it.get("group", "Genel")),
                "label": str(it.get("label", "")),
                "text": str(it.get("text", "")),
                "terminator": str(it.get("terminator", DEFAULT_TERMINATOR)),
                "matched_indices": list(indices),
            }
            for orig_idx, it, indices in matched
        ]
        return OperationResult(
            ok=True,
            exit_code=0,
            message=f"Hazır cevaplar listelendi: {len(out_items)} kayıt.",
            data={"items": out_items, "count": len(out_items), "category": cat, "query": query},
        )

    def op_search(self, query: str, *, category: str = "ALL") -> OperationResult:
        res = self.op_list_items(category=category, query=query)
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

    def op_copy(self, target: str) -> OperationResult:
        found = self.resolve_item(target)
        if found is None:
            err = f"Öğe bulunamadı: {target}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)
        idx, item = found
        text = str(item.get("text", ""))
        raw_key = str(item.get("raw_key") or f"text_{idx:03d}")

        ok = self._clipboard_fn(text) if self._clipboard_fn is not None else copy_to_clipboard(text)
        if not ok:
            err = "Pano erişimi başarısız: grafik oturumu veya pano desteği bulunamadı."
            return OperationResult(ok=False, exit_code=3, message=err, error=err)

        self.logger.info("Panoya kopyalandı: kategori=%s anahtar=%s", item.get("keys", ""), raw_key)
        return OperationResult(
            ok=True,
            exit_code=0,
            message="Panoya kopyalandı ✔",
            data={"raw_key": raw_key, "keys": item.get("keys", ""), "text": text},
        )

    def op_paste(self, target: str, *, previous_app: Any = None) -> OperationResult:
        found = self.resolve_item(target)
        if found is None:
            err = f"Öğe bulunamadı: {target}"
            return OperationResult(ok=False, exit_code=2, message=err, error=err)
        idx, item = found
        text = str(item.get("text", ""))
        raw_key = str(item.get("raw_key") or f"text_{idx:03d}")
        has_end = str(item.get("terminator", DEFAULT_TERMINATOR)) == DEFAULT_TERMINATOR

        if self._paste_fn is not None:
            res = self._paste_fn(
                text,
                has_end_marker=has_end,
                enter_after_paste=bool(self.settings.get("enter_after_paste", True)),
                paste_method=str(self.settings.get("paste_method", "auto")),
                previous_app=previous_app,
            )
        else:
            res = paste_into_active_app(
                text,
                has_end_marker=has_end,
                enter_after_paste=bool(self.settings.get("enter_after_paste", True)),
                paste_method=str(self.settings.get("paste_method", "auto")),
                previous_app=previous_app,
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
            },
            warning=res.warning,
        )

    def op_export_ini(self, target_path: str | Path) -> OperationResult:
        if not self.items:
            err = "HATA: Dışa aktarılacak hazır cevap kaydı bulunamadı."
            return OperationResult(ok=False, exit_code=1, message=err, error=err)
        try:
            dest = Path(target_path)
            ini_text = build_qtp_ini(
                self.items,
                program=self.program_meta,
                extra_sections=self.extra_sections,
                preserve_test_ini=True,
            )
            with self._suppress_write(dest):
                write_qtp_ini(dest, ini_text, encoding="utf-16-le-bom", create_bak=True)
            msg = f"INI dışa aktarıldı: {dest} ({len(self.items)} kayıt)."
            self.logger.info(msg)
            return OperationResult(ok=True, exit_code=0, message=msg, data={"path": str(dest), "count": len(self.items)})
        except Exception as exc:
            err = f"HATA: INI dışa aktarılamadı: {exc}"
            self.logger.error(err)
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

    def op_import_ini(self, source_path: str | Path, *, mode: str = "merge") -> OperationResult:
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
        if mode == "replace":
            merged = incoming
            added = len(incoming)
            if doc.program:
                self.program_meta = dict(doc.program)
            if doc.extra_sections:
                self.extra_sections = list(doc.extra_sections)
        else:
            merged = list(self.items)
            seen = {(str(it.get("keys", "")), str(it.get("group", "")), str(it.get("text", ""))) for it in merged}
            added = 0
            for it in incoming:
                sig = (str(it.get("keys", "")), str(it.get("group", "")), str(it.get("text", "")))
                if sig not in seen:
                    merged.append(it)
                    seen.add(sig)
                    added += 1
            if not self.program_meta and doc.program:
                self.program_meta = dict(doc.program)
            if not self.extra_sections and doc.extra_sections:
                self.extra_sections = list(doc.extra_sections)

        for idx, it in enumerate(merged):
            it["raw_key"] = f"text_{idx:03d}"

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
        msg = f"INI içe aktarıldı: {added} yeni kayıt eklendi (toplam {len(merged)} kayıt korundu)."
        self.logger.info(msg)
        return OperationResult(
            ok=True,
            exit_code=0,
            message=msg,
            data={"added": added, "count": len(merged), "mode": mode},
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
            err = str(exc)
            return OperationResult(ok=False, exit_code=1, message=err, error=err)
        except Exception as exc:
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
                data={"key": key, "value": val_out},
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
    ) -> OperationResult:
        raw_text = str(text or "")
        if not raw_text.strip():
            err = "Metin alanı boş olamaz."
            return OperationResult(ok=False, exit_code=2, message=err, error=err)

        new_item: dict[str, Any] = {
            "keys": str(keys or "").strip(),
            "group": str(group or "Genel").strip() or "Genel",
            "label": str(label or "").strip(),
            "text": raw_text,
            "terminator": DEFAULT_TERMINATOR if terminator is None else str(terminator),
        }
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

        if keys is not None:
            item["keys"] = str(keys).strip()
        if group is not None:
            item["group"] = str(group).strip() or "Genel"
        if label is not None:
            item["label"] = str(label).strip()
        if terminator is not None:
            item["terminator"] = str(terminator)

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
