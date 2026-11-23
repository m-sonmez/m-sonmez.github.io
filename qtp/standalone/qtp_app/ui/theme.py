"""Çapraz platform birebir UI/UX sabitleri, renk paletleri, Inter yazı tipi ve stil şablonu."""

from __future__ import annotations

import importlib.resources
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette

WINDOW_WIDTH = 720
WINDOW_HEIGHT = 520
WINDOW_MIN_WIDTH = 560
WINDOW_MIN_HEIGHT = 400
WINDOW_CORNER_RADIUS = 12

ANIMATION_DURATION_MS = 180
ANIMATION_SLIDE_OFFSET_PX = 8
TOAST_DURATION_MS = 1200

PADDING_OUTER = 16
PADDING_HEADER_V = 12
PADDING_HEADER_H = 16
PADDING_ROW_V = 10
PADDING_ROW_H = 14
ROW_RADIUS = 10
PILL_RADIUS = 14
BADGE_RADIUS = 6

FONT_FAMILY_PRIMARY = "Inter"
FONT_SIZE_TEXT = 14
FONT_SIZE_INPUT = 14
FONT_SIZE_PILL = 12
FONT_SIZE_META = 11
FONT_SIZE_HINT = 11

ACCENT_PURPLE = "#7C3AED"
ACCENT_CYAN = "#22D3EE"
ACCENT_GRADIENT_QSS = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #0E7490)"

SEARCH_PLACEHOLDER = "Ara… (mesaj, kategori, etiket)"
SEARCH_CHIP_TEXT = "Ctrl+K"
FOOTER_HINTS_TEXT = "↑↓ Gezin · ⏎ Yapıştır · Ctrl+⏎ Kopyala · Esc Kapat"
QUICK_EMOJIS: tuple[str, ...] = (
    "😊",
    "👍",
    "🎉",
    "🚀",
    "✅",
    "⚠️",
    "🙏",
    "💳",
    "📦",
    "🛵",
    "📞",
    "❤️",
    "🔥",
    "⭐",
    "💡",
    "📌",
)

CATEGORY_TABS: tuple[tuple[str, str, str], ...] = (
    ("ALL", "Tümü", ""),
    ("A", "A · İş Ortağı", "L-Win+A"),
    ("Z", "Z · Kurye", "L-Win+Z"),
    ("X", "X · Canlı Yardım", "L-Win+X"),
    ("Q", "Q · Turkcell", "L-Win+Q"),
)

_RGBA_RE = re.compile(
    r"^\s*rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*([0-9]*\.?[0-9]+))?\s*\)\s*$",
    re.IGNORECASE,
)


def parse_qcolor(color_str: str) -> QColor:
    """CSS hex veya rgb/rgba renk dizgesini geçerli QColor nesnesine dönüştürür."""
    raw = str(color_str or "").strip()
    m = _RGBA_RE.match(raw)
    if m:
        r = max(0, min(255, int(m.group(1))))
        g = max(0, min(255, int(m.group(2))))
        b = max(0, min(255, int(m.group(3))))
        alpha_grp = m.group(4)
        if alpha_grp is None:
            a = 255
        else:
            alpha_val = float(alpha_grp)
            a = int(round(alpha_val * 255)) if alpha_val <= 1.0 else int(round(alpha_val))
            a = max(0, min(255, a))
        return QColor(r, g, b, a)
    c = QColor(raw)
    if not c.isValid():
        raise ValueError(f"Geçersiz renk değeri: {color_str!r}")
    return c


@dataclass(frozen=True)
class ThemePalette:
    """Koyu veya açık tema renk tanımları (OS bağımsız)."""

    name: str
    window_bg: str
    window_bg_translucent: str
    surface: str
    surface_alt: str
    input_bg: str
    input_border: str
    input_placeholder: str
    border: str
    text_primary: str
    text_secondary: str
    text_muted: str
    pill_bg: str
    pill_hover: str
    pill_text: str
    pill_active_text: str
    btn_bg: str
    btn_hover: str
    btn_text: str
    btn_border: str
    card_bg: str
    card_hover: str
    card_selected: str
    hover_bg: str
    selected_bg: str
    selected_border: str
    badge_bg: str
    badge_text: str
    highlight_bg: str
    highlight_text: str
    toast_bg: str
    toast_text: str
    toast_border: str
    menu_bg: str
    menu_text: str
    menu_hover_bg: str
    menu_hover_text: str
    menu_border: str
    scrollbar_bg: str
    scrollbar_handle: str
    scrollbar_handle_hover: str
    tooltip_bg: str
    tooltip_text: str
    tooltip_border: str
    danger_bg: str
    danger_text: str
    danger_border: str
    danger_hover_bg: str
    danger_hover_text: str
    heading_color: str
    focus_border: str
    success_text: str
    warning_text: str
    shadow_color: str


DARK_PALETTE = ThemePalette(
    name="dark",
    window_bg="#121216",
    window_bg_translucent="rgba(18, 18, 22, 0.92)",
    surface="#18181F",
    surface_alt="#1F1F29",
    input_bg="#18181F",
    input_border="#2E2E3E",
    input_placeholder="#94A3B8",
    border="#2E2E3E",
    text_primary="#F8FAFC",
    text_secondary="#CBD5E1",
    text_muted="#94A3B8",
    pill_bg="#272734",
    pill_hover="#32284A",
    pill_text="#E2E8F0",
    pill_active_text="#FFFFFF",
    btn_bg="#23232E",
    btn_hover="#32284A",
    btn_text="#F1F5F9",
    btn_border="#38384A",
    card_bg="#18181F",
    card_hover="rgba(124, 58, 237, 0.18)",
    card_selected="rgba(124, 58, 237, 0.28)",
    hover_bg="rgba(124, 58, 237, 0.18)",
    selected_bg="rgba(124, 58, 237, 0.28)",
    selected_border="#22D3EE",
    badge_bg="rgba(34, 211, 238, 0.16)",
    badge_text="#22D3EE",
    highlight_bg="rgba(34, 211, 238, 0.30)",
    highlight_text="#FFFFFF",
    toast_bg="#1F1F29",
    toast_text="#F8FAFC",
    toast_border="#22D3EE",
    menu_bg="#18181F",
    menu_text="#F8FAFC",
    menu_hover_bg="#32284A",
    menu_hover_text="#FFFFFF",
    menu_border="#38384A",
    scrollbar_bg="#121216",
    scrollbar_handle="#64748B",
    scrollbar_handle_hover="#22D3EE",
    tooltip_bg="#1F1F29",
    tooltip_text="#F8FAFC",
    tooltip_border="#38384A",
    danger_bg="rgba(239, 68, 68, 0.18)",
    danger_text="#FCA5A5",
    danger_border="rgba(248, 113, 113, 0.45)",
    danger_hover_bg="#DC2626",
    danger_hover_text="#FFFFFF",
    heading_color="#22D3EE",
    focus_border="#22D3EE",
    success_text="#34D399",
    warning_text="#FBBF24",
    shadow_color="rgba(0, 0, 0, 0.55)",
)

LIGHT_PALETTE = ThemePalette(
    name="light",
    window_bg="#F8FAFC",
    window_bg_translucent="rgba(248, 250, 252, 0.92)",
    surface="#FFFFFF",
    surface_alt="#F1F5F9",
    input_bg="#FFFFFF",
    input_border="#CBD5E1",
    input_placeholder="#64748B",
    border="#CBD5E1",
    text_primary="#0F172A",
    text_secondary="#334155",
    text_muted="#475569",
    pill_bg="#E2E8F0",
    pill_hover="#EDE9FE",
    pill_text="#1E293B",
    pill_active_text="#FFFFFF",
    btn_bg="#F1F5F9",
    btn_hover="#EDE9FE",
    btn_text="#1E293B",
    btn_border="#CBD5E1",
    card_bg="#FFFFFF",
    card_hover="rgba(124, 58, 237, 0.10)",
    card_selected="rgba(124, 58, 237, 0.16)",
    hover_bg="rgba(124, 58, 237, 0.10)",
    selected_bg="rgba(124, 58, 237, 0.16)",
    selected_border="#7C3AED",
    badge_bg="#EDE9FE",
    badge_text="#5B21B6",
    highlight_bg="#DDD6FE",
    highlight_text="#0F172A",
    toast_bg="#FFFFFF",
    toast_text="#0F172A",
    toast_border="#7C3AED",
    menu_bg="#FFFFFF",
    menu_text="#0F172A",
    menu_hover_bg="#EDE9FE",
    menu_hover_text="#4C1D95",
    menu_border="#CBD5E1",
    scrollbar_bg="#F1F5F9",
    scrollbar_handle="#64748B",
    scrollbar_handle_hover="#7C3AED",
    tooltip_bg="#FFFFFF",
    tooltip_text="#0F172A",
    tooltip_border="#CBD5E1",
    danger_bg="#FEE2E2",
    danger_text="#B91C1C",
    danger_border="#FCA5A5",
    danger_hover_bg="#DC2626",
    danger_hover_text="#FFFFFF",
    heading_color="#5B21B6",
    focus_border="#7C3AED",
    success_text="#047857",
    warning_text="#B45309",
    shadow_color="rgba(15, 23, 42, 0.16)",
)


def resolve_palette(theme_setting: str, *, os_is_dark: bool = True) -> ThemePalette:
    """Tema ayarını ('auto' | 'dark' | 'light') ThemePalette nesnesine çözer."""
    t = (theme_setting or "light").strip().lower()
    if t == "dark":
        return DARK_PALETTE
    if t == "auto":
        return DARK_PALETTE if os_is_dark else LIGHT_PALETTE
    return LIGHT_PALETTE


def build_qpalette(palette: ThemePalette) -> QPalette:
    """İşletim sisteminin koyu/açık renk sızıntısını önleyen tam QPalette oluşturur."""
    qpal = QPalette()
    roles = {
        QPalette.ColorRole.Window: parse_qcolor(palette.window_bg),
        QPalette.ColorRole.WindowText: parse_qcolor(palette.text_primary),
        QPalette.ColorRole.Base: parse_qcolor(palette.input_bg),
        QPalette.ColorRole.AlternateBase: parse_qcolor(palette.surface_alt),
        QPalette.ColorRole.ToolTipBase: parse_qcolor(palette.tooltip_bg),
        QPalette.ColorRole.ToolTipText: parse_qcolor(palette.tooltip_text),
        QPalette.ColorRole.PlaceholderText: parse_qcolor(palette.input_placeholder),
        QPalette.ColorRole.Text: parse_qcolor(palette.text_primary),
        QPalette.ColorRole.Button: parse_qcolor(palette.btn_bg),
        QPalette.ColorRole.ButtonText: parse_qcolor(palette.btn_text),
        QPalette.ColorRole.BrightText: parse_qcolor(palette.pill_active_text),
        QPalette.ColorRole.Highlight: parse_qcolor(ACCENT_PURPLE),
        QPalette.ColorRole.HighlightedText: parse_qcolor(palette.pill_active_text),
        QPalette.ColorRole.Link: parse_qcolor(palette.heading_color),
        QPalette.ColorRole.LinkVisited: parse_qcolor(palette.heading_color),
        QPalette.ColorRole.Light: parse_qcolor(palette.surface),
        QPalette.ColorRole.Midlight: parse_qcolor(palette.surface_alt),
        QPalette.ColorRole.Mid: parse_qcolor(palette.border),
        QPalette.ColorRole.Dark: parse_qcolor(palette.text_muted),
        QPalette.ColorRole.Shadow: parse_qcolor(palette.shadow_color),
    }
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        for role, color in roles.items():
            qpal.setColor(group, role, color)

    muted = parse_qcolor(palette.text_muted)
    for role, color in roles.items():
        qpal.setColor(QPalette.ColorGroup.Disabled, role, color)
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        qpal.setColor(QPalette.ColorGroup.Disabled, role, muted)
    return qpal


def get_asset_path(relative_path: str) -> Path:
    """Geliştirme ortamında ve PyInstaller tek dosya paketinde varlık yolunu çözer."""
    try:
        files_fn = getattr(importlib.resources, "files", None)
        if files_fn is not None:
            pkg_root = files_fn("qtp_app")
            candidate = Path(str(pkg_root)) / "assets" / relative_path
            if candidate.exists():
                return candidate
    except Exception:
        pass
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_asset = Path(getattr(sys, "_MEIPASS")) / "qtp_app" / "assets" / relative_path
        if meipass_asset.exists():
            return meipass_asset
    return Path(__file__).resolve().parent.parent / "assets" / relative_path


def load_bundled_fonts() -> str:
    """qtp_app/assets/fonts/ altındaki Inter TTF yazı tiplerini yükler."""
    fonts_dir = get_asset_path("fonts")
    loaded_family = ""
    if fonts_dir.is_dir():
        for ttf in sorted(fonts_dir.glob("Inter-*.ttf")):
            font_id = QFontDatabase.addApplicationFont(str(ttf))
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families and not loaded_family:
                    loaded_family = families[0]
    return loaded_family or FONT_FAMILY_PRIMARY


def create_app_font(family: str = FONT_FAMILY_PRIMARY, size_px: int = FONT_SIZE_TEXT, *, bold: bool = False) -> QFont:
    """Tüm platformlarda aynı piksel boyutunda yazı tipi döndürür."""
    font = QFont(family)
    font.setPixelSize(size_px)
    if bold:
        font.setWeight(QFont.Weight.DemiBold)
    return font


def _shared_popup_and_scrollbar_qss(palette: ThemePalette) -> str:
    return f"""
    QMenu {{
        background-color: {palette.menu_bg};
        color: {palette.menu_text};
        border: 1px solid {palette.menu_border};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        background-color: transparent;
        color: {palette.menu_text};
        padding: 6px 18px;
        border-radius: 6px;
    }}
    QMenu::item:selected {{
        background-color: {palette.menu_hover_bg};
        color: {palette.menu_hover_text};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {palette.menu_border};
        margin: 4px 8px;
    }}
    QToolTip {{
        background-color: {palette.tooltip_bg};
        color: {palette.tooltip_text};
        border: 1px solid {palette.tooltip_border};
        border-radius: 6px;
        padding: 4px 8px;
    }}
    QScrollBar:vertical {{
        background: {palette.scrollbar_bg};
        width: 8px;
        margin: 2px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {palette.scrollbar_handle};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {palette.scrollbar_handle_hover};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: {palette.scrollbar_bg};
        height: 8px;
        margin: 2px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {palette.scrollbar_handle};
        border-radius: 4px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {palette.scrollbar_handle_hover};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: none;
        width: 0px;
    }}
    """


def build_overlay_stylesheet(palette: ThemePalette, *, translucent: bool = False) -> str:
    """Overlay penceresi için platformdan bağımsız tam QSS stil şablonunu üretir."""
    bg = palette.window_bg_translucent if translucent else palette.window_bg
    return f"""
    QFrame#OverlayCard {{
        background-color: {bg};
        border: 1px solid {palette.border};
        border-radius: {WINDOW_CORNER_RADIUS}px;
    }}
    QFrame#DragHeader {{
        background-color: transparent;
        border: none;
    }}
    QLabel#WindowTitleLabel {{
        color: {palette.text_muted};
        background-color: transparent;
        font-size: {FONT_SIZE_META}px;
        font-weight: 600;
    }}
    QPushButton#WindowChromeBtn {{
        background-color: transparent;
        color: {palette.btn_text};
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 2px;
        min-width: 24px;
        min-height: 22px;
    }}
    QPushButton#WindowChromeBtn:hover {{
        background-color: {palette.btn_hover};
        border: 1px solid {palette.border};
    }}
    QLineEdit#SearchInput {{
        background-color: {palette.input_bg};
        color: {palette.text_primary};
        border: 1.5px solid {palette.input_border};
        border-radius: 10px;
        padding: 8px 68px 8px 14px;
        font-size: {FONT_SIZE_INPUT}px;
        selection-background-color: {ACCENT_PURPLE};
        selection-color: {palette.pill_active_text};
    }}
    QLineEdit#SearchInput:focus {{
        border: 1.5px solid {palette.focus_border};
    }}
    QLabel#ShortcutChip {{
        background-color: {palette.pill_bg};
        color: {palette.text_muted};
        border: 1px solid {palette.border};
        border-radius: 6px;
        padding: 2px 7px;
        font-size: {FONT_SIZE_META}px;
        font-weight: 600;
    }}
    QPushButton.CategoryPill {{
        background-color: {palette.pill_bg};
        color: {palette.pill_text};
        border: 1px solid {palette.border};
        border-radius: {PILL_RADIUS}px;
        padding: 5px 12px;
        font-size: {FONT_SIZE_PILL}px;
        font-weight: 600;
        letter-spacing: 0.4px;
    }}
    QPushButton.CategoryPill:hover {{
        background-color: {palette.pill_hover};
        color: {palette.text_primary};
        border: 1px solid {palette.selected_border};
    }}
    QPushButton.CategoryPill[active="true"] {{
        background: {ACCENT_GRADIENT_QSS};
        color: {palette.pill_active_text};
        border: 1px solid {palette.selected_border};
    }}
    QListView#SnippetList {{
        background-color: transparent;
        border: none;
        outline: 0;
    }}
    QListView#SnippetList::viewport {{
        background-color: transparent;
    }}
    QListView#SnippetList::item {{
        border-radius: {ROW_RADIUS}px;
        margin: 2px 0px;
    }}
    QFrame#FooterBar {{
        border-top: 1px solid {palette.border};
        background-color: transparent;
    }}
    QLabel#FooterHints {{
        color: {palette.text_muted};
        background-color: transparent;
        font-size: {FONT_SIZE_HINT}px;
    }}
    QLabel#ItemCountLabel {{
        color: {palette.text_muted};
        background-color: transparent;
        font-size: {FONT_SIZE_HINT}px;
        font-weight: 600;
    }}
    QPushButton#HeaderActionBtn {{
        background-color: {palette.btn_bg};
        color: {palette.btn_text};
        border: 1px solid {palette.btn_border};
        border-radius: 8px;
        padding: 5px 9px;
        font-size: {FONT_SIZE_META}px;
        font-weight: 600;
    }}
    QPushButton#HeaderActionBtn:hover {{
        background-color: {palette.btn_hover};
        color: {palette.text_primary};
        border: 1px solid {palette.selected_border};
    }}
    QPushButton#HeaderActionBtn:disabled {{
        background-color: {palette.surface_alt};
        color: {palette.text_muted};
        border: 1px solid {palette.border};
    }}
    QPushButton#HeaderActionBtn[active="true"],
    QPushButton#HeaderActionBtn:checked {{
        background: {ACCENT_GRADIENT_QSS};
        color: {palette.pill_active_text};
        border: 1px solid {palette.selected_border};
    }}
    QComboBox#CompactCombo {{
        background-color: {palette.input_bg};
        color: {palette.text_primary};
        border: 1px solid {palette.input_border};
        border-radius: 7px;
        padding: 3px 8px;
        font-size: {FONT_SIZE_META}px;
    }}
    QComboBox#CompactCombo QAbstractItemView {{
        background-color: {palette.menu_bg};
        color: {palette.menu_text};
        border: 1px solid {palette.menu_border};
        selection-background-color: {palette.menu_hover_bg};
        selection-color: {palette.menu_hover_text};
    }}
    QFrame#BulkActionBar {{
        background-color: {palette.surface_alt};
        border: 1px solid {palette.selected_border};
        border-radius: 8px;
    }}
    QTableView#SnippetTable {{
        background-color: {palette.input_bg};
        alternate-background-color: {palette.surface_alt};
        color: {palette.text_primary};
        gridline-color: {palette.border};
        border: 1px solid {palette.border};
        border-radius: 8px;
        selection-background-color: {palette.card_selected};
        selection-color: {palette.text_primary};
        outline: 0;
    }}
    QTableView#SnippetTable::item:hover {{
        background-color: {palette.card_hover};
        color: {palette.text_primary};
    }}
    QTableView#SnippetTable::item:selected {{
        background-color: {palette.card_selected};
        color: {palette.text_primary};
    }}
    QHeaderView::section {{
        background-color: {palette.surface_alt};
        color: {palette.text_primary};
        border: none;
        border-bottom: 1px solid {palette.border};
        border-right: 1px solid {palette.border};
        padding: 5px 8px;
        font-size: {FONT_SIZE_META}px;
        font-weight: 700;
    }}
    QTableCornerButton::section {{
        background-color: {palette.surface_alt};
        border: none;
        border-bottom: 1px solid {palette.border};
        border-right: 1px solid {palette.border};
    }}
    QLabel#ToastLabel {{
        background-color: {palette.toast_bg};
        color: {palette.toast_text};
        border: 1px solid {palette.toast_border};
        border-radius: 10px;
        padding: 8px 14px;
        font-size: {FONT_SIZE_META + 1}px;
        font-weight: 600;
    }}
    QSizeGrip {{
        background: transparent;
    }}
    QMessageBox {{
        background-color: {palette.surface};
        color: {palette.text_primary};
    }}
    QMessageBox QLabel {{
        color: {palette.text_primary};
        background-color: transparent;
    }}
    QMessageBox QPushButton {{
        background-color: {palette.btn_bg};
        color: {palette.btn_text};
        border: 1px solid {palette.btn_border};
        border-radius: 8px;
        padding: 6px 14px;
        font-weight: 600;
    }}
    QMessageBox QPushButton:hover {{
        background-color: {palette.btn_hover};
        color: {palette.text_primary};
    }}
    {_shared_popup_and_scrollbar_qss(palette)}
    """


def build_dialog_stylesheet(palette: ThemePalette) -> str:
    """Ayarlar, Düzenleyici, Yedekler ve Yardım pencereleri için tema stil şablonu."""
    return f"""
    QDialog, QMessageBox {{
        background-color: {palette.surface};
        color: {palette.text_primary};
    }}
    QScrollArea, QWidget#DialogScrollContainer {{
        background-color: {palette.surface};
        color: {palette.text_primary};
        border: none;
    }}
    QGroupBox {{
        background-color: {palette.window_bg};
        color: {palette.text_primary};
        border: 1px solid {palette.border};
        border-radius: 8px;
        margin-top: 12px;
        padding: 14px 10px 10px 10px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0 6px;
        color: {palette.heading_color};
        background-color: {palette.surface};
        border-radius: 4px;
    }}
    QLabel {{
        color: {palette.text_primary};
        background-color: transparent;
        font-size: 13px;
    }}
    QLabel.MutedHint {{
        color: {palette.text_muted};
        background-color: transparent;
        font-size: 11px;
    }}
    QLineEdit, QPlainTextEdit, QTextBrowser, QComboBox, QSpinBox {{
        background-color: {palette.input_bg};
        color: {palette.text_primary};
        border: 1px solid {palette.input_border};
        border-radius: 8px;
        padding: 6px 10px;
        font-size: 13px;
        selection-background-color: {ACCENT_PURPLE};
        selection-color: {palette.pill_active_text};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextBrowser:focus, QComboBox:focus, QSpinBox:focus {{
        border: 1.5px solid {palette.focus_border};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
        background: transparent;
    }}
    QComboBox QAbstractItemView {{
        background-color: {palette.menu_bg};
        color: {palette.menu_text};
        border: 1px solid {palette.menu_border};
        selection-background-color: {palette.menu_hover_bg};
        selection-color: {palette.menu_hover_text};
        outline: 0;
    }}
    QListView, QListWidget {{
        background-color: {palette.input_bg};
        color: {palette.text_primary};
        border: 1px solid {palette.border};
        border-radius: 8px;
        outline: 0;
    }}
    QListView::item, QListWidget::item {{
        padding: 6px 8px;
        border-radius: 6px;
        color: {palette.text_primary};
    }}
    QListView::item:hover, QListWidget::item:hover {{
        background-color: {palette.card_hover};
        color: {palette.text_primary};
    }}
    QListView::item:selected, QListWidget::item:selected {{
        background-color: {palette.card_selected};
        color: {palette.text_primary};
    }}
    QCheckBox {{
        color: {palette.text_primary};
        background-color: transparent;
        font-size: 13px;
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1.5px solid {palette.input_border};
        border-radius: 4px;
        background-color: {palette.input_bg};
    }}
    QCheckBox::indicator:hover {{
        border-color: {palette.focus_border};
    }}
    QCheckBox::indicator:checked {{
        background-color: {ACCENT_PURPLE};
        border-color: {ACCENT_PURPLE};
    }}
    QPushButton {{
        background-color: {palette.btn_bg};
        color: {palette.btn_text};
        border: 1px solid {palette.btn_border};
        border-radius: 8px;
        padding: 7px 14px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {palette.btn_hover};
        color: {palette.text_primary};
        border-color: {palette.selected_border};
    }}
    QPushButton:checked {{
        background-color: {palette.card_selected};
        color: {palette.text_primary};
        border-color: {palette.selected_border};
    }}
    QPushButton#PrimaryBtn {{
        background: {ACCENT_GRADIENT_QSS};
        color: {palette.pill_active_text};
        border: none;
    }}
    QPushButton#DangerBtn {{
        background-color: {palette.danger_bg};
        color: {palette.danger_text};
        border: 1px solid {palette.danger_border};
    }}
    QPushButton#DangerBtn:hover {{
        background-color: {palette.danger_hover_bg};
        color: {palette.danger_hover_text};
    }}
    QPushButton#HeaderActionBtn {{
        background-color: {palette.btn_bg};
        color: {palette.btn_text};
        border: 1px solid {palette.btn_border};
        border-radius: 8px;
        padding: 5px 10px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#HeaderActionBtn:hover {{
        background-color: {palette.btn_hover};
        color: {palette.text_primary};
    }}
    QPushButton#EmojiChipBtn {{
        background-color: {palette.btn_bg};
        color: {palette.text_primary};
        border: 1px solid {palette.btn_border};
        border-radius: 6px;
        padding: 3px 6px;
        font-size: 13px;
        min-width: 28px;
    }}
    QPushButton#EmojiChipBtn:hover {{
        background-color: {palette.btn_hover};
        border-color: {palette.selected_border};
    }}
    QListWidget::indicator, QTableView::indicator {{
        width: 15px;
        height: 15px;
    }}
    QTabWidget::pane {{
        border: 1px solid {palette.border};
        border-radius: 8px;
        background-color: {palette.surface};
    }}
    QTabBar::tab {{
        background-color: {palette.surface_alt};
        color: {palette.text_secondary};
        border: 1px solid {palette.border};
        padding: 7px 16px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        margin-right: 4px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {ACCENT_GRADIENT_QSS};
        color: {palette.pill_active_text};
        border-color: transparent;
    }}
    {_shared_popup_and_scrollbar_qss(palette)}
    """
