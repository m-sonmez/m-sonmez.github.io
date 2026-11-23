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

        # Göreli Markdown bağlantıları geçerli hedeflere işaret etmeli
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
