"""INI çoklu kodlama, kayıpsız gidiş-dönüş (round-trip) ve hata testleri."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from qtp_app.core.ini_parser import (
    IniParseError,
    build_qtp_ini,
    decode_bytes_auto,
    detect_encoding,
    encode_qtp_ini,
    parse_qtp_ini,
    read_text_auto,
    serialize_qtp_ini,
    write_qtp_ini,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


def test_bundled_quicktextpaste_ini_byte_identical_roundtrip():
    ini_path = FIXTURES_DIR / "QuickTextPaste.ini"
    raw_bytes = ini_path.read_bytes()
    assert detect_encoding(raw_bytes) == "utf-16-le-bom"

    decoded_text, enc = decode_bytes_auto(raw_bytes)
    assert enc == "utf-16-le-bom"

    doc = parse_qtp_ini(decoded_text)
    assert len(doc.items) >= 500
    expected_total = len(doc.items)
    expected_prefix_counts = Counter(item.hotkey_prefix for item in doc.items)

    serialized = serialize_qtp_ini(doc, update_test_ini=False)
    assert serialized == decoded_text

    reencoded = encode_qtp_ini(serialized, encoding="utf-16-le-bom")
    assert reencoded == raw_bytes

    reparsed = parse_qtp_ini(serialized)
    assert len(reparsed.items) == expected_total
    assert Counter(item.hotkey_prefix for item in reparsed.items) == expected_prefix_counts
    assert reparsed.program == doc.program


@pytest.mark.parametrize(
    ("filename", "expected_enc"),
    [
        ("minimal.ini", "utf-16-le-bom"),
        ("encoding_utf16le.ini", "utf-16-le-bom"),
        ("encoding_utf16be.ini", "utf-16-be-bom"),
        ("encoding_utf8bom.ini", "utf-8-bom"),
        ("encoding_cp1254.ini", "cp1254"),
    ],
)
def test_encoding_fixtures_roundtrip(filename: str, expected_enc: str):
    raw = (FIXTURES_DIR / filename).read_bytes()
    assert detect_encoding(raw) == expected_enc

    text, detected = decode_bytes_auto(raw)
    assert detected == expected_enc

    doc = parse_qtp_ini(text)
    assert len(doc.items) >= 1
    assert "Türkçe" in doc.items[0].text or "Merhaba" in doc.items[0].text

    serialized = serialize_qtp_ini(doc)
    assert serialized == text
    reparsed = parse_qtp_ini(serialized)
    assert [it.text for it in reparsed.items] == [it.text for it in doc.items]
    assert [it.hotkey_prefix for it in reparsed.items] == [it.hotkey_prefix for it in doc.items]


def test_bomless_utf16_and_utf8_autodetect():
    sample = "[Program]\r\nlng=21\r\n[list_text]\r\ntext_000=L-Win+A=Şğüöçıİ 😊<E<N<D|\r\n"
    for raw, exp in (
        (sample.encode("utf-16-le"), "utf-16-le"),
        (sample.encode("utf-16-be"), "utf-16-be"),
        (sample.encode("utf-8"), "utf-8"),
    ):
        assert detect_encoding(raw) == exp
        decoded, enc = decode_bytes_auto(raw)
        assert enc == exp
        doc = parse_qtp_ini(decoded)
        assert doc.items[0].text == "Şğüöçıİ 😊"
        assert doc.items[0].terminator == "<E<N<D|"


def test_edge_cases_empty_program_only_list_text_only_crlf_and_mixed_terminators():
    empty_doc = parse_qtp_ini("")
    assert empty_doc.items == []
    assert serialize_qtp_ini(empty_doc) == ""

    prog_only = "[Program]\r\nlng=21\r\nstart_tray=1\r\n"
    prog_doc = parse_qtp_ini(prog_only)
    assert prog_doc.items == []
    assert prog_doc.program["lng"] == "21"
    assert serialize_qtp_ini(prog_doc) == prog_only

    lt_only = "[list_text]\ntext_000=L-Win+Z=Satır 1\\nSatır 2<E<N<D|\n"
    lt_doc = parse_qtp_ini(lt_only)
    assert len(lt_doc.items) == 1
    assert lt_doc.items[0].text == "Satır 1\nSatır 2"
    assert serialize_qtp_ini(lt_doc) == lt_only

    mixed = (
        "[Program]\r\nTestIni=42\r\n"
        "[list_text]\r\n"
        "text_000=L-Win+A=Enter gönderir<E<N<D|\r\n"
        "text_001=L-Win+Z=Enter göndermez\r\n"
        "[list_order]\r\ntext_000=1\r\ntext_001=2\r\n"
        "[list_label]\r\ntext_000=Partner/Birinci\r\ntext_001=Düz Etiket\r\n"
    )
    mixed_doc = parse_qtp_ini(mixed)
    assert mixed_doc.items[0].terminator == "<E<N<D|"
    assert mixed_doc.items[1].terminator == ""
    assert mixed_doc.items[1].group == "Genel"
    assert mixed_doc.items[1].label == "Düz Etiket"
    assert serialize_qtp_ini(mixed_doc) == mixed


@pytest.mark.parametrize(
    ("bad_content", "expected_substr"),
    [
        ("bu geçerli bir ini değildir", "Bölüm ([...]) başlığı dışında içerik bulundu"),
        ("[Program\r\nlng=21\r\n", "Bölüm başlığı düzgün kapatılmamış"),
        ("[]\r\n", "Boş bölüm adı kullanılamaz"),
        ("[Program]\r\nhatali_satir\r\n", "Anahtar=değer biçimi bekleniyor"),
        ("[list_text]\r\ntext_000=eksik_esittir\r\n", "[list_text] satırı 'kimlik=kısayol=metin' biçiminde değil"),
        ("[list_order]\r\ntext_000=abc\r\n", "[list_order] sayısal değer bekliyor"),
        ("[Program]\r\n\x00", "geçersiz ikili (null) karakter içeriyor"),
    ],
)
def test_malformed_ini_raises_turkish_error_matching_sss(bad_content: str, expected_substr: str):
    sss_text = (ROOT_DIR / "docs" / "SSS.md").read_text(encoding="utf-8")
    assert expected_substr in sss_text

    with pytest.raises(IniParseError) as exc_info:
        parse_qtp_ini(bad_content)
    assert expected_substr in str(exc_info.value)


def test_corrupt_utf16_bom_and_null_bytes_raise_ini_parse_error():
    sss_text = (ROOT_DIR / "docs" / "SSS.md").read_text(encoding="utf-8")
    with pytest.raises(IniParseError) as exc_le:
        decode_bytes_auto(b"\xff\xfe\x41\x00\x42")
    assert "bozuk veya eksik UTF-16 LE bayt dizisi" in str(exc_le.value)
    assert "bozuk veya eksik UTF-16 LE bayt dizisi" in sss_text

    with pytest.raises(IniParseError) as exc_null:
        decode_bytes_auto(b"abc\x00def")
    assert "geçersiz ikili (null) bayt içeriği" in str(exc_null.value)
    assert "geçersiz ikili (null) bayt içeriği" in sss_text


def test_write_qtp_ini_creates_utf16le_bom_and_bak_backup(tmp_path: Path):
    target = tmp_path / "QuickTextPaste.ini"
    ini_v1 = build_qtp_ini([{"keys": "L-Win+A", "group": "Test", "label": "İlk", "text": "Birinci"}])
    write_qtp_ini(target, ini_v1, create_bak=True)
    assert target.read_bytes().startswith(b"\xff\xfe")
    assert not (tmp_path / "QuickTextPaste.ini.bak").exists()

    ini_v2 = build_qtp_ini([{"keys": "L-Win+Z", "group": "Test", "label": "İki", "text": "İkinci"}])
    write_qtp_ini(target, ini_v2, create_bak=True)
    bak = tmp_path / "QuickTextPaste.ini.bak"
    assert bak.is_file()
    assert "Birinci" in read_text_auto(bak)
    assert "İkinci" in read_text_auto(target)


def test_qtp_item_helpers_extra_sections_and_encoding_variants():
    from qtp_app.core.ini_parser import QtpItem, parse_qtp_ini_full

    it = QtpItem.from_dict(
        {"keys": "L-Win+A", "group": "Test", "label": "Lbl", "text": "Merhaba", "order": "bad", "favorite": True, "copyCount": 3},
        index=5,
    )
    assert it.keys == "L-Win+A"
    it.keys = "L-Win+Z"
    assert it.hotkey_prefix == "L-Win+Z"
    assert it.order is None
    meta_d = it.to_dict(include_meta=True)
    assert meta_d["favorite"] is True and meta_d["copyCount"] == 3

    ini_extra = (
        "; Üst yorum satırı\r\n"
        "[Program]\r\n"
        "lng=21\r\n"
        "[list_text]\r\n"
        "text_000=L-Win+A=Metin<E<N<D|\r\n"
        "[list_order]\r\n"
        "text_000=1\r\n"
        "[list_label]\r\n"
        "text_000=Grup/Etiket\r\n"
        "[CustomSection]\r\n"
        "; Ek bölüm yorumu\r\n"
        "ozel=123\r\n"
    )
    doc = parse_qtp_ini(ini_extra)
    assert len(doc.extra_sections) == 1
    assert doc.extra_sections[0]["name"] == "CustomSection"
    assert serialize_qtp_ini(doc, update_test_ini=True).startswith("[Program]")
    full = parse_qtp_ini_full(ini_extra)
    assert len(full["items"]) == 1

    for enc in ("utf-8-bom", "utf-8", "utf-16-be-bom", "cp1254", "utf-16-le-bom"):
        encoded = encode_qtp_ini("Şğüöç", encoding=enc)
        txt, _ = decode_bytes_auto(encoded)
        assert txt == "Şğüöç"

    rebuilt_no_winrc = build_qtp_ini(
        [{"keys": "L-Win+A", "group": "", "label": "", "text": "Uzun " * 15}],
        m_show_tree=None,
        keep_winrc=False,
        extra_sections=[{"name": "Ek", "lines": ["a=b"]}],
    )
    assert "WinRC=" not in rebuilt_no_winrc
    assert "[Ek]" in rebuilt_no_winrc

