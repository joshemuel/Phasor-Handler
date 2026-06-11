"""
Design tokens for the Phasor Handler themes.

Single source of truth for every color used across the app (Qt stylesheet,
matplotlib styling, and any inline widget code). The module exposes the *active*
palette as module-level names (BASE, SURFACE, ... ACCENT, ...) so existing code
that does `from . import tokens; tokens.ACCENT` keeps working unchanged.

Five palettes ship:
  - "mono"    : black & white (the default) - monochrome chrome, white accent;
                only data-critical markers (stim/danger, frame/warn) keep a hue.
  - "ghibli"  : warm cream paper + Totoro forest green (light theme), with
                hand-drawn character touches applied by the QSS layer.
  - "ice"     : the futuristic Ice Cyan palette (near-black blue + cyan accent).
  - "noir"    : graphite surfaces + warm amber accent.
  - "default" : neutral dark, reproducing the pre-redesign qdarktheme look
                (medium-grey surfaces + blue accent).

Switch palettes at runtime with set_active_palette(name); it rebinds the
module-level names in place. Rebuild the QSS and re-apply the matplotlib rcParams
afterwards (theme.apply_theme handles that).
"""

# --- Palette definitions -------------------------------------------------------
# Each palette carries the full set of color tokens. Radii, spacing, border width
# and with_alpha() are shared across palettes (defined below, outside the dicts).

MONO = {
    # Pure monochrome ramp (near-black -> elevated grey)
    "BASE": "#0A0A0A",       # window / deepest background
    "SURFACE": "#121212",    # panels, group boxes
    "ELEVATED": "#1B1B1B",   # inputs, lists, log fields, cards
    "HAIRLINE": "#2C2C2C",   # borders, dividers, plot spines
    # Text
    "TEXT": "#F5F5F5",
    "MUTED": "#8C8C8C",
    # Accent is white; semantic markers keep a muted hue because they encode
    # data (stimulation lines, current-frame indicator) - not chrome.
    "ACCENT": "#FFFFFF",
    "ACCENT_DIM": "#5A5A5A",
    "DANGER": "#D96A5F",
    "SUCCESS": "#79B97C",
    "WARN": "#D9A441",
    # Derived shades
    "ACCENT_HOVER": "#FFFFFF",
    "ACCENT_PRESSED": "#C9C9C9",
    "SURFACE_HOVER": "#181818",
    "ELEVATED_HOVER": "#242424",
    "DISABLED_BG": "#101010",
    "DISABLED_TEXT": "#4A4A4A",
}

GHIBLI = {
    # Warm, muted cream paper - the one light palette. Toned down from a bright
    # near-white cream to a softer, easier-on-the-eyes parchment.
    "BASE": "#E7DFC6",       # muted cream paper
    "SURFACE": "#DDD3B8",    # warm panel
    "ELEVATED": "#F0E9D4",   # inputs sit lighter than panels in a light theme
    "HAIRLINE": "#C0B393",   # dry-grass hairline
    # Text (soot-sprite charcoal)
    "TEXT": "#3A3833",
    "MUTED": "#857C6B",
    # Accent + semantic (forest green, clay, acorn amber)
    "ACCENT": "#4E7B52",
    "ACCENT_DIM": "#9DB89F",
    "DANGER": "#C75B4A",
    "SUCCESS": "#6F9940",
    "WARN": "#C98A2B",
    # Derived shades
    "ACCENT_HOVER": "#5E8F62",
    "ACCENT_PRESSED": "#3E6342",
    "SURFACE_HOVER": "#D5CAAD",
    "ELEVATED_HOVER": "#E7DFC7",
    "DISABLED_BG": "#D9D0B6",
    "DISABLED_TEXT": "#AEA590",
}

ICE = {
    # Core surface ramp (near-black -> elevated)
    "BASE": "#0B0E14",       # window / deepest background
    "SURFACE": "#131A26",    # panels, group boxes
    "ELEVATED": "#1B2535",   # inputs, lists, log fields, cards
    "HAIRLINE": "#243349",   # borders, dividers, plot spines
    # Text
    "TEXT": "#E7EEF7",       # primary text
    "MUTED": "#6B7C95",      # secondary text, ticks, placeholders
    # Accent + semantic
    "ACCENT": "#38E1FF",     # primary action, selection, focus, trace line
    "ACCENT_DIM": "#1E6E84", # accent border at rest, hover scrim
    "DANGER": "#FF4D6D",     # stimulation markers, errors, destructive actions
    "SUCCESS": "#3FE0A3",    # success / run confirmation
    "WARN": "#FFB23E",       # warnings, current-frame indicator
    # Derived shades (hover / pressed states)
    "ACCENT_HOVER": "#5BEBFF",
    "ACCENT_PRESSED": "#1FB9D6",
    "SURFACE_HOVER": "#1A2333",
    "ELEVATED_HOVER": "#223045",
    "DISABLED_BG": "#10151E",
    "DISABLED_TEXT": "#3F4C60",
}

NOIR = {
    # Graphite ramp (charcoal -> elevated grey)
    "BASE": "#0E0E10",
    "SURFACE": "#16161A",
    "ELEVATED": "#1F1F24",
    "HAIRLINE": "#33333B",
    # Text (warm off-white)
    "TEXT": "#ECE8E1",
    "MUTED": "#8A8578",
    # Accent + semantic (warm amber)
    "ACCENT": "#E0A23E",
    "ACCENT_DIM": "#7A5A20",
    "DANGER": "#E5604E",
    "SUCCESS": "#8FB46B",
    "WARN": "#E0A23E",
    # Derived shades
    "ACCENT_HOVER": "#F0B559",
    "ACCENT_PRESSED": "#C2871F",
    "SURFACE_HOVER": "#1C1C21",
    "ELEVATED_HOVER": "#27272E",
    "DISABLED_BG": "#121214",
    "DISABLED_TEXT": "#54514A",
}

DEFAULT = {
    # Neutral grey ramp (pre-redesign qdarktheme look)
    "BASE": "#1E1E1E",
    "SURFACE": "#262626",
    "ELEVATED": "#2F2F2F",
    "HAIRLINE": "#3C3C3C",
    # Text
    "TEXT": "#E4E4E4",
    "MUTED": "#9A9A9A",
    # Accent + semantic (qdarktheme blue)
    "ACCENT": "#3C8DE0",
    "ACCENT_DIM": "#2A5C8F",
    "DANGER": "#E0584E",
    "SUCCESS": "#5BB85B",
    "WARN": "#E0A23E",
    # Derived shades
    "ACCENT_HOVER": "#5BA3EC",
    "ACCENT_PRESSED": "#2F73BD",
    "SURFACE_HOVER": "#303030",
    "ELEVATED_HOVER": "#3A3A3A",
    "DISABLED_BG": "#202020",
    "DISABLED_TEXT": "#5A5A5A",
}

PALETTES = {
    "mono": MONO,
    "ghibli": GHIBLI,
    "ice": ICE,
    "noir": NOIR,
    "default": DEFAULT,
}

# Human-readable labels for the preferences menu.
PALETTE_LABELS = {
    "mono": "Black & White",
    "ghibli": "Ghibli",
    "ice": "Ice Cyan",
    "noir": "Noir",
    "default": "Classic Dark",
}

# Name of the palette currently bound to the module-level names.
ACTIVE_NAME = "mono"


# --- Active palette (module-level names) --------------------------------------
# Initialised from MONO so `tokens.ACCENT` etc. work at import time. Rebound by
# set_active_palette().
BASE = MONO["BASE"]
SURFACE = MONO["SURFACE"]
ELEVATED = MONO["ELEVATED"]
HAIRLINE = MONO["HAIRLINE"]
TEXT = MONO["TEXT"]
MUTED = MONO["MUTED"]
ACCENT = MONO["ACCENT"]
ACCENT_DIM = MONO["ACCENT_DIM"]
DANGER = MONO["DANGER"]
SUCCESS = MONO["SUCCESS"]
WARN = MONO["WARN"]
ACCENT_HOVER = MONO["ACCENT_HOVER"]
ACCENT_PRESSED = MONO["ACCENT_PRESSED"]
SURFACE_HOVER = MONO["SURFACE_HOVER"]
ELEVATED_HOVER = MONO["ELEVATED_HOVER"]
DISABLED_BG = MONO["DISABLED_BG"]
DISABLED_TEXT = MONO["DISABLED_TEXT"]


# --- Shared (palette-independent) tokens --------------------------------------
# --- Corner radii (px) ---
RADIUS_PANEL = 10       # panels, cards
RADIUS_CONTROL = 6      # buttons, inputs
RADIUS_PILL = 999       # pill toggles

# --- Spacing scale (px) ---
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24

# --- Border width (px) ---
BORDER = 1


def set_active_palette(name):
    """Rebind the module-level color names to the palette `name`.

    Unknown names fall back to "mono". Returns the resolved name. Callers must
    rebuild the QSS and re-apply matplotlib styling afterwards for the change to
    show (theme.apply_theme does this).
    """
    global ACTIVE_NAME
    palette = PALETTES.get(name)
    if palette is None:
        name = "mono"
        palette = PALETTES["mono"]
    globals().update(palette)
    ACTIVE_NAME = name
    return name


def with_alpha(hex_color, alpha):
    """Return an 'rgba(r, g, b, a)' string for a #RRGGBB color and 0..1 alpha.

    Useful for translucent scrims/glows in QSS where a flat hex will not do.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"
