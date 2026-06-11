"""
Qt stylesheet builder for the Phasor Handler themes.

build_qss() returns one application-wide stylesheet assembled from the design
tokens (whichever palette is active) and the resolved font families. It
deliberately covers every widget class the app uses (and the native dialogs
qdarktheme used to style) so dropping qdarktheme leaves nothing unthemed.
Palette-specific decorations (the Ghibli soot-sprite slider handles) are
appended when their palette is active.
"""

from . import tokens as t
from . import fonts as f


def build_qss(arrows=None):
    """Return the full application stylesheet as a string.

    arrows: optional dict {"up": path, "down": path} of QSS-ready paths to arrow
    images for spin-box / combo-box sub-controls. When provided, explicit
    ::up-arrow / ::down-arrow rules are emitted so the arrows render (Qt hides the
    native glyph once the buttons are themed). When None, those rules are omitted.
    """
    display = f.DISPLAY_FAMILY
    mono = f.MONO_FAMILY
    accent_glow = t.with_alpha(t.ACCENT, 0.12)
    chevron_idle = t.with_alpha(t.TEXT, 0.5)
    arrow_qss = _spin_arrow_rules(arrows)
    combo_arrow_qss = _combo_arrow_rule(arrows)

    return f"""
    /* ---------- Base ---------- */
    QWidget {{
        background-color: {t.BASE};
        color: {t.TEXT};
        font-family: "{display}";
        font-size: 13px;
        selection-background-color: {t.ACCENT};
        selection-color: {t.BASE};
    }}
    QMainWindow, QDialog {{
        background-color: {t.BASE};
    }}
    QToolTip {{
        background-color: {t.ELEVATED};
        color: {t.TEXT};
        border: {t.BORDER}px solid {t.ACCENT_DIM};
        border-radius: {t.RADIUS_CONTROL}px;
        padding: 4px 8px;
    }}

    /* ---------- Tabs ---------- */
    QTabWidget::pane {{
        border: {t.BORDER}px solid {t.HAIRLINE};
        border-radius: {t.RADIUS_PANEL}px;
        background-color: {t.BASE};
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {t.MUTED};
        padding: 9px 20px;
        margin-right: 4px;
        border: none;
        border-bottom: 2px solid transparent;
        font-weight: 600;
        letter-spacing: 0.5px;
    }}
    QTabBar::tab:selected {{
        color: {t.TEXT};
        border-bottom: 2px solid {t.ACCENT};
    }}
    QTabBar::tab:hover:!selected {{
        color: {t.TEXT};
        border-bottom: 2px solid {t.ACCENT_DIM};
    }}

    /* ---------- Group boxes ---------- */
    /* The title floats fully above the frame (margin-top > title height) with a
       transparent background, so no rectangle ever overlaps the border line. */
    QGroupBox {{
        background-color: {t.SURFACE};
        border: {t.BORDER}px solid {t.HAIRLINE};
        border-radius: {t.RADIUS_PANEL}px;
        margin-top: 18px;
        padding: 10px 10px 8px 10px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 6px;
        top: 0px;
        padding: 0 2px;
        background-color: transparent;
        color: {t.MUTED};
        font-size: 11px;
        letter-spacing: 0.6px;
    }}

    /* ---------- Buttons ---------- */
    QPushButton {{
        background-color: {t.ELEVATED};
        color: {t.TEXT};
        border: {t.BORDER}px solid {t.HAIRLINE};
        padding: 6px 14px;
        border-radius: {t.RADIUS_CONTROL}px;
        min-height: 16px;
    }}
    QPushButton:hover {{
        border-color: {t.ACCENT};
        background-color: {t.SURFACE_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {t.BASE};
        border-color: {t.ACCENT_PRESSED};
    }}
    QPushButton:checked {{
        background-color: {accent_glow};
        border-color: {t.ACCENT};
        color: {t.ACCENT};
    }}
    QPushButton:checked:hover {{
        border-color: {t.ACCENT_HOVER};
    }}
    QPushButton:disabled {{
        background-color: {t.DISABLED_BG};
        color: {t.DISABLED_TEXT};
        border-color: {t.HAIRLINE};
    }}
    /* Primary action buttons (set property class="primary") */
    QPushButton[class="primary"] {{
        background-color: {t.ACCENT};
        color: {t.BASE};
        border: {t.BORDER}px solid {t.ACCENT};
        font-weight: 700;
        padding: 7px 18px;
    }}
    QPushButton[class="primary"]:hover {{
        background-color: {t.ACCENT_HOVER};
        border-color: {t.ACCENT_HOVER};
    }}
    QPushButton[class="primary"]:pressed {{
        background-color: {t.ACCENT_PRESSED};
        border-color: {t.ACCENT_PRESSED};
    }}
    QPushButton[class="primary"]:disabled {{
        background-color: {t.DISABLED_BG};
        color: {t.DISABLED_TEXT};
        border-color: {t.HAIRLINE};
    }}

    /* Preferences gear in the tab-bar corner: flat, muted, accent on hover */
    QPushButton#prefs_button {{
        background-color: transparent;
        color: {t.MUTED};
        border: none;
        padding: 4px 10px;
        margin: 0 6px 2px 0;
        font-weight: 600;
    }}
    QPushButton#prefs_button:hover {{
        color: {t.ACCENT};
        background-color: transparent;
        border: none;
    }}
    QPushButton#prefs_button:pressed {{
        color: {t.ACCENT_PRESSED};
    }}

    /* Collapse/expand chevrons on the First Level side columns: flat, no
       background, half-opacity foreground, accent on hover. */
    QToolButton#collapseChevron {{
        background-color: transparent;
        color: {chevron_idle};
        border: none;
        padding: 0px;
        font-size: 14px;
        font-weight: bold;
    }}
    QToolButton#collapseChevron:hover {{
        color: {t.ACCENT};
        background-color: transparent;
        border: none;
    }}
    QToolButton#collapseChevron:pressed {{
        color: {t.ACCENT_PRESSED};
        background-color: transparent;
    }}

    /* ---------- Text inputs / logs ---------- */
    QTextEdit, QPlainTextEdit {{
        background-color: {t.ELEVATED};
        color: {t.TEXT};
        border: {t.BORDER}px solid {t.HAIRLINE};
        border-radius: {t.RADIUS_CONTROL}px;
        font-family: "{mono}";
        font-size: 12px;
        selection-background-color: {t.ACCENT};
        selection-color: {t.BASE};
    }}
    QLineEdit {{
        background-color: {t.ELEVATED};
        color: {t.TEXT};
        border: {t.BORDER}px solid {t.HAIRLINE};
        border-radius: {t.RADIUS_CONTROL}px;
        padding: 4px 8px;
        font-family: "{mono}";
        selection-background-color: {t.ACCENT};
        selection-color: {t.BASE};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {t.ACCENT};
    }}

    /* ---------- Lists / trees ---------- */
    QListWidget, QTreeView, QTreeWidget, QTableView {{
        background-color: {t.ELEVATED};
        border: {t.BORDER}px solid {t.HAIRLINE};
        border-radius: {t.RADIUS_CONTROL}px;
        alternate-background-color: {t.SURFACE};
        outline: none;
    }}
    QListWidget::item {{
        padding: 5px 6px;
        border-bottom: {t.BORDER}px solid {t.HAIRLINE};
    }}
    QListWidget::item:selected, QTreeView::item:selected {{
        background-color: {accent_glow};
        color: {t.ACCENT};
    }}
    QListWidget::item:hover, QTreeView::item:hover {{
        background-color: {t.SURFACE_HOVER};
    }}
    QHeaderView::section {{
        background-color: {t.SURFACE};
        color: {t.MUTED};
        border: none;
        border-bottom: {t.BORDER}px solid {t.HAIRLINE};
        padding: 4px 8px;
    }}

    /* ---------- Combo boxes ---------- */
    QComboBox {{
        background-color: {t.ELEVATED};
        color: {t.TEXT};
        border: {t.BORDER}px solid {t.HAIRLINE};
        border-radius: {t.RADIUS_CONTROL}px;
        padding: 4px 8px;
        min-width: 6em;
    }}
    QComboBox:hover {{
        border-color: {t.ACCENT};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 22px;
        border-left: {t.BORDER}px solid {t.HAIRLINE};
        border-top-right-radius: {t.RADIUS_CONTROL}px;
        border-bottom-right-radius: {t.RADIUS_CONTROL}px;
        background-color: {t.SURFACE};
    }}
    QComboBox::drop-down:hover {{
        background-color: {t.SURFACE_HOVER};
    }}{combo_arrow_qss}
    QComboBox QAbstractItemView {{
        background-color: {t.ELEVATED};
        color: {t.TEXT};
        border: {t.BORDER}px solid {t.HAIRLINE};
        selection-background-color: {t.ACCENT};
        selection-color: {t.BASE};
        outline: none;
    }}

    /* ---------- Spin boxes (mono numerics) ---------- */
    QSpinBox, QDoubleSpinBox {{
        background-color: {t.ELEVATED};
        color: {t.TEXT};
        border: {t.BORDER}px solid {t.HAIRLINE};
        border-radius: {t.RADIUS_CONTROL}px;
        padding: 3px 6px;
        font-family: "{mono}";
    }}
    QSpinBox:hover, QDoubleSpinBox:hover {{
        border-color: {t.ACCENT};
    }}
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {t.ACCENT};
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        background-color: {t.SURFACE};
        border-left: {t.BORDER}px solid {t.HAIRLINE};
        border-bottom: {t.BORDER}px solid {t.HAIRLINE};
        border-top-right-radius: {t.RADIUS_CONTROL}px;
        width: 18px;
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        background-color: {t.SURFACE};
        border-left: {t.BORDER}px solid {t.HAIRLINE};
        border-top: {t.BORDER}px solid {t.HAIRLINE};
        border-bottom-right-radius: {t.RADIUS_CONTROL}px;
        width: 18px;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover,
    QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {t.SURFACE_HOVER};
    }}
{arrow_qss}

    /* ---------- Checkboxes ---------- */
    QCheckBox {{
        color: {t.TEXT};
        background-color: transparent;
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: {t.BORDER}px solid {t.HAIRLINE};
        border-radius: 4px;
        background-color: {t.ELEVATED};
    }}
    QCheckBox::indicator:checked {{
        background-color: {t.ACCENT};
        border-color: {t.ACCENT};
    }}
    QCheckBox::indicator:hover {{
        border-color: {t.ACCENT};
    }}

    /* ---------- Sliders ---------- */
    QSlider::groove:horizontal {{
        border: none;
        height: 4px;
        background-color: {t.HAIRLINE};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background-color: {t.ACCENT_DIM};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background-color: {t.ACCENT};
        border: none;
        width: 14px;
        height: 14px;
        margin: -6px 0;
        border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{
        background-color: {t.ACCENT_HOVER};
    }}

    /* ---------- Scroll bars ---------- */
    QScrollArea {{
        border: none;
        background-color: {t.BASE};
    }}
    QScrollBar:vertical {{
        background-color: {t.BASE};
        width: 12px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background-color: {t.HAIRLINE};
        border-radius: 6px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {t.ACCENT_DIM};
    }}
    QScrollBar:horizontal {{
        background-color: {t.BASE};
        height: 12px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {t.HAIRLINE};
        border-radius: 6px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {t.ACCENT_DIM};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        background: none;
        border: none;
        width: 0;
        height: 0;
    }}
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: none;
    }}

    /* ---------- Progress bar ---------- */
    QProgressBar {{
        background-color: {t.ELEVATED};
        border: {t.BORDER}px solid {t.HAIRLINE};
        border-radius: {t.RADIUS_CONTROL}px;
        text-align: center;
        color: {t.TEXT};
        font-family: "{mono}";
        height: 18px;
    }}
    QProgressBar::chunk {{
        background-color: {t.ACCENT};
        border-radius: {t.RADIUS_CONTROL - 1}px;
    }}

    /* ---------- Menus ---------- */
    QMenu {{
        background-color: {t.ELEVATED};
        color: {t.TEXT};
        border: {t.BORDER}px solid {t.HAIRLINE};
        border-radius: {t.RADIUS_CONTROL}px;
    }}
    QMenu::item:selected {{
        background-color: {accent_glow};
        color: {t.ACCENT};
    }}
    QMenuBar {{
        background-color: {t.BASE};
        color: {t.TEXT};
    }}
    QMenuBar::item:selected {{
        background-color: {t.SURFACE_HOVER};
    }}

    /* ---------- Tool bars (e.g. matplotlib navigation) ---------- */
    QToolBar {{
        background-color: {t.SURFACE};
        border: none;
        border-radius: {t.RADIUS_CONTROL}px;
        spacing: 2px;
        padding: 2px;
    }}
    QToolButton {{
        background-color: transparent;
        color: {t.TEXT};
        border: {t.BORDER}px solid transparent;
        border-radius: {t.RADIUS_CONTROL}px;
        padding: 3px;
    }}
    QToolButton:hover {{
        background-color: {t.ELEVATED};
        border-color: {t.ACCENT_DIM};
    }}
    QToolButton:checked {{
        background-color: {accent_glow};
        border-color: {t.ACCENT};
    }}

    /* ---------- Labels ---------- */
    QLabel {{
        background-color: transparent;
        color: {t.TEXT};
    }}

    /* ---------- BnC greyed-out when a Z-projection is active ---------- */
    QGroupBox#bnc_group[zprojActive="true"] {{
        background-color: {t.DISABLED_BG};
        border: {t.BORDER}px solid {t.HAIRLINE};
    }}
    QGroupBox#bnc_group[zprojActive="true"] QLabel,
    QGroupBox#bnc_group[zprojActive="true"] QPushButton,
    QGroupBox#bnc_group[zprojActive="true"] QDoubleSpinBox {{
        color: {t.DISABLED_TEXT};
    }}
{_ghibli_rules()}
    """


def _ghibli_rules():
    """Ghibli-only decorations: soot-sprite (susuwatari) slider handles.

    Returns '' for every other palette or when asset generation fails, so the
    base styling above always remains intact.
    """
    if t.ACTIVE_NAME != "ghibli":
        return ""
    try:
        from . import icons
        assets = icons.ensure_ghibli_assets(t.TEXT)
    except Exception:  # noqa: BLE001
        return ""
    if not assets or "soot" not in assets:
        return ""
    return f"""
    /* ---------- Ghibli: soot-sprite slider handle ---------- */
    QSlider::handle:horizontal {{
        image: url("{assets['soot']}");
        background: transparent;
        border: none;
        width: 20px;
        height: 20px;
        margin: -8px 0;
        border-radius: 0;
    }}
    QSlider::groove:horizontal {{
        height: 4px;
        background-color: {t.HAIRLINE};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background-color: {t.ACCENT_DIM};
        border-radius: 2px;
    }}"""


def _spin_arrow_rules(arrows):
    """QSS for spin-box up/down arrow images, or '' when no assets were generated."""
    if not arrows or "up" not in arrows or "down" not in arrows:
        return ""
    up = arrows["up"]
    down = arrows["down"]
    return f"""
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        image: url("{up}");
        width: 8px;
        height: 8px;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        image: url("{down}");
        width: 8px;
        height: 8px;
    }}"""


def _combo_arrow_rule(arrows):
    """QSS for the combo-box drop-down arrow image, or '' when unavailable."""
    if not arrows or "down" not in arrows:
        return ""
    return f"""
    QComboBox::down-arrow {{
        image: url("{arrows['down']}");
        width: 9px;
        height: 9px;
    }}"""
