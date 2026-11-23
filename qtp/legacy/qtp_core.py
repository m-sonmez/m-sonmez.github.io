#!/usr/bin/env python3
"""
QuickTextPaste & Hazır Cevaplar Çekirdek Modülü (qtp_core.py)
- Tam Unicode QuickTextPaste.ini <-> data.json çift yönlü dönüştürücü
- Tüm [Program] ayarlarını ve ek INI bölümlerini kayıpsız koruma
- Otomatik yedekleme/geri yükleme ve Word (.docx/.doc) dışa aktarma
- QuickTextPaste (Windows) kurulum, algılama, başlatma ve yeniden yükleme yönetimi
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import html as _html
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable


QTP_DOWNLOAD_URL_X64 = "https://www.softwareok.com/Download/QuickTextPaste_x64_Portable.zip"
QTP_DOWNLOAD_URL_X86 = "https://www.softwareok.com/Download/QuickTextPaste_Portable.zip"
QTP_HOMEPAGE_URL = "https://www.softwareok.com/?Download=QuickTextPaste"

DEFAULT_QTP_PROGRAM: dict[str, str] = {
    "m_show_tree": "1",
    "lng": "21",
    "start_tray": "1",
    "WinRC": "2399;17;3368;1335;1;x,y,w,h,SW",
}

QTP_EXE_CANDIDATES = (
    "QuickTextPaste_x64_p.exe",
    "QuickTextPaste_p.exe",
    "QuickTextPaste_x64.exe",
    "QuickTextPaste.exe",
)

STATE_FILENAME = ".qtp_state.json"
BACKUPS_DIRNAME = "backups"


def _looks_like_utf16_no_bom(raw: bytes) -> str | None:
    """BOM olmayan UTF-16 LE/BE dosyalarını null-bayt örüntüsüyle tespit eder."""
    if len(raw) < 6 or len(raw) % 2 != 0:
        return None
    sample = raw[: min(200, len(raw))]
    even_zeros = sum(1 for i in range(0, len(sample), 2) if sample[i] == 0)
    odd_zeros = sum(1 for i in range(1, len(sample), 2) if sample[i] == 0)
    half = len(sample) // 2
    if odd_zeros >= max(3, int(half * 0.6)) and even_zeros <= max(1, int(half * 0.15)):
        return "utf-16-le"
    if even_zeros >= max(3, int(half * 0.6)) and odd_zeros <= max(1, int(half * 0.15)):
        return "utf-16-be"
    return None


def decode_bytes_auto(raw: bytes) -> tuple[str, str]:
    """Bayt dizisinden kodlamayı otomatik algılar; (metin, kodlama_adı) döndürür."""
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16-le", errors="replace"), "utf-16-le-bom"
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="replace"), "utf-16-be-bom"
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace"), "utf-8-bom"

    no_bom_u16 = _looks_like_utf16_no_bom(raw)
    if no_bom_u16:
        try:
            return raw.decode(no_bom_u16), no_bom_u16
        except UnicodeDecodeError:
            pass

    for enc in ("utf-8", "cp1254", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def read_text_auto(filepath: str | Path) -> str:
    """UTF-16 (Win32 QTP Unicode), UTF-8 BOM, UTF-8 ve Türkçe CP1254 otomatik algılar."""
    raw = Path(filepath).read_bytes()
    text, _ = decode_bytes_auto(raw)
    return text


def atomic_write_bytes(filepath: str | Path, data: bytes) -> None:
    """Yarım kalmış yazımlara karşı geçici dosya + atomik yeniden adlandırma kullanır."""
    target = Path(filepath)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".qtp_tmp_", dir=str(target.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp_path), str(target))
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def atomic_write_text(filepath: str | Path, text: str, encoding: str = "utf-8") -> None:
    atomic_write_bytes(filepath, text.encode(encoding))


def sanitize_group_part(text: str) -> str:
    """Grup adında iç içe alt menü '/' yapısını koruyarak güvenli hale getirir."""
    cleaned = str(text or "").replace("\r", " ").replace("\n", " ").strip()
    parts = [p.strip() for p in cleaned.split("/") if p.strip()]
    return "/".join(parts)


def sanitize_label_part(text: str) -> str:
    """Etiket içinde QTP alt menü ayıracı '/' karakterini güvenli hale getirir."""
    return str(text or "").replace("/", "-").replace("\r", " ").replace("\n", " ").strip()


def normalize_record(raw: dict[str, Any], idx: int = 0) -> dict[str, Any]:
    """Kayıt sözlüğünü standartlaştırır (opsiyonel alanları koruyarak)."""
    rec: dict[str, Any] = {
        "keys": str(raw.get("keys", "")).strip(),
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
    return rec


def strip_for_data_json(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """data.json için temiz ve standart şemayı üretir (keys, group, label?, text)."""
    out: list[dict[str, Any]] = []
    for item in items:
        obj: dict[str, Any] = {
            "keys": str(item.get("keys", "")).strip(),
            "group": str(item.get("group") or "Genel").strip() or "Genel",
        }
        lbl = str(item.get("label", "")).strip()
        if lbl:
            obj["label"] = lbl
        obj["text"] = str(item.get("text", ""))
        out.append(obj)
    return out


def parse_qtp_ini_full(content: str) -> dict[str, Any]:
    """
    QuickTextPaste.ini içeriğini tüm [Program] ayarları ve ek bölümlerle birlikte
    kayıpsız olarak ayrıştırır.
    """
    section_lower: str | None = None
    section_orig: str | None = None
    texts: dict[str, tuple[str, str, int]] = {}
    orders: dict[str, int] = {}
    labels: dict[str, str] = {}
    program: dict[str, str] = {}
    extra_sections_map: dict[str, list[str]] = {}
    seq = 0

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section_orig = stripped[1:-1].strip()
            section_lower = section_orig.lower()
            if section_lower not in ("program", "list_text", "list_order", "list_label"):
                extra_sections_map.setdefault(section_orig, [])
            continue

        if section_lower not in ("program", "list_text", "list_order", "list_label") and section_orig:
            extra_sections_map.setdefault(section_orig, []).append(raw_line)
            continue

        if stripped.startswith((";", "#")):
            continue
        if "=" not in raw_line:
            continue

        if section_lower == "program":
            k, v = raw_line.split("=", 1)
            program[k.strip()] = v.strip()

        elif section_lower == "list_text":
            parts = raw_line.split("=", 2)
            if len(parts) < 3:
                continue
            tid = parts[0].strip()
            hotkey = parts[1].strip()
            val = parts[2]
            while val.rstrip().endswith("<E<N<D|"):
                val = val.rstrip()[:-7]
            val = val.replace("\\r\\n", "\n").replace("\\n", "\n")
            texts[tid] = (hotkey, val, seq)
            seq += 1

        elif section_lower == "list_order":
            k, v = raw_line.split("=", 1)
            try:
                orders[k.strip()] = int(v.strip())
            except ValueError:
                pass

        elif section_lower == "list_label":
            k, v = raw_line.split("=", 1)
            labels[k.strip()] = v.strip()

    def sort_key(tid: str) -> tuple[int, int, int]:
        o = orders.get(tid, 10**9)
        _, _, parse_seq = texts[tid]
        m = re.search(r"(\d+)$", tid)
        idx = int(m.group(1)) if m else 999999
        return (o, parse_seq, idx)

    items: list[dict[str, Any]] = []
    for tid in sorted(texts.keys(), key=sort_key):
        hotkey, text, _ = texts[tid]
        raw_label = labels.get(tid, "")
        if "/" in raw_label:
            grp, lbl = raw_label.rsplit("/", 1)
            grp = sanitize_group_part(grp) or "Genel"
            lbl = lbl.strip()
        else:
            grp = "Genel"
            lbl = raw_label.strip()
        entry: dict[str, Any] = {"keys": hotkey, "group": grp, "text": text}
        if lbl:
            entry["label"] = lbl
        items.append(entry)

    extra_sections = [
        {"name": name, "lines": lines}
        for name, lines in extra_sections_map.items()
        if lines
    ]
    return {"items": items, "program": program, "extra_sections": extra_sections}


def parse_qtp_ini(content: str) -> list[dict[str, Any]]:
    """Geriye dönük uyumluluk: yalnızca kayıt listesini döndürür."""
    return parse_qtp_ini_full(content)["items"]


def build_qtp_ini(
    items: list[dict[str, Any]],
    m_show_tree: int | None = 1,
    include_program: bool = True,
    program: dict[str, Any] | None = None,
    extra_sections: list[dict[str, Any]] | None = None,
    tr_prefs: bool = True,
    keep_winrc: bool = True,
) -> str:
    """data.json listesini ve [Program]/ek bölümleri geçerli QuickTextPaste.ini biçimine çevirir."""
    lines: list[str] = []
    if include_program:
        prog_out: dict[str, str] = {}
        if program:
            for k, v in program.items():
                if v is not None and str(k).strip():
                    prog_out[str(k).strip()] = str(v)

        prog_out["TestIni"] = str(int(time.time()))
        if m_show_tree is not None:
            prog_out["m_show_tree"] = "1" if int(m_show_tree) else "0"
        elif "m_show_tree" not in prog_out:
            prog_out["m_show_tree"] = DEFAULT_QTP_PROGRAM["m_show_tree"]

        prog_out["listcmd_count"] = str(len(items))

        if keep_winrc:
            if not prog_out.get("WinRC"):
                prog_out["WinRC"] = DEFAULT_QTP_PROGRAM["WinRC"]
        else:
            prog_out.pop("WinRC", None)

        if tr_prefs:
            prog_out.setdefault("lng", DEFAULT_QTP_PROGRAM["lng"])
            prog_out.setdefault("start_tray", DEFAULT_QTP_PROGRAM["start_tray"])

        lines.append("[Program]")
        preferred_order = ["TestIni", "m_show_tree", "listcmd_count", "WinRC", "lng", "start_tray"]
        written_keys: set[str] = set()
        for k in preferred_order:
            if k in prog_out:
                lines.append(f"{k}={prog_out[k]}")
                written_keys.add(k)
        for k, v in prog_out.items():
            if k not in written_keys:
                lines.append(f"{k}={v}")

    lines.append("[list_text]")
    for i, item in enumerate(items):
        tid = f"text_{i:03d}"
        keys = str(item.get("keys", "")).strip()
        text = (
            str(item.get("text", ""))
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace("\n", "\\n")
        )
        lines.append(f"{tid}={keys}={text}<E<N<D|")

    lines.append("[list_order]")
    for i in range(len(items)):
        lines.append(f"text_{i:03d}={i + 1}")

    lines.append("[list_label]")
    for i, item in enumerate(items):
        tid = f"text_{i:03d}"
        raw_grp = str(item.get("group", ""))
        grp = "" if raw_grp.strip() in ("", "(Kök)", "(Grupsuz)") else sanitize_group_part(raw_grp)
        lbl = sanitize_label_part(str(item.get("label", "")))
        if not lbl:
            preview = str(item.get("text", "")).replace("\n", " ").strip()
            lbl = sanitize_label_part(preview[:45] + ("..." if len(preview) > 45 else ""))
        full_label = f"{grp}/{lbl}" if grp else lbl
        lines.append(f"{tid}={full_label}")

    if extra_sections:
        for sec in extra_sections:
            name = str(sec.get("name", "")).strip()
            sec_lines = sec.get("lines") or []
            if name and sec_lines:
                lines.append(f"[{name}]")
                lines.extend(str(l) for l in sec_lines)

    return "\r\n".join(lines) + "\r\n"


def encode_qtp_ini(ini_text: str, encoding: str = "utf-16-le-bom") -> bytes:
    if encoding == "utf-8-bom":
        return b"\xef\xbb\xbf" + ini_text.encode("utf-8")
    if encoding == "utf-8":
        return ini_text.encode("utf-8")
    return b"\xff\xfe" + ini_text.encode("utf-16-le")


def parse_any_content(content: str, filename: str = "") -> dict[str, Any]:
    """
    .ini, standart data.json veya qtp-pwa-backup JSON içeriğini otomatik algılayıp ayrıştırır.
    Dönüş: {"kind": "ini"|"json"|"backup", "items": [...], "program": {...}, "extra_sections": [...], "settings": {...}|None}
    """
    lower = filename.lower()
    stripped = content.lstrip()
    first_line = stripped.splitlines()[0].strip() if stripped else ""
    looks_like_ini_header = bool(re.match(r"^\[[A-Za-z0-9_]+\]$", first_line))

    is_ini = lower.endswith(".ini") or (
        not lower.endswith(".json")
        and (looks_like_ini_header or "[list_text]" in content or "[Program]" in content or not stripped.startswith(("[", "{")))
    )
    if is_ini:
        parsed = parse_qtp_ini_full(content)
        return {
            "kind": "ini",
            "items": parsed["items"],
            "program": parsed["program"],
            "extra_sections": parsed["extra_sections"],
            "settings": None,
        }

    raw = json.loads(content)
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
        }

    if isinstance(raw, list):
        items = [normalize_record(d, i) for i, d in enumerate(raw) if isinstance(d, dict)]
        return {
            "kind": "json",
            "items": items,
            "program": {},
            "extra_sections": [],
            "settings": None,
        }

    raise ValueError("Desteklenmeyen dosya biçimi: Geçerli INI, JSON listesi ([...]) veya QTP Tam Yedek bekleniyor.")


def normalize_tr(s: str) -> str:
    return (
        s.lower()
        .replace("ı", "i").replace("İ", "i").replace("ğ", "g")
        .replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    )


def export_word_document(items: list[dict[str, Any]], filepath: str) -> tuple[bool, str]:
    """python-docx varsa yerel .docx, yoksa Word/Google Docs uyumlu yazdırılabilir .doc üretir."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(item.get("group") or "Genel", []).append(item)

    try:
        import docx
        from docx.shared import Inches, Pt, RGBColor

        doc = docx.Document()
        for sec in doc.sections:
            sec.top_margin = Inches(0.6)
            sec.bottom_margin = Inches(0.6)
            sec.left_margin = Inches(0.65)
            sec.right_margin = Inches(0.65)

        title = doc.add_heading("Hazır Cevaplar ve Kısayol Rehberi", level=0)
        title.runs[0].font.color.rgb = RGBColor(0x31, 0x2E, 0x81)

        meta = doc.add_paragraph(
            f"Toplam {len(items)} kayıt • {len(grouped)} grup • "
            f"Oluşturulma: {time.strftime('%d.%m.%Y %H:%M')}"
        )
        meta.runs[0].font.size = Pt(9.5)
        meta.runs[0].font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

        for grp_name, grp_items in grouped.items():
            h = doc.add_heading(f"{grp_name} ({len(grp_items)})", level=1)
            h.runs[0].font.color.rgb = RGBColor(0x43, 0x38, 0xCA)

            table = doc.add_table(rows=1, cols=3)
            table.style = "Table Grid"
            hdr = table.rows[0].cells
            hdr[0].text = "Kısayol"
            hdr[1].text = "Başlık / Senaryo"
            hdr[2].text = "Hazır Cevap Metni"
            for cell in hdr:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.bold = True
                        r.font.size = Pt(9.5)

            for it in grp_items:
                row = table.add_row().cells
                row[0].text = str(it.get("keys", ""))
                row[1].text = str(it.get("label", ""))
                row[2].text = str(it.get("text", ""))
                for cell in row:
                    for p in cell.paragraphs:
                        for r in p.runs:
                            r.font.size = Pt(9.5)
            doc.add_paragraph("")

        doc.save(filepath)
        return True, f"Word (.docx) başarıyla oluşturuldu:\n{filepath}"

    except ImportError:
        fallback_path = str(Path(filepath).with_suffix(".doc"))
        parts = [
            "<!DOCTYPE html><html lang='tr'><head><meta charset='utf-8'>",
            "<style>body{font-family:Calibri,Arial,sans-serif;font-size:10.5pt;color:#0f172a;}"
            "h1{color:#312e81;border-bottom:2px solid #4f46e5;padding-bottom:6px;}"
            "h2{color:#4338ca;margin-top:20px;}"
            "table{width:100%;border-collapse:collapse;margin-bottom:14px;}"
            "th,td{border:1px solid #cbd5e1;padding:6px 8px;text-align:left;vertical-align:top;}"
            "th{background:#eef2ff;font-weight:bold;} .k{font-family:Consolas,monospace;white-space:nowrap;}</style>",
            "</head><body>",
            "<h1>Hazır Cevaplar ve Kısayol Rehberi</h1>",
            f"<p>Toplam {len(items)} kayıt • {len(grouped)} grup • {time.strftime('%d.%m.%Y %H:%M')}</p>",
        ]
        for grp_name, grp_items in grouped.items():
            parts.append(f"<h2>{_html.escape(grp_name)} ({len(grp_items)})</h2>")
            parts.append("<table><tr><th>Kısayol</th><th>Başlık</th><th>Hazır Cevap Metni</th></tr>")
            for it in grp_items:
                parts.append(
                    f"<tr><td class='k'>{_html.escape(str(it.get('keys', '')))}</td>"
                    f"<td>{_html.escape(str(it.get('label', '')))}</td>"
                    f"<td>{_html.escape(str(it.get('text', ''))).replace(chr(10), '<br>')}</td></tr>"
                )
            parts.append("</table>")
        parts.append("</body></html>")
        atomic_write_bytes(fallback_path, b"\xef\xbb\xbf" + "\n".join(parts).encode("utf-8"))
        return True, (
            "python-docx kurulu olmadığı için Word ve Google Docs uyumlu .doc dosyası oluşturuldu:\n"
            f"{fallback_path}\n\n"
            "(Yerel .docx için: pip install python-docx)"
        )


def is_wsl() -> bool:
    if os.name != "posix":
        return False
    try:
        rel = platform.release().lower()
        return "microsoft" in rel or "wsl" in rel
    except Exception:
        return False


def is_windows_environment() -> bool:
    return os.name == "nt" or is_wsl()


def _win_no_window_flags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return 0


def _to_windows_path(path: Path) -> str:
    s = str(path)
    if is_wsl():
        try:
            out = subprocess.check_output(["wslpath", "-w", s], text=True, timeout=3).strip()
            if out:
                return out
        except Exception:
            pass
    return s


def find_quicktextpaste_exe(work_dir: str | Path) -> Path | None:
    wd = Path(work_dir).resolve()
    search_dirs: list[Path] = [wd, wd / "legacy", wd / "bin"]

    if os.name == "nt":
        for env_key, sub in (
            ("LOCALAPPDATA", "QuickTextPaste"),
            ("APPDATA", "QuickTextPaste"),
            ("ProgramFiles", "QuickTextPaste"),
            ("ProgramFiles(x86)", "QuickTextPaste"),
        ):
            val = os.environ.get(env_key)
            if val:
                search_dirs.append(Path(val) / sub)

    for path_entry in os.environ.get("PATH", "").split(os.pathsep):
        if path_entry:
            search_dirs.append(Path(path_entry))

    seen_dirs: set[Path] = set()
    for folder in search_dirs:
        try:
            resolved_dir = folder.resolve()
        except OSError:
            continue
        if resolved_dir in seen_dirs or not resolved_dir.is_dir():
            continue
        seen_dirs.add(resolved_dir)
        for exe_name in QTP_EXE_CANDIDATES:
            candidate = resolved_dir / exe_name
            if candidate.is_file():
                return candidate
    return None


def resolve_ini_targets(work_dir: str | Path, exe_path: Path | None = None) -> list[Path]:
    """Yazılacak QuickTextPaste.ini hedeflerini belirler (çalışma dizini + taşınabilir exe dizini)."""
    wd = Path(work_dir).resolve()
    targets: list[Path] = [wd / "QuickTextPaste.ini"]

    if exe_path:
        exe_ini = exe_path.parent / "QuickTextPaste.ini"
        if exe_ini.resolve() != targets[0].resolve():
            targets.append(exe_ini)

    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            appdata_ini = Path(appdata) / "QuickTextPaste" / "QuickTextPaste.ini"
            if appdata_ini.exists() and appdata_ini.resolve() not in {t.resolve() for t in targets}:
                targets.append(appdata_ini)

    return targets


def get_running_qtp_processes() -> list[dict[str, Any]]:
    """Çalışan QuickTextPaste işlemlerini döndürür: [{'name': ..., 'pid': ...}]."""
    if not is_windows_environment():
        return []

    cmd = ["tasklist", "/FO", "CSV", "/NH"] if os.name == "nt" else ["tasklist.exe", "/FO", "CSV", "/NH"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            creationflags=_win_no_window_flags(),
        )
        if proc.returncode != 0:
            return []
        running: list[dict[str, Any]] = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line or "quicktextpaste" not in line.lower():
                continue
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) >= 2:
                name = parts[0]
                try:
                    pid = int(parts[1])
                except ValueError:
                    pid = 0
                if "quicktextpaste" in name.lower():
                    running.append({"name": name, "pid": pid})
        return running
    except Exception:
        return []


def get_exe_version(exe_path: Path | None) -> str | None:
    if not exe_path or not exe_path.is_file():
        return None
    if os.name != "nt":
        return None
    try:
        ps_cmd = f"(Get-Item -LiteralPath '{str(exe_path).replace(chr(39), chr(39)*2)}').VersionInfo.FileVersion"
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=_win_no_window_flags(),
        )
        ver = proc.stdout.strip()
        return ver or None
    except Exception:
        return None


def get_qtp_status(work_dir: str | Path) -> dict[str, Any]:
    wd = Path(work_dir).resolve()
    exe = find_quicktextpaste_exe(wd)
    procs = get_running_qtp_processes()
    ini_targets = resolve_ini_targets(wd, exe)
    primary_ini = ini_targets[0]
    active_ini = exe.parent / "QuickTextPaste.ini" if exe else primary_ini
    data_json = wd / "data.json"
    is_64 = "64" in platform.machine() or platform.architecture()[0] == "64bit"

    return {
        "platform": sys_platform_label(),
        "is_windows": is_windows_environment(),
        "is_wsl": is_wsl(),
        "installed": exe is not None,
        "exe_path": str(exe) if exe else None,
        "exe_name": exe.name if exe else None,
        "version": get_exe_version(exe) if exe else None,
        "running": len(procs) > 0,
        "pids": [p["pid"] for p in procs if p["pid"]],
        "processes": procs,
        "ini_path": str(active_ini),
        "ini_exists": active_ini.is_file(),
        "work_ini_path": str(primary_ini),
        "work_ini_exists": primary_ini.is_file(),
        "data_json_path": str(data_json),
        "data_json_exists": data_json.is_file(),
        "download_url": QTP_DOWNLOAD_URL_X64 if is_64 else QTP_DOWNLOAD_URL_X86,
        "homepage_url": QTP_HOMEPAGE_URL,
    }


def sys_platform_label() -> str:
    if os.name == "nt":
        return "windows"
    if is_wsl():
        return "wsl"
    return platform.system().lower()


def install_quicktextpaste(
    work_dir: str | Path,
    arch: str = "auto",
    progress_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """
    QuickTextPaste taşınabilir sürümünü resmi SoftwareOK adresinden indirir,
    doğrular ve hedef klasöre çıkarır. Halihazırda kuruluysa üzerine yazmaz.
    """
    wd = Path(work_dir).resolve()
    existing = find_quicktextpaste_exe(wd)
    if existing:
        exe_ini = existing.parent / "QuickTextPaste.ini"
        work_ini = wd / "QuickTextPaste.ini"
        if not exe_ini.exists() and work_ini.exists():
            shutil.copy2(work_ini, exe_ini)
        return {"ok": True, "already_installed": True, "status": get_qtp_status(wd)}

    if arch == "x86":
        url = QTP_DOWNLOAD_URL_X86
    elif arch == "x64":
        url = QTP_DOWNLOAD_URL_X64
    else:
        is_64 = "64" in platform.machine() or platform.architecture()[0] == "64bit"
        url = QTP_DOWNLOAD_URL_X64 if is_64 else QTP_DOWNLOAD_URL_X86

    if progress_cb:
        progress_cb(f"İndiriliyor: {url}")

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "QTP-Manager/3.0 (+https://m-sonmez.github.io/qtp)"},
    )
    with tempfile.TemporaryDirectory(prefix="qtp_dl_") as tmpdir:
        zip_path = Path(tmpdir) / "QuickTextPaste.zip"
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = resp.read()
        if len(payload) < 50_000:
            raise RuntimeError("İndirilen QuickTextPaste paketi beklenenden küçük veya bozuk.")
        zip_path.write_bytes(payload)

        with zipfile.ZipFile(zip_path, "r") as zf:
            bad = zf.testzip()
            if bad is not None:
                raise RuntimeError(f"ZIP arşivi bozuk: {bad}")
            extracted_exe: Path | None = None
            for member in zf.infolist():
                if member.is_dir():
                    continue
                name = Path(member.filename).name
                if not name:
                    continue
                if name.lower().endswith(".exe") and "quicktextpaste" in name.lower():
                    dest = wd / name
                    with zf.open(member, "r") as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted_exe = dest
                    break
            if not extracted_exe:
                raise RuntimeError("İndirilen ZIP içinde QuickTextPaste çalıştırılabilir dosyası bulunamadı.")

    work_ini = wd / "QuickTextPaste.ini"
    data_json = wd / "data.json"
    if not work_ini.exists():
        if data_json.exists():
            items = json.loads(read_text_auto(data_json))
        else:
            items = []
        ini_text = build_qtp_ini(items)
        atomic_write_bytes(work_ini, encode_qtp_ini(ini_text, "utf-16-le-bom"))

    return {"ok": True, "already_installed": False, "status": get_qtp_status(wd)}


def stop_quicktextpaste(timeout: float = 4.0) -> dict[str, Any]:
    """Çalışan QuickTextPaste işlemlerini güvenli şekilde kapatır."""
    if not is_windows_environment():
        return {"ok": False, "message": "QuickTextPaste yalnızca Windows ortamında çalışır."}

    procs = get_running_qtp_processes()
    if not procs:
        return {"ok": True, "stopped": 0, "message": "QuickTextPaste zaten çalışmıyor."}

    names = sorted({p["name"] for p in procs})
    kill_exe = "taskkill" if os.name == "nt" else "taskkill.exe"

    for img in names:
        subprocess.run(
            [kill_exe, "/IM", img],
            capture_output=True,
            timeout=5,
            creationflags=_win_no_window_flags(),
        )

    deadline = time.time() + min(timeout, 2.0)
    while time.time() < deadline:
        if not get_running_qtp_processes():
            return {"ok": True, "stopped": len(procs), "message": "QuickTextPaste kapatıldı."}
        time.sleep(0.25)

    for img in names:
        subprocess.run(
            [kill_exe, "/F", "/IM", img],
            capture_output=True,
            timeout=5,
            creationflags=_win_no_window_flags(),
        )

    deadline = time.time() + max(1.0, timeout - 2.0)
    while time.time() < deadline:
        if not get_running_qtp_processes():
            return {"ok": True, "stopped": len(procs), "message": "QuickTextPaste kapatıldı."}
        time.sleep(0.25)

    remaining = get_running_qtp_processes()
    return {
        "ok": len(remaining) == 0,
        "stopped": len(procs) - len(remaining),
        "message": "Bazı işlemler kapatılamadı." if remaining else "QuickTextPaste kapatıldı.",
    }


def start_quicktextpaste(
    work_dir: str | Path,
    background: bool = True,
    ensure_installed: bool = True,
) -> dict[str, Any]:
    """QuickTextPaste uygulamasını başlatır (gerekirse önce indirip kurar)."""
    wd = Path(work_dir).resolve()
    if not is_windows_environment():
        return {
            "ok": False,
            "error": "QuickTextPaste yerel Windows uygulamasıdır; bu platformda otomatik çalıştırılamaz.",
            "status": get_qtp_status(wd),
        }

    running = get_running_qtp_processes()
    if running:
        return {"ok": True, "already_running": True, "status": get_qtp_status(wd)}

    exe = find_quicktextpaste_exe(wd)
    if not exe and ensure_installed:
        install_quicktextpaste(wd)
        exe = find_quicktextpaste_exe(wd)

    if not exe:
        return {
            "ok": False,
            "error": "QuickTextPaste bulunamadı ve kurulamadı.",
            "status": get_qtp_status(wd),
        }

    exe_ini = exe.parent / "QuickTextPaste.ini"
    work_ini = wd / "QuickTextPaste.ini"
    if not exe_ini.exists() and work_ini.exists():
        shutil.copy2(work_ini, exe_ini)

    args = [str(exe)]
    if background:
        args.append("-bg")

    if os.name == "nt":
        flags = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | _win_no_window_flags()
        )
        subprocess.Popen(
            args,
            cwd=str(exe.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
    else:
        win_exe = _to_windows_path(exe)
        win_cwd = _to_windows_path(exe.parent)
        bg_flag = " -bg" if background else ""
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", "/D", win_cwd, win_exe + bg_flag],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    deadline = time.time() + 4.0
    while time.time() < deadline:
        if get_running_qtp_processes():
            return {"ok": True, "already_running": False, "status": get_qtp_status(wd)}
        time.sleep(0.25)

    return {"ok": True, "already_running": False, "status": get_qtp_status(wd)}


def _items_digest(items: list[dict[str, Any]]) -> str:
    """Kayıt listesinin içerik özetini (SHA-256) üretir."""
    canonical = json.dumps(strip_for_data_json(items), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_state(work_dir: str | Path) -> dict[str, Any]:
    """Çalışma dizinindeki data.json + QuickTextPaste.ini + .qtp_state.json dosyalarını okur."""
    wd = Path(work_dir).resolve()
    data_json_path = wd / "data.json"
    ini_path = wd / "QuickTextPaste.ini"
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

    ini_mtime = ini_path.stat().st_mtime if ini_path.is_file() else 0.0
    json_mtime = data_json_path.stat().st_mtime if data_json_path.is_file() else 0.0

    json_items: list[dict[str, Any]] = []
    json_valid = False
    if data_json_path.is_file():
        try:
            raw_list = json.loads(read_text_auto(data_json_path))
            if isinstance(raw_list, list):
                json_items = [normalize_record(d, i) for i, d in enumerate(raw_list) if isinstance(d, dict)]
                json_valid = True
        except Exception:
            json_valid = False

    parsed_ini: dict[str, Any] | None = None
    if ini_path.is_file():
        try:
            parsed_ini = parse_qtp_ini_full(read_text_auto(ini_path))
        except Exception:
            parsed_ini = None

    use_ini = False
    if parsed_ini is not None and not json_valid:
        use_ini = True
    elif parsed_ini is not None and json_valid and ini_mtime > json_mtime + 2.0:
        last_digest = state_meta.get("itemsDigest")
        if last_digest:
            ini_digest = _items_digest(parsed_ini["items"])
            json_digest = _items_digest(json_items)
            if ini_digest != last_digest and json_digest == last_digest:
                use_ini = True

    if use_ini and parsed_ini is not None:
        items = parsed_ini["items"]
        if parsed_ini["program"]:
            program.update(parsed_ini["program"])
        if parsed_ini["extra_sections"]:
            extra_sections = parsed_ini["extra_sections"]
        source = "QuickTextPaste.ini"
    elif json_valid:
        items = json_items
        source = "data.json"
        if parsed_ini is not None:
            if not program and parsed_ini["program"]:
                program = parsed_ini["program"]
            if not extra_sections and parsed_ini["extra_sections"]:
                extra_sections = parsed_ini["extra_sections"]

    for idx, it in enumerate(items):
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


def save_state(
    work_dir: str | Path,
    items: list[dict[str, Any]],
    program: dict[str, Any] | None = None,
    extra_sections: list[dict[str, Any]] | None = None,
    qtp_prefs: dict[str, Any] | None = None,
    encoding: str = "utf-16-le-bom",
    create_backup_flag: bool = True,
    backup_reason: str = "save",
    reload_qtp: bool = False,
    start_qtp_if_stopped: bool = False,
) -> dict[str, Any]:
    """
    Veriyi hem data.json hem de QuickTextPaste.ini (ve exe dizini) üzerine atomik olarak yazar.
    Gerekirse yedek alır ve QuickTextPaste'i güvenle durdurup yeni INI ile yeniden başlatır.
    """
    wd = Path(work_dir).resolve()
    exe = find_quicktextpaste_exe(wd)
    was_running = bool(get_running_qtp_processes()) if (reload_qtp or start_qtp_if_stopped) else False

    if create_backup_flag and ((wd / "data.json").is_file() or (wd / "QuickTextPaste.ini").is_file()):
        create_backup(wd, reason=backup_reason)

    if reload_qtp and was_running:
        stop_quicktextpaste()

    clean_json_items = strip_for_data_json(items)
    json_text = json.dumps(clean_json_items, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(wd / "data.json", json_text, encoding="utf-8")

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

    ini_text = build_qtp_ini(
        clean_json_items,
        m_show_tree=m_show_tree_val,
        include_program=True,
        program=merged_prog,
        extra_sections=extra_sections,
        tr_prefs=str(merged_prog.get("lng", "21")) == "21",
        keep_winrc=bool(merged_prog.get("WinRC", DEFAULT_QTP_PROGRAM["WinRC"])),
    )
    ini_bytes = encode_qtp_ini(ini_text, encoding=encoding)
    for target in resolve_ini_targets(wd, exe):
        atomic_write_bytes(target, ini_bytes)

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

    qtp_restarted = False
    if (reload_qtp and was_running) or start_qtp_if_stopped:
        if is_windows_environment() and find_quicktextpaste_exe(wd):
            res = start_quicktextpaste(wd, background=True, ensure_installed=False)
            qtp_restarted = bool(res.get("ok"))

    return {
        "ok": True,
        "count": len(clean_json_items),
        "qtp_restarted": qtp_restarted,
        "status": get_qtp_status(wd),
    }


def create_backup(
    work_dir: str | Path,
    reason: str = "manual",
    max_keep: int = 30,
) -> dict[str, Any] | None:
    """Mevcut data.json + QuickTextPaste.ini + .qtp_state.json dosyalarının zaman damgalı yedeğini alır."""
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
    for old_dir in existing[max_keep:]:
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


def restore_backup(
    work_dir: str | Path,
    backup_id: str,
    reload_qtp: bool = True,
) -> dict[str, Any]:
    wd = Path(work_dir).resolve()
    safe_id = Path(backup_id).name
    src_dir = wd / BACKUPS_DIRNAME / safe_id
    if not src_dir.is_dir():
        raise FileNotFoundError(f"Yedek bulunamadı: {safe_id}")

    create_backup(wd, reason="pre_restore")

    was_running = bool(get_running_qtp_processes()) if reload_qtp else False
    if reload_qtp and was_running:
        stop_quicktextpaste()

    for fname in ("data.json", "QuickTextPaste.ini", STATE_FILENAME):
        src = src_dir / fname
        if src.is_file():
            shutil.copy2(src, wd / fname)

    exe = find_quicktextpaste_exe(wd)
    if (wd / "QuickTextPaste.ini").is_file() and exe:
        for target in resolve_ini_targets(wd, exe):
            if target.resolve() != (wd / "QuickTextPaste.ini").resolve():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(wd / "QuickTextPaste.ini", target)

    if reload_qtp and was_running and is_windows_environment():
        start_quicktextpaste(wd, background=True, ensure_installed=False)

    return {"ok": True, "restored": safe_id, "state": load_state(wd), "status": get_qtp_status(wd)}
