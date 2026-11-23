"""Statik çapraz platform UI/UX eşitliği denetimi (theme.py, overlay.py ve Türkçe belgeler)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from qtp_app.core.operations import OPERATIONS

QTP_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
UI_DIR = Path(__file__).resolve().parent.parent / "ui"
DOCS_DIR = QTP_ROOT_DIR / "docs"

_VISUAL_TOKENS = (
    "color",
    "palette",
    "radius",
    "padding",
    "margin",
    "font",
    "size",
    "width",
    "height",
    "duration",
    "animation",
    "hint",
    "footer",
    "placeholder",
    "rgba",
    "#7C3AED",
    "#22D3EE",
)


def _node_mentions_platform(node: ast.AST) -> bool:
    src = ast.unparse(node)
    return (
        "sys.platform" in src
        or "platform.system" in src
        or "os.name" in src
    )


def test_no_platform_branches_alter_visual_constants_or_animations():
    for fname in ("theme.py", "overlay.py"):
        source = (UI_DIR / fname).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=fname)

        for node in ast.walk(tree):
            if isinstance(node, ast.If) and _node_mentions_platform(node.test):
                branch_src = ast.unparse(node).lower()
                for token in _VISUAL_TOKENS:
                    assert token.lower() not in branch_src, (
                        f"{fname} içinde platforma göre görsel sabit değişimi yasak ({token}): {branch_src}"
                    )


def test_theme_constants_are_single_cross_platform_definitions():
    source = (UI_DIR / "theme.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="theme.py")

    assigned_names: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned_names[target.id] = assigned_names.get(target.id, 0) + 1
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigned_names[node.target.id] = assigned_names.get(node.target.id, 0) + 1

    required_singles = (
        "WINDOW_WIDTH",
        "WINDOW_HEIGHT",
        "WINDOW_CORNER_RADIUS",
        "ANIMATION_DURATION_MS",
        "ANIMATION_SLIDE_OFFSET_PX",
        "TOAST_DURATION_MS",
        "FONT_SIZE_TEXT",
        "FONT_SIZE_INPUT",
        "FONT_SIZE_PILL",
        "FONT_SIZE_META",
        "FONT_SIZE_HINT",
        "FOOTER_HINTS_TEXT",
        "SEARCH_PLACEHOLDER",
        "SEARCH_CHIP_TEXT",
        "CATEGORY_TABS",
    )
    for const_name in required_singles:
        assert assigned_names.get(const_name) == 1, (
            f"theme.py içinde {const_name} tam olarak 1 kez ve platformdan bağımsız tanımlanmalıdır."
        )


def test_overlay_uses_shared_footer_and_search_constants():
    overlay_src = (UI_DIR / "overlay.py").read_text(encoding="utf-8")
    assert "FOOTER_HINTS_TEXT" in overlay_src
    assert "SEARCH_PLACEHOLDER" in overlay_src
    assert "ANIMATION_DURATION_MS" in overlay_src
    assert "sys.platform" not in overlay_src


def test_all_required_turkish_docs_exist_and_have_no_placeholders():
    expected_docs = ("KURULUM.md", "KULLANIM.md", "KISAYOLLAR.md", "SSS.md", "GELISTIRICI.md")
    for doc_name in expected_docs:
        path = DOCS_DIR / doc_name
        assert path.is_file(), f"Eksik belge: {doc_name}"
        text = path.read_text(encoding="utf-8")
        assert len(text.strip()) > 400
        low = text.lower()
        assert "todo" not in low
        assert "coming soon" not in low
        assert "yakında" not in low


def test_markdown_docs_have_no_local_paths_or_todos_and_links_valid():
    skip_parts = {".venv", ".pytest_cache", "build", "dist", "__pycache__"}
    forbidden_tokens = ("file:///", "C:/Users", "C:\\Users", "TODO", "FIXME")
    link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

    for md_path in QTP_ROOT_DIR.rglob("*.md"):
        if any(part in skip_parts for part in md_path.parts):
            continue
        text = md_path.read_text(encoding="utf-8")
        for tok in forbidden_tokens:
            assert tok not in text, f"{md_path.relative_to(QTP_ROOT_DIR)} içinde yasak ifade '{tok}' bulundu."

        for match in link_re.finditer(text):
            target = match.group(1).strip()
            if not target or target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            rel_file = target.split("#", 1)[0]
            if rel_file:
                resolved = (md_path.parent / rel_file).resolve()
                assert resolved.exists(), (
                    f"{md_path.relative_to(QTP_ROOT_DIR)} içinde kırık Markdown bağlantısı: {target}"
                )


def test_all_operations_errors_match_sss_verbatim():
    sss_text = (DOCS_DIR / "SSS.md").read_text(encoding="utf-8")
    for op in OPERATIONS:
        for err_msg in op.error_msgs_tr:
            assert err_msg in sss_text, (
                f"operations.py ({op.op_id}) hata mesajı docs/SSS.md içinde birebir bulunamadı: {err_msg!r}"
            )


def test_all_operations_documented_in_kullanim_parity_matrix():
    kullanim_text = (DOCS_DIR / "KULLANIM.md").read_text(encoding="utf-8")
    for op in OPERATIONS:
        assert op.op_id in kullanim_text, f"docs/KULLANIM.md eksik işlem: {op.op_id}"
        assert op.cli_flag in kullanim_text, f"docs/KULLANIM.md eksik CLI bayrağı: {op.cli_flag}"
        assert op.web_route in kullanim_text, f"docs/KULLANIM.md eksik Web rotası: {op.web_route}"


def test_overlay_detect_os_dark_qt_pre65_fallback():
    from types import SimpleNamespace
    from unittest import mock
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    from qtp_app.ui.overlay import OverlayWindow

    app = QApplication.instance() or QApplication([])
    ov = OverlayWindow([], theme="auto")
    try:
        with mock.patch("qtp_app.ui.overlay.QGuiApplication.styleHints", return_value=SimpleNamespace()):
            assert ov._detect_os_dark() is True
        with mock.patch.object(Qt, "ColorScheme", None, create=True):
            assert ov._detect_os_dark() is True
    finally:
        ov.close()
        ov.deleteLater()
        app.processEvents()


def _scan_js_comments_safe(code: str) -> list[str]:
    found: list[str] = []
    i = 0
    n = len(code)
    prev_tok = None
    ident_re = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
    num_re = re.compile(r"0[xXbBoO][0-9A-Fa-f_]+|\d[\d_]*(?:\.[\d_]*)?(?:[eE][+-]?\d+)?")
    after_kw = {"return", "throw", "case", "delete", "void", "typeof", "await", "yield", "in", "instanceof", "of", "new", "else", "do"}
    while i < n:
        ch = code[i]
        if ch in " \t\r\n":
            i += 1
            continue
        if code.startswith("//", i):
            end = code.find("\n", i)
            end = n if end == -1 else end
            found.append(code[i:end])
            i = end
            continue
        if code.startswith("/*", i):
            end = code.find("*/", i + 2)
            end = n if end == -1 else end + 2
            found.append(code[i:end])
            i = end
            continue
        if ch in ('"', "'"):
            q = ch
            i += 1
            while i < n and code[i] != q:
                i += 2 if code[i] == "\\" else 1
            i += 1
            prev_tok = "operand"
            continue
        if ch == "`":
            depth = 0
            i += 1
            while i < n:
                if code[i] == "\\":
                    i += 2
                    continue
                if code[i] == "`" and depth == 0:
                    i += 1
                    break
                if code[i : i + 2] == "${":
                    depth += 1
                    i += 2
                    continue
                if code[i] == "}" and depth > 0:
                    depth -= 1
                    i += 1
                    continue
                i += 1
            prev_tok = "operand"
            continue
        if ch == "/" and prev_tok in (None, "operator"):
            j = i + 1
            in_cls = False
            ok = False
            while j < n:
                rc = code[j]
                if rc == "\\":
                    j += 2
                    continue
                if rc == "[":
                    in_cls = True
                elif rc == "]":
                    in_cls = False
                elif rc == "/" and not in_cls:
                    j += 1
                    while j < n and code[j].isalpha():
                        j += 1
                    ok = True
                    break
                elif rc in "\r\n" and not in_cls:
                    break
                j += 1
            if ok:
                i = j
                prev_tok = "operand"
                continue
        if ch.isalpha() or ch in "_$":
            m = ident_re.match(code, i)
            word = m.group(0)
            i = m.end()
            prev_tok = "operator" if word in after_kw else "operand"
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and code[i + 1].isdigit()):
            m = num_re.match(code, i)
            i = m.end() if m else i + 1
            prev_tok = "operand"
            continue
        if ch in ")]}":
            i += 1
            prev_tok = "operand"
            continue
        if ch in "+-" and code[i : i + 2] in ("++", "--"):
            i += 2
            prev_tok = "operand"
            continue
        i += 1
        prev_tok = "operator"
    return found


def _scan_css_comments_safe(css: str) -> list[str]:
    found: list[str] = []
    i = 0
    n = len(css)
    while i < n:
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            end = n if end == -1 else end + 2
            found.append(css[i:end])
            i = end
        elif css[i] in ('"', "'"):
            q = css[i]
            i += 1
            while i < n and css[i] != q:
                i += 2 if css[i] == "\\" else 1
            i += 1
        else:
            i += 1
    return found


def _scan_html_comments_safe(html_src: str) -> list[str]:
    found: list[str] = []
    i = 0
    n = len(html_src)
    while i < n:
        low = html_src[i : i + 9].lower()
        if html_src.startswith("<!--", i):
            end = html_src.find("-->", i + 4)
            end = n if end == -1 else end + 3
            found.append(html_src[i:end])
            i = end
        elif low.startswith("<style"):
            gt = html_src.find(">", i)
            end_tag = html_src.lower().find("</style>", gt + 1)
            found.extend(_scan_css_comments_safe(html_src[gt + 1 : end_tag]))
            i = end_tag + 8
        elif low.startswith("<script"):
            gt = html_src.find(">", i)
            attrs = html_src[i:gt].lower()
            end_tag = html_src.lower().find("</script>", gt + 1)
            if "src=" not in attrs:
                found.extend(_scan_js_comments_safe(html_src[gt + 1 : end_tag]))
            i = end_tag + 9
        else:
            i += 1
    return found


def test_no_unnecessary_comments():
    import io
    import tokenize
    from qtp_app.ui.theme import DARK_PALETTE, build_dialog_stylesheet, build_overlay_stylesheet

    app_dir = QTP_ROOT_DIR / "qtp_app"
    py_violations: list[str] = []
    for path in sorted(list(app_dir.rglob("*.py")) + list((app_dir / "build").glob("*.spec"))):
        if "__pycache__" in path.parts:
            continue
        src = path.read_text(encoding="utf-8")
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                if tok.start[0] == 1 and tok.string.startswith("#!"):
                    continue
                rel = path.relative_to(QTP_ROOT_DIR).as_posix()
                py_violations.append(f"{rel}:{tok.start[0]}: {tok.string}")

    assert not py_violations, "Python/.spec dosyalarında gereksiz yorumlar bulundu:\n" + "\n".join(py_violations)

    web_html = (app_dir / "web" / "index.html").read_text(encoding="utf-8")
    web_css = (app_dir / "web" / "theme.css").read_text(encoding="utf-8")
    assert not _scan_html_comments_safe(web_html), "qtp_app/web/index.html içinde yorum bulundu"
    assert not _scan_css_comments_safe(web_css), "qtp_app/web/theme.css içinde yorum bulundu"

    for qss in (build_overlay_stylesheet(DARK_PALETTE), build_dialog_stylesheet(DARK_PALETTE)):
        assert not _scan_css_comments_safe(qss), "ui/theme.py QSS çıktısında CSS yorumu bulundu"

    for rel_cfg in (".gitignore", "Makefile", "make.bat", ".github/workflows/ci.yml"):
        lines = (QTP_ROOT_DIR / rel_cfg).read_text(encoding="utf-8").splitlines()
        for ln_no, ln in enumerate(lines, start=1):
            st = ln.strip()
            if ln_no == 1 and st.startswith("#!"):
                continue
            if st.startswith("#") or st.upper().startswith("REM ") or st.startswith("::"):
                raise AssertionError(f"{rel_cfg}:{ln_no} gereksiz yorum bulundu: {st}")

