"""Arayüzden bağımsız (Qt-free) QTP çekirdek motoru — --gui, --tui, --cli ve --web için tek kaynak."""

from __future__ import annotations

import copy
import importlib.resources
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from qtp_app import __build_date__, __display_name__, __version__
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
from qtp_app.core.logging_setup import get_logger, setup_logging
from qtp_app.core.paster import copy_to_clipboard, paste_into_active_app
from qtp_app.core.settings import (
    DEFAULT_SETTINGS,
    SETTINGS_FILENAME,
    SettingValidationError,
    get_app_dir,
    get_setting_value,
    is_dir_writable,
    load_settings,
    resolve_config_dir,
    resolve_data_path,
    save_settings,
    set_setting_value,
)
from qtp_app.ui.search import FuzzyMatcher

CATEGORY_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("ALL", "Tümü", ""),
    ("A", "A · İş Ortağı", "L-Win+A"),
    ("Z", "Z · Kurye", "L-Win+Z"),
    ("X", "X · Canlı Yardım", "L-Win+X"),
    ("Q", "Q · Turkcell", "L-Win+Q"),
)

FIRST_RUN_TOAST = "QTP hazır. Win+Z / Win+A / Win+X / Win+Q"


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


def get_bundled_default_path(filename: str) -> Path:
    """Paket içi varsayılan varlık (QuickTextPaste.ini / data.json) yolunu döndürür."""
    try:
        pkg_root = Path(str(importlib.resources.files("qtp_app")))
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
    return Path(__file__).resolve().parent.parent.parent / filename


def get_bundled_docs_dir() -> Path:
    """Gömülü Türkçe dokümantasyon klasörünü döndürür."""
    try:
        pkg_root = Path(str(importlib.resources.files("qtp_app")))
        for candidate in (pkg_root / "docs", pkg_root.parent / "docs"):
            if candidate.is_dir():
                return candidate
    except Exception:
        pass
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_docs = Path(getattr(sys, "_MEIPASS")) / "docs"
        if meipass_docs.is_dir():
            return meipass_docs
    return Path(__file__).resolve().parent.parent.parent / "docs"


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
        clipboard_fn: Callable[[str], bool] | None = None,
        paste_fn: Callable[..., Any] | None = None,
    ):
        requested_dir = Path(work_dir).resolve() if work_dir else get_app_dir()
        if ephemeral:
            # Salt-okunur / bilgi komutları (--selftest, --version, --modes) diskte yan etki bırakmaz
            self.config_dir = requested_dir
            self.portable = True
            self.work_dir = requested_dir
            self.first_run = False
            self.logger = get_logger("engine")
            self.settings = copy.deepcopy(DEFAULT_SETTINGS)
            self.settings_path = self.config_dir / SETTINGS_FILENAME
            self.settings_warning = None
        else:
            self.config_dir, self.portable = resolve_config_dir(requested_dir)
            # Veri dosyaları yazılabilir çalışma dizininde yoksa config_dir üzerinde tutulur
            self.work_dir = requested_dir if is_dir_writable(requested_dir) else self.config_dir
            self.first_run = not (self.config_dir / SETTINGS_FILENAME).is_file()

            setup_logging(self.config_dir, level="info")
            self.logger = get_logger("engine")

            self.settings, self.settings_path, self.settings_warning = load_settings(self.config_dir)
            setup_logging(self.config_dir, level=str(self.settings.get("log_level", "info")))

        self._matcher = FuzzyMatcher()
        self._clipboard_fn = clipboard_fn
        self._paste_fn = paste_fn
        self.items: list[dict[str, Any]] = []
        self.program_meta: dict[str, str] = {}
        self.extra_sections: list[dict[str, Any]] = []
        self.ini_path: Path = resolve_data_path(self.settings, self.work_dir)

        self._seed_defaults_if_empty(seed_defaults and not ephemeral)
        self.reload_data()

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

    def reload_data(self) -> OperationResult:
        """Diskten QuickTextPaste.ini / data.json verisini yeniden yükler."""
        self.ini_path = resolve_data_path(self.settings, self.work_dir)
        try:
            if self.ini_path.is_file() or (self.work_dir / "data.json").is_file():
                state = load_state(self.work_dir, ini_path=self.ini_path)
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
                    it.to_dict(include_meta=False) | {"terminator": it.terminator, "raw_key": it.raw_key}
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

    def op_help(self, help_text: str = "") -> OperationResult:
        return OperationResult(
            ok=True,
            exit_code=0,
            message=help_text or read_doc_text("KULLANIM.md"),
            data={
                "usage": help_text,
                "kullanim": read_doc_text("KULLANIM.md"),
                "kisayollar": read_doc_text("KISAYOLLAR.md"),
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

            # Geçici klasör içinde sıfır yan etkili dosya I/O gidiş-dönüş doğrulaması
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
                        it.to_dict(include_meta=False) | {"terminator": it.terminator, "raw_key": it.raw_key}
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
                    # Qt olmadan da çekirdek INI testi geçer
                    pass
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
            it.to_dict(include_meta=False) | {"terminator": it.terminator}
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
        # 1. Dosya yolundan geri yükleme (tam yedek veya JSON/INI)
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
            msg = f"Yedek geri yüklendi ✔ ({len(merged)} kayıt, mod={mode})"
            self.logger.info(msg)
            return OperationResult(ok=True, exit_code=0, message=msg, data={"count": len(merged), "mode": mode})

        # 2. backups/ altındaki yedek kimliğinden geri yükleme
        if "/" in raw_str or "\\" in raw_str or raw_str.endswith((".json", ".ini")):
            err = f"Yedek bulunamadı: {raw_str}"
            return OperationResult(ok=False, exit_code=1, message=err, error=err)

        try:
            res = restore_backup(self.work_dir, raw_str)
            st = res["state"]
            self.items = st["items"]
            self.program_meta = st.get("program") or {}
            self.extra_sections = st.get("extraSections") or []
            for idx, it in enumerate(self.items):
                it.setdefault("raw_key", f"text_{idx:03d}")
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
            save_settings(updated, self.settings_path)
            self.settings = updated
            setup_logging(self.config_dir, level=str(self.settings.get("log_level", "info")))
            return OperationResult(
                ok=True,
                exit_code=0,
                message="Ayarlar kaydedildi ✔",
                data={"key": key, "value": get_setting_value(self.settings, key)},
            )
        except SettingValidationError as exc:
            err = str(exc)
            return OperationResult(ok=False, exit_code=2, message=err, error=err)
