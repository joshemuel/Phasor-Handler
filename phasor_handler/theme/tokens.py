"""
Design tokens for the Phasor Handler "Ice Cyan" theme.

Single source of truth for every color, radius, and spacing value used across the
app (Qt stylesheet, matplotlib styling, and any inline widget code). Change a value
here and it propagates everywhere. Aesthetic: futuristic, noir, sleek.
"""

# --- Core surface ramp (near-black -> elevated) ---
BASE = "#0B0E14"        # window / deepest background
SURFACE = "#131A26"     # panels, group boxes
ELEVATED = "#1B2535"    # inputs, lists, log fields, cards
HAIRLINE = "#243349"    # borders, dividers, plot spines

# --- Text ---
TEXT = "#E7EEF7"        # primary text
MUTED = "#6B7C95"       # secondary text, ticks, placeholders

# --- Accent + semantic ---
ACCENT = "#38E1FF"      # primary action, selection, focus, trace line
ACCENT_DIM = "#1E6E84"  # accent border at rest, hover scrim
DANGER = "#FF4D6D"      # stimulation markers, errors, destructive actions
SUCCESS = "#3FE0A3"     # success / run confirmation
WARN = "#FFB23E"        # warnings, current-frame indicator

# --- Derived shades (hover / pressed states) ---
ACCENT_HOVER = "#5BEBFF"
ACCENT_PRESSED = "#1FB9D6"
SURFACE_HOVER = "#1A2333"
ELEVATED_HOVER = "#223045"
DISABLED_BG = "#10151E"
DISABLED_TEXT = "#3F4C60"

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


def with_alpha(hex_color, alpha):
    """Return an 'rgba(r, g, b, a)' string for a #RRGGBB color and 0..1 alpha.

    Useful for translucent scrims/glows in QSS where a flat hex will not do.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"
