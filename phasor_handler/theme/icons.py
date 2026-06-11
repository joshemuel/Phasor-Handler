"""
Theme icon assets generated at runtime.

Qt style sheets suppress the native spin-box / combo-box arrow glyph as soon as
the arrow sub-controls are themed without an `image:`. So we paint our own tiny
triangle PNGs (tinted with the active palette color) and reference them from the
QSS. Generating at runtime keeps the arrow color in step with whatever palette is
active and avoids shipping per-theme binary assets.

ensure_arrow_assets(color) returns absolute, forward-slashed file paths suitable
for dropping straight into a QSS `url(...)`.
"""

import hashlib
import os
import tempfile

_CACHE_ROOT = os.path.join(tempfile.gettempdir(), "phasor_handler_theme")


def _qss_path(path):
    """Normalise a filesystem path for use inside a QSS url(): forward slashes."""
    return path.replace("\\", "/")


def _draw_triangle(size, color, direction):
    """Return a QPixmap of `size` px with a filled triangle pointing `direction`.

    direction: "up" or "down". Antialiased, transparent background.
    """
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QColor, QPainter, QPixmap, QPolygonF

    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pm)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        qcol = QColor(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcol)

        # Inset so the glyph has a little breathing room inside its box.
        m = size * 0.28          # horizontal margin
        top = size * 0.34        # vertical margin
        bottom = size - top
        if direction == "up":
            pts = [
                QPointF(size / 2.0, top),
                QPointF(size - m, bottom),
                QPointF(m, bottom),
            ]
        else:  # "down"
            pts = [
                QPointF(m, top),
                QPointF(size - m, top),
                QPointF(size / 2.0, bottom),
            ]
        painter.drawPolygon(QPolygonF(pts))
    finally:
        painter.end()
    return pm


def _draw_soot_sprite(size, body_color):
    """Return a QPixmap of a susuwatari (soot sprite): fuzzy ball + white eyes.

    Used as the QSlider handle in the Ghibli theme. Drawn as a many-pointed
    star (the fuzz) over a solid core, with two white eyes and dark pupils.
    """
    import math

    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QColor, QPainter, QPixmap, QPolygonF

    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pm)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        body = QColor(body_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(body)

        cx = cy = size / 2.0
        outer = size * 0.48
        inner = size * 0.30
        spikes = 14
        pts = []
        for i in range(spikes * 2):
            r = outer if i % 2 == 0 else inner
            ang = math.pi * i / spikes
            pts.append(QPointF(cx + r * math.cos(ang), cy + r * math.sin(ang)))
        painter.drawPolygon(QPolygonF(pts))
        painter.drawEllipse(QPointF(cx, cy), inner * 1.05, inner * 1.05)

        eye_r = size * 0.105
        for ex in (cx - size * 0.115, cx + size * 0.115):
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawEllipse(QPointF(ex, cy - size * 0.02), eye_r, eye_r)
            painter.setBrush(body)
            painter.drawEllipse(QPointF(ex, cy - size * 0.02),
                                eye_r * 0.38, eye_r * 0.38)
    finally:
        painter.end()
    return pm


def _draw_totoro_outline(size, color):
    """Return a QPixmap with a hand-drawn-style Totoro outline (no fill).

    Egg body, leaf ears, round eyes, nose wedge, whiskers and the belly
    chevrons - enough to read instantly as Totoro at icon sizes.
    """
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    s = float(size)

    painter = QPainter(pm)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        qcol = QColor(color)
        pen = QPen(qcol)
        pen.setWidthF(max(1.2, s / 26.0))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Body: tall egg, widest just below the middle.
        body = QPainterPath()
        body.moveTo(0.50 * s, 0.22 * s)
        body.cubicTo(0.78 * s, 0.22 * s, 0.92 * s, 0.55 * s, 0.86 * s, 0.78 * s)
        body.cubicTo(0.80 * s, 0.96 * s, 0.20 * s, 0.96 * s, 0.14 * s, 0.78 * s)
        body.cubicTo(0.08 * s, 0.55 * s, 0.22 * s, 0.22 * s, 0.50 * s, 0.22 * s)
        painter.drawPath(body)

        # Ears: leaf-shaped spikes (mirrored).
        for sgn in (-1, 1):
            tip_x = 0.50 * s + sgn * 0.18 * s
            ear = QPainterPath()
            ear.moveTo(0.50 * s + sgn * 0.10 * s, 0.24 * s)
            ear.quadTo(0.50 * s + sgn * 0.14 * s, 0.10 * s, tip_x, 0.05 * s)
            ear.quadTo(0.50 * s + sgn * 0.24 * s, 0.12 * s,
                       0.50 * s + sgn * 0.26 * s, 0.30 * s)
            painter.drawPath(ear)

        # Eyes + nose.
        for sgn in (-1, 1):
            painter.drawEllipse(QPointF(0.50 * s + sgn * 0.14 * s, 0.36 * s),
                                0.045 * s, 0.045 * s)
        nose = QPainterPath()
        nose.moveTo(0.46 * s, 0.41 * s)
        nose.lineTo(0.54 * s, 0.41 * s)
        nose.lineTo(0.50 * s, 0.455 * s)
        nose.closeSubpath()
        painter.fillPath(nose, qcol)

        # Whiskers: two per side, fanning slightly outward.
        for sgn in (-1, 1):
            painter.drawLine(QPointF((0.50 + sgn * 0.20) * s, 0.40 * s),
                             QPointF((0.50 + sgn * 0.38) * s, 0.37 * s))
            painter.drawLine(QPointF((0.50 + sgn * 0.20) * s, 0.45 * s),
                             QPointF((0.50 + sgn * 0.38) * s, 0.46 * s))

        # Belly: top boundary curve + three chevrons.
        belly = QPainterPath()
        belly.moveTo(0.26 * s, 0.60 * s)
        belly.quadTo(0.50 * s, 0.50 * s, 0.74 * s, 0.60 * s)
        painter.drawPath(belly)
        for x in (0.38, 0.50, 0.62):
            chev = QPainterPath()
            chev.moveTo((x - 0.04) * s, 0.72 * s)
            chev.lineTo(x * s, 0.65 * s)
            chev.lineTo((x + 0.04) * s, 0.72 * s)
            painter.drawPath(chev)
    finally:
        painter.end()
    return pm


def ensure_ghibli_assets(color, soot_size=20, totoro_size=64):
    """Generate (or reuse cached) Ghibli decoration PNGs tinted with `color`.

    Returns {"soot": <path>, "totoro": <path>} with QSS/QIcon-ready paths, or an
    empty dict if generation fails (callers then simply skip the decorations).
    """
    try:
        key = hashlib.md5(
            f"ghibli:{color}:{soot_size}:{totoro_size}".encode("utf-8")
        ).hexdigest()[:10]
        cache_dir = os.path.join(_CACHE_ROOT, key)
        os.makedirs(cache_dir, exist_ok=True)

        paths = {}
        for name, draw in (
            ("soot", lambda: _draw_soot_sprite(soot_size, color)),
            ("totoro", lambda: _draw_totoro_outline(totoro_size, color)),
        ):
            path = os.path.join(cache_dir, f"{name}.png")
            if not os.path.isfile(path):
                pm = draw()
                if not pm.save(path, "PNG"):
                    return {}
            paths[name] = _qss_path(path)
        return paths
    except Exception as exc:  # noqa: BLE001
        print(f"[theme] ensure_ghibli_assets failed: {exc}")
        return {}


def _draw_nav_arrow(size, color, direction):
    """Return a QPixmap with a clean directional arrow (stem + arrowhead).

    direction: "left", "right" or "up". Used to give the themed (non-native)
    QFileDialog navigation buttons high-contrast, unambiguous glyphs instead of
    the low-contrast style defaults that blend into the dark palettes.
    """
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap

    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    s = float(size)

    painter = QPainter(pm)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color))
        pen.setWidthF(max(1.6, s / 9.0))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        # Draw a left-pointing arrow in a centred frame, then rotate for the
        # other directions so all three share identical geometry.
        painter.translate(s / 2.0, s / 2.0)
        if direction == "right":
            painter.rotate(180)
        elif direction == "up":
            painter.rotate(90)  # clockwise (y-down): left -> up

        half = s * 0.30
        head = s * 0.22
        tip = QPointF(-half, 0.0)
        painter.drawLine(QPointF(half, 0.0), tip)                 # stem
        painter.drawLine(tip, QPointF(-half + head, -head))       # upper barb
        painter.drawLine(tip, QPointF(-half + head, head))        # lower barb
    finally:
        painter.end()
    return pm


def ensure_nav_assets(color, size=18):
    """Generate (or reuse cached) back/forward/up navigation arrow PNGs.

    Returns {"back": <path>, "forward": <path>, "up": <path>} with QSS/QIcon-ready
    paths, or an empty dict if generation fails.
    """
    try:
        key = hashlib.md5(f"nav:{color}:{size}".encode("utf-8")).hexdigest()[:10]
        cache_dir = os.path.join(_CACHE_ROOT, key)
        os.makedirs(cache_dir, exist_ok=True)

        paths = {}
        for name, direction in (("back", "left"), ("forward", "right"), ("up", "up")):
            path = os.path.join(cache_dir, f"{name}.png")
            if not os.path.isfile(path):
                pm = _draw_nav_arrow(size, color, direction)
                if not pm.save(path, "PNG"):
                    return {}
            paths[name] = _qss_path(path)
        return paths
    except Exception as exc:  # noqa: BLE001
        print(f"[theme] ensure_nav_assets failed: {exc}")
        return {}


def ensure_arrow_assets(color, size=12):
    """Generate (or reuse cached) up/down arrow PNGs tinted with `color`.

    Returns a dict {"up": <path>, "down": <path>} with QSS-ready paths, or an
    empty dict if generation fails (caller then simply omits the image rules).
    """
    try:
        key = hashlib.md5(f"{color}:{size}".encode("utf-8")).hexdigest()[:10]
        cache_dir = os.path.join(_CACHE_ROOT, key)
        os.makedirs(cache_dir, exist_ok=True)

        paths = {}
        for direction in ("up", "down"):
            path = os.path.join(cache_dir, f"{direction}.png")
            if not os.path.isfile(path):
                pm = _draw_triangle(size, color, direction)
                if not pm.save(path, "PNG"):
                    return {}
            paths[direction] = _qss_path(path)
        return paths
    except Exception as exc:  # noqa: BLE001
        print(f"[theme] ensure_arrow_assets failed: {exc}")
        return {}
