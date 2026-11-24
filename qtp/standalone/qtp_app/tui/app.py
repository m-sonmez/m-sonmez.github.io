"""Çapraz platform etkileşimli terminal arayüzü (--tui): GUI ile birebir işlem ve kısayol eşitliği."""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import unicodedata
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


def _char_display_width(ch: str) -> int:
    if unicodedata.combining(ch) or unicodedata.category(ch) in ("Mn", "Me", "Cf"):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F") or (0x1F300 <= ord(ch) <= 0x1FAFF):
        return 2
    return 1


def display_width(text: str) -> int:
    """Metnin uçbirim görsel sütun genişliğini (geniş emoji/CJK = 2, birleştirme = 0) döndürür."""
    return sum(_char_display_width(ch) for ch in text)


def clip_to_width(text: str, width: int, ellipsis: str = "…") -> str:
    """Metni görsel sütun genişliğine göre kırpar ve taşma varsa sonuna '…' ekler."""
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return text
    el_w = display_width(ellipsis)
    if width <= el_w:
        return ellipsis if el_w == width else ""
    limit = width - el_w
    out: list[str] = []
    used = 0
    for ch in text:
        cw = _char_display_width(ch)
        if used + cw > limit:
            break
        out.append(ch)
        used += cw
    return "".join(out) + ellipsis


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
        if getattr(engine, "startup_warning", None):
            self.status_message = str(engine.startup_warning)
        elif self.quiet:
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
        self.prompt_mode: str = ""
        self.prompt_buffer: str = ""
        self.prompt_target: str = ""
        self.checked_keys: set[str] = set()
        self.only_favorites: bool = False
        self.only_notes: bool = False
        self.group_filter: str = ""
        self.sort_by: str = str(engine.settings.get("sort_by", "order") or "order")
        self.strip_emoji: bool = bool(engine.settings.get("strip_emoji", False))
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
            list_res = self.engine.op_list_items(
                category=self.category,
                query=self.query,
                only_favorites=self.only_favorites,
                only_notes=self.only_notes,
                group=self.group_filter,
                sort_by=self.sort_by,
            )
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
            inner_w = max(40, width)
            lines: list[str] = []

            search_state = "[YAZIYOR]" if self.search_mode else "[/ Ara]"
            lines.append(
                clip_to_width(
                    f"QTP v{__version__} | Mod: TUI | Ara: \"{self.query}\" {search_state} | Kayıt: {len(self._visible_items)}/{len(self.engine.items)}",
                    inner_w,
                )
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
            full_cat_line = "Kategoriler: " + " | ".join(pills)
            if inner_w < 100 or display_width(full_cat_line) > inner_w:
                compact_pills: list[str] = []
                for cat in self._categories_cache:
                    code = cat["code"]
                    cnt = cat["count"]
                    short = "Tümü" if code == "ALL" else code
                    if code == self.category:
                        compact_pills.append(f"[{short}({cnt})]")
                    else:
                        compact_pills.append(f"{short}({cnt})")
                cat_line = clip_to_width("Kategoriler: " + " ".join(compact_pills), inner_w)
            else:
                cat_line = full_cat_line
            lines.append(cat_line)
            lines.append("-" * min(inner_w, 96))

            body_rows = max(5, height - 6)
            if self.modal_lines:
                vis_rows = max(1, body_rows - 1)
                max_scroll = max(0, len(self.modal_lines) - vis_rows)
                self.modal_scroll = max(0, min(self.modal_scroll, max_scroll))
                if max_scroll > 0:
                    lines.append(
                        clip_to_width(
                            f"=== {self.modal_title} [{self.modal_scroll + 1}/{len(self.modal_lines)}] (↑↓ Kaydır · Kapatmak için Esc/q) ===",
                            inner_w,
                        )
                    )
                else:
                    lines.append(clip_to_width(f"=== {self.modal_title} (Kapatmak için Esc/q) ===", inner_w))
                for mline in self.modal_lines[self.modal_scroll : self.modal_scroll + vis_rows]:
                    lines.append(clip_to_width(mline, inner_w))
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
                    rk = str(item.get("raw_key", ""))
                    keys = str(item.get("keys", ""))
                    badge = keys.rsplit("+", 1)[-1].upper() if "+" in keys else (keys.upper() or "•")
                    snippet = str(item.get("text", "")).replace("\r\n", " ").replace("\n", " ")
                    chk_pfx = "[x] " if rk in self.checked_keys else ""
                    fav_pfx = "★ " if item.get("favorite") else ""
                    row_txt = f"{pointer} {abs_idx + 1:>3}. {chk_pfx}{fav_pfx}[{badge}] {snippet}"
                    lines.append(clip_to_width(row_txt, inner_w))
                if not slice_items:
                    lines.append(clip_to_width("  (Eşleşen hazır cevap bulunamadı)", inner_w))
                while len(lines) < 3 + body_rows:
                    lines.append("")

            lines.append("-" * min(inner_w, 96))
            if self.prompt_mode == "add":
                status_line = f"Yeni Cevap (⏎ Kaydet · Esc İptal): {self.prompt_buffer}"
            elif self.prompt_mode == "edit":
                status_line = f"Düzenle [{self.prompt_target}] (⏎ Kaydet · Esc İptal): {self.prompt_buffer}"
            elif self.prompt_mode == "delete":
                status_line = f"Sil [{self.prompt_target}]? (⏎/e Onayla · Esc İptal)"
            elif self.prompt_mode == "bulk_prefix":
                status_line = f"Toplu Önek ({len(self.checked_keys)} kayıt) (⏎ Uygula · Esc İptal): {self.prompt_buffer}"
            elif self.prompt_mode == "bulk_delete":
                status_line = f"Seçili {len(self.checked_keys)} kayıt silinsin mi? (⏎/e Onayla · Esc İptal)"
            elif self.prompt_mode == "rename_group":
                status_line = f"Grubu Yeniden Adlandır [{self.prompt_target}] → (⏎ Uygula · Esc İptal): {self.prompt_buffer}"
            elif self.prompt_mode == "delete_group":
                status_line = f"Grup silinsin mi [{self.prompt_target}]? (⏎/e Onayla · Esc İptal)"
            else:
                status_line = f"Durum: {self.status_message}"
            lines.append(clip_to_width(status_line, inner_w))
            lines.append(clip_to_width(TUI_FOOTER_HINTS, inner_w))
            return [clip_to_width(ln, inner_w) for ln in lines]

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
                    "=== Kurulum ve Sistem Gereksinimleri ===\n\n" + res.data.get("kurulum", ""),
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
            return self._record_result(
                self.engine.op_list_items(
                    category=self.category,
                    query=self.query,
                    only_favorites=self.only_favorites,
                    only_notes=self.only_notes,
                    group=self.group_filter,
                    sort_by=self.sort_by,
                )
            )
        if op_id == "search":
            self.query = arg
            self._refresh_view_data()
            return self._record_result(
                self.engine.op_search(
                    arg,
                    category=self.category,
                    only_favorites=self.only_favorites,
                    only_notes=self.only_notes,
                    group=self.group_filter,
                    sort_by=self.sort_by,
                )
            )
        if op_id == "show_ini":
            res = self.engine.op_show_ini(target)
            if res.ok:
                self.modal_title = f"INI Kaydı ({res.data['raw_key']})"
                self.modal_lines = str(res.data["preview"]).splitlines()
            return self._record_result(res)
        if op_id == "copy":
            res = self.engine.op_copy(target, strip_emoji=self.strip_emoji if extra == "" else bool(extra))
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "paste":
            res = self.engine.op_paste(target, strip_emoji=self.strip_emoji if extra == "" else bool(extra))
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "export_ini":
            raw_keys = [k.strip() for k in extra.split(",") if k.strip()] if extra else None
            return self._record_result(
                self.engine.op_export_ini(arg or (self.engine.work_dir / "QuickTextPaste_export.ini"), raw_keys=raw_keys)
            )
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
        if op_id == "add_item":
            payload: dict[str, Any] = {}
            if extra and extra.lstrip().startswith("{"):
                try:
                    raw_p = json.loads(extra)
                    if isinstance(raw_p, dict):
                        payload = raw_p
                except Exception:
                    payload = {}
            res = self.engine.op_add_item(
                arg,
                keys=str(payload.get("keys", extra if not payload else "")),
                group=str(payload.get("group", "Genel")),
                label=str(payload.get("label", "")),
                terminator=str(payload.get("terminator", "<E<N<D|")),
                favorite=bool(payload.get("favorite", False)),
            )
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "update_item":
            payload = {}
            text_arg: str | None = extra if extra != "" else None
            if extra and extra.lstrip().startswith("{"):
                try:
                    raw_p = json.loads(extra)
                    if isinstance(raw_p, dict):
                        payload = raw_p
                        text_arg = payload.get("text")
                except Exception:
                    payload = {}
            res = self.engine.op_update_item(
                target,
                keys=payload.get("keys"),
                group=payload.get("group"),
                label=payload.get("label"),
                text=text_arg,
                terminator=payload.get("terminator"),
                favorite=payload.get("favorite"),
            )
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "delete_item":
            res = self.engine.op_delete_item(target)
            self.checked_keys.discard(target)
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "save_all":
            return self._record_result(self.engine.op_save_all())
        if op_id == "duplicate_item":
            res = self.engine.op_duplicate_item(target)
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "move_item":
            if arg in ("up", "down") and not extra:
                mv_target = self.current_raw_key()
                mv_dir = arg
            else:
                mv_target = target
                mv_dir = extra or "up"
            res = self.engine.op_move_item(mv_target, direction=mv_dir)
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "toggle_favorite":
            res = self.engine.op_toggle_favorite(target)
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "bulk_edit":
            b_targets = arg or ",".join(sorted(self.checked_keys))
            b_payload: dict[str, Any] = {}
            if extra and extra.lstrip().startswith("{"):
                try:
                    parsed = json.loads(extra)
                    if isinstance(parsed, dict):
                        b_payload = parsed
                except Exception:
                    b_payload = {}
            res = self.engine.op_bulk_edit(
                b_targets,
                keys=b_payload.get("keys"),
                group=b_payload.get("group"),
                find=b_payload.get("find"),
                replace=str(b_payload.get("replace", "") or ""),
                ignore_case=bool(b_payload.get("ignore_case", False)),
                prefix=str(b_payload.get("prefix", extra if not b_payload else "") or ""),
                suffix=str(b_payload.get("suffix", "") or ""),
                strip_emojis=bool(b_payload.get("strip_emojis", False)),
                add_emoji=str(b_payload.get("add_emoji", "") or ""),
                favorite_action=str(b_payload.get("favorite_action", "keep") or "keep"),
            )
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "bulk_delete":
            b_targets = arg or ",".join(sorted(self.checked_keys))
            res = self.engine.op_bulk_delete(b_targets)
            if res.ok:
                for dk in res.data.get("deleted_keys", []):
                    self.checked_keys.discard(dk)
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "rename_group":
            res = self.engine.op_rename_group(arg, extra)
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "delete_group":
            res = self.engine.op_delete_group(arg)
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "undo":
            res = self.engine.op_undo()
            self._refresh_view_data()
            return self._record_result(res)
        if op_id == "redo":
            res = self.engine.op_redo()
            self._refresh_view_data()
            return self._record_result(res)

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

        if self.prompt_mode:
            if key == "ESC":
                self.prompt_mode = ""
                self.prompt_buffer = ""
                self.prompt_target = ""
                return
            if self.prompt_mode == "delete":
                if key in ("ENTER", "e", "E", "y", "Y"):
                    tgt = self.prompt_target
                    self.prompt_mode = ""
                    self.prompt_target = ""
                    self.execute_operation("delete_item", tgt)
                return
            if self.prompt_mode == "bulk_delete":
                if key in ("ENTER", "e", "E", "y", "Y"):
                    self.prompt_mode = ""
                    self.prompt_target = ""
                    self.execute_operation("bulk_delete")
                return
            if self.prompt_mode == "delete_group":
                if key in ("ENTER", "e", "E", "y", "Y"):
                    grp = self.prompt_target
                    self.prompt_mode = ""
                    self.prompt_target = ""
                    self.execute_operation("delete_group", grp)
                return
            if key == "ENTER":
                mode_now = self.prompt_mode
                buf_now = self.prompt_buffer
                tgt_now = self.prompt_target
                self.prompt_mode = ""
                self.prompt_buffer = ""
                self.prompt_target = ""
                if mode_now == "add":
                    self.execute_operation("add_item", buf_now)
                elif mode_now == "edit":
                    self.execute_operation("update_item", tgt_now, buf_now)
                elif mode_now == "bulk_prefix":
                    self.execute_operation("bulk_edit", "", json.dumps({"prefix": buf_now}, ensure_ascii=False))
                elif mode_now == "rename_group":
                    self.execute_operation("rename_group", tgt_now, buf_now)
                return
            if key == "BACKSPACE":
                self.prompt_buffer = self.prompt_buffer[:-1]
                return
            if len(key) == 1 and key.isprintable():
                self.prompt_buffer += key
                return
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
        elif key == "a":
            self.prompt_mode = "add"
            self.prompt_buffer = ""
            self.prompt_target = ""
        elif key == "E":
            cur = self.current_item()
            if cur is not None:
                self.prompt_mode = "edit"
                self.prompt_target = self.current_raw_key()
                self.prompt_buffer = str(cur.get("text", ""))
        elif key == "d":
            cur = self.current_item()
            if cur is not None:
                self.prompt_mode = "delete"
                self.prompt_target = self.current_raw_key()
                self.prompt_buffer = ""
        elif key == " ":
            rk = self.current_raw_key()
            if rk:
                if rk in self.checked_keys:
                    self.checked_keys.remove(rk)
                else:
                    self.checked_keys.add(rk)
                self.status_message = f"{len(self.checked_keys)} kayıt seçili"
        elif key == "w":
            self.execute_operation("save_all")
        elif key == "D":
            self.execute_operation("duplicate_item")
        elif key == "K":
            self.execute_operation("move_item", self.current_raw_key(), "up")
        elif key == "J":
            self.execute_operation("move_item", self.current_raw_key(), "down")
        elif key == "f":
            self.execute_operation("toggle_favorite")
        elif key == "F":
            self.only_favorites = not self.only_favorites
            self._refresh_view_data()
            self.status_message = "Yalnızca favoriler" if self.only_favorites else "Tüm kayıtlar"
        elif key == "N":
            self.only_notes = not self.only_notes
            self._refresh_view_data()
            self.status_message = "Yalnızca notlar" if self.only_notes else "Tüm kayıtlar"
        elif key == "m":
            self.strip_emoji = not self.strip_emoji
            self.engine.op_set_setting("strip_emoji", self.strip_emoji)
            self.status_message = "Emojisiz kopyalama etkin" if self.strip_emoji else "Emojili kopyalama etkin"
        elif key == "U":
            if self.checked_keys:
                self.prompt_mode = "bulk_prefix"
                self.prompt_buffer = ""
                self.prompt_target = ""
            else:
                self.execute_operation("bulk_edit", "")
        elif key == "X":
            if self.checked_keys:
                self.prompt_mode = "bulk_delete"
                self.prompt_buffer = ""
                self.prompt_target = ""
            else:
                self.execute_operation("bulk_delete", "")
        elif key == "g":
            cur = self.current_item()
            if cur is not None:
                self.prompt_mode = "rename_group"
                self.prompt_target = str(cur.get("group") or "Genel")
                self.prompt_buffer = self.prompt_target
        elif key == "G":
            cur = self.current_item()
            if cur is not None:
                self.prompt_mode = "delete_group"
                self.prompt_target = str(cur.get("group") or "Genel")
                self.prompt_buffer = ""
        elif key == "u":
            self.execute_operation("undo")
        elif key == "y":
            self.execute_operation("redo")
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
                    and k in ("c", "ENTER", "F1", "e", "b", "B", "x", "r", "s", "k", "C", "P", "V", "T", "M", "a", "E", "d")
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

        os.environ.setdefault("ESCDELAY", "25")

        def _curses_loop(stdscr: Any) -> None:
            curses.curs_set(0)
            stdscr.keypad(True)
            while tui.running:
                max_y, max_x = stdscr.getmaxyx()
                if max_x <= 1 or max_y <= 1:
                    continue
                tui.term_size = (max(40, max_x), max(14, max_y))
                stdscr.erase()
                avail_cols = max(1, max_x - 1)
                for row_i, line in enumerate(tui.render_plain_lines()[: max_y - 1]):
                    clipped = clip_to_width(line, avail_cols)
                    stdscr.addnstr(row_i, 0, clipped, len(clipped))
                stdscr.refresh()
                ch = stdscr.get_wch()
                if ch == getattr(curses, "KEY_RESIZE", -1):
                    continue
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
