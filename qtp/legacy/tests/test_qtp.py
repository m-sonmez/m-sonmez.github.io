#!/usr/bin/env python3
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
import sys
from unittest import mock

LEGACY_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = LEGACY_DIR.parent
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

import qtp_core
import qtp_server


class TestQtpCore(unittest.TestCase):
    def test_sample_ini_and_json_match(self):
        ini_text = qtp_core.read_text_auto(ROOT_DIR / "QuickTextPaste.ini")
        parsed = qtp_core.parse_qtp_ini_full(ini_text)
        json_items = json.loads((ROOT_DIR / "data.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(json_items), 500)
        self.assertEqual(len(parsed["items"]), len(json_items))
        self.assertEqual(parsed["items"], json_items)
        self.assertEqual(parsed["program"].get("lng"), "21")
        self.assertEqual(parsed["program"].get("m_show_tree"), "1")

    def test_high_count_1200_records_ini_roundtrip(self):
        items = [
            {
                "keys": "L-Win+A" if i % 2 == 0 else "L-Win+Z",
                "group": f"Rol{i % 5} - Alt Kategori {i % 13}",
                "label": f"Başlık {i}",
                "text": f"Hazır cevap #{i} (Türkçe şğıöç = test)\nİkinci satır {i}",
            }
            for i in range(1200)
        ]
        ini_text = qtp_core.build_qtp_ini(items)
        self.assertIn("listcmd_count=1200\r\n", ini_text)
        self.assertIn("text_000=", ini_text)
        self.assertIn("text_526=", ini_text)
        self.assertIn("text_1199=", ini_text)
        reparsed = qtp_core.parse_qtp_ini_full(ini_text)
        self.assertEqual(len(reparsed["items"]), 1200)
        self.assertEqual(reparsed["items"], items)

    def test_load_state_prevents_stale_ini_overwrite(self):
        tmp = Path(tempfile.mkdtemp(prefix="qtp_stale_ini_"))
        try:
            old_items = [{"keys": "L-Win+Z", "group": "Eski", "label": f"E{i}", "text": f"Eski {i}"} for i in range(73)]
            new_items = json.loads((ROOT_DIR / "data.json").read_text(encoding="utf-8"))

            qtp_core.save_state(tmp, old_items, create_backup_flag=False)
            (tmp / "data.json").write_text(json.dumps(new_items, ensure_ascii=False, indent=2), encoding="utf-8")
            now = 1800000000.0
            os.utime(tmp / "data.json", (now, now))
            os.utime(tmp / "QuickTextPaste.ini", (now + 10.0, now + 10.0))

            state = qtp_core.load_state(tmp)
            self.assertEqual(state["source"], "data.json")
            self.assertEqual(len(state["items"]), len(new_items))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_encoding_autodetect(self):
        sample = "[Program]\r\nlng=21\r\n[list_text]\r\ntext_000=L-Win+A=Şğüöçıİ 😊<E<N<D|\r\n"
        variants = [
            b"\xff\xfe" + sample.encode("utf-16-le"),
            b"\xfe\xff" + sample.encode("utf-16-be"),
            sample.encode("utf-16-le"),
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
        for fname in ("index.html", "qtp.html", "data.json", "QuickTextPaste.ini", "manifest.webmanifest", "sw.js"):
            if (ROOT_DIR / fname).is_file():
                shutil.copy2(ROOT_DIR / fname, self.tmp / fname)
        (self.tmp / "legacy").mkdir(exist_ok=True)
        shutil.copy2(LEGACY_DIR / "cevaplar.html", self.tmp / "legacy" / "cevaplar.html")
        shutil.copy2(LEGACY_DIR / "cevaplar.html", self.tmp / "cevaplar.html")

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
        status, hdrs, _ = self._req(
            "/api/status",
            method="OPTIONS",
            headers={"Access-Control-Request-Private-Network": "true"},
        )
        self.assertEqual(status, 204)
        self.assertEqual(hdrs.get("Access-Control-Allow-Origin"), "https://m-sonmez.github.io")
        self.assertEqual(hdrs.get("Access-Control-Allow-Private-Network"), "true")

        status, _, raw = self._req("/api/data")
        self.assertEqual(status, 200)
        data = json.loads(raw.decode("utf-8"))
        self.assertTrue(data["ok"])
        initial_count = len(data["items"])
        self.assertGreaterEqual(initial_count, 500)

        updated = data["items"] + [{"keys": "L-Ctrl+1", "group": "TestGrup", "label": "Yeni", "text": "Merhaba Dünya!"}]
        status, _, raw = self._req("/api/data", method="POST", body={
            "items": updated,
            "createBackup": True,
            "backupReason": "unit_test",
            "reloadQtp": False,
        })
        self.assertEqual(status, 200)
        res = json.loads(raw.decode("utf-8"))
        self.assertEqual(res["count"], initial_count + 1)

        self.assertEqual(len(json.loads((self.tmp / "data.json").read_text(encoding="utf-8"))), initial_count + 1)
        ini_parsed = qtp_core.parse_qtp_ini(qtp_core.read_text_auto(self.tmp / "QuickTextPaste.ini"))
        self.assertEqual(len(ini_parsed), initial_count + 1)
        self.assertEqual(ini_parsed[-1]["text"], "Merhaba Dünya!")

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

        live_items = json.loads((ROOT_DIR / "data.json").read_text(encoding="utf-8"))
        status, exp_hdrs, post_ini_bytes = self._req("/api/export/ini", method="POST", body={
            "items": live_items,
            "encoding": "utf-16-le-bom",
        })
        self.assertEqual(status, 200)
        self.assertTrue(post_ini_bytes.startswith(b"\xff\xfe"))
        self.assertEqual(exp_hdrs.get("X-QTP-Count"), str(len(live_items)))
        post_decoded, _ = qtp_core.decode_bytes_auto(post_ini_bytes)
        self.assertIn(f"listcmd_count={len(live_items)}\r\n", post_decoded)
        post_reparsed = qtp_core.parse_qtp_ini(post_decoded)
        self.assertEqual(len(post_reparsed), len(live_items))

        status, _, raw = self._req("/api/import", method="POST", body={
            "content": json.dumps(live_items, ensure_ascii=False),
            "filename": "data.json",
            "mode": "replace",
            "reloadQtp": False,
        })
        self.assertEqual(status, 200)
        imp_527 = json.loads(raw.decode("utf-8"))
        self.assertEqual(imp_527["count"], len(live_items))

        _, _, raw_b = self._req("/api/backups")
        backups = json.loads(raw_b.decode("utf-8"))["backups"]
        self.assertGreaterEqual(len(backups), 2)
        target_bak = next(b for b in backups if b["count"] == initial_count)
        status, _, raw_r = self._req("/api/backups/restore", method="POST", body={"id": target_bak["id"], "reloadQtp": False})
        self.assertEqual(status, 200)
        restored = json.loads(raw_r.decode("utf-8"))
        self.assertEqual(len(restored["state"]["items"]), initial_count)

        _, get_hdrs, ini_bytes = self._req("/api/export/ini")
        self.assertTrue(ini_bytes.startswith(b"\xff\xfe"))
        self.assertEqual(get_hdrs.get("X-QTP-Count"), str(initial_count))
        get_decoded, _ = qtp_core.decode_bytes_auto(ini_bytes)
        self.assertIn(f"listcmd_count={initial_count}\r\n", get_decoded)
        self.assertEqual(len(qtp_core.parse_qtp_ini(get_decoded)), initial_count)


class TestHtmlJsParity(unittest.TestCase):
    def test_no_hardcoded_default_items_and_size_reduction(self):
        import re as _re

        index_path = ROOT_DIR / "index.html"
        qtp_html_path = ROOT_DIR / "qtp.html"
        cevaplar_path = LEGACY_DIR / "cevaplar.html"
        index_html = index_path.read_text(encoding="utf-8")
        qtp_html = qtp_html_path.read_text(encoding="utf-8")
        cevaplar_html = cevaplar_path.read_text(encoding="utf-8")

        for blob in (index_html, qtp_html, cevaplar_html):
            self.assertNotIn("DEFAULT_ITEMS", blob)
            self.assertNotIn("Talebinizi detaylı olarak iletmeniz halinde", blob)
            self.assertIsNone(_re.search(r'\[\s*\{"keys"\s*:', blob))

        self.assertNotIn("http://", qtp_html)
        self.assertNotIn("https://", qtp_html)
        self.assertIn("./theme.css", qtp_html)
        self.assertIn("./index.html", qtp_html)
        self.assertIn("./qtp.html", index_html)
        self.assertIn("./legacy/cevaplar.html", index_html)
        self.assertIn("standaloneDownloadMeta", index_html)

        idx_scripts = _re.findall(r"<script>([\s\S]*?)</script>", index_html)
        self.assertGreaterEqual(len(idx_scripts), 3)
        self.assertLess(len(idx_scripts[2].encode("utf-8")), 105_000)

        sw_js = (ROOT_DIR / "sw.js").read_text(encoding="utf-8")
        self.assertIn("qtp-pwa-cache-v3.5.1", sw_js)
        self.assertIn("/api/", sw_js)
        self.assertIn("data.json", sw_js)
        self.assertIn("./theme.css", sw_js)
        self.assertIn("./qtp.html", sw_js)
        self.assertIn("./legacy/cevaplar.html", sw_js)
        self.assertIn("./QuickTextPaste.ini", sw_js)
        self.assertIn("./docs/KURULUM.md", sw_js)

    def test_index_html_ini_parser_and_builder_with_node(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js kurulu değil")

        idx_html_old = (ROOT_DIR / "index.html").read_text(encoding="utf-8")
        marker_start = "function detectUtf16NoBom(uint8) {"
        marker_end = "function genId() {"
        s_idx = idx_html_old.index(marker_start)
        e_idx = idx_html_old.index(marker_end)
        js_block = (
            "const DEFAULT_QTP_PREFS = { m_show_tree: 1, lng: 21, start_tray: 1, WinRC: '2399;17;3368;1335;1;x,y,w,h,SW' };\n"
            + idx_html_old[s_idx:e_idx]
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

        qtp_html = (ROOT_DIR / "qtp.html").read_text(encoding="utf-8")
        u_start = qtp_html.index("function decodeBytesAuto(uint8) {")
        u_end = qtp_html.index("function formatIniPreview(")
        u_js = (
            "const DEFAULT_TERMINATOR = '<E<N<D|';\n"
            + qtp_html[u_start:u_end]
            + "\nconst assert = require('assert');\nconst s = '[Program]\\r\\nlng=21\\r\\n[list_text]\\r\\ntext_000=L-Win+A=Şğü = ok<E<N<D|\\r\\n[list_order]\\r\\ntext_000=1\\r\\n[list_label]\\r\\ntext_000=A/Etiket\\r\\n';\nconst p = parseQtpIni(s);\nassert.strictEqual(p.items[0].text, 'Şğü = ok');\nconst r = buildQtpIni(p.items, p.program, p.extraSections);\nconst b = encodeUtf16LeBom(r);\nassert.strictEqual(b[0], 0xFF); assert.strictEqual(b[1], 0xFE);\nconst dec = decodeBytesAuto(b);\nassert.strictEqual(dec.encoding, 'utf-16-le-bom');\nconsole.log('UNIFIED_JS_INI_OK');\n"
        )
        proc_u = subprocess.run([node, "-e", u_js], capture_output=True, text=True, check=False)
        self.assertEqual(proc_u.returncode, 0, msg=f"STDERR:\n{proc_u.stderr}\nSTDOUT:\n{proc_u.stdout}")
        self.assertIn("UNIFIED_JS_INI_OK", proc_u.stdout)

    def test_qtp_app_vm_import_export_527_filters_and_header_state(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js kurulu değil")

        vm_script = r"""
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const rootDir = process.env.QTP_ROOT;
const html = fs.readFileSync(path.join(rootDir, 'index.html'), 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
const appScript = scripts[2];
const dataJsonBytes = fs.readFileSync(path.join(rootDir, 'data.json'));
const dataJsonArr = JSON.parse(dataJsonBytes.toString('utf8'));
assert(dataJsonArr.length >= 527, 'data.json en az 527 kayıt içermeli');

function createHarness({ proto = 'https:', host = 'm-sonmez.github.io', lsInit = {}, failFetch = false } = {}) {
  const ls = { ...lsInit };
  const downloaded = [];
  const sandbox = {
    console, setTimeout, clearTimeout, TextEncoder, TextDecoder, ArrayBuffer, DataView, Uint8Array,
    Blob: class FakeBlob { constructor(parts, opts) { this.parts = parts; this.type = opts?.type || ''; } },
    URL: { createObjectURL: (b) => { downloaded.push(b); return 'blob:fake'; }, revokeObjectURL: () => {} },
    window: {
      addEventListener: () => {},
      location: { hostname: host, protocol: proto, origin: `${proto}//${host}` },
      getSelection: () => null,
    },
    navigator: { onLine: true, storage: null },
    document: {
      documentElement: { classList: { toggle: () => {} } },
      addEventListener: () => {},
      querySelector: () => null,
      createElement: () => ({ style: {}, click: () => {}, setAttribute: () => {} }),
      body: { appendChild: () => {}, removeChild: () => {} },
      activeElement: null,
    },
    localStorage: {
      getItem: (k) => (k in ls ? ls[k] : null),
      setItem: (k, v) => { ls[k] = String(v); },
    },
    fetch: async (url) => {
      if (failFetch) throw new Error('CORS blocked');
      if (String(url).includes('data.json')) {
        return { ok: true, json: async () => JSON.parse(JSON.stringify(dataJsonArr)) };
      }
      return { ok: false, status: 404 };
    },
  };
  sandbox.window.window = sandbox.window;
  sandbox.location = sandbox.window.location;
  vm.runInNewContext(appScript, sandbox);
  const app = sandbox.qtpApp();
  app.$nextTick = (fn) => fn();
  app.$refs = {};
  return { app, sandbox, ls, downloaded };
}

(async () => {
  const h1 = createHarness();
  await h1.app.init();
  assert.strictEqual(h1.app.items.length, dataJsonArr.length);
  assert.strictEqual(h1.app.allGroups.length, 39);
  assert.strictEqual(JSON.stringify(h1.app.selectedGroups), '[]');

  const old73 = dataJsonArr.slice(0, 73);
  const h2 = createHarness({
    lsInit: {
      qtp_pwa_items_v2: JSON.stringify(old73),
      qtp_pwa_meta_v2: JSON.stringify({ updatedAt: 1000, count: 73, sourceKind: 'edit', unsyncedToServer: false }),
    },
  });
  await h2.app.init();
  assert.strictEqual(h2.app.items.length, 73);

  const fakeFile = {
    name: 'data.json',
    arrayBuffer: async () => dataJsonBytes.buffer.slice(dataJsonBytes.byteOffset, dataJsonBytes.byteOffset + dataJsonBytes.byteLength),
  };
  await h2.app.processIncomingFiles([fakeFile], false);
  assert.strictEqual(h2.app.importSummary.records.length, dataJsonArr.length);
  assert.strictEqual(h2.app.importMode, 'replace');
  await h2.app.confirmImport();
  assert.strictEqual(h2.app.items.length, dataJsonArr.length);

  await h2.app.confirmIniExport();
  assert.strictEqual(h2.downloaded.length, 1);
  const exportedBytes = h2.downloaded[0].parts[0];
  assert.strictEqual(exportedBytes[0], 0xFF);
  assert.strictEqual(exportedBytes[1], 0xFE);
  const decodedIni = h2.sandbox.decodeBytesAutoWithInfo(exportedBytes).text;
  assert(decodedIni.includes(`listcmd_count=${dataJsonArr.length}\r\n`));
  assert(decodedIni.includes('text_000='));
  assert(decodedIni.includes(`text_${String(dataJsonArr.length - 1).padStart(3, '0')}=`));
  const reparsed = h2.sandbox.parseQtpIni(decodedIni);
  assert.strictEqual(reparsed.items.length, dataJsonArr.length);
  assert.strictEqual(h2.app.toastMsg, `QuickTextPaste.ini indirildi: ${dataJsonArr.length} kayıt`);

  h2.app.categorySearch = 'musteri odeme';
  const catMatches = h2.app.filteredCategoryOptions.map((g) => g.name);
  assert(catMatches.includes('Müşteri - Ödeme, İade, Bahşiş ve Cüzdan'));

  h2.app.toggleCategorySelection('Müşteri - Ödeme, İade, Bahşiş ve Cüzdan');
  assert.strictEqual(h2.app.selectedGroups.length, 1);
  assert.strictEqual(h2.app.filteredItems.length, 12);
  h2.app.openAddModal();
  assert.strictEqual(h2.app.editorForm.group, 'Müşteri - Ödeme, İade, Bahşiş ve Cüzdan');
  h2.app.editorOpen = false;

  h2.app.toggleCategorySelection('Restoran - Kapanış ve Geri Bildirim');
  assert.strictEqual(h2.app.selectedGroups.length, 2);
  assert.strictEqual(h2.app.filteredItems.length, 18);
  assert(h2.app.categorySummaryLabel.includes('2 kategori seçili (18 kayıt)'));

  h2.app.clearSelectedCategories();
  assert.strictEqual(h2.app.selectedGroups.length, 0);
  const restoranPref = h2.app.categoryPrefixes.find((p) => p.prefix === 'Restoran');
  h2.app.togglePrefixSelection(restoranPref);
  assert.strictEqual(h2.app.selectedGroups.length, 9);
  h2.app.togglePrefixSelection({ ...restoranPref, allSelected: true });
  assert.strictEqual(h2.app.selectedGroups.length, 0);

  await h2.app.toggleHeaderCollapsed(true);
  assert.strictEqual(h2.app.headerCollapsed, true);
  const h3 = createHarness({ lsInit: h2.ls });
  await h3.app.init();
  assert.strictEqual(h3.app.headerCollapsed, true);
  assert.strictEqual(h3.app.items.length, dataJsonArr.length);

  const hFile = createHarness({ proto: 'file:', host: '', failFetch: true });
  await hFile.app.init();
  assert.strictEqual(hFile.app.items.length, 0);
  assert.strictEqual(hFile.app.dataLoadError, 'file-cors');

  console.log('QTP_APP_VM_ALL_OK');
})();
"""
        env = dict(os.environ, QTP_ROOT=str(ROOT_DIR), QTP_LEGACY=str(LEGACY_DIR))
        proc = subprocess.run([node, "-e", vm_script], capture_output=True, text=True, env=env, check=False)
        self.assertEqual(proc.returncode, 0, msg=f"STDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}")
        self.assertIn("QTP_APP_VM_ALL_OK", proc.stdout)

    def test_cevaplar_and_sw_syntax_and_multiselect_with_node(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js kurulu değil")

        vm_script = r"""
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const rootDir = process.env.QTP_ROOT;
const legacyDir = process.env.QTP_LEGACY;
const cevHtml = fs.readFileSync(path.join(legacyDir, 'cevaplar.html'), 'utf8');
const swJs = fs.readFileSync(path.join(rootDir, 'sw.js'), 'utf8');
const scripts = [...cevHtml.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
assert(scripts.length >= 3);
scripts.forEach((s) => new vm.Script(s));
new vm.Script(swJs);

const dataJsonArr = JSON.parse(fs.readFileSync(path.join(rootDir, 'data.json'), 'utf8'));

function makeEl(id) {
  const cls = new Set();
  return {
    id, value: id === 'hotkeyFilter' || id === 'scopeFilter' ? (id === 'scopeFilter' ? 'all' : 'ALL') : (id === 'sortFilter' ? 'default' : ''),
    textContent: '', innerHTML: '', checked: false,
    children: [],
    classList: {
      add: (...a) => a.forEach((c) => cls.add(c)),
      remove: (...a) => a.forEach((c) => cls.delete(c)),
      toggle: (c, f) => { if (f === undefined) { if (cls.has(c)) cls.delete(c); else cls.add(c); } else if (f) cls.add(c); else cls.delete(c); },
      contains: (c) => cls.has(c),
    },
    addEventListener: () => {},
    querySelector: () => makeEl(id + '_child'),
    appendChild: (c) => {},
    focus: () => {}, blur: () => {}, click: () => {},
    contains: () => false,
  };
}
const els = new Map();
const ls = {};
const sandbox = {
  console, setTimeout, clearTimeout, TextEncoder, TextDecoder, Uint8Array, alert: (m) => { throw new Error('alert:' + m); },
  requestAnimationFrame: (fn) => fn(),
  localStorage: { getItem: (k) => (k in ls ? ls[k] : null), setItem: (k, v) => { ls[k] = String(v); } },
  window: { addEventListener: () => {}, location: { hostname: 'm-sonmez.github.io', protocol: 'https:' } },
  document: {
    documentElement: { classList: { toggle: () => {} } },
    activeElement: null,
    getElementById: (id) => { if (!els.has(id)) els.set(id, makeEl(id)); return els.get(id); },
    createElement: (tag) => makeEl(tag),
    addEventListener: () => {},
  },
  fetch: async (url) => {
    if (String(url).includes('data.json')) {
      return { ok: true, json: async () => JSON.parse(JSON.stringify(dataJsonArr)) };
    }
    return { ok: false, status: 404 };
  },
};
sandbox.window.window = sandbox.window;
sandbox.location = sandbox.window.location;
const ctx = vm.createContext(sandbox);
vm.runInContext(scripts[2], ctx);

setTimeout(async () => {
  try {
    const groups = ctx.getAllGroupsMeta();
    assert.strictEqual(groups.length, 39);
    vm.runInContext("categorySearch = 'kurye odeme';", ctx);
    const matches = ctx.getFilteredCategoryOptions(groups).map((g) => g.name);
    assert(matches.includes('Kurye - Ödeme, Nakit ve POS'));
    vm.runInContext("selectedGroups = ['Kurye - Ödeme, Nakit ve POS', 'Restoran - Kapanış ve Geri Bildirim'];", ctx);
    ctx.updateCategoryDropdownUI();
    assert(els.get('catBtnLabel').textContent.includes('2 kategori seçili (21 kayıt)'));
    ctx.render();
    assert(els.get('statsText').textContent.startsWith('21 / ' + dataJsonArr.length));
    await ctx.toggleHeaderCollapsed(true);
    assert.strictEqual(JSON.parse(ls['qtp_pwa_settings_v2']).headerCollapsed, true);
    console.log('CEVAPLAR_AND_SW_VM_OK');
  } catch (e) {
    console.error(e);
    process.exit(1);
  }
}, 50);
"""
        env = dict(os.environ, QTP_ROOT=str(ROOT_DIR), QTP_LEGACY=str(LEGACY_DIR))
        proc = subprocess.run([node, "-e", vm_script], capture_output=True, text=True, env=env, check=False)
        self.assertEqual(proc.returncode, 0, msg=f"STDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}")
        self.assertIn("CEVAPLAR_AND_SW_VM_OK", proc.stdout)

    def test_legacy_python_files_compile_cleanly(self):
        import py_compile

        py_files = sorted(LEGACY_DIR.rglob("*.py"))
        self.assertGreaterEqual(len(py_files), 4)
        for py_path in py_files:
            py_compile.compile(str(py_path), doraise=True)


if __name__ == "__main__":
    unittest.main()
