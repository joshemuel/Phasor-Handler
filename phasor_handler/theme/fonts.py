"""
Bundled-font loading for the Phasor Handler themes.

Registers the bundled OFL TTFs (Space Grotesk for display, JetBrains Mono for
numerics/logs/plots) with both Qt (QFontDatabase) and matplotlib (font_manager),
then resolves the actual family names. Everything degrades gracefully: if the
fonts/ directory is empty or a file fails to register, we fall back to system
fonts and the app still launches and looks correct.

Resolved families are exposed as module-level names that qss.py and mpl.py read,
so nothing else hardcodes a font family string.
"""

import sys
from importlib.resources import files, as_file

from PyQt6.QtGui import QFontDatabase

# Resolved at load time by load_fonts(); seeded with safe system fallbacks so the
# module is usable even if load_fonts() is never called or fails entirely.
DISPLAY_FAMILY = "Segoe UI" if sys.platform.startswith("win") else "Sans Serif"
MONO_FAMILY = "Consolas" if sys.platform.startswith("win") else "Monospace"

# Preferred bundled families, in resolution priority.
_DISPLAY_PREFS = ["Space Grotesk", "Segoe UI", "Arial", "Sans Serif"]
_MONO_PREFS = ["JetBrains Mono", "Consolas", "Courier New", "Monospace"]

_loaded = False


def _resolve(preferred, available):
    """Return the first preferred family that is actually available."""
    avail_lower = {a.lower(): a for a in available}
    for name in preferred:
        if name.lower() in avail_lower:
            return avail_lower[name.lower()]
    return preferred[-1]


def load_fonts():
    """Register bundled TTFs with Qt and matplotlib; resolve family names.

    Idempotent and exception-safe. Updates module globals DISPLAY_FAMILY and
    MONO_FAMILY. Returns (DISPLAY_FAMILY, MONO_FAMILY).
    """
    global DISPLAY_FAMILY, MONO_FAMILY, _loaded
    if _loaded:
        return DISPLAY_FAMILY, MONO_FAMILY

    registered_families = set()
    try:
        font_dir = files("phasor_handler.theme") / "fonts"
        ttfs = [p for p in font_dir.iterdir() if p.name.lower().endswith(".ttf")]
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        ttfs = []

    for ttf in ttfs:
        # --- Qt registration (data form: survives zip/frozen installs) ---
        try:
            data = ttf.read_bytes()
            font_id = QFontDatabase.addApplicationFontFromData(data)
            if font_id != -1:
                for fam in QFontDatabase.applicationFontFamilies(font_id):
                    registered_families.add(fam)
        except Exception as exc:  # noqa: BLE001 - never let a font block launch
            print(f"[theme] Qt font registration failed for {ttf.name}: {exc}")

        # --- matplotlib registration (independent of Qt; needs a real path) ---
        try:
            from matplotlib import font_manager
            with as_file(ttf) as real_path:
                font_manager.fontManager.addfont(str(real_path))
        except Exception as exc:  # noqa: BLE001
            print(f"[theme] matplotlib font registration failed for {ttf.name}: {exc}")

    # Resolve against everything Qt knows about (bundled + system).
    try:
        all_families = set(QFontDatabase.families())
    except Exception:  # noqa: BLE001
        all_families = set()
    all_families |= registered_families

    DISPLAY_FAMILY = _resolve(_DISPLAY_PREFS, all_families)
    MONO_FAMILY = _resolve(_MONO_PREFS, all_families)
    _loaded = True
    print(f"[theme] fonts resolved -> display='{DISPLAY_FAMILY}', mono='{MONO_FAMILY}'")
    return DISPLAY_FAMILY, MONO_FAMILY
