"""Çapraz platform birebir UI/UX sabitleri, renk paletleri, Inter yazı tipi ve stil şablonu."""

from __future__ import annotations

import importlib.resources
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtGui import QFont, QFontDatabase

# Tüm işletim sistemlerinde birebir aynı kalan boyut, yarıçap, boşluk ve animasyon sabitleri
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
ACCENT_GRADIENT_QSS = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #22D3EE)"

SEARCH_PLACEHOLDER = "Ara… (mesaj, kategori, etiket)"
SEARCH_CHIP_TEXT = "Ctrl+K"
FOOTER_HINTS_TEXT = "↑↓ Gezin · ⏎ Yapıştır · Ctrl+⏎ Kopyala · Esc Kapat"

CATEGORY_TABS: tuple[tuple[str, str, str], ...] = (
    ("ALL", "Tümü", ""),
    ("A", "A · İş Ortağı", "L-Win+A"),
    ("Z", "Z · Kurye", "L-Win+Z"),
    ("X", "X · Canlı Yardım", "L-Win+X"),
    ("Q", "Q · Turkcell", "L-Win+Q"),
)


@dataclass(frozen=True)
class ThemePalette:
    """Koyu veya açık tema renk tanımları (OS bağımsız)."""

    name: str
    window_bg: str
    window_bg_translucent: str
    surface: str
    surface_alt: str
    border: str
    text_primary: str
    text_secondary: str
    text_muted: str
    hover_bg: str
    selected_bg: str
    selected_border: str
    pill_bg: str
    pill_text: str
    badge_bg: str
    badge_text: str
    highlight_bg: str
    highlight_text: str
    toast_bg: str
    toast_text: str


DARK_PALETTE = ThemePalette(
    name="dark",
    window_bg="rgba(18, 18, 22, 0.94)",
    window_bg_translucent="rgba(18, 18, 22, 0.85)",
    surface="#1A1A22",
    surface_alt="#23232E",
    border="rgba(255, 255, 255, 0.11)",
    text_primary="#F8FAFC",
    text_secondary="#CBD5E1",
    text_muted="#94A3B8",
    hover_bg="rgba(124, 58, 237, 0.18)",
    selected_bg="rgba(124, 58, 237, 0.28)",
    selected_border="#22D3EE",
    pill_bg="rgba(255, 255, 255, 0.07)",
    pill_text="#CBD5E1",
    badge_bg="rgba(34, 211, 238, 0.14)",
    badge_text="#22D3EE",
    highlight_bg="rgba(34, 211, 238, 0.28)",
    highlight_text="#FFFFFF",
    toast_bg="rgba(24, 24, 32, 0.96)",
    toast_text="#F8FAFC",
)

LIGHT_PALETTE = ThemePalette(
    name="light",
    window_bg="rgba(248, 250, 252, 0.96)",
    window_bg_translucent="rgba(248, 250, 252, 0.88)",
    surface="#FFFFFF",
    surface_alt="#F1F5F9",
    border="rgba(15, 23, 42, 0.12)",
    text_primary="#0F172A",
    text_secondary="#334155",
    text_muted="#64748B",
    hover_bg="rgba(124, 58, 237, 0.14)",
    selected_bg="rgba(124, 58, 237, 0.22)",
    selected_border="#7C3AED",
    pill_bg="rgba(15, 23, 42, 0.06)",
    pill_text="#334155",
    badge_bg="rgba(124, 58, 237, 0.12)",
    badge_text="#6D28D9",
    highlight_bg="rgba(124, 58, 237, 0.22)",
    highlight_text="#0F172A",
    toast_bg="rgba(15, 23, 42, 0.94)",
    toast_text="#F8FAFC",
)


def resolve_palette(theme_setting: str, *, os_is_dark: bool = True) -> ThemePalette:
    """Tema ayarını ('auto' | 'dark' | 'light') ThemePalette nesnesine çözer."""
    t = (theme_setting or "dark").strip().lower()
    if t == "light":
        return LIGHT_PALETTE
    if t == "auto":
        return DARK_PALETTE if os_is_dark else LIGHT_PALETTE
    return DARK_PALETTE


def get_asset_path(relative_path: str) -> Path:
    """Geliştirme ortamında ve PyInstaller tek dosya paketinde varlık yolunu çözer."""
    try:
        pkg_root = importlib.resources.files("qtp_app")
        candidate = Path(str(pkg_root)) / "assets" / relative_path
        if candidate.exists():
            return candidate
    except Exception:
        pass
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


def build_overlay_stylesheet(palette: ThemePalette, *, translucent: bool = False) -> str:
    """Overlay penceresi için platformdan bağımsız tam QSS stil şablonunu üretir."""
    bg = palette.window_bg_translucent if translucent else palette.window_bg
    return f"""
    QFrame#OverlayCard {{
        background-color: {bg};
        border: 1px solid {palette.border};
        border-radius: {WINDOW_CORNER_RADIUS}px;
    }}
    QLineEdit#SearchInput {{
        background-color: {palette.surface};
        color: {palette.text_primary};
        border: 1.5px solid {palette.border};
        border-radius: 10px;
        padding: 8px 68px 8px 14px;
        font-size: {FONT_SIZE_INPUT}px;
        selection-background-color: {ACCENT_PURPLE};
    }}
    QLineEdit#SearchInput:focus {{
        border: 1.5px solid {ACCENT_CYAN};
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
        border: 1px solid transparent;
        border-radius: {PILL_RADIUS}px;
        padding: 5px 12px;
        font-size: {FONT_SIZE_PILL}px;
        font-weight: 600;
        letter-spacing: 0.4px;
    }}
    QPushButton.CategoryPill:hover {{
        background-color: {palette.hover_bg};
        color: {palette.text_primary};
    }}
    QPushButton.CategoryPill[active="true"] {{
        background: {ACCENT_GRADIENT_QSS};
        color: #FFFFFF;
        border: 1px solid rgba(255, 255, 255, 0.18);
    }}
    QListView#SnippetList {{
        background-color: transparent;
        border: none;
        outline: 0;
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
        font-size: {FONT_SIZE_HINT}px;
    }}
    QLabel#ItemCountLabel {{
        color: {palette.text_muted};
        font-size: {FONT_SIZE_HINT}px;
        font-weight: 600;
    }}
    QPushButton#HeaderActionBtn {{
        background-color: {palette.pill_bg};
        color: {palette.text_secondary};
        border: 1px solid {palette.border};
        border-radius: 8px;
        padding: 5px 10px;
        font-size: {FONT_SIZE_META}px;
        font-weight: 600;
    }}
    QPushButton#HeaderActionBtn:hover {{
        background-color: {palette.hover_bg};
        color: {palette.text_primary};
    }}
    QLabel#ToastLabel {{
        background-color: {palette.toast_bg};
        color: {palette.toast_text};
        border: 1px solid {ACCENT_CYAN};
        border-radius: 10px;
        padding: 8px 14px;
        font-size: {FONT_SIZE_META + 1}px;
        font-weight: 600;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(148, 163, 184, 0.35);
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: rgba(124, 58, 237, 0.65);
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """


def build_dialog_stylesheet(palette: ThemePalette) -> str:
    """Ayarlar ve Yardım pencereleri için tema stil şablonu."""
    return f"""
    QDialog {{
        background-color: {palette.surface};
        color: {palette.text_primary};
    }}
    QLabel {{
        color: {palette.text_primary};
        font-size: 13px;
    }}
    QLabel.MutedHint {{
        color: {palette.text_muted};
        font-size: 11px;
    }}
    QLineEdit, QComboBox, QSpinBox, QTextBrowser {{
        background-color: {palette.surface_alt};
        color: {palette.text_primary};
        border: 1px solid {palette.border};
        border-radius: 8px;
        padding: 6px 10px;
        font-size: 13px;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border: 1.5px solid {ACCENT_CYAN};
    }}
    QCheckBox {{
        color: {palette.text_primary};
        font-size: 13px;
        spacing: 8px;
    }}
    QPushButton {{
        background-color: {palette.pill_bg};
        color: {palette.text_primary};
        border: 1px solid {palette.border};
        border-radius: 8px;
        padding: 7px 14px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {palette.hover_bg};
    }}
    QPushButton#PrimaryBtn {{
        background: {ACCENT_GRADIENT_QSS};
        color: #FFFFFF;
        border: none;
    }}
    QTabWidget::pane {{
        border: 1px solid {palette.border};
        border-radius: 8px;
        background-color: {palette.surface};
    }}
    QTabBar::tab {{
        background-color: {palette.surface_alt};
        color: {palette.text_secondary};
        padding: 7px 16px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        margin-right: 4px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {ACCENT_GRADIENT_QSS};
        color: #FFFFFF;
    }}
    """
