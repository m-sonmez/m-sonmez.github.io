"""Uygulama içi Türkçe yardım penceresi (F1) — docs/*.md tek kaynaklı çevrimdışı Markdown görüntüleyici."""

from __future__ import annotations

import html
from pathlib import Path
import re

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from qtp_app.core.engine import build_cli_help_text, get_bundled_docs_dir, read_doc_text
from qtp_app.core.i18n import t
from qtp_app.ui.theme import (
    ThemePalette,
    build_dialog_stylesheet,
    build_qpalette,
    create_app_font,
    load_bundled_fonts,
)

HELP_WIDTH = 740
HELP_HEIGHT = 540

_locate_docs_dir = get_bundled_docs_dir
read_doc_markdown = read_doc_text


def markdown_to_html(md_text: str, palette: ThemePalette) -> str:
    """Bağımlılıksız, çevrimdışı Markdown -> HTML dönüştürücüsü (başlıklar, tablolar, listeler, kod blokları)."""
    lines = md_text.splitlines()
    out: list[str] = [
        f"<html><head><meta charset='utf-8'><style>"
        f"body {{ background-color: {palette.input_bg}; color: {palette.text_primary}; font-family: Inter, sans-serif; font-size: 13px; line-height: 1.55; }}"
        f"h1 {{ font-size: 20px; color: {palette.heading_color}; border-bottom: 1px solid {palette.border}; padding-bottom: 6px; }}"
        f"h2 {{ font-size: 16px; color: {palette.heading_color}; margin-top: 16px; }}"
        f"h3 {{ font-size: 14px; color: {palette.text_primary}; margin-top: 12px; }}"
        f"a {{ color: {palette.heading_color}; }}"
        f"code {{ background: {palette.surface_alt}; color: {palette.text_primary}; border: 1px solid {palette.border}; padding: 1px 5px; border-radius: 4px; font-family: monospace; }}"
        f"pre {{ background: {palette.surface_alt}; color: {palette.text_primary}; padding: 10px; border-radius: 8px; border: 1px solid {palette.border}; }}"
        f"pre code {{ border: none; padding: 0; background: transparent; }}"
        f"table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}"
        f"th, td {{ border: 1px solid {palette.border}; color: {palette.text_primary}; padding: 6px 8px; text-align: left; }}"
        f"th {{ background: {palette.surface_alt}; color: {palette.text_primary}; font-weight: bold; }}"
        f"blockquote {{ border-left: 3px solid {palette.heading_color}; padding-left: 10px; color: {palette.text_secondary}; }}"
        f"hr {{ border: none; border-top: 1px solid {palette.border}; }}"
        f"</style></head><body>"
    ]

    in_code = False
    in_list = False
    in_table = False
    table_header_done = False

    def _inline(text: str) -> str:
        placeholders: dict[str, str] = {}

        def _put(fragment: str) -> str:
            tok = f"\x00QTP{len(placeholders)}\x00"
            placeholders[tok] = fragment
            return tok

        def _code_repl(m: re.Match[str]) -> str:
            return _put(f"<code>{html.escape(m.group(1))}</code>")

        def _link_repl(m: re.Match[str]) -> str:
            label_raw = m.group(1)
            url_raw = m.group(2).strip()
            low = url_raw.lower()
            head = url_raw.split("/", 1)[0]
            if low.startswith(("http://", "https://", "mailto:", "#")) or (
                ":" not in head and not url_raw.startswith("//")
            ):
                href = html.escape(url_raw, quote=True)
                lbl = html.escape(label_raw)
                lbl = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", lbl)
                lbl = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", lbl)
                return _put(f'<a href="{href}">{lbl}</a>')
            return html.escape(m.group(0))

        staged = re.sub(r"`([^`]+)`", _code_repl, text)
        staged = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link_repl, staged)
        esc = html.escape(staged)
        esc = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", esc)
        esc = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", esc)
        for tok, frag in placeholders.items():
            esc = esc.replace(html.escape(tok), frag).replace(tok, frag)
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
        language: str = "en",
        config_dir: Path | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._language = str(language or "en")
        self._config_dir = config_dir
        self.setWindowTitle(t("help.title", self._language, self._config_dir))
        self.setMinimumSize(520, 380)
        self.resize(HELP_WIDTH, HELP_HEIGHT)
        self.setSizeGripEnabled(True)
        self._palette = palette
        self._font_family = load_bundled_fonts()
        self.setFont(create_app_font(self._font_family, 13))
        self.setPalette(build_qpalette(palette))
        self.setStyleSheet(build_dialog_stylesheet(palette))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.tabs = QTabWidget(self)
        self.browsers: list[QTextBrowser] = []
        for title, doc_file in (
            (t("help.tab.usage", self._language, self._config_dir), "KULLANIM.md"),
            (t("help.tab.install", self._language, self._config_dir), "KURULUM.md"),
            (t("help.tab.hotkeys", self._language, self._config_dir), "KISAYOLLAR.md"),
            (t("help.tab.faq", self._language, self._config_dir), "SSS.md"),
        ):
            browser = QTextBrowser(self)
            browser.setPalette(build_qpalette(palette))
            browser.setOpenExternalLinks(False)
            browser.setFont(create_app_font(self._font_family, 13))
            md_text = read_doc_markdown(doc_file)
            browser.setHtml(markdown_to_html(md_text, palette))
            browser.verticalScrollBar().setValue(0)
            self.tabs.addTab(browser, title)
            self.browsers.append(browser)

        cli_help_text = build_cli_help_text(verbose=True, lang=self._language, config_dir=self._config_dir)
        cli_browser = QTextBrowser(self)
        cli_browser.setPalette(build_qpalette(palette))
        cli_browser.setOpenExternalLinks(False)
        cli_browser.setFont(create_app_font(self._font_family, 13))
        cli_title = t("help.tab.cli", self._language, self._config_dir)
        cli_md = f"# {cli_title} (--verbose --help)\n\n```\n{cli_help_text}\n```\n"
        cli_browser.setHtml(markdown_to_html(cli_md, palette))
        cli_browser.verticalScrollBar().setValue(0)
        self.tabs.addTab(cli_browser, cli_title)
        self.browsers.append(cli_browser)

        if 0 <= initial_tab < self.tabs.count():
            self.tabs.setCurrentIndex(initial_tab)

        layout.addWidget(self.tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(t("help.close", self._language, self._config_dir), self)
        close_btn.setObjectName("PrimaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def scroll_to_anchor_text(self, needle: str) -> None:
        """Yardım sekmesini belirli bir başlığa kaydırır."""
        browser = self.tabs.currentWidget()
        if isinstance(browser, QTextBrowser) and needle:
            browser.find(needle)
