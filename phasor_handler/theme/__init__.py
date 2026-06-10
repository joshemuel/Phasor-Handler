"""
Phasor Handler "Ice Cyan" theme package.

A single source of truth for the app's visual language: design tokens drive the Qt
stylesheet, matplotlib styling, and bundled fonts. Call apply_theme(app) once at
startup.
"""

from . import tokens
from . import fonts
from . import mpl
from .fonts import load_fonts
from .qss import build_qss
from .mpl import apply_mpl_theme, style_axes, plot_trace_on_ax, render_trace_pixmap

__all__ = [
    "apply_theme",
    "tokens",
    "fonts",
    "mpl",
    "load_fonts",
    "build_qss",
    "apply_mpl_theme",
    "style_axes",
    "plot_trace_on_ax",
    "render_trace_pixmap",
]


def apply_theme(app):
    """Apply the full Ice Cyan theme to a QApplication.

    Loads bundled fonts, sets the application stylesheet, and configures matplotlib
    rcParams. Every step is exception-safe so a theming problem can never block the
    app from launching.
    """
    try:
        load_fonts()
    except Exception as exc:  # noqa: BLE001
        print(f"[theme] load_fonts failed, using system fonts: {exc}")

    try:
        app.setStyleSheet(build_qss())
    except Exception as exc:  # noqa: BLE001
        print(f"[theme] setStyleSheet failed: {exc}")

    try:
        apply_mpl_theme()
    except Exception as exc:  # noqa: BLE001
        print(f"[theme] apply_mpl_theme failed: {exc}")
