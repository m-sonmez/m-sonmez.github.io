"""Yerel Web sunucusu (--web), çevrimdışı HTML/CSS, kısayol API ve canlı revizyon yenileme testi."""

from __future__ import annotations

import http.client
import json
import shutil
import threading
import time
from pathlib import Path
from unittest import mock

import pytest

from qtp_app.core.engine import QtpEngine
from qtp_app.core.ini_parser import build_qtp_ini, write_qtp_ini
from qtp_app.ui.theme import ACCENT_CYAN, ACCENT_PURPLE, DARK_PALETTE, FOOTER_HINTS_TEXT
from qtp_app.web import create_web_server, run_web_server


def test_web_ui_has_no_external_urls_and_matches_theme(tmp_path: Path):
    eng = QtpEngine(work_dir=tmp_path)
    srv = create_web_server(eng, host="127.0.0.1", port=0)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        r_html = conn.getresponse()
        assert r_html.status == 200
        html = r_html.read().decode("utf-8")

        conn.request("GET", "/theme.css")
        r_css = conn.getresponse()
        assert r_css.status == 200
        css = r_css.read().decode("utf-8")

        conn.request("GET", "/./theme.css")
        r_rel_css = conn.getresponse()
        assert r_rel_css.status == 200
        assert r_rel_css.read().decode("utf-8") == css

        conn.request("GET", "/icon.svg")
        assert conn.getresponse().status == 200

        conn.request("GET", "/docs/KULLANIM.md")
        assert conn.getresponse().status == 200

        for blob in (html, css):
            assert "http://" not in blob
            assert "https://" not in blob
            assert "//cdn" not in blob
            assert "fonts.googleapis" not in blob

        assert 'href="./theme.css"' in html
        assert 'href="/theme.css"' not in html
        assert "detectBackendMode" in html
        assert "./qtp.exe" in html and "./qtp.bin" in html and "./old.html" in html

        assert ACCENT_PURPLE in css
        assert ACCENT_CYAN in css
        assert DARK_PALETTE.surface in css
        assert DARK_PALETTE.window_bg in css
        assert DARK_PALETTE.text_primary in css

        assert FOOTER_HINTS_TEXT in html
        assert "ArrowDown" in html and "ArrowUp" in html and "F1" in html and "Escape" in html

        conn.request("GET", "/api")
        api_idx = json.loads(conn.getresponse().read().decode("utf-8"))
        assert api_idx["ok"] is True
        assert len(api_idx["data"]["routes"]) >= 18

        conn.request("GET", "/api/completion?shell=powershell")
        comp = json.loads(conn.getresponse().read().decode("utf-8"))
        assert comp["ok"] is True and "Register-ArgumentCompleter" in comp["data"]["script"]

        conn.request("GET", "/api/hotkeys/check")
        chk = json.loads(conn.getresponse().read().decode("utf-8"))
        assert chk["ok"] is True and chk["data"]["clean"] is True

        conn.request(
            "POST",
            "/api/hotkeys/preset",
            body=json.dumps({"preset": "function_keys"}),
            headers={"Content-Type": "application/json"},
        )
        pr = json.loads(conn.getresponse().read().decode("utf-8"))
        assert pr["ok"] is True and pr["data"]["hotkeys"]["all"] == "Ctrl+Shift+F1"

        conn.request(
            "POST",
            "/api/hotkeys/modifiers",
            body=json.dumps({"modifiers": "Win+Ctrl"}),
            headers={"Content-Type": "application/json"},
        )
        mr = json.loads(conn.getresponse().read().decode("utf-8"))
        assert mr["ok"] is True and mr["data"]["hotkeys"]["all"] == "Win+Ctrl+F1"

        conn.request("GET", "/api/help?verbose=1")
        h_resp = json.loads(conn.getresponse().read().decode("utf-8"))
        assert h_resp["ok"] is True
        for key in ("usage", "usage_verbose", "kullanim", "kisayollar", "sss"):
            assert h_resp["data"][key], f"/api/help eksik alan: {key}"
        assert "Ayrıntılı Başvuru (--verbose):" in h_resp["message"]
        assert "btnHelp" in html and "showHelpModal" in html and "/api/help?verbose=1" in html
        assert "helpTabs" in html and "CLI &amp; Parametreler" in html

        conn.request("GET", "/api/revision")
        rev = json.loads(conn.getresponse().read().decode("utf-8"))
        assert rev["ok"] is True and rev["data"]["revision"] >= 2
        assert rev["data"]["initial_category"] == "ALL"
        assert rev["data"]["initial_query"] == ""

        conn.request("GET", "/api/olmayan_rota")
        assert conn.getresponse().status == 404
    finally:
        srv.shutdown()
        srv.server_close()


def test_web_live_hot_reload_from_external_file_changes(tmp_path: Path):
    eng = QtpEngine(work_dir=tmp_path)
    eng.settings["auto_reload_interval_ms"] = 100
    srv = create_web_server(eng, host="127.0.0.1", port=0)
    port = srv.server_address[1]
    eng.start_watcher(debounce_ms=80)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/items")
        before = json.loads(conn.getresponse().read().decode("utf-8"))["data"]["count"]
        assert before >= 500

        new_items = [
            {"keys": "L-Win+A", "group": "Test", "label": f"L{i}", "text": f"Öğe {i}"}
            for i in range(before + 1)
        ]
        write_qtp_ini(tmp_path / "QuickTextPaste.ini", build_qtp_ini(new_items), create_bak=False)

        deadline = time.monotonic() + 3.0
        after = before
        while time.monotonic() < deadline:
            conn.request("GET", "/api/items")
            after = json.loads(conn.getresponse().read().decode("utf-8"))["data"]["count"]
            if after == before + 1:
                break
            time.sleep(0.05)
        assert after == before + 1
    finally:
        eng.stop_watcher()
        srv.shutdown()
        srv.server_close()


def test_web_server_refuses_non_loopback_host(tmp_path: Path):
    eng = QtpEngine(work_dir=tmp_path)
    with pytest.raises(ValueError) as exc:
        create_web_server(eng, host="0.0.0.0", port=0)
    assert "127.0.0.1" in str(exc.value)


def test_web_server_backups_shutdown_and_error_status(tmp_path: Path):
    eng = QtpEngine(work_dir=tmp_path)
    srv = create_web_server(eng, host="127.0.0.1", port=0)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/backups")
        r_bak = conn.getresponse()
        assert r_bak.status == 200 and json.loads(r_bak.read())["ok"] is True

        conn.request("POST", "/api/olmayan", body="{bad")
        assert conn.getresponse().status == 404

        conn.request("POST", "/api/import-ini", body=json.dumps({"path": str(tmp_path / "yok.ini")}))
        assert conn.getresponse().status == 400

        conn.request("POST", "/api/shutdown", body="{}")
        assert conn.getresponse().status == 200
        th.join(timeout=3)
    finally:
        srv.server_close()

    assert run_web_server(eng, port=0, open_browser=False, shutdown_after=0.1, quiet=True) == 0
    with mock.patch("qtp_app.web.create_web_server", side_effect=OSError("Address already in use")):
        assert run_web_server(eng, port=8765) == 1

    import sys
    from qtp_app.web import _read_web_asset

    mei = tmp_path / "mei_web"
    (mei / "qtp_app" / "web").mkdir(parents=True)
    (mei / "qtp_app" / "web" / "index.html").write_text("<h1>frozen</h1>", encoding="utf-8")
    (mei / "qtp_app" / "web" / "theme.css").write_text(":root{}", encoding="utf-8")
    with mock.patch.object(sys, "frozen", True, create=True), \
         mock.patch.object(sys, "_MEIPASS", str(mei), create=True), \
         mock.patch("qtp_app.web.importlib.resources.files", side_effect=RuntimeError("frozen")):
        assert _read_web_asset("index.html") == b"<h1>frozen</h1>"
        assert _read_web_asset("theme.css") == b":root{}"


def test_github_pages_sync_static_http_serving_and_js_syntax(tmp_path: Path):
    import functools
    import http.server
    import re
    import subprocess

    qtp_root = Path(__file__).resolve().parent.parent.parent
    repo_root = qtp_root.parent
    web_dir = qtp_root / "qtp_app" / "web"

    assert (qtp_root / "index.html").read_bytes() == (web_dir / "index.html").read_bytes()
    assert (qtp_root / "theme.css").read_bytes() == (web_dir / "theme.css").read_bytes()
    assert (qtp_root / "old.html").is_file() and (qtp_root / "old.html").stat().st_size > 50_000

    html = (qtp_root / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script>([\s\S]*?)</script>", html)
    assert len(scripts) == 1

    node = shutil.which("node")
    if node:
        js_file = tmp_path / "unified_web.js"
        js_file.write_text(scripts[0], encoding="utf-8")
        proc = subprocess.run([node, "--check", str(js_file)], capture_output=True, text=True, check=False)
        assert proc.returncode == 0, f"JS syntax hatası: {proc.stderr}"

        start_pure = scripts[0].index("function trLower(text) {")
        end_pure = scripts[0].index("function downloadBytes(")
        pure_js = (
            scripts[0].split("const state = {", 1)[0]
            + "\nfunction copyTextBrowser() { return Promise.resolve(true); }\n"
            + scripts[0][start_pure:end_pure]
            + "\n"
            + scripts[0][scripts[0].index("function normalizeComboText("):scripts[0].index("function showToast(")]
        )
        vm_script = (
            "const assert = require('assert');\n"
            + pure_js
            + "\nconst hit = filterItemsStatic('şifre', ["
            + "{keys:'L-Win+A', group:'G', label:'İ', text:'Şifre sıfırlama bağlantısı'},"
            + "{keys:'L-Win+Z', group:'G', label:'K', text:'Kurye notu'}"
            + "]);"
            + "\nassert.strictEqual(hit.length, 1);"
            + "\nassert(hit[0].matched_indices.length >= 5);"
            + "\nconst conf = detectHotkeyConflictsStatic({all:'Ctrl+Shift+Space', Q:'Ctrl+Alt+Q'});"
            + "\nassert(conf.Q && conf.Q[0].includes('AltGr+Q'));"
            + "\nconsole.log('STATIC_SEARCH_AND_HOTKEY_OK');\n"
        )
        proc_vm = subprocess.run([node, "-e", vm_script], capture_output=True, text=True, check=False)
        assert proc_vm.returncode == 0, f"VM hatası: {proc_vm.stderr}\n{proc_vm.stdout}"
        assert "STATIC_SEARCH_AND_HOTKEY_OK" in proc_vm.stdout

        full_vm_script = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const htmlSrc = fs.readFileSync(process.env.QTP_INDEX_HTML, 'utf8');
const dataArr = JSON.parse(fs.readFileSync(process.env.QTP_DATA_JSON, 'utf8'));
const scriptCode = htmlSrc.match(/<script>([\s\S]*?)<\/script>/)[1];

function runSim(liveMode) {
  const ls = {};
  const elsById = new Map();
  function mkEl(tag) {
    const el = {
      tagName: String(tag || 'DIV').toUpperCase(),
      style: {},
      dataset: {},
      children: [],
      value: '',
      _text: '',
      className: '',
      scrollTop: 0,
      classList: {
        _set: new Set(),
        toggle(c, f) { if (f) this._set.add(c); else this._set.delete(c); },
        add(c) { this._set.add(c); },
        contains(c) { return this._set.has(c); }
      },
      addEventListener() {},
      appendChild(c) { this.children.push(c); return c; },
      removeChild(c) { this.children = this.children.filter((x) => x !== c); },
      querySelectorAll(sel) {
        if (sel === '[data-section]') {
          return ['all','usage_verbose','kullanim','kisayollar','sss'].map((s) => {
            const b = mkEl('button'); b.dataset.section = s; return b;
          });
        }
        return [];
      },
      focus() {},
      select() {},
      click() {},
      scrollIntoView() {},
      get textContent() { return this._text; },
      set textContent(v) { this._text = String(v); },
      set innerHTML(v) { if (v === '') this.children = []; },
    };
    return el;
  }
  const sandbox = {
    console, setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 2, clearInterval: () => {},
    TextEncoder, TextDecoder, ArrayBuffer, DataView, Uint8Array, URLSearchParams,
    Blob: class FakeBlob { constructor(parts, opts) { this.parts = parts; this.type = opts?.type || ''; } },
    URL: { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} },
    location: { protocol: 'https:', search: liveMode ? '' : '?category=Z' },
    navigator: { onLine: true, clipboard: { writeText: async () => {} } },
    localStorage: { getItem: (k) => (k in ls ? ls[k] : null), setItem: (k, v) => { ls[k] = String(v); } },
    document: {
      addEventListener() {},
      execCommand: () => true,
      createElement: (t) => mkEl(t),
      createTextNode: (t) => ({ nodeType: 3, textContent: String(t) }),
      getElementById: (id) => { if (!elsById.has(id)) elsById.set(id, mkEl('div')); return elsById.get(id); },
      body: mkEl('body'),
      activeElement: null,
    },
    fetch: async (url) => {
      const u = String(url);
      if (u.includes('/api/revision')) {
        if (!liveMode) return { ok: false, status: 404, headers: { get: () => 'text/html' } };
        return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ ok: true, data: { revision: 3, initial_category: 'A', initial_query: '' } }) };
      }
      if (u.includes('/api/categories')) {
        return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ ok: true, data: { categories: [{ code: 'ALL', label: 'Tümü', count: dataArr.length }] } }) };
      }
      if (u.includes('/api/items')) {
        return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ ok: true, data: { items: dataArr.slice(0, 5).map((it, i) => ({ ...it, raw_key: 'text_' + i, matched_indices: [] })) } }) };
      }
      if (u.includes('data.json')) {
        return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => dataArr };
      }
      if (u.includes('/docs/')) {
        return { ok: true, status: 200, headers: { get: () => 'text/markdown' }, text: async () => '# Doc' };
      }
      return { ok: false, status: 404, headers: { get: () => 'text/plain' } };
    },
  };
  const ctx = vm.createContext(sandbox);
  vm.runInContext(scriptCode, ctx);
  return new Promise((resolve) => setTimeout(() => resolve({
    ctx,
    elsById,
    getState: () => vm.runInContext('state', ctx),
  }), 60));
}

(async () => {
  const st = await runSim(false);
  const stState = st.getState();
  assert.strictEqual(stState.isStatic, true);
  assert.strictEqual(stState.category, 'Z');
  assert(stState.allItems.length >= 500);
  assert(st.elsById.get('modeBadge').textContent.includes('Statik Web'));
  await st.ctx.showHelpModal('all');
  assert(st.elsById.get('modalBody').textContent.includes('QTP v2.1.0'));
  await st.ctx.showHotkeysModal();
  assert(st.elsById.get('modalBody').textContent.includes('Win+Alt+Space'));

  const lv = await runSim(true);
  const lvState = lv.getState();
  assert.strictEqual(lvState.isStatic, false);
  assert.strictEqual(lvState.category, 'A');
  assert(lv.elsById.get('modeBadge').textContent.includes('Canlı Mod'));
  console.log('DUAL_MODE_VM_OK');
})();
"""
        env = dict(
            __import__("os").environ,
            QTP_INDEX_HTML=str(qtp_root / "index.html"),
            QTP_DATA_JSON=str(qtp_root / "data.json"),
        )
        proc_dual = subprocess.run([node, "-e", full_vm_script], capture_output=True, text=True, env=env, check=False)
        assert proc_dual.returncode == 0, f"Dual VM hatası: {proc_dual.stderr}\n{proc_dual.stdout}"
        assert "DUAL_MODE_VM_OK" in proc_dual.stdout

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(repo_root))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        for req_path in (
            "/qtp/",
            "/qtp/index.html",
            "/qtp/theme.css",
            "/qtp/old.html",
            "/qtp/data.json",
            "/qtp/QuickTextPaste.ini",
            "/qtp/docs/KULLANIM.md",
            "/qtp/docs/KISAYOLLAR.md",
            "/qtp/docs/SSS.md",
        ):
            conn.request("GET", req_path)
            resp = conn.getresponse()
            body = resp.read()
            assert resp.status == 200, f"Statik HTTP hatası {req_path} -> {resp.status}"
            assert len(body) > 100
    finally:
        srv.shutdown()
        srv.server_close()
