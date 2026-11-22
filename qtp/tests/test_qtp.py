#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QTP Full-Stack Kapsamlı Test Paketi
- Kodlama algılama (UTF-16 LE BOM, BOM'suz UTF-16 LE, UTF-16 BE BOM, UTF-8 BOM, CP1254)
- Kayıpsız INI <-> JSON dönüşümü ([Program] ayarları, ek bölümler, iç içe alt menüler, '=' işaretli metinler)
- Yedekleme oluşturma ve geri yükleme
- Full-Stack REST API (GET/POST /api/data, /api/import, /api/backups, /api/export/ini, CORS/PNA)
- index.html içindeki JS parser/builder ile qtp_core.py uyumluluk testi (Node.js mevcutsa)
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock

import qtp_core
import qtp_server


ROOT_DIR = Path(__file__).resolve().parent.parent


class TestQtpCore(unittest.TestCase):
    def test_sample_ini_and_json_match(self):
        ini_text = qtp_core.read_text_auto(ROOT_DIR / "QuickTextPaste.ini")
        parsed = qtp_core.parse_qtp_ini_full(ini_text)
        json_items = json.loads((ROOT_DIR / "data.json").read_text(encoding="utf-8"))
        self.assertEqual(len(parsed["items"]), 73)
        self.assertEqual(parsed["items"], json_items)
        self.assertEqual(parsed["program"].get("lng"), "21")
        self.assertEqual(parsed["program"].get("m_show_tree"), "1")

    def test_encoding_autodetect(self):
        sample = "[Program]\r\nlng=21\r\n[list_text]\r\ntext_000=L-Win+A=Şğüöçıİ 😊<E<N<D|\r\n"
        variants = [
            b"\xff\xfe" + sample.encode("utf-16-le"),
            b"\xfe\xff" + sample.encode("utf-16-be"),
            sample.encode("utf-16-le"),  # BOM'suz UTF-16 LE
            b"\xef\xbb\xbf" + sample.encode("utf-8"),
            sample.encode("utf-8"),
        ]
        for raw in variants:
            decoded, _enc = qtp_core.decode_bytes_auto(raw)
            items = qtp_core.parse_qtp_ini(decoded)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["text"], "Şğüöçıİ 😊")

        cp_sample = "[list_text]\r\ntext_000=L-Win+A=Türkçe şğıöç<E<N<D|\r\n"
        decoded_cp, enc_cp = qtp_core.decode_bytes_auto(cp_sample.encode("cp1254"))
        self.assertEqual(enc_cp, "cp1254")
        self.assertEqual(qtp_core.parse_qtp_ini(decoded_cp)[0]["text"], "Türkçe şğıöç")

    def test_lossless_ini_roundtrip_with_extra_sections_and_nested_groups(self):
        ini_src = (
            "[Program]\r\n"
            "TestIni=1700000000\r\n"
            "m_show_tree=1\r\n"
            "listcmd_count=3\r\n"
            "WinRC=10;20;800;600;1;x,y,w,h,SW\r\n"
            "lng=21\r\n"
            "start_tray=1\r\n"
            "restore_old_clipboard=1\r\n"
            "use_date_format=dd.MM.yyyy\r\n"
            "[list_text]\r\n"
            "text_002=L-Ctrl+3=Üçüncü = işaretli\\nSatır 2<E<N<D|\r\n"
            "text_000=L-Win+Z=Birinci metin<E<N<D|\r\n"
            "text_001==Kısayolsuz metin<E<N<D|\r\n"
            "[list_order]\r\n"
            "text_000=1\r\n"
            "text_001=2\r\n"
            "[list_label]\r\n"
            "text_000=Destek/Kurye/Karşılama\r\n"
            "text_001=Düz Etiket\r\n"
            "text_002=Alt/Üçüncü\r\n"
            "[CustomExtra]\r\n"
            "foo=bar\r\n"
        )
        parsed = qtp_core.parse_qtp_ini_full(ini_src)
        items = parsed["items"]
        self.assertEqual(len(items), 3)
        # Sıralama: text_000 (1), text_001 (2), text_002 (list_order'da yok -> en sonda!)
        self.assertEqual(items[0]["group"], "Destek/Kurye")
        self.assertEqual(items[0]["label"], "Karşılama")
        self.assertEqual(items[1]["keys"], "")
        self.assertEqual(items[1]["group"], "Genel")
        self.assertEqual(items[1]["label"], "Düz Etiket")
        self.assertEqual(items[2]["text"], "Üçüncü = işaretli\nSatır 2")

        rebuilt = qtp_core.build_qtp_ini(
            items,
            program=parsed["program"],
            extra_sections=parsed["extra_sections"],
        )
        reparsed = qtp_core.parse_qtp_ini_full(rebuilt)
        self.assertEqual(reparsed["items"], items)
        self.assertEqual(reparsed["program"].get("restore_old_clipboard"), "1")
        self.assertEqual(reparsed["program"].get("use_date_format"), "dd.MM.yyyy")
        self.assertEqual(reparsed["program"].get("WinRC"), "10;20;800;600;1;x,y,w,h,SW")
        self.assertEqual(reparsed["extra_sections"], [{"name": "CustomExtra", "lines": ["foo=bar"]}])

    def test_parse_any_content_full_backup(self):
        backup = {
            "type": "qtp-pwa-backup",
            "version": 2,
            "settings": {"theme": "dark", "qtpPrefs": {"lng": 21}},
            "program": {"WinRC": "1;2;3;4;1;x,y,w,h,SW"},
            "items": [{"keys": "L-Win+A", "group": "Test", "label": "Merhaba", "text": "Selam", "favorite": True}],
        }
        parsed = qtp_core.parse_any_content(json.dumps(backup), "yedek.json")
        self.assertEqual(parsed["kind"], "backup")
        self.assertEqual(len(parsed["items"]), 1)
        self.assertTrue(parsed["items"][0]["favorite"])
        self.assertEqual(parsed["program"].get("WinRC"), "1;2;3;4;1;x,y,w,h,SW")

    def test_install_quicktextpaste_extracts_safe_exe_and_creates_ini(self):
        tmp = Path(tempfile.mkdtemp(prefix="qtp_inst_test_"))
        try:
            (tmp / "data.json").write_text(
                json.dumps([{"keys": "L-Win+A", "group": "Test", "label": "Hi", "text": "Merhaba"}]),
                encoding="utf-8",
            )
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("../evil.exe", b"BAD" * 100)
                zf.writestr("QuickTextPaste_x64_p.exe", b"MZ" + b"\x00" * 60000)
            zip_bytes = buf.getvalue()

            class FakeResp:
                def __enter__(self): return self
                def __exit__(self, *a): return False
                def read(self): return zip_bytes

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(tmp / "la"), "APPDATA": str(tmp / "ad")}), \
                 mock.patch("qtp_core.find_quicktextpaste_exe", side_effect=[None, tmp / "QuickTextPaste_x64_p.exe"]), \
                 mock.patch("urllib.request.urlopen", return_value=FakeResp()):
                res = qtp_core.install_quicktextpaste(tmp)

            self.assertTrue(res["ok"])
            self.assertFalse(res["already_installed"])
            self.assertTrue((tmp / "QuickTextPaste_x64_p.exe").is_file())
            self.assertTrue((tmp / "QuickTextPaste.ini").is_file())
            self.assertFalse((tmp.parent / "evil.exe").exists())
            parsed_ini = qtp_core.parse_qtp_ini(qtp_core.read_text_auto(tmp / "QuickTextPaste.ini"))
            self.assertEqual(len(parsed_ini), 1)
            self.assertEqual(parsed_ini[0]["text"], "Merhaba")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestFullStackServer(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="qtp_srv_test_"))
        for fname in ("index.html", "cevaplar.html", "data.json", "QuickTextPaste.ini", "manifest.webmanifest", "sw.js"):
            shutil.copy2(ROOT_DIR / fname, self.tmp / fname)

        self.env_patch = mock.patch.dict(os.environ, {
            "APPDATA": str(self.tmp / "appdata"),
            "LOCALAPPDATA": str(self.tmp / "localappdata"),
        })
        self.env_patch.start()
        self.qtp_exe_patch = mock.patch("qtp_core.find_quicktextpaste_exe", return_value=None)
        self.qtp_exe_patch.start()

        self.srv = qtp_server.create_http_server(self.tmp, host="127.0.0.1", port=0)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.qtp_exe_patch.stop()
        self.env_patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _req(self, path: str, method: str = "GET", body: dict | None = None, headers: dict | None = None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req_headers = {"Origin": "https://m-sonmez.github.io"}
        if headers:
            req_headers.update(headers)
        if data is not None:
            req_headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, dict(resp.headers), resp.read()

    def test_api_lifecycle_crud_import_and_backups(self):
        # 1. CORS + Private Network Access Preflight
        status, hdrs, _ = self._req(
            "/api/status",
            method="OPTIONS",
            headers={"Access-Control-Request-Private-Network": "true"},
        )
        self.assertEqual(status, 204)
        self.assertEqual(hdrs.get("Access-Control-Allow-Origin"), "https://m-sonmez.github.io")
        self.assertEqual(hdrs.get("Access-Control-Allow-Private-Network"), "true")

        # 2. GET /api/data
        status, _, raw = self._req("/api/data")
        self.assertEqual(status, 200)
        data = json.loads(raw.decode("utf-8"))
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["items"]), 73)

        # 3. POST /api/data (yeni kayıt + disk senkronizasyonu + otomatik yedek)
        updated = data["items"] + [{"keys": "L-Ctrl+1", "group": "TestGrup", "label": "Yeni", "text": "Merhaba Dünya!"}]
        status, _, raw = self._req("/api/data", method="POST", body={
            "items": updated,
            "createBackup": True,
            "backupReason": "unit_test",
            "reloadQtp": False,
        })
        self.assertEqual(status, 200)
        res = json.loads(raw.decode("utf-8"))
        self.assertEqual(res["count"], 74)

        # Disk üzerindeki data.json ve QuickTextPaste.ini gerçekten güncellendi mi?
        self.assertEqual(len(json.loads((self.tmp / "data.json").read_text(encoding="utf-8"))), 74)
        ini_parsed = qtp_core.parse_qtp_ini(qtp_core.read_text_auto(self.tmp / "QuickTextPaste.ini"))
        self.assertEqual(len(ini_parsed), 74)
        self.assertEqual(ini_parsed[-1]["text"], "Merhaba Dünya!")

        # 4. POST /api/import (INI yükleyip tümünü değiştirme)
        custom_ini = "[Program]\r\nlng=21\r\nWinRC=1;2;3;4;1;x,y,w,h,SW\r\n[list_text]\r\ntext_000=L-Alt+Q=Özel INI kaydı<E<N<D|\r\n[list_order]\r\ntext_000=1\r\n[list_label]\r\ntext_000=Özel/Deneme\r\n"
        status, _, raw = self._req("/api/import", method="POST", body={
            "content": custom_ini,
            "filename": "QuickTextPaste.ini",
            "mode": "replace",
            "reloadQtp": False,
        })
        self.assertEqual(status, 200)
        imp = json.loads(raw.decode("utf-8"))
        self.assertEqual(imp["count"], 1)
        self.assertEqual(imp["state"]["items"][0]["label"], "Deneme")

        # 5. Yedekleri listele ve önceki 73/74 kayıtlı yedeğe geri dön
        _, _, raw_b = self._req("/api/backups")
        backups = json.loads(raw_b.decode("utf-8"))["backups"]
        self.assertGreaterEqual(len(backups), 2)
        target_bak = next(b for b in backups if b["count"] == 73)
        status, _, raw_r = self._req("/api/backups/restore", method="POST", body={"id": target_bak["id"], "reloadQtp": False})
        self.assertEqual(status, 200)
        restored = json.loads(raw_r.decode("utf-8"))
        self.assertEqual(len(restored["state"]["items"]), 73)

        # 6. Export INI (UTF-16 LE BOM doğrulama)
        _, _, ini_bytes = self._req("/api/export/ini")
        self.assertTrue(ini_bytes.startswith(b"\xff\xfe"))


class TestHtmlJsParity(unittest.TestCase):
    def test_index_html_ini_parser_and_builder_with_node(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js kurulu değil")

        html = (ROOT_DIR / "index.html").read_text(encoding="utf-8")
        marker_start = "// QuickTextPaste.ini <-> data.json Kayıpsız Dönüştürücü"
        marker_end = "// Yardımcı Fonksiyonlar"
        s_idx = html.index(marker_start)
        e_idx = html.index(marker_end)
        js_block = (
            "const DEFAULT_QTP_PREFS = { m_show_tree: 1, lng: 21, start_tray: 1, WinRC: '2399;17;3368;1335;1;x,y,w,h,SW' };\n"
            + html[s_idx:e_idx]
        )

        test_script = js_block + """
const assert = require('assert');
const sampleIni = [
  '[Program]',
  'm_show_tree=1',
  'WinRC=5;6;7;8;1;x,y,w,h,SW',
  'custom_opt=42',
  '[list_text]',
  'text_001=L-Win+B=İkinci satır\\\\nDevam<E<N<D|',
  'text_000=L-Win+A=Birinci = değer<E<N<D|',
  '[list_order]',
  'text_000=1',
  '[list_label]',
  'text_000=Grup/Alt/Başlık',
  'text_001=Tek Etiket',
  '[ExtraSec]',
  'k=v'
].join('\\r\\n');

const parsed = parseQtpIni(sampleIni);
assert.strictEqual(parsed.items.length, 2);
assert.strictEqual(parsed.items[0].group, 'Grup/Alt');
assert.strictEqual(parsed.items[0].label, 'Başlık');
assert.strictEqual(parsed.items[0].text, 'Birinci = değer');
assert.strictEqual(parsed.items[1].group, 'Genel');
assert.strictEqual(parsed.items[1].label, 'Tek Etiket');
assert.strictEqual(parsed.items[1].text, 'İkinci satır\\nDevam');
assert.strictEqual(parsed.program.custom_opt, '42');
assert.strictEqual(parsed.extraSections.length, 1);

const rebuilt = buildQtpIni(parsed.items, { program: parsed.program, extraSections: parsed.extraSections });
const bytes = encodeUtf16LeBom(rebuilt);
assert.strictEqual(bytes[0], 0xFF);
assert.strictEqual(bytes[1], 0xFE);
const decoded = decodeBytesAutoWithInfo(bytes);
assert.strictEqual(decoded.encoding, 'utf-16-le-bom');
const reparsed = parseQtpIni(decoded.text);
assert.deepStrictEqual(reparsed.items, parsed.items);
assert.strictEqual(reparsed.program.custom_opt, '42');
assert.deepStrictEqual(reparsed.extraSections, parsed.extraSections);
console.log('JS_PARITY_OK');
"""
        proc = subprocess.run([node, "-e", test_script], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, msg=f"STDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}")
        self.assertIn("JS_PARITY_OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
