"""
Phasor Handler theme package.

A single source of truth for the app's visual language: design tokens drive the Qt
stylesheet, matplotlib styling, and bundled fonts. Five palettes ship (mono /
ghibli / ice / noir / default), with black & white ("mono") as the default. Call
apply_theme(app) once at startup; switch live with set_theme(app, name). The
chosen theme is remembered across launches via QSettings.
"""

from . import tokens
from . import fonts
from . import mpl
from . import icons
from .fonts import load_fonts
from .qss import build_qss
from .mpl import apply_mpl_theme, style_axes, plot_trace_on_ax, render_trace_pixmap

__all__ = [
    "apply_theme",
    "set_theme",
    "current_theme",
    "available_themes",
    "tokens",
    "fonts",
    "mpl",
    "icons",
    "load_fonts",
    "build_qss",
    "apply_mpl_theme",
    "style_axes",
    "plot_trace_on_ax",
    "render_trace_pixmap",
]

_SETTINGS_ORG = "PhasorHandler"
_SETTINGS_APP = "PhasorHandler"
_SETTINGS_KEY = "theme"


def _settings():
    from PyQt6.QtCore import QSettings
    return QSettings(_SETTINGS_ORG, _SETTINGS_APP)


def available_themes():
    """Return [(name, label), ...] for every selectable theme, in display order."""
    return [(name, tokens.PALETTE_LABELS.get(name, name.title()))
            for name in ("mono", "ghibli", "ice", "noir", "default")]


def current_theme():
    """Return the name of the currently active palette."""
    return tokens.ACTIVE_NAME


def _load_saved_theme():
    """Return the persisted theme name, or 'mono' (black & white) if none/invalid."""
    try:
        value = _settings().value(_SETTINGS_KEY, "mono")
        name = str(value) if value is not None else "mono"
        return name if name in tokens.PALETTES else "mono"
    except Exception:  # noqa: BLE001
        return "mono"


def apply_theme(app, name=None):
    """Apply a theme to a QApplication.

    Loads bundled fonts (once is enough, but re-calling is cheap), binds the named
    palette (or the persisted one when name is None), regenerates the spin/combo
    arrow assets for the palette color, sets the application stylesheet, and
    configures matplotlib rcParams. Every step is exception-safe so a theming
    problem can never block the app from launching.
    """
    if name is None:
        name = _load_saved_theme()
    resolved = tokens.set_active_palette(name)

    try:
        load_fonts()
    except Exception as exc:  # noqa: BLE001
        print(f"[theme] load_fonts failed, using system fonts: {exc}")

    arrows = icons.ensure_arrow_assets(tokens.MUTED)

    try:
        app.setStyleSheet(build_qss(arrows))
    except Exception as exc:  # noqa: BLE001
        print(f"[theme] setStyleSheet failed: {exc}")

    try:
        apply_mpl_theme()
    except Exception as exc:  # noqa: BLE001
        print(f"[theme] apply_mpl_theme failed: {exc}")

    return resolved


def set_theme(app, name):
    """Switch the live theme, persist the choice, and refresh dynamic content.

    The QSS + matplotlib rcParams update immediately, but matplotlib figures that
    captured token colors at construction (the BnC histogram, the trace plot, the
    Second Level cards) only restyle when redrawn, so we trigger those redraws.
    """
    resolved = apply_theme(app, name)

    try:
        _settings().setValue(_SETTINGS_KEY, resolved)
    except Exception as exc:  # noqa: BLE001
        print(f"[theme] could not persist theme: {exc}")

    _refresh_dynamic_content(app)
    return resolved


def _refresh_dynamic_content(app):
    """Restyle/redraw matplotlib-embedded widgets so they pick up the new palette.

    The QSS chrome and rcParams update instantly; matplotlib figures that captured
    token colors at construction need a nudge. Any widget exposing restyle_theme()
    gets called (BnC histogram, trace plot); the open image frame and the Second
    Level card grid are re-rendered through their existing hooks.
    """
    # Component-level restyle: anything that opts in via restyle_theme().
    try:
        for widget in app.allWidgets():
            restyle = getattr(widget, "restyle_theme", None)
            if callable(restyle):
                try:
                    restyle()
                except Exception:  # noqa: BLE001
                    pass
    except Exception:  # noqa: BLE001
        pass

    try:
        from PyQt6.QtWidgets import QMainWindow
    except Exception:  # noqa: BLE001
        return

    for widget in app.topLevelWidgets():
        if not isinstance(widget, QMainWindow):
            continue
        # First Level: re-render the current image frame if the hook exists.
        fn = getattr(widget, "update_tif_frame", None)
        if callable(fn):
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass
        # Second Level: rebuild the trace-card grid (re-renders pixmaps from tokens).
        slw = getattr(widget, "second_level_widget", None)
        refresh = getattr(slw, "refresh_plots", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:  # noqa: BLE001
                pass
