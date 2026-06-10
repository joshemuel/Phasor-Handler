"""
Qt stylesheet builder for the Ice Cyan theme.

build_qss() returns one application-wide stylesheet assembled from the design
tokens and the resolved font families. It deliberately covers every widget class
the app uses (and the native dialogs qdarktheme used to style) so dropping
qdarktheme leaves nothing unthemed.
"""

from . import tokens as t
from . import fonts as f


def build_qss():
    """Return the full application stylesheet as a string."""
    display = f.DISPLAY_FAMILY
    mono = f.MONO_FAMILY
    accent_glow = t.with_alpha(t.ACCENT, 0.12)

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
    QGroupBox {{
        background-color: {t.SURFACE};
        border: {t.BORDER}px solid {t.HAIRLINE};
        border-radius: {t.RADIUS_PANEL}px;
        margin-top: 14px;
        padding: 10px 10px 8px 10px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 6px;
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
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        background-color: {t.SURFACE};
        border: {t.BORDER}px solid {t.HAIRLINE};
        width: 18px;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover,
    QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {t.SURFACE_HOVER};
        border-color: {t.ACCENT};
    }}

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
    """
