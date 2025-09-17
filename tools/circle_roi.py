from PyQt6.QtCore import QObject, pyqtSignal, Qt, QRect, QPoint, QSize, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PyQt6.QtWidgets import QLabel
from typing import Optional
import numpy as np


class CircleRoiTool(QObject):
    """Ellipse ROI tool attached to a QLabel showing a scaled pixmap.

    Internal bbox is stored as a float tuple (left, top, width, height).
    Translation uses QPointF anchor and bbox_origin floats so moving does
    not introduce rounding drift that changes size.
    """
    roiChanged = pyqtSignal(tuple)   # (x0, y0, x1, y1) in image coords (during drag)
    roiFinalized = pyqtSignal(tuple) # (x0, y0, x1, y1) in image coords (on release)

    def __init__(self, label: QLabel, parent=None):
        super().__init__(parent)
        self._label = label
        self._label.setMouseTracking(True)
        self._label.installEventFilter(self)

        # Display geometry
        self._draw_rect = None   # QRect of the drawn pixmap within the label
        self._img_w = None
        self._img_h = None
        self._base_pixmap = None

        # ROI/drawing state
        self._start_pos = None   # QPointF (press)
        self._current_pos = None # QPointF (current mouse)
        # bbox stored as float tuple: (left, top, width, height)
        self._bbox = None
        self._dragging = False

        # persistent saved ROIs: list of dicts with keys 'name','xyxy','color'
        # color may be a QColor or (r,g,b,a) tuple
        self._saved_rois = []

        # translation state
        self._mode = None  # 'draw' or 'translate' or None
        self._translate_anchor = None  # QPointF
        self._bbox_origin = None       # (left, top, w, h) float tuple

    # --- Public API you call from app.py when the image view updates ---

    def set_draw_rect(self, rect: QRect):
        """Rectangle where the scaled pixmap is drawn inside the label."""
        if rect is None:
            self._draw_rect = None
        else:
            self._draw_rect = QRect(rect)

    def set_image_size(self, w: int, h: int):
        """True image size in pixels (width, height)."""
        self._img_w = int(w)
        self._img_h = int(h)

    def set_pixmap(self, pm: Optional[QPixmap]):
        """The pixmap currently shown in the label (scaled)."""
        self._base_pixmap = pm

    def clear(self):
        """Clear the ROI overlay and internal state."""
        self._start_pos = None
        self._current_pos = None
        self._bbox = None
        self._dragging = False
        if self._base_pixmap is not None:
            self._label.setPixmap(self._base_pixmap)

    # --- Event filter for mouse handling and painting overlay ---

    def eventFilter(self, obj, event):
        if obj is not self._label:
            return False

        et = event.type()

        if et == event.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton and self._in_draw_rect(event.position()):
                # start drawing: left button defines first corner
                self._mode = 'draw'
                self._dragging = True
                self._start_pos = event.position()  # QPointF
                self._current_pos = self._start_pos
                self._update_bbox_from_points()
                self._paint_overlay()
                return True

            # right button: start translation only if click is inside existing bbox
            if event.button() == Qt.MouseButton.RightButton and self._bbox is not None:
                p = event.position()  # QPointF
                left, top, w, h = self._bbox
                right = left + w
                bottom = top + h
                # 1-pixel margin tolerance
                if (left - 1 <= p.x() <= right + 1) and (top - 1 <= p.y() <= bottom + 1):
                    self._mode = 'translate'
                    self._dragging = True
                    self._translate_anchor = p
                    self._bbox_origin = (left, top, w, h)
                    return True

        elif et == event.Type.MouseMove:
            if not self._dragging:
                return False
            pos = self._constrain_to_draw_rect(event.position())
            if self._mode == 'draw' and self._start_pos is not None:
                self._current_pos = pos
                self._update_bbox_from_points()
                self._paint_overlay()
                # Emit live ROI (image coords)
                xyxy = self._current_roi_image_coords()
                if xyxy is not None:
                    self.roiChanged.emit(xyxy)
                return True

            elif self._mode == 'translate' and self._bbox_origin is not None and self._translate_anchor is not None:
                # compute delta and move bbox using float math to avoid size drift
                anchor = self._translate_anchor
                dx = pos.x() - anchor.x()
                dy = pos.y() - anchor.y()
                ox, oy, ow, oh = self._bbox_origin
                new_left = ox + dx
                new_top = oy + dy
                # constrain inside draw_rect if available
                if self._draw_rect is not None:
                    dl = float(self._draw_rect.left())
                    dt = float(self._draw_rect.top())
                    dr = float(self._draw_rect.left() + self._draw_rect.width())
                    db = float(self._draw_rect.top() + self._draw_rect.height())
                    if new_left < dl:
                        new_left = dl
                    if new_top < dt:
                        new_top = dt
                    if new_left + ow > dr:
                        new_left = dr - ow
                    if new_top + oh > db:
                        new_top = db - oh
                self._bbox = (new_left, new_top, ow, oh)
                self._paint_overlay()
                xyxy = self._current_roi_image_coords()
                if xyxy is not None:
                    self.roiChanged.emit(xyxy)
                return True

        elif et == event.Type.MouseButtonRelease:
            if not self._dragging:
                return False
            if self._mode == 'draw' and event.button() == Qt.MouseButton.LeftButton:
                self._dragging = False
                # finalize current pos and bbox
                self._current_pos = self._constrain_to_draw_rect(event.position())
                self._update_bbox_from_points()
                self._paint_overlay(final=True)
                xyxy = self._current_roi_image_coords()
                if xyxy is not None:
                    self.roiFinalized.emit(xyxy)
                self._mode = None
                return True

            if self._mode == 'translate' and event.button() == Qt.MouseButton.RightButton:
                self._dragging = False
                # finalize translation
                self._translate_anchor = None
                self._bbox_origin = None
                xyxy = self._current_roi_image_coords()
                if xyxy is not None:
                    self.roiFinalized.emit(xyxy)
                self._mode = None
                return True

        return False

    # --- Helpers ---

    def _in_draw_rect(self, posf):
        if self._draw_rect is None:
            return False
        return self._draw_rect.contains(posf.toPoint())

    def _constrain_to_draw_rect(self, posf):
        # Accept and return QPointF for sub-pixel precision when possible
        try:
            x = float(posf.x())
            y = float(posf.y())
        except Exception:
            p = posf.toPoint()
            x = float(p.x()); y = float(p.y())
        # Return raw position (no clamping). Mask/computation will clip later.
        return QPointF(x, y)

    def _update_bbox_from_points(self):
        """Compute rectangular bbox (left,top,w,h) in label coords from start/current QPointF."""
        if self._start_pos is None or self._current_pos is None:
            self._bbox = None
            return
        x0 = float(self._start_pos.x())
        y0 = float(self._start_pos.y())
        x1 = float(self._current_pos.x())
        y1 = float(self._current_pos.y())
        left = min(x0, x1)
        top = min(y0, y1)
        w = max(1.0, abs(x1 - x0))
        h = max(1.0, abs(y1 - y0))
        self._bbox = (left, top, w, h)

    def _paint_overlay(self, final=False):
        if self._base_pixmap is None:
            return
        overlay = QPixmap(self._base_pixmap)
        painter = QPainter(overlay)
        pen = QPen(QColor(255, 255, 0, 180))
        pen.setWidth(3)
        painter.setPen(pen)

        if self._bbox is not None:
            left, top, w, h = self._bbox
            painter.drawEllipse(int(round(left)), int(round(top)), int(round(w)), int(round(h)))

        # Draw any saved ROIs on top of the overlay
        try:
            font = QFont()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            for idx, saved in enumerate(list(self._saved_rois or [])):
                try:
                    xyxy = saved.get('xyxy')
                    if xyxy is None:
                        continue
                    lbbox = self._label_bbox_from_image_xyxy(xyxy)
                    if lbbox is None:
                        continue
                    lx0, ly0, lw, lh = lbbox
                    # determine color
                    col = saved.get('color')
                    if isinstance(col, QColor):
                        qcol = col
                    elif isinstance(col, (tuple, list)) and len(col) >= 3:
                        a = col[3] if len(col) > 3 else 200
                        qcol = QColor(int(col[0]), int(col[1]), int(col[2]), int(a))
                    else:
                        qcol = QColor(200, 100, 10, 200)
                    spen = QPen(qcol)
                    spen.setWidth(3)
                    painter.setPen(spen)
                    painter.drawEllipse(int(round(lx0)), int(round(ly0)), int(round(lw)), int(round(lh)))
                    # draw index in middle
                    tx = int(round(lx0 + lw / 2.0))
                    ty = int(round(ly0 + lh / 2.0))
                    # choose text color that contrasts (white or black)
                    text_col = QColor(255, 255, 255)
                    painter.setPen(QPen(text_col))
                    painter.drawText(tx - 6, ty + 6, str(idx + 1))
                except Exception:
                    continue
        except Exception:
            pass

        painter.end()
        self._label.setPixmap(overlay)

    def show_bbox_image_coords(self, xyxy):
        """Draw the stored bbox given in IMAGE coordinates (x0,y0,x1,y1).
        Maps image coords to label/pixmap coords using the current draw_rect
        and image size, sets the internal bbox, and repaints the overlay.
        Returns True when painted, False otherwise.
        """
        if xyxy is None:
            return False
        if self._draw_rect is None or self._img_w is None or self._img_h is None:
            return False
        if self._base_pixmap is None:
            return False

        try:
            X0, Y0, X1, Y1 = xyxy
        except Exception:
            return False

        pw = float(self._draw_rect.width())
        ph = float(self._draw_rect.height())

        nx0 = float(X0) / max(1.0, float(self._img_w))
        ny0 = float(Y0) / max(1.0, float(self._img_h))
        nx1 = float(X1) / max(1.0, float(self._img_w))
        ny1 = float(Y1) / max(1.0, float(self._img_h))

        lx0 = float(self._draw_rect.left() + nx0 * pw)
        ly0 = float(self._draw_rect.top()  + ny0 * ph)
        lx1 = float(self._draw_rect.left() + nx1 * pw)
        ly1 = float(self._draw_rect.top()  + ny1 * ph)

        w = max(1.0, lx1 - lx0)
        h = max(1.0, ly1 - ly0)

        self._bbox = (lx0, ly0, w, h)
        self._paint_overlay()
        return True

    def _label_bbox_from_image_xyxy(self, xyxy):
        """Return (lx0, ly0, w, h) mapping provided image xyxy into label coords or None."""
        if xyxy is None:
            return None
        if self._draw_rect is None or self._img_w is None or self._img_h is None:
            return None
        try:
            X0, Y0, X1, Y1 = xyxy
        except Exception:
            return None

        pw = float(self._draw_rect.width())
        ph = float(self._draw_rect.height())

        nx0 = float(X0) / max(1.0, float(self._img_w))
        ny0 = float(Y0) / max(1.0, float(self._img_h))
        nx1 = float(X1) / max(1.0, float(self._img_w))
        ny1 = float(Y1) / max(1.0, float(self._img_h))

        lx0 = float(self._draw_rect.left() + nx0 * pw)
        ly0 = float(self._draw_rect.top()  + ny0 * ph)
        lx1 = float(self._draw_rect.left() + nx1 * pw)
        ly1 = float(self._draw_rect.top()  + ny1 * ph)

        w = max(1.0, lx1 - lx0)
        h = max(1.0, ly1 - ly0)
        return (lx0, ly0, w, h)

    def set_saved_rois(self, saved_rois):
        """Provide a list of saved ROI dicts (name, xyxy, color) to be drawn persistently."""
        try:
            if saved_rois is None:
                self._saved_rois = []
            else:
                # store a shallow copy
                self._saved_rois = list(saved_rois)
        except Exception:
            self._saved_rois = []

    # Backwards-compatible alias: some callers expect `show_box_image_coords`
    def show_box_image_coords(self, xyxy):
        """Deprecated alias for show_bbox_image_coords kept for compatibility."""
        return self.show_bbox_image_coords(xyxy)

    def _current_roi_image_coords(self):
        """Return (x0,y0,x1,y1) in IMAGE coords covering the ellipse's bounding box,"""
        if self._bbox is None:
            return None
        if self._draw_rect is None or self._img_w is None or self._img_h is None:
            return None
        if self._base_pixmap is None:
            return None

        left, top, w, h = self._bbox
        right = left + w
        bottom = top + h

        dl = float(self._draw_rect.left())
        dt = float(self._draw_rect.top())
        dr = float(self._draw_rect.left() + self._draw_rect.width())
        db = float(self._draw_rect.top() + self._draw_rect.height())

        inter_left = max(left, dl)
        inter_top = max(top, dt)
        inter_right = min(right, dr)
        inter_bottom = min(bottom, db)
        if inter_right <= inter_left or inter_bottom <= inter_top:
            return None

        pw = float(self._draw_rect.width())
        ph = float(self._draw_rect.height())
        nx0 = (inter_left - dl) / max(pw, 1.0)
        ny0 = (inter_top  - dt) / max(ph, 1.0)
        nx1 = (inter_right - dl) / max(pw, 1.0)
        ny1 = (inter_bottom - dt) / max(ph, 1.0)

        X0 = int(round(nx0 * self._img_w));  X1 = int(round(nx1 * self._img_w))
        Y0 = int(round(ny0 * self._img_h));  Y1 = int(round(ny1 * self._img_h))

        X0 = max(0, min(X0, self._img_w)); X1 = max(0, min(X1, self._img_w))
        Y0 = max(0, min(Y0, self._img_h)); Y1 = max(0, min(Y1, self._img_h))
        if X1 <= X0 or Y1 <= Y0:
            return None
        return (X0, Y0, X1, Y1)

    def get_ellipse_mask(self):
        """Return (X0,Y0,X1,Y1, mask) where mask is a boolean numpy array
        for pixels inside the ellipse in image coordinates. Returns None if
        ROI is not available or mapping info missing.
        """
        img_coords = self._current_roi_image_coords()
        if img_coords is None:
            return None
        X0, Y0, X1, Y1 = img_coords
        H = Y1 - Y0
        W = X1 - X0
        if H <= 0 or W <= 0:
            return None

        cx = (X0 + X1) / 2.0
        cy = (Y0 + Y1) / 2.0
        rx = max(0.5, (X1 - X0) / 2.0)
        ry = max(0.5, (Y1 - Y0) / 2.0)

        ys = np.arange(Y0, Y1, dtype=float)
        xs = np.arange(X0, X1, dtype=float)
        yy, xx = np.meshgrid(ys, xs, indexing='xy')
        nx = (xx - cx) / rx
        ny = (yy - cy) / ry
        mask = (nx * nx + ny * ny) <= 1.0
        mask = mask.T
        return (X0, Y0, X1, Y1, mask)
