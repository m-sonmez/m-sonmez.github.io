"""Çapraz platform etkileşimli terminal arayüzü (--tui): GUI ile birebir işlem ve kısayol eşitliği."""

from __future__ import annotations

import os
import shutil
import sys
import threading
from typing import Any, Callable, Iterable, TextIO

from qtp_app import __version__
from qtp_app.core.engine import CATEGORY_DEFINITIONS, OperationResult, QtpEngine, format_hotkeys_toast
from qtp_app.core.logging_setup import get_logger
from qtp_app.core.operations import OPERATIONS
from qtp_app.core.watcher import ReloadEvent

tui_logger = get_logger("tui")

TUI_FOOTER_HINTS = (
    "↑↓ Gezin · ⏎ Yapıştır · c Kopyala · e INI'de Göster · b Yedekle · s Ayarlar · F1 Yardım · q Çıkış"
)

_CATEGORY_CODES = [code for code, _lbl, _pref in CATEGORY_DEFINITIONS]


class QtpTui:
    """
    GUI katmanının mantıksal yerleşimini ve tüm operations.py işlemlerini sunan TUI adaptörü.
    Canlı terminalde veya başsız test/betik akışında çalışır.
    """

    def __init__(
        self,
        engine: QtpEngine,
        *,
        term_size: tuple[int, int] = (100, 28),
        use_color: bool = True,
        initial_category: str | None = None,
        initial_query: str = "",
        quiet: bool = False,
    ):
        self.engine = engine
        self.term_size = term_size
        self.use_color = use_color
        self.quiet = bool(quiet) and int(getattr(engine, "verbose", 0) or 0) <= 0
        raw_cat = initial_category if initial_category is not None else engine.settings.get("last_category", "ALL")
        self.category: str = str(raw_cat).strip().upper()
        if self.category not in _CATEGORY_CODES:
            self.category = "ALL"
        self.query: str = str(initial_query or "")
        self.search_mode: bool = False
        self.selected_idx: int = 0
        self.scroll_offset: int = 0
        self.modal_title: str = ""
        self.modal_lines: list[str] = []
        self.modal_scroll: int = 0
        if self.quiet:
            self.status_message = f"{len(engine.items)} kayıt"
        else:
            self.status_message = (
                format_hotkeys_toast(engine.settings.get("hotkeys"))
                if engine.first_run
                else f"QTP hazır ({len(engine.items)} kayıt)"
            )
        self.last_result: OperationResult = OperationResult(
            ok=True,
            exit_code=0,
            message=self.status_message,
        )
        self.exit_code: int = 0
        self.running: bool = True
        self._visible_items: list[dict[str, Any]] = []
        self._categories_cache: list[dict[str, Any]] = []
        self.recorded_frames: list[str] = []
        self._reload_lock = threading.RLock()
        self._refresh_view_data()

    def apply_reload_event(self, event: ReloadEvent) -> None:
        """İzleyici iş parçacığından gelen canlı değişiklik özetini TUI görünümüne uygular."""
        with self._reload_lock:
            self._refresh_view_data()
            if event.warning:
                self.status_message = event.warning
            elif event.items_changed:
                self.status_message = f"Hazır cevaplar otomatik yenilendi ({len(self.engine.items)} kayıt) ✔"
            elif event.settings_changed:
                self.status_message = "Ayarlar ve kısayollar otomatik güncellendi ✔"
            tui_logger.info(
                "TUI canlı yenileme: öğe=%d uyarı=%s",
                len(self.engine.items),
                event.warning or "yok",
            )

    def _refresh_view_data(self) -> None:
        with self._reload_lock:
            cat_res = self.engine.op_list_categories()
            self._categories_cache = cat_res.data["categories"]
            list_res = self.engine.op_list_items(category=self.category, query=self.query)
            self._visible_items = list_res.data["items"]
            if not self._visible_items:
                self.selected_idx = 0
                self.scroll_offset = 0
            else:
                self.selected_idx = max(0, min(self.selected_idx, len(self._visible_items) - 1))

    def current_item(self) -> dict[str, Any] | None:
        if 0 <= self.selected_idx < len(self._visible_items):
            return self._visible_items[self.selected_idx]
        return None

    def current_raw_key(self) -> str:
        item = self.current_item()
        return str(item.get("raw_key", "")) if item else ""

    def render_plain_lines(self) -> list[str]:
        """Altın anlık görüntü (golden snapshot) ve düz metin doğrulaması için deterministik ekran."""
        with self._reload_lock:
            width, height = self.term_size
            inner_w = max(50, width)
            lines: list[str] = []

            search_state = "[YAZIYOR]" if self.search_mode else "[/ Ara]"
            lines.append(
                f"QTP v{__version__} | Mod: TUI | Ara: \"{self.query}\" {search_state} | Kayıt: {len(self._visible_items)}/{len(self.engine.items)}"
            )

            pills: list[str] = []
            for cat in self._categories_cache:
                code = cat["code"]
                label = cat["label"]
                cnt = cat["count"]
                if code == self.category:
                    pills.append(f"[{label} ({cnt})]")
                else:
                    pills.append(f"{label} ({cnt})")
            lines.append("Kategoriler: " + " | ".join(pills))
            lines.append("-" * min(inner_w, 96))

            body_rows = max(5, height - 6)
            if self.modal_lines:
                vis_rows = max(1, body_rows - 1)
                max_scroll = max(0, len(self.modal_lines) - vis_rows)
                self.modal_scroll = max(0, min(self.modal_scroll, max_scroll))
                if max_scroll > 0:
                    lines.append(
                        f"=== {self.modal_title} [{self.modal_scroll + 1}/{len(self.modal_lines)}] (↑↓ Kaydır · Kapatmak için Esc/q) ==="
                    )
                else:
                    lines.append(f"=== {self.modal_title} (Kapatmak için Esc/q) ===")
                for mline in self.modal_lines[self.modal_scroll : self.modal_scroll + vis_rows]:
                    lines.append(mline[:inner_w])
                while len(lines) < 3 + body_rows:
                    lines.append("")
            else:
                if self.selected_idx < self.scroll_offset:
                    self.scroll_offset = self.selected_idx
                elif self.selected_idx >= self.scroll_offset + body_rows:
                    self.scroll_offset = self.selected_idx - body_rows + 1

                slice_items = self._visible_items[self.scroll_offset : self.scroll_offset + body_rows]
                for offset, item in enumerate(slice_items):
                    abs_idx = self.scroll_offset + offset
                    pointer = ">" if abs_idx == self.selected_idx else " "
                    keys = str(item.get("keys", ""))
                    badge = keys.rsplit("+", 1)[-1].upper() if "+" in keys else (keys.upper() or "•")
                    snippet = str(item.get("text", "")).replace("\r\n", " ").replace("\n", " ")
                    row_txt = f"{pointer} {abs_idx + 1:>3}. [{badge}] {snippet}"
                    if len(row_txt) > inner_w:
                        row_txt = row_txt[: inner_w - 1] + "…"
                    lines.append(row_txt)
                if not slice_items:
                    lines.append("  (Eşleşen hazır cevap bulunamadı)")
                while len(lines) < 3 + body_rows:
                    lines.append("")

            lines.append("-" * min(inner_w, 96))
            lines.append(f"Durum: {self.status_message[:inner_w - 7]}")
            lines.append(TUI_FOOTER_HINTS[:inner_w])
            return lines

    def render_ansi_lines(self) -> list[str]:
        """Renkli 256/TrueColor ANSI terminal görünümü üretir (ui/theme.py renkleriyle uyumlu)."""
        plain = self.render_plain_lines()
        if not self.use_color:
            return plain
        styled: list[str] = []
        for idx, line in enumerate(plain):
            if idx == 0:
                styled.append(f"\x1b[1;38;2;34;211;238m{line}\x1b[0m")
            elif idx == 1:
                styled.append(f"\x1b[38;2;196;181;253m{line}\x1b[0m")
            elif line.startswith("> "):
                styled.append(f"\x1b[48;2;124;58;237m\x1b[38;2;255;255;255m{line}\x1b[0m")
            elif line.startswith("Durum:"):
                color = "34;211;238" if self.last_result.ok else "248;113;113"
                styled.append(f"\x1b[1;38;2;{color}m{line}\x1b[0m")
            elif idx == len(plain) - 1:
                styled.append(f"\x1b[38;2;148;163;184m{line}\x1b[0m")
            else:
                styled.append(line)
        return styled

    def _record_result(self, res: OperationResult, *, status_override: str | None = None) -> OperationResult:
        self.last_result = res
        raw_msg = status_override if status_override is not None else res.message
        self.status_message = " ".join(str(raw_msg).splitlines()).strip()
        if not res.ok:
            self.exit_code = res.exit_code
        tui_logger.debug("TUI işlem sonucu: ok=%s exit=%d mesaj=%s", res.ok, res.exit_code, self.status_message)
        return res

    def execute_operation(self, op_id: str, arg: str = "", extra: str = "") -> OperationResult:
        """Belirtilen operations.py kimliğini engine üzerinden doğrudan çalıştırır."""
        target = arg or self.current_raw_key()
        tui_logger.info("TUI işlemi yürütülüyor: op=%s hedef=%r", op_id, target)
        if op_id == "version":
            res = self.engine.op_version()
            self.modal_title = "Sürüm Bilgisi"
            self.modal_lines = [res.message]
            self.modal_scroll = 0
            return self._record_result(res)
        if op_id == "help":
            res = self.engine.op_help(verbose=True)
            self.modal_title = "QTP Türkçe Yardım (F1)"
            sep = "\n\n" + ("=" * 60) + "\n\n"
            docs_txt = sep.join(
                (
                    "=== CLI & Parametreler (--verbose --help) ===\n\n" + res.data["usage_verbose"],
                    "=== Kullanım Kılavuzu ===\n\n" + res.data["kullanim"],
                    "=== Kısayollar ===\n\n" + res.data["kisayollar"],
                    "=== Sorun Giderme (SSS) ===\n\n" + res.data["sss"],
                )
            )
            self.modal_lines = docs_txt.splitlines()
            self.modal_scroll = 0
            return self._record_result(res, status_override="Kullanım yardımı görüntülendi.")
        if op_id == "selftest":
            return self._record_result(self.engine.op_selftest(run_ui_smoke=False))
        if op_id == "modes":
            res = self.engine.op_modes()
            self.modal_title = "Desteklenen Modlar"
            self.modal_lines = [res.message]
            self.modal_scroll = 0
            return self._record_result(res)
        if op_id == "completion":
            res = self.engine.op_completion(arg or "auto")
            if res.ok:
                self.modal_title = f"Kabuk Tamamlama ({res.data['shell']})"
                self.modal_lines = str(res.data["script"]).splitlines()
                self.modal_scroll = 0
            return self._record_result(res)
        if op_id == "list_categories":
            return self._record_result(self.engine.op_list_categories())
        if op_id == "list_items":
            return self._record_result(self.engine.op_list_items(category=self.category, query=self.query))
        if op_id == "search":
            self.query = arg
            self._refresh_view_data()
            return self._record_result(self.engine.op_search(arg, category=self.category))
        if op_id == "show_ini":
            res = self.engine.op_show_ini(target)
            if res.ok:
                self.modal_title = f"INI Kaydı ({res.data['raw_key']})"
                self.modal_lines = str(res.data["preview"]).splitlines()
            return self._record_result(res)
        if op_id == "copy":
            return self._record_result(self.engine.op_copy(target))
        if op_id == "paste":
            return self._record_result(self.engine.op_paste(target))
        if op_id == "export_ini":
            return self._record_result(self.engine.op_export_ini(arg or (self.engine.work_dir / "QuickTextPaste_export.ini")))
        if op_id == "import_ini":
            res = self.engine.op_import_ini(arg, mode=extra or "merge")
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "export_backup":
            return self._record_result(self.engine.op_export_backup(arg or self.engine.work_dir))
        if op_id == "restore":
            res = self.engine.op_restore(arg, mode=extra or "replace")
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "backup":
            return self._record_result(self.engine.op_backup())
        if op_id == "reload":
            res = self.engine.reload_data()
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "get_setting":
            res = self.engine.op_get_setting(arg or None)
            if res.ok:
                self.modal_title = "Ayarlar (qtp_settings.json)"
                if "settings" in res.data:
                    self.modal_lines = [f"{k}: {v}" for k, v in res.data["settings"].items()]
                else:
                    self.modal_lines = [f"{res.data['key']}: {res.data['value']}"]
            return self._record_result(res)
        if op_id == "set_setting":
            res = self.engine.op_set_setting(arg, extra)
            return self._record_result(res)
        if op_id == "check_hotkeys":
            res = self.engine.op_check_hotkeys()
            self.modal_title = "Kısayol Çakışma Denetimi"
            lines = [f"{k}: {v}" for k, v in res.data["hotkeys"].items()]
            if res.data["conflicts"]:
                lines.append("")
                for k, msgs in res.data["conflicts"].items():
                    lines.append(f"[!] {k}: {'; '.join(msgs)}")
            self.modal_lines = lines
            return self._record_result(res)
        if op_id == "hotkey_preset":
            return self._record_result(self.engine.op_apply_hotkey_preset(arg or "recommended"))
        if op_id == "hotkey_modifiers":
            return self._record_result(self.engine.op_apply_hotkey_modifiers(arg or "Win+Alt"))

        err = f"Bilinmeyen TUI işlemi: {op_id}"
        return self._record_result(OperationResult(ok=False, exit_code=2, message=err, error=err))

    def handle_key(self, key: str) -> None:
        """Tek tuş basımını işler; ESC/q modalı kapatır veya uygulamadan çıkar."""
        if self.modal_lines:
            body_rows = max(5, self.term_size[1] - 6)
            vis_rows = max(1, body_rows - 1)
            page_step = max(1, vis_rows - 1)
            max_scroll = max(0, len(self.modal_lines) - vis_rows)
            if key == "UP":
                self.modal_scroll = max(0, self.modal_scroll - 1)
            elif key == "DOWN":
                self.modal_scroll = min(max_scroll, self.modal_scroll + 1)
            elif key == "PGUP":
                self.modal_scroll = max(0, self.modal_scroll - page_step)
            elif key == "PGDN":
                self.modal_scroll = min(max_scroll, self.modal_scroll + page_step)
            elif key in ("ESC", "q", "ENTER"):
                self.modal_lines = []
                self.modal_title = ""
                self.modal_scroll = 0
            return

        if self.search_mode:
            if key == "ESC":
                self.search_mode = False
                return
            if key == "ENTER":
                self.search_mode = False
                if self._visible_items:
                    self.execute_operation("paste")
                return
            if key == "BACKSPACE":
                self.query = self.query[:-1]
                self._refresh_view_data()
                return
            if key in ("UP", "DOWN", "PGUP", "PGDN"):
                pass
            elif len(key) == 1 and key.isprintable():
                self.query += key
                self._refresh_view_data()
                return

        if key == "UP":
            self.selected_idx = max(0, self.selected_idx - 1)
        elif key == "DOWN":
            if self._visible_items:
                self.selected_idx = min(len(self._visible_items) - 1, self.selected_idx + 1)
        elif key == "PGUP":
            self.selected_idx = max(0, self.selected_idx - 6)
        elif key == "PGDN":
            if self._visible_items:
                self.selected_idx = min(len(self._visible_items) - 1, self.selected_idx + 6)
        elif key == "TAB":
            idx = _CATEGORY_CODES.index(self.category)
            self.category = _CATEGORY_CODES[(idx + 1) % len(_CATEGORY_CODES)]
            self._refresh_view_data()
        elif key in ("1", "2", "3", "4", "5"):
            self.category = _CATEGORY_CODES[int(key) - 1]
            self._refresh_view_data()
        elif key == "/":
            self.search_mode = True
        elif key == "ENTER":
            self.execute_operation("paste")
        elif key == "c":
            self.execute_operation("copy")
        elif key == "e":
            self.execute_operation("show_ini")
        elif key == "b":
            self.execute_operation("backup")
        elif key == "B":
            self.execute_operation("export_backup")
        elif key == "x":
            self.execute_operation("export_ini")
        elif key == "r":
            self.execute_operation("reload")
        elif key == "s":
            self.execute_operation("get_setting")
        elif key == "k":
            self.execute_operation("check_hotkeys")
        elif key == "C":
            self.execute_operation("completion")
        elif key == "P":
            self.execute_operation("hotkey_preset", "recommended")
        elif key == "F1":
            self.execute_operation("help")
        elif key == "V":
            self.execute_operation("version")
        elif key == "T":
            self.execute_operation("selftest")
        elif key == "M":
            self.execute_operation("modes")
        elif key in ("q", "ESC"):
            self.running = False

    def _capture_script_frame(self) -> None:
        frame = "\n".join(self.render_plain_lines())
        if not self.recorded_frames or self.recorded_frames[-1] != frame:
            self.recorded_frames.append(frame)

    def run_scripted(self, keys: Iterable[str]) -> list[str]:
        """Betiklenmiş tuş dizisini çalıştırır ve son ekran satırlarını döndürür."""
        self.recorded_frames = []
        for k in keys:
            if not self.running:
                break
            prev_modal = bool(self.modal_lines)
            prev_search = self.search_mode
            self.handle_key(k)
            if (
                (not prev_modal and self.modal_lines)
                or (prev_modal and self.modal_lines and k in ("UP", "DOWN", "PGUP", "PGDN"))
                or (
                    not prev_modal
                    and (not prev_search or k == "ENTER")
                    and k in ("c", "ENTER", "F1", "e", "b", "B", "x", "r", "s", "k", "C", "P", "V", "T", "M")
                )
            ):
                self._capture_script_frame()
        self._capture_script_frame()
        return self.render_plain_lines()


def _parse_stream_keys(raw_text: str) -> list[str]:
    """Pipe/stdin test akışı için satır veya kaçış dizisi ayrıştırır."""
    keys: list[str] = []
    i = 0
    n = len(raw_text)
    while i < n:
        if raw_text[i : i + 3] == "\x1b[A":
            keys.append("UP")
            i += 3
        elif raw_text[i : i + 3] == "\x1b[B":
            keys.append("DOWN")
            i += 3
        elif raw_text[i : i + 4] == "\x1b[5~":
            keys.append("PGUP")
            i += 4
        elif raw_text[i : i + 4] == "\x1b[6~":
            keys.append("PGDN")
            i += 4
        elif raw_text[i : i + 3] == "\x1bOP":
            keys.append("F1")
            i += 3
        elif raw_text[i : i + 5] == "\x1b[11~":
            keys.append("F1")
            i += 5
        elif raw_text[i : i + 2] == "\r\n":
            keys.append("ENTER")
            i += 2
        elif raw_text[i] in ("\r", "\n"):
            keys.append("ENTER")
            i += 1
        elif raw_text[i] == "\x1b":
            keys.append("ESC")
            i += 1
        elif raw_text[i] == "\t":
            keys.append("TAB")
            i += 1
        elif raw_text[i] in ("\x08", "\x7f"):
            keys.append("BACKSPACE")
            i += 1
        else:
            keys.append(raw_text[i])
            i += 1
    return keys


def _decode_posix_key(read_ch: Callable[[int], str], has_more: Callable[[], bool] | None = None) -> str:
    ch = read_ch(1)
    if not ch:
        return "q"
    if ch in ("\r", "\n"):
        return "ENTER"
    if ch == "\t":
        return "TAB"
    if ch in ("\x08", "\x7f"):
        return "BACKSPACE"
    if ch == "\x03":
        return "q"
    if ch == "\x1b":
        if has_more is not None and not has_more():
            return "ESC"
        seq = read_ch(1)
        if not seq:
            return "ESC"
        if seq == "[":
            code = read_ch(1)
            if code == "A":
                return "UP"
            if code == "B":
                return "DOWN"
            if code in ("5", "6"):
                read_ch(1)
                return "PGUP" if code == "5" else "PGDN"
            if code == "1":
                rest = read_ch(2)
                if rest.startswith("1"):
                    return "F1"
        elif seq == "O":
            if read_ch(1) == "P":
                return "F1"
        return "ESC"
    return ch


def _run_posix_termios_fallback(tui: QtpTui, out: TextIO) -> int:
    dumb_term = os.environ.get("TERM", "").strip().lower() == "dumb"
    tui.use_color = not dumb_term
    try:
        import termios
        import tty

        in_stream = sys.stdin
        if in_stream is None or not hasattr(in_stream, "fileno"):
            raise OSError("stdin fd yok")
        fd = in_stream.fileno()
        old_attrs = termios.tcgetattr(fd)

        def _has_more() -> bool:
            try:
                import select

                r, _, _ = select.select([fd], [], [], 0.05)
                return bool(r)
            except Exception:
                return False

        try:
            tty.setcbreak(fd)
            while tui.running:
                ts = shutil.get_terminal_size((100, 30))
                tui.term_size = (max(40, ts.columns), max(14, ts.lines))
                lines = tui.render_ansi_lines() if tui.use_color else tui.render_plain_lines()
                if not dumb_term:
                    out.write("\x1b[H\x1b[2J")
                out.write("\n".join(lines) + "\n")
                out.flush()
                key = _decode_posix_key(in_stream.read, _has_more)
                if key:
                    tui.handle_key(key)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
        return tui.exit_code
    except Exception:
        tui.use_color = False
        while tui.running:
            ts = shutil.get_terminal_size((100, 30))
            tui.term_size = (max(40, ts.columns), max(14, ts.lines))
            out.write("\n".join(tui.render_plain_lines()) + "\n> ")
            out.flush()
            if sys.stdin is None:
                break
            raw_line = sys.stdin.readline()
            if not raw_line:
                break
            line_clean = raw_line.rstrip("\r\n")
            keys = _parse_stream_keys(line_clean) if line_clean else ["ENTER"]
            for k in keys:
                if not tui.running:
                    break
                tui.handle_key(k)
        return tui.exit_code


def run_tui(
    engine: QtpEngine,
    *,
    scripted_keys: Iterable[str] | None = None,
    out_stream: TextIO | None = None,
    verbose: int = 0,
    quiet: bool = False,
    initial_category: str | None = None,
    initial_query: str = "",
) -> int:
    """Etkileşimli veya betikli TUI döngüsünü çalıştırıp çıkış kodunu döndürür."""
    eff_verbose = max(int(verbose or 0), int(getattr(engine, "verbose", 0) or 0))
    eff_quiet = bool(quiet) and eff_verbose <= 0
    if eff_verbose > 0:
        engine.configure_verbosity(eff_verbose, eff_quiet)
        engine.emit_startup_diagnostics("tui")

    out = out_stream if out_stream is not None else sys.stdout
    tui = QtpTui(
        engine,
        initial_category=initial_category,
        initial_query=initial_query,
        quiet=eff_quiet,
    )

    if scripted_keys is not None:
        tui_logger.info("TUI başlatıldı (arka_uç=scripted, kategori=%s, sorgu=%r).", tui.category, tui.query)
        tui.run_scripted(scripted_keys)
        out.write("\n---\n".join(tui.recorded_frames) + "\n")
        out.flush()
        tui_logger.info("TUI sonlandırıldı (arka_uç=scripted, çıkış=%d).", tui.exit_code)
        return tui.exit_code

    if sys.stdin is not None and not sys.stdin.isatty():
        tui_logger.info("TUI başlatıldı (arka_uç=pipe, kategori=%s, sorgu=%r).", tui.category, tui.query)
        raw_in = sys.stdin.read()
        keys = _parse_stream_keys(raw_in) if raw_in else ["ESC"]
        tui.run_scripted(keys)
        out.write("\n---\n".join(tui.recorded_frames) + "\n")
        out.flush()
        tui_logger.info("TUI sonlandırıldı (arka_uç=pipe, çıkış=%d).", tui.exit_code)
        return tui.exit_code

    engine.start_watcher(on_reload=tui.apply_reload_event)
    try:
        if sys.platform == "win32":
            from qtp_app.tui._win_console import WinConsoleBackend

            tui_logger.info("TUI başlatıldı (arka_uç=WinConsoleBackend, kategori=%s, sorgu=%r).", tui.category, tui.query)
            backend = WinConsoleBackend(out)
            backend.enter()
            tui.use_color = backend.supports_ansi
            try:
                while tui.running:
                    tui.term_size = backend.size()
                    lines = tui.render_ansi_lines() if backend.supports_ansi else tui.render_plain_lines()
                    backend.render(lines)
                    key = backend.read_key()
                    if key:
                        tui.handle_key(key)
            finally:
                backend.leave()
            tui_logger.info("TUI sonlandırıldı (arka_uç=WinConsoleBackend, çıkış=%d).", tui.exit_code)
            return tui.exit_code

        try:
            import curses
        except ImportError:
            tui_logger.info("TUI başlatıldı (arka_uç=termios, kategori=%s, sorgu=%r).", tui.category, tui.query)
            return _run_posix_termios_fallback(tui, out)

        def _curses_loop(stdscr: Any) -> None:
            curses.curs_set(0)
            stdscr.keypad(True)
            while tui.running:
                max_y, max_x = stdscr.getmaxyx()
                tui.term_size = (max(40, max_x), max(14, max_y))
                stdscr.erase()
                for row_i, line in enumerate(tui.render_plain_lines()[: max_y - 1]):
                    stdscr.addnstr(row_i, 0, line, max_x - 1)
                stdscr.refresh()
                ch = stdscr.get_wch()
                if ch in ("\n", "\r", curses.KEY_ENTER):
                    tui.handle_key("ENTER")
                elif ch == curses.KEY_UP:
                    tui.handle_key("UP")
                elif ch == curses.KEY_DOWN:
                    tui.handle_key("DOWN")
                elif ch == curses.KEY_PPAGE:
                    tui.handle_key("PGUP")
                elif ch == curses.KEY_NPAGE:
                    tui.handle_key("PGDN")
                elif ch == curses.KEY_F1:
                    tui.handle_key("F1")
                elif ch in (curses.KEY_BACKSPACE, "\x08", "\x7f"):
                    tui.handle_key("BACKSPACE")
                elif ch == "\t":
                    tui.handle_key("TAB")
                elif ch == "\x1b":
                    tui.handle_key("ESC")
                elif isinstance(ch, str):
                    tui.handle_key(ch)

        try:
            tui_logger.info("TUI başlatıldı (arka_uç=curses, kategori=%s, sorgu=%r).", tui.category, tui.query)
            curses.wrapper(_curses_loop)
        except Exception:
            tui_logger.info("TUI curses geri dönüşü -> arka_uç=termios.")
            return _run_posix_termios_fallback(tui, out)
        tui_logger.info("TUI sonlandırıldı (arka_uç=curses, çıkış=%d).", tui.exit_code)
        return tui.exit_code
    finally:
        engine.stop_watcher()
