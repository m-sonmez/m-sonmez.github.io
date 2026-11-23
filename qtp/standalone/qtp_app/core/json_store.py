"""data.json, INI ↔ JSON dönüşümü ve tam yedekleme (qtp-tam-yedek-*.json) yönetimi."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from qtp_app.core.ini_parser import (
    DEFAULT_QTP_PROGRAM,
    IniParseError,
    atomic_write_bytes,
    build_qtp_ini,
    encode_qtp_ini,
    parse_qtp_ini,
    parse_qtp_ini_full,
    read_text_auto,
    write_qtp_ini,
)
from qtp_app.core.logging_setup import get_logger

STATE_FILENAME = ".qtp_state.json"
BACKUPS_DIRNAME = "backups"

logger = get_logger("json_store")


class JsonStoreError(ValueError):
    """Bozuk veya uyumsuz JSON/yedek verileri için tiplendirilmiş Türkçe hata."""


def normalize_record(raw: dict[str, Any], idx: int = 0) -> dict[str, Any]:
    """Kayıt sözlüğünü data.json / PWA şemasına göre standartlaştırır."""
    rec: dict[str, Any] = {
        "keys": str(raw.get("keys", raw.get("hotkey_prefix", ""))).strip(),
        "group": str(raw.get("group") or "Genel").strip() or "Genel",
        "text": str(raw.get("text", "")),
    }
    lbl = str(raw.get("label", "")).strip()
    if lbl:
        rec["label"] = lbl
    if raw.get("id"):
        rec["id"] = str(raw["id"])
    if "favorite" in raw:
        rec["favorite"] = bool(raw["favorite"])
    if "copyCount" in raw:
        try:
            rec["copyCount"] = int(raw["copyCount"])
        except (TypeError, ValueError):
            rec["copyCount"] = 0
    if "terminator" in raw:
        rec["terminator"] = str(raw["terminator"])
    return rec


def strip_for_data_json(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """data.json için temiz standart alanları döndürür (keys, group, label?, text)."""
    out: list[dict[str, Any]] = []
    for item in items:
        obj: dict[str, Any] = {
            "keys": str(item.get("keys", item.get("hotkey_prefix", ""))).strip(),
            "group": str(item.get("group") or "Genel").strip() or "Genel",
        }
        lbl = str(item.get("label", "")).strip()
        if lbl:
            obj["label"] = lbl
        obj["text"] = str(item.get("text", ""))
        out.append(obj)
    return out


def atomic_write_text(filepath: str | Path, text: str, encoding: str = "utf-8") -> None:
    atomic_write_bytes(filepath, text.encode(encoding))


def load_data_json(filepath: str | Path) -> list[dict[str, Any]]:
    """data.json dosyasını okur ve kayıt listesini döndürür."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"data.json dosyası bulunamadı: {path}")
    try:
        raw = json.loads(read_text_auto(path))
    except json.JSONDecodeError as exc:
        raise JsonStoreError(f"data.json çözümlenemedi: geçersiz JSON biçimi ({exc}).") from exc
    if not isinstance(raw, list):
        raise JsonStoreError("data.json biçimi geçersiz: kök eleman bir JSON dizisi ([...]) olmalıdır.")
    return [normalize_record(d, i) for i, d in enumerate(raw) if isinstance(d, dict)]


def save_data_json(filepath: str | Path, items: list[dict[str, Any]], *, create_bak: bool = False) -> Path:
    """Kayıt listesini standart data.json şemasıyla diske yazar."""
    path = Path(filepath)
    if create_bak and path.is_file():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    clean = strip_for_data_json(items)
    payload = json.dumps(clean, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(path, payload, encoding="utf-8")
    return path


def ini_to_json(ini_text: str) -> list[dict[str, Any]]:
    """INI metnini standart data.json uyumlu kayıt listesine çevirir."""
    parsed = parse_qtp_ini_full(ini_text)
    return parsed["items"]


def json_to_ini(
    items: list[dict[str, Any]],
    *,
    program: dict[str, Any] | None = None,
    extra_sections: list[dict[str, Any]] | None = None,
    encoding: str = "utf-16-le-bom",
    preserve_test_ini: bool = False,
) -> bytes:
    """Kayıt listesini kodlanmış QuickTextPaste.ini bayt dizisine çevirir."""
    clean = strip_for_data_json(items)
    ini_text = build_qtp_ini(
        clean,
        m_show_tree=1,
        include_program=True,
        program=program,
        extra_sections=extra_sections,
        preserve_test_ini=preserve_test_ini,
    )
    return encode_qtp_ini(ini_text, encoding=encoding)


def export_full_backup(
    items: list[dict[str, Any]],
    *,
    settings: dict[str, Any] | None = None,
    program: dict[str, Any] | None = None,
    extra_sections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Web PWA ile tam uyumlu qtp-pwa-backup v2 sözlüğü oluşturur."""
    return {
        "type": "qtp-pwa-backup",
        "version": 2,
        "exportedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "settings": settings or {},
        "program": program or {},
        "extraSections": extra_sections or [],
        "items": [normalize_record(it, i) if isinstance(it, dict) else it.to_dict(include_meta=True) for i, it in enumerate(items)],
    }


def write_full_backup_file(
    target: str | Path,
    items: list[dict[str, Any]],
    *,
    settings: dict[str, Any] | None = None,
    program: dict[str, Any] | None = None,
    extra_sections: list[dict[str, Any]] | None = None,
) -> Path:
    """qtp-tam-yedek-YYYY-MM-DD.json dosyasını diske yazar."""
    p = Path(target)
    if p.is_dir() or (not p.suffix):
        stamp = _dt.datetime.now().strftime("%Y-%m-%d")
        p = p / f"qtp-tam-yedek-{stamp}.json"
    payload = export_full_backup(
        items,
        settings=settings,
        program=program,
        extra_sections=extra_sections,
    )
    atomic_write_text(p, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def parse_any_content(content: str, filename: str = "") -> dict[str, Any]:
    """
    .ini, data.json veya qtp-tam-yedek-*.json içeriğini otomatik algılayıp ayrıştırır.
    Dönüş: {"kind": "ini"|"json"|"backup", "items": [...], "program": {...}, "extra_sections": [...], "settings": {...}|None}
    """
    lower = filename.lower()
    stripped = content.lstrip()
    first_line = stripped.splitlines()[0].strip() if stripped else ""
    looks_like_ini_header = bool(re.match(r"^\[[A-Za-z0-9_]+\]$", first_line))

    is_ini = lower.endswith(".ini") or (
        not lower.endswith(".json")
        and (
            looks_like_ini_header
            or "[list_text]" in content
            or "[Program]" in content
            or not stripped.startswith(("[", "{"))
        )
    )
    if is_ini:
        doc = parse_qtp_ini(content)
        return {
            "kind": "ini",
            "items": [it.to_dict(include_meta=False) for it in doc.items],
            "program": dict(doc.program),
            "extra_sections": list(doc.extra_sections),
            "settings": None,
            "document": doc,
        }

    try:
        raw = json.loads(content)
    except json.JSONDecodeError as exc:
        raise JsonStoreError(f"JSON dosyası ayrıştırılamadı: {exc}") from exc

    if isinstance(raw, dict) and raw.get("type") == "qtp-pwa-backup" and isinstance(raw.get("items"), list):
        items = [normalize_record(d, i) for i, d in enumerate(raw["items"]) if isinstance(d, dict)]
        settings = raw.get("settings") if isinstance(raw.get("settings"), dict) else {}
        program = raw.get("program") or settings.get("qtpPrefs") or {}
        extra_sections = raw.get("extraSections") or raw.get("extra_sections") or []
        return {
            "kind": "backup",
            "items": items,
            "program": {str(k): str(v) for k, v in program.items()} if isinstance(program, dict) else {},
            "extra_sections": extra_sections if isinstance(extra_sections, list) else [],
            "settings": settings,
            "document": None,
        }

    if isinstance(raw, list):
        items = [normalize_record(d, i) for i, d in enumerate(raw) if isinstance(d, dict)]
        return {
            "kind": "json",
            "items": items,
            "program": {},
            "extra_sections": [],
            "settings": None,
            "document": None,
        }

    raise JsonStoreError(
        "Desteklenmeyen dosya biçimi: Geçerli INI, JSON listesi ([...]) veya QTP Tam Yedek bekleniyor."
    )


def _items_digest(items: list[dict[str, Any]]) -> str:
    canonical = json.dumps(strip_for_data_json(items), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_state(
    work_dir: str | Path,
    ini_path: Path | None = None,
    *,
    prefer_source: str | None = None,
) -> dict[str, Any]:
    """Çalışma dizinindeki QuickTextPaste.ini + data.json + .qtp_state.json durumunu yükler."""
    wd = Path(work_dir).resolve()
    data_json_path = wd / "data.json"
    ini_file = Path(ini_path).resolve() if ini_path else (wd / "QuickTextPaste.ini")
    state_path = wd / STATE_FILENAME

    state_meta: dict[str, Any] = {}
    if state_path.is_file():
        try:
            state_meta = json.loads(read_text_auto(state_path))
        except Exception:
            state_meta = {}

    items: list[dict[str, Any]] = []
    program: dict[str, str] = dict(state_meta.get("program") or {})
    extra_sections: list[dict[str, Any]] = list(state_meta.get("extraSections") or [])
    qtp_prefs: dict[str, Any] = dict(state_meta.get("qtpPrefs") or {})
    favorites_meta: dict[str, dict[str, Any]] = dict(state_meta.get("itemMeta") or {})
    source = "empty"
    terminators: dict[int, str] = {}

    ini_mtime = ini_file.stat().st_mtime if ini_file.is_file() else 0.0
    json_mtime = data_json_path.stat().st_mtime if data_json_path.is_file() else 0.0

    json_items: list[dict[str, Any]] = []
    json_valid = False
    if data_json_path.is_file():
        try:
            json_items = load_data_json(data_json_path)
            json_valid = True
        except Exception as exc:
            logger.warning("data.json okunamadı (%s): %s", data_json_path, exc)
            json_valid = False

    parsed_doc = None
    if ini_file.is_file():
        try:
            parsed_doc = parse_qtp_ini(read_text_auto(ini_file))
        except IniParseError as exc:
            logger.error("QuickTextPaste.ini ayrıştırma hatası (%s): %s", ini_file, exc)
            parsed_doc = None

    use_ini = False
    if prefer_source == "ini" and parsed_doc is not None:
        use_ini = True
    elif prefer_source == "json" and json_valid:
        use_ini = False
    elif parsed_doc is not None and not json_valid:
        use_ini = True
    elif parsed_doc is not None and json_valid:
        if ini_mtime > json_mtime + 2.0:
            last_digest = state_meta.get("itemsDigest")
            ini_items = [it.to_dict(include_meta=False) for it in parsed_doc.items]
            if not last_digest:
                use_ini = True
            else:
                ini_digest = _items_digest(ini_items)
                json_digest = _items_digest(json_items)
                if ini_digest != last_digest and json_digest == last_digest:
                    use_ini = True

    if use_ini and parsed_doc is not None:
        items = [it.to_dict(include_meta=False) for it in parsed_doc.items]
        for idx, it in enumerate(parsed_doc.items):
            terminators[idx] = it.terminator
        if parsed_doc.program:
            program.update(parsed_doc.program)
        if parsed_doc.extra_sections:
            extra_sections = parsed_doc.extra_sections
        source = "QuickTextPaste.ini"
    elif json_valid:
        items = json_items
        source = "data.json"
        if parsed_doc is not None:
            if not program and parsed_doc.program:
                program = dict(parsed_doc.program)
            if not extra_sections and parsed_doc.extra_sections:
                extra_sections = list(parsed_doc.extra_sections)
            for idx, it in enumerate(parsed_doc.items):
                if idx < len(items) and items[idx].get("text") == it.text:
                    terminators[idx] = it.terminator

    for idx, it in enumerate(items):
        if idx in terminators:
            it["terminator"] = terminators[idx]
        else:
            it.setdefault("terminator", "<E<N<D|")
        key = f"{it.get('group', '')}||{it.get('text', '')}"
        meta = favorites_meta.get(key)
        if meta:
            if "favorite" not in it and "favorite" in meta:
                it["favorite"] = bool(meta["favorite"])
            if "copyCount" not in it and "copyCount" in meta:
                it["copyCount"] = int(meta["copyCount"] or 0)
            if "id" not in it and meta.get("id"):
                it["id"] = str(meta["id"])
        if not it.get("id"):
            it["id"] = f"qtp_{idx:03d}"

    return {
        "items": items,
        "program": program,
        "extraSections": extra_sections,
        "qtpPrefs": qtp_prefs,
        "source": source,
        "iniMtime": ini_mtime,
        "jsonMtime": json_mtime,
    }


def create_backup(
    work_dir: str | Path,
    reason: str = "manual",
    max_keep: int = 15,
) -> dict[str, Any] | None:
    """Mevcut data.json, QuickTextPaste.ini ve .qtp_state.json dosyalarını yedekler."""
    wd = Path(work_dir).resolve()
    backups_root = wd / BACKUPS_DIRNAME
    backups_root.mkdir(parents=True, exist_ok=True)

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    safe_reason = re.sub(r"[^a-zA-Z0-9_-]", "", reason)[:20] or "bak"
    backup_id = f"{stamp}_{safe_reason}"
    dest_dir = backups_root / backup_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for fname in ("data.json", "QuickTextPaste.ini", STATE_FILENAME):
        src = wd / fname
        if src.is_file():
            shutil.copy2(src, dest_dir / fname)
            copied.append(fname)

    if not copied:
        shutil.rmtree(dest_dir, ignore_errors=True)
        return None

    item_count = 0
    if (dest_dir / "data.json").is_file():
        try:
            item_count = len(json.loads(read_text_auto(dest_dir / "data.json")))
        except Exception:
            pass

    meta = {
        "id": backup_id,
        "createdAt": _dt.datetime.now().isoformat(timespec="seconds"),
        "reason": reason,
        "files": copied,
        "count": item_count,
    }
    atomic_write_text(dest_dir / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

    existing = sorted(
        [d for d in backups_root.iterdir() if d.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    )
    for old_dir in existing[max(1, max_keep):]:
        shutil.rmtree(old_dir, ignore_errors=True)

    return meta


def list_backups(work_dir: str | Path) -> list[dict[str, Any]]:
    wd = Path(work_dir).resolve()
    backups_root = wd / BACKUPS_DIRNAME
    if not backups_root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for d in sorted([p for p in backups_root.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True):
        meta_file = d / "meta.json"
        if meta_file.is_file():
            try:
                out.append(json.loads(meta_file.read_text(encoding="utf-8")))
                continue
            except Exception:
                pass
        out.append({"id": d.name, "createdAt": d.name, "reason": "unknown", "files": [], "count": 0})
    return out


def restore_backup(work_dir: str | Path, backup_id: str) -> dict[str, Any]:
    wd = Path(work_dir).resolve()
    safe_id = Path(backup_id).name
    src_dir = wd / BACKUPS_DIRNAME / safe_id
    if not src_dir.is_dir():
        raise FileNotFoundError(f"Yedek bulunamadı: {safe_id}")

    create_backup(wd, reason="pre_restore")
    for fname in ("data.json", "QuickTextPaste.ini", STATE_FILENAME):
        src = src_dir / fname
        if src.is_file():
            shutil.copy2(src, wd / fname)
    return {"ok": True, "restored": safe_id, "state": load_state(wd)}


def save_state(
    work_dir: str | Path,
    items: list[dict[str, Any]],
    *,
    program: dict[str, Any] | None = None,
    extra_sections: list[dict[str, Any]] | None = None,
    qtp_prefs: dict[str, Any] | None = None,
    encoding: str = "utf-16-le-bom",
    create_backup_flag: bool = True,
    backup_reason: str = "save",
    max_backups: int = 15,
    ini_path: Path | None = None,
    update_ini: bool = True,
) -> dict[str, Any]:
    """Kayıtları hem data.json hem de QuickTextPaste.ini (.bak yedeğiyle) üzerine atomik yazar."""
    wd = Path(work_dir).resolve()
    wd.mkdir(parents=True, exist_ok=True)
    target_ini = Path(ini_path).resolve() if ini_path else (wd / "QuickTextPaste.ini")

    if create_backup_flag and ((wd / "data.json").is_file() or target_ini.is_file()):
        create_backup(wd, reason=backup_reason, max_keep=max_backups)

    clean_json_items = strip_for_data_json(items)
    save_data_json(wd / "data.json", clean_json_items)

    merged_prog: dict[str, str] = {}
    if isinstance(program, dict):
        merged_prog.update({str(k): str(v) for k, v in program.items() if v is not None})
    if isinstance(qtp_prefs, dict):
        for k in ("m_show_tree", "lng", "start_tray", "WinRC"):
            if k in qtp_prefs and qtp_prefs[k] is not None:
                merged_prog[k] = str(qtp_prefs[k])

    m_show_tree_val = 1
    if "m_show_tree" in merged_prog:
        try:
            m_show_tree_val = 1 if int(merged_prog["m_show_tree"]) else 0
        except ValueError:
            m_show_tree_val = 1

    if update_ini:
        ini_text = build_qtp_ini(
            items,
            m_show_tree=m_show_tree_val,
            include_program=True,
            program=merged_prog,
            extra_sections=extra_sections,
            tr_prefs=str(merged_prog.get("lng", "21")) == "21",
            keep_winrc=bool(merged_prog.get("WinRC", DEFAULT_QTP_PROGRAM["WinRC"])),
        )
        write_qtp_ini(target_ini, ini_text, encoding=encoding, create_bak=True)

    item_meta: dict[str, dict[str, Any]] = {}
    for it in items:
        key = f"{it.get('group') or 'Genel'}||{it.get('text', '')}"
        meta_entry: dict[str, Any] = {}
        if it.get("id"):
            meta_entry["id"] = str(it["id"])
        if it.get("favorite"):
            meta_entry["favorite"] = True
        if it.get("copyCount"):
            meta_entry["copyCount"] = int(it["copyCount"])
        if meta_entry:
            item_meta[key] = meta_entry

    state_payload = {
        "updatedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "savedCount": len(clean_json_items),
        "itemsDigest": _items_digest(clean_json_items),
        "program": merged_prog,
        "extraSections": extra_sections or [],
        "qtpPrefs": qtp_prefs or {},
        "itemMeta": item_meta,
    }
    atomic_write_text(
        wd / STATE_FILENAME,
        json.dumps(state_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("Durum kaydedildi: %d kayıt (%s)", len(clean_json_items), target_ini)
    return {"ok": True, "count": len(clean_json_items), "ini_path": str(target_ini)}
