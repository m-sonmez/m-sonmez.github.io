"""QuickTextPaste.ini çoklu kodlama algılama ve kayıpsız ayrıştırma/serileştirme modülü."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_TERMINATOR = "<E<N<D|"

DEFAULT_QTP_PROGRAM: dict[str, str] = {
    "m_show_tree": "1",
    "lng": "21",
    "start_tray": "1",
    "WinRC": "2399;17;3368;1335;1;x,y,w,h,SW",
}

_SECTION_RE = re.compile(r"^\[([^\[\]]+)\]$")
_VALID_LIST_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class IniParseError(ValueError):
    """Bozuk veya geçersiz QuickTextPaste.ini dosyaları için tiplendirilmiş Türkçe hata."""


@dataclass
class QtpItem:
    """Tek bir QuickTextPaste hazır cevap kaydı."""

    raw_key: str
    hotkey_prefix: str
    text: str
    terminator: str = DEFAULT_TERMINATOR
    group: str = "Genel"
    label: str = ""
    order: int | None = None
    item_id: str = ""
    favorite: bool = False
    copy_count: int = 0
    raw_label: str | None = None

    @property
    def keys(self) -> str:
        return self.hotkey_prefix

    @keys.setter
    def keys(self, value: str) -> None:
        self.hotkey_prefix = value

    def to_dict(self, include_meta: bool = False) -> dict[str, Any]:
        """data.json şemasına uyumlu sözlük döndürür."""
        obj: dict[str, Any] = {
            "keys": self.hotkey_prefix.strip(),
            "group": (self.group or "Genel").strip() or "Genel",
        }
        lbl = self.label.strip()
        if lbl:
            obj["label"] = lbl
        obj["text"] = self.text
        if include_meta:
            if self.item_id:
                obj["id"] = self.item_id
            if self.favorite:
                obj["favorite"] = True
            if self.copy_count:
                obj["copyCount"] = int(self.copy_count)
        return obj

    @classmethod
    def from_dict(cls, raw: dict[str, Any], index: int = 0) -> "QtpItem":
        """Sözlükten QtpItem oluşturur."""
        raw_key = str(raw.get("raw_key") or f"text_{index:03d}")
        hotkey = str(raw.get("keys", raw.get("hotkey_prefix", ""))).strip()
        group = str(raw.get("group") or "Genel").strip() or "Genel"
        label = str(raw.get("label", "")).strip()
        text = str(raw.get("text", ""))
        terminator = str(raw.get("terminator", DEFAULT_TERMINATOR))
        order_val = raw.get("order")
        if order_val is not None:
            try:
                order_val = int(order_val)
            except (TypeError, ValueError):
                order_val = None
        return cls(
            raw_key=raw_key,
            hotkey_prefix=hotkey,
            text=text,
            terminator=terminator,
            group=group,
            label=label,
            order=order_val,
            item_id=str(raw.get("id") or f"qtp_{index:03d}"),
            favorite=bool(raw.get("favorite", False)),
            copy_count=int(raw.get("copyCount", 0) or 0),
        )


@dataclass
class QtpDocument:
    """QuickTextPaste.ini dosyasının kayıpsız tam bellek modeli."""

    items: list[QtpItem] = field(default_factory=list)
    program: dict[str, str] = field(default_factory=dict)
    extra_sections: list[dict[str, Any]] = field(default_factory=list)
    section_order: list[str] = field(default_factory=list)
    raw_text_order: list[str] = field(default_factory=list)
    raw_order_keys: list[str] = field(default_factory=list)
    raw_label_keys: list[str] = field(default_factory=list)
    line_ending: str = "\r\n"
    trailing_newline: bool = True


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


def detect_encoding(raw: bytes) -> str:
    """Bayt dizisinin karakter kodlamasını otomatik algılar."""
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le-bom"
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be-bom"
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-bom"

    no_bom_u16 = _looks_like_utf16_no_bom(raw)
    if no_bom_u16:
        try:
            raw.decode(no_bom_u16)
            return no_bom_u16
        except UnicodeDecodeError:
            pass

    for enc in ("utf-8", "cp1254", "latin-1"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def decode_bytes_auto(raw: bytes) -> tuple[str, str]:
    """Bayt dizisinden kodlamayı algılar ve (metin, kodlama_adı) döndürür."""
    if raw.startswith(b"\xff\xfe"):
        payload = raw[2:]
        if len(payload) % 2 != 0:
            raise IniParseError("INI dosyası okunamadı: bozuk veya eksik UTF-16 LE bayt dizisi.")
        return payload.decode("utf-16-le", errors="replace"), "utf-16-le-bom"
    if raw.startswith(b"\xfe\xff"):
        payload = raw[2:]
        if len(payload) % 2 != 0:
            raise IniParseError("INI dosyası okunamadı: bozuk veya eksik UTF-16 BE bayt dizisi.")
        return payload.decode("utf-16-be", errors="replace"), "utf-16-be-bom"
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace"), "utf-8-bom"

    no_bom_u16 = _looks_like_utf16_no_bom(raw)
    if no_bom_u16:
        try:
            return raw.decode(no_bom_u16), no_bom_u16
        except UnicodeDecodeError:
            pass

    if b"\x00" in raw:
        raise IniParseError("INI dosyası okunamadı: geçersiz ikili (null) bayt içeriği.")

    for enc in ("utf-8", "cp1254", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def read_text_auto(filepath: str | Path) -> str:
    """Dosyayı otomatik kodlama algılama ile okur."""
    raw = Path(filepath).read_bytes()
    text, _ = decode_bytes_auto(raw)
    return text


def atomic_write_bytes(filepath: str | Path, data: bytes) -> None:
    """Geçici dosya + atomik yeniden adlandırma ile veri kaybını önleyerek yazar."""
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


def sanitize_group_part(text: str) -> str:
    """Grup adındaki '/' alt menü hiyerarşisini temizler."""
    cleaned = str(text or "").replace("\r", " ").replace("\n", " ").strip()
    parts = [p.strip() for p in cleaned.split("/") if p.strip()]
    return "/".join(parts)


def sanitize_label_part(text: str) -> str:
    """Etiket adındaki '/' karakterini güvenli hale getirir."""
    return str(text or "").replace("/", "-").replace("\r", " ").replace("\n", " ").strip()


def _detect_line_ending(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    if "\n" in text:
        return "\n"
    return "\r\n"


def parse_qtp_ini(content: str) -> QtpDocument:
    """
    QuickTextPaste.ini metnini kayıpsız QtpDocument yapısına ayrıştırır.
    Bozuk sözdizimi durumunda Türkçe IniParseError fırlatır.
    """
    if not isinstance(content, str):
        raise IniParseError("INI dosyası çözümlenemedi: metin türü geçersiz.")

    if "\x00" in content:
        raise IniParseError("INI dosyası okunamadı: geçersiz ikili (null) karakter içeriyor.")

    if content.startswith("\ufeff"):
        content = content[1:]

    if not content.strip():
        return QtpDocument()

    line_ending = _detect_line_ending(content)
    trailing_newline = content.endswith(("\n", "\r"))

    section_lower: str | None = None
    section_orig: str | None = None
    section_order: list[str] = []
    texts: dict[str, tuple[str, str, str, int]] = {}
    raw_text_order: list[str] = []
    orders: dict[str, int] = {}
    raw_order_keys: list[str] = []
    labels: dict[str, str] = {}
    raw_label_keys: list[str] = []
    program: dict[str, str] = {}
    extra_sections_map: dict[str, list[str]] = {}
    seq = 0

    for line_no, raw_line in enumerate(content.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue

        if stripped.startswith("["):
            if not stripped.endswith("]"):
                raise IniParseError(
                    f"INI dosyası biçimi geçersiz (satır {line_no}): Bölüm başlığı düzgün kapatılmamış."
                )
            section_orig = stripped[1:-1].strip()
            if not section_orig:
                raise IniParseError(
                    f"INI dosyası biçimi geçersiz (satır {line_no}): Boş bölüm adı kullanılamaz."
                )
            section_lower = section_orig.lower()
            if section_orig not in section_order:
                section_order.append(section_orig)
            if section_lower not in ("program", "list_text", "list_order", "list_label"):
                extra_sections_map.setdefault(section_orig, [])
            continue

        if stripped.startswith((";", "#")):
            if section_lower not in (None, "program", "list_text", "list_order", "list_label") and section_orig:
                extra_sections_map.setdefault(section_orig, []).append(raw_line)
            continue

        if section_lower is None:
            raise IniParseError(
                f"INI dosyası biçimi geçersiz (satır {line_no}): Bölüm ([...]) başlığı dışında içerik bulundu."
            )

        if section_lower not in ("program", "list_text", "list_order", "list_label") and section_orig:
            extra_sections_map.setdefault(section_orig, []).append(raw_line)
            continue

        if "=" not in raw_line:
            raise IniParseError(
                f"INI dosyası biçimi geçersiz (satır {line_no}): Anahtar=değer biçimi bekleniyor."
            )

        if section_lower == "program":
            k, v = raw_line.split("=", 1)
            program[k.strip()] = v.strip()

        elif section_lower == "list_text":
            parts = raw_line.split("=", 2)
            if len(parts) < 3:
                raise IniParseError(
                    f"INI dosyası biçimi geçersiz (satır {line_no}): [list_text] satırı 'kimlik=kısayol=metin' biçiminde değil."
                )
            tid = parts[0].strip()
            if not tid or not _VALID_LIST_KEY_RE.match(tid):
                raise IniParseError(
                    f"INI dosyası biçimi geçersiz (satır {line_no}): Geçersiz öğe kimliği '{tid}'."
                )
            hotkey = parts[1].strip()
            val = parts[2]
            terminator = ""
            rstripped = val.rstrip()
            if rstripped.endswith("<E<N<D|"):
                terminator = "<E<N<D|"
                while rstripped.endswith("<E<N<D|"):
                    rstripped = rstripped[:-7]
                val = rstripped
            val = val.replace("\\r\\n", "\n").replace("\\n", "\n")
            texts[tid] = (hotkey, val, terminator, seq)
            raw_text_order.append(tid)
            seq += 1

        elif section_lower == "list_order":
            k, v = raw_line.split("=", 1)
            tid = k.strip()
            raw_order_keys.append(tid)
            try:
                orders[tid] = int(v.strip())
            except ValueError as exc:
                raise IniParseError(
                    f"INI dosyası biçimi geçersiz (satır {line_no}): [list_order] sayısal değer bekliyor."
                ) from exc

        elif section_lower == "list_label":
            k, v = raw_line.split("=", 1)
            tid = k.strip()
            raw_label_keys.append(tid)
            labels[tid] = v.strip()

    def sort_key(tid: str) -> tuple[int, int, int]:
        o = orders.get(tid, 10**9)
        _, _, _, parse_seq = texts[tid]
        m = re.search(r"(\d+)$", tid)
        idx = int(m.group(1)) if m else 999999
        return (o, parse_seq, idx)

    items: list[QtpItem] = []
    for sorted_idx, tid in enumerate(sorted(texts.keys(), key=sort_key)):
        hotkey, text, terminator, _ = texts[tid]
        raw_label = labels.get(tid, "")
        if "/" in raw_label:
            grp, lbl = raw_label.rsplit("/", 1)
            grp = sanitize_group_part(grp) or "Genel"
            lbl = lbl.strip()
        else:
            grp = "Genel"
            lbl = raw_label.strip()
        items.append(
            QtpItem(
                raw_key=tid,
                hotkey_prefix=hotkey,
                text=text,
                terminator=terminator,
                group=grp,
                label=lbl,
                order=orders.get(tid),
                item_id=f"qtp_{sorted_idx:03d}",
                raw_label=raw_label if tid in labels else None,
            )
        )

    extra_sections = [
        {"name": name, "lines": lines}
        for name, lines in extra_sections_map.items()
        if lines
    ]

    return QtpDocument(
        items=items,
        program=program,
        extra_sections=extra_sections,
        section_order=section_order,
        raw_text_order=raw_text_order,
        raw_order_keys=raw_order_keys,
        raw_label_keys=raw_label_keys,
        line_ending=line_ending,
        trailing_newline=trailing_newline,
    )


def serialize_qtp_ini(doc: QtpDocument, *, update_test_ini: bool = False) -> str:
    """
    QtpDocument nesnesini QuickTextPaste.ini metnine kayıpsız geri dönüştürür.
    Varsayılan olarak tüm TestIni, ham anahtar, terminatör ve satır sonu yapısını birebir korur.
    """
    if not doc.section_order and not doc.items and not doc.program and not doc.extra_sections:
        return ""

    eol = doc.line_ending or "\r\n"
    by_key: dict[str, QtpItem] = {it.raw_key: it for it in doc.items}
    sections_to_write = list(doc.section_order) if doc.section_order else []

    if not sections_to_write:
        if doc.program:
            sections_to_write.append("Program")
        if doc.items:
            sections_to_write.extend(["list_text", "list_order", "list_label"])
        for sec in doc.extra_sections:
            name = str(sec.get("name", "")).strip()
            if name and name not in sections_to_write:
                sections_to_write.append(name)

    extra_by_lower = {str(s.get("name", "")).lower(): s for s in doc.extra_sections}
    lines: list[str] = []

    for sec_name in sections_to_write:
        sec_low = sec_name.lower()
        if sec_low == "program":
            lines.append("[Program]")
            prog_out = dict(doc.program)
            if update_test_ini:
                prog_out["TestIni"] = str(int(time.time()))
                prog_out["listcmd_count"] = str(len(doc.items))
            for k, v in prog_out.items():
                lines.append(f"{k}={v}")

        elif sec_low == "list_text":
            lines.append("[list_text]")
            ordered_keys = (
                [k for k in doc.raw_text_order if k in by_key]
                + [it.raw_key for it in doc.items if it.raw_key not in set(doc.raw_text_order)]
            )
            for k in ordered_keys:
                it = by_key[k]
                encoded_text = (
                    it.text.replace("\r\n", "\n")
                    .replace("\r", "\n")
                    .replace("\n", "\\n")
                )
                lines.append(f"{it.raw_key}={it.hotkey_prefix}={encoded_text}{it.terminator}")

        elif sec_low == "list_order":
            lines.append("[list_order]")
            order_keys = (
                [k for k in doc.raw_order_keys if k in by_key and by_key[k].order is not None]
                + [
                    it.raw_key
                    for it in doc.items
                    if it.raw_key not in set(doc.raw_order_keys) and it.order is not None
                ]
            )
            if not order_keys and doc.items:
                for idx, it in enumerate(doc.items, start=1):
                    lines.append(f"{it.raw_key}={idx}")
            else:
                for k in order_keys:
                    it = by_key[k]
                    lines.append(f"{it.raw_key}={it.order}")

        elif sec_low == "list_label":
            lines.append("[list_label]")
            label_keys = (
                [k for k in doc.raw_label_keys if k in by_key]
                + [it.raw_key for it in doc.items if it.raw_key not in set(doc.raw_label_keys)]
            )
            for k in label_keys:
                it = by_key[k]
                if it.raw_label is not None:
                    full_label = it.raw_label
                else:
                    raw_grp = it.group
                    grp = "" if raw_grp.strip() in ("", "Genel", "(Kök)", "(Grupsuz)") else sanitize_group_part(raw_grp)
                    lbl = sanitize_label_part(it.label)
                    if not lbl:
                        preview = it.text.replace("\n", " ").strip()
                        lbl = sanitize_label_part(preview[:45] + ("..." if len(preview) > 45 else ""))
                    full_label = f"{grp}/{lbl}" if grp else lbl
                lines.append(f"{it.raw_key}={full_label}")

        else:
            sec = extra_by_lower.get(sec_low)
            if sec and sec.get("lines"):
                lines.append(f"[{sec['name']}]")
                lines.extend(str(l) for l in sec["lines"])

    if not lines:
        return ""
    body = eol.join(lines)
    if doc.trailing_newline:
        body += eol
    return body


def parse_qtp_ini_full(content: str) -> dict[str, Any]:
    """qtp_core.py uyumlu tam sözlük çıktısı döndürür."""
    doc = parse_qtp_ini(content)
    return {
        "items": [it.to_dict(include_meta=False) for it in doc.items],
        "program": dict(doc.program),
        "extra_sections": list(doc.extra_sections),
    }


def build_qtp_ini(
    items: list[dict[str, Any]],
    m_show_tree: int | None = 1,
    include_program: bool = True,
    program: dict[str, Any] | None = None,
    extra_sections: list[dict[str, Any]] | None = None,
    tr_prefs: bool = True,
    keep_winrc: bool = True,
    preserve_test_ini: bool = False,
) -> str:
    """Kayıt listesini standart QuickTextPaste.ini metnine dönüştürür."""
    lines: list[str] = []
    if include_program:
        prog_out: dict[str, str] = {}
        if program:
            for k, v in program.items():
                if v is not None and str(k).strip():
                    prog_out[str(k).strip()] = str(v)

        if not (preserve_test_ini and prog_out.get("TestIni")):
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
        tid = str(item.get("raw_key") or f"text_{i:03d}")
        keys = str(item.get("keys", item.get("hotkey_prefix", ""))).strip()
        term = str(item.get("terminator", DEFAULT_TERMINATOR))
        text = (
            str(item.get("text", ""))
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace("\n", "\\n")
        )
        lines.append(f"{tid}={keys}={text}{term}")

    lines.append("[list_order]")
    for i, item in enumerate(items):
        tid = str(item.get("raw_key") or f"text_{i:03d}")
        lines.append(f"{tid}={i + 1}")

    lines.append("[list_label]")
    for i, item in enumerate(items):
        tid = str(item.get("raw_key") or f"text_{i:03d}")
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
    """INI metnini belirtilen kodlamada baytlara çevirir."""
    enc = encoding.lower()
    if enc == "utf-8-bom":
        return b"\xef\xbb\xbf" + ini_text.encode("utf-8")
    if enc == "utf-8":
        return ini_text.encode("utf-8")
    if enc == "utf-16-be-bom":
        return b"\xfe\xff" + ini_text.encode("utf-16-be")
    if enc == "cp1254":
        return ini_text.encode("cp1254")
    return b"\xff\xfe" + ini_text.encode("utf-16-le")


def write_qtp_ini(
    filepath: str | Path,
    ini_text: str,
    *,
    encoding: str = "utf-16-le-bom",
    create_bak: bool = True,
) -> Path:
    """INI metnini atomik olarak yazar; varsa .bak yedeği oluşturur."""
    target = Path(filepath)
    if create_bak and target.is_file():
        bak_path = target.with_name(target.name + ".bak")
        shutil.copy2(target, bak_path)
    atomic_write_bytes(target, encode_qtp_ini(ini_text, encoding=encoding))
    return target
