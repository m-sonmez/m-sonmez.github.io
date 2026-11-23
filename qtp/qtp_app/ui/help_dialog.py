"""Uygulama içi Türkçe yardım penceresi (F1) — docs/*.md tek kaynaklı çevrimdışı Markdown görüntüleyici."""

from __future__ import annotations

import html
import importlib.resources
import re
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from qtp_app.ui.theme import (
    ACCENT_CYAN,
    ThemePalette,
    build_dialog_stylesheet,
    create_app_font,
    load_bundled_fonts,
)

HELP_WIDTH = 740
HELP_HEIGHT = 540


def _locate_docs_dir() -> Path:
    """docs/ klasörünü önce PyInstaller paketinden, ardından geliştirme kökünden çözer."""
    try:
        pkg_root = Path(str(importlib.resources.files("qtp_app")))
        for candidate in (pkg_root / "docs", pkg_root.parent / "docs"):
            if candidate.is_dir():
                return candidate
    except Exception:
        pass
    import sys

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_docs = Path(getattr(sys, "_MEIPASS")) / "docs"
        if meipass_docs.is_dir():
            return meipass_docs
    return Path(__file__).resolve().parent.parent.parent / "docs"


def read_doc_markdown(filename: str) -> str:
    """Belirtilen Türkçe belge dosyasını UTF-8 olarak okur."""
    docs_dir = _locate_docs_dir()
    path = docs_dir / filename
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return f"# {filename}\n\nBelge dosyası bulunamadı: `{path}`"


def markdown_to_html(md_text: str, palette: ThemePalette) -> str:
    """Bağımlılıksız, çevrimdışı Markdown -> HTML dönüştürücüsü (başlıklar, tablolar, listeler, kod blokları)."""
    lines = md_text.splitlines()
    out: list[str] = [
        f"<html><head><meta charset='utf-8'><style>"
        f"body {{ color: {palette.text_primary}; font-family: Inter, sans-serif; font-size: 13px; line-height: 1.55; }}"
        f"h1 {{ font-size: 20px; color: {ACCENT_CYAN}; border-bottom: 1px solid {palette.border}; padding-bottom: 6px; }}"
        f"h2 {{ font-size: 16px; color: {ACCENT_CYAN}; margin-top: 16px; }}"
        f"h3 {{ font-size: 14px; color: {palette.text_primary}; margin-top: 12px; }}"
        f"code {{ background: {palette.surface_alt}; padding: 1px 5px; border-radius: 4px; font-family: monospace; }}"
        f"pre {{ background: {palette.surface_alt}; padding: 10px; border-radius: 8px; border: 1px solid {palette.border}; }}"
        f"table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}"
        f"th, td {{ border: 1px solid {palette.border}; padding: 6px 8px; text-align: left; }}"
        f"th {{ background: {palette.pill_bg}; font-weight: bold; }}"
        f"blockquote {{ border-left: 3px solid {ACCENT_CYAN}; padding-left: 10px; color: {palette.text_secondary}; }}"
        f"</style></head><body>"
    ]

    in_code = False
    in_list = False
    in_table = False
    table_header_done = False

    def _inline(text: str) -> str:
        esc = html.escape(text)
        esc = re.sub(r"`([^`]+)`", r"<code>\1</code>", esc)
        esc = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", esc)
        esc = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", esc)
        return esc

    def _close_blocks() -> None:
        nonlocal in_list, in_table, table_header_done
        if in_list:
            out.append("</ul>")
            in_list = False
        if in_table:
            out.append("</table>")
            in_table = False
            table_header_done = False

    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("```"):
            _close_blocks()
            if not in_code:
                out.append("<pre><code>")
                in_code = True
            else:
                out.append("</code></pre>")
                in_code = False
            continue
        if in_code:
            out.append(html.escape(raw) + "\n")
            continue

        if not stripped:
            _close_blocks()
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            if in_list:
                out.append("</ul>")
                in_list = False
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(re.match(r"^:?-{2,}:?$", c) for c in cells):
                continue
            if not in_table:
                out.append("<table>")
                in_table = True
                table_header_done = False
            tag = "th" if not table_header_done else "td"
            row_html = "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells)
            out.append(f"<tr>{row_html}</tr>")
            table_header_done = True
            continue
        elif in_table:
            out.append("</table>")
            in_table = False
            table_header_done = False

        if stripped.startswith("### "):
            _close_blocks()
            out.append(f"<h3>{_inline(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            _close_blocks()
            out.append(f"<h2>{_inline(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            _close_blocks()
            out.append(f"<h1>{_inline(stripped[2:])}</h1>")
        elif stripped.startswith("> "):
            _close_blocks()
            out.append(f"<blockquote>{_inline(stripped[2:])}</blockquote>")
        elif stripped.startswith(("- ", "* ")) or re.match(r"^\d+\.\s+", stripped):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item_text = re.sub(r"^([-*]|\d+\.)\s+", "", stripped)
            out.append(f"<li>{_inline(item_text)}</li>")
        elif stripped == "---":
            _close_blocks()
            out.append("<hr/>")
        else:
            _close_blocks()
            out.append(f"<p>{_inline(stripped)}</p>")

    _close_blocks()
    if in_code:
        out.append("</code></pre>")
    out.append("</body></html>")
    return "\n".join(out)


class HelpDialog(QDialog):
    """docs/KULLANIM.md ve diğer Türkçe belgeleri sunan çapraz platform yardım penceresi."""

    def __init__(
        self,
        palette: ThemePalette,
        *,
        initial_tab: int = 0,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("QTP Yardım ve Kullanım Kılavuzu")
        self.setFixedSize(HELP_WIDTH, HELP_HEIGHT)
        self._palette = palette
        self._font_family = load_bundled_fonts()
        self.setFont(create_app_font(self._font_family, 13))
        self.setStyleSheet(build_dialog_stylesheet(palette))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.tabs = QTabWidget(self)
        self.browsers: list[QTextBrowser] = []
        for title, doc_file in (
            ("Kullanım Kılavuzu", "KULLANIM.md"),
            ("Kısayollar", "KISAYOLLAR.md"),
            ("Sorun Giderme (SSS)", "SSS.md"),
        ):
            browser = QTextBrowser(self)
            browser.setOpenExternalLinks(False)
            browser.setFont(create_app_font(self._font_family, 13))
            md_text = read_doc_markdown(doc_file)
            browser.setHtml(markdown_to_html(md_text, palette))
            browser.verticalScrollBar().setValue(0)
            self.tabs.addTab(browser, title)
            self.browsers.append(browser)

        if 0 <= initial_tab < self.tabs.count():
            self.tabs.setCurrentIndex(initial_tab)

        layout.addWidget(self.tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Kapat", self)
        close_btn.setObjectName("PrimaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def scroll_to_anchor_text(self, needle: str) -> None:
        """Yardım sekmesini belirli bir başlığa kaydırır."""
        browser = self.tabs.currentWidget()
        if isinstance(browser, QTextBrowser) and needle:
            browser.find(needle)
