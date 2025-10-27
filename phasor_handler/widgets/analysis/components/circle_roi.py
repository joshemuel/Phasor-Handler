# TODO: Make it so that ROIs can be removed seamlessly
# TODO Any left click redefines a new ROI, never edit. Edit is only right click and drag

from PyQt6.QtCore import QObject, pyqtSignal, Qt, QRect, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PyQt6.QtWidgets import QLabel
from typing import Optional
import numpy as np
import math


class CircleRoiTool(QObject):
    """Ellipse ROI tool attached to a QLabel showing a scaled pixmap.

    Internal bbox is stored as a float tuple (left, top, width, height).
    Translation uses QPointF anchor and bbox_origin floats so moving does
    not introduce rounding drift that changes size.
    """
    roiChanged = pyqtSignal(tuple)   # (x0, y0, x1, y1) in image coords (during drag)
    roiFinalized = pyqtSignal(tuple) # (x0, y0, x1, y1) in image coords (on release)
    roiSelected = pyqtSignal(int)    # index of ROI selected by right-click
    roiDrawingStarted = pyqtSignal() # emitted when user starts drawing a new ROI

    def __init__(self, label: QLabel, parent=None):
        super().__init__(parent)
        self._label = label
        self._label.setMouseTracking(True)
        self._label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
        self._rotation_angle = 0.0  # rotation angle in radians

        # persistent saved ROIs: list of dicts with keys 'name','xyxy','color'
        # color may be a QColor or (r,g,b,a) tuple
        self._saved_rois = []

        # stimulus ROIs: list of dicts with keys 'id','xyxy','name'
        self._stim_rois = []
        # visibility flags: allow hiding various overlay elements without
        # modifying the underlying data structures
        self._show_saved_rois = True
        self._show_stim_rois = True
        self._show_current_bbox = True
        self._show_labels = True

        # interaction modes
        self._mode = None  # 'draw', 'translate', 'rotate', or None
        self._interaction_mode = 'translate'  # 'translate' or 'rotate' - toggleable with 'y' key
        self._translate_anchor = None  # QPointF
        self._bbox_origin = None       # (left, top, w, h) float tuple
        self._rotation_anchor = None   # QPointF for rotation center
        self._rotation_origin = None   # original angle before rotation starts
        # whether to show the small mode text in the overlay (can be toggled by view)
        self._show_mode_text = True

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
        self._rotation_angle = 0.0
        self._dragging = False
        if self._base_pixmap is not None:
            self._label.setPixmap(self._base_pixmap)

    def clear_selection(self):
        """Clear only the current (interactive) bbox/selection but keep
        saved and stimulus ROIs intact and visible according to visibility
        flags."""
        self._start_pos = None
        self._current_pos = None
        self._bbox = None
        self._dragging = False
        # Keep the current interaction mode active
        # Don't reset rotation angle - preserve it for the next ROI
        # self._rotation_angle = 0.0
        # repaint overlay to show saved/stim ROIs
        if self._base_pixmap is not None:
            self._paint_overlay()

    def toggle_interaction_mode(self):
        """Toggle between translation and rotation modes."""
        if self._interaction_mode == 'translate':
            self._interaction_mode = 'rotate'
            print("Switched to rotation mode - right-click and drag to rotate")
        else:
            self._interaction_mode = 'translate'
            print("Switched to translation mode - right-click and drag to move")
        
        # Repaint overlay to show any mode-specific visual cues
        if self._base_pixmap is not None:
            self._paint_overlay()

    def _get_bbox_center(self):
        """Get the center point of the current bbox."""
        if self._bbox is None:
            return None
        left, top, w, h = self._bbox
        cx = left + w / 2.0
        cy = top + h / 2.0
        return QPointF(cx, cy)

    def _calculate_rotation_angle(self, anchor_point, current_point, center_point):
        """Calculate rotation angle from anchor to current point around center."""
        # Vector from center to anchor
        anchor_dx = anchor_point.x() - center_point.x()
        anchor_dy = anchor_point.y() - center_point.y()
        
        # Vector from center to current
        current_dx = current_point.x() - center_point.x()
        current_dy = current_point.y() - center_point.y()
        
        # Calculate angles
        anchor_angle = math.atan2(anchor_dy, anchor_dx)
        current_angle = math.atan2(current_dy, current_dx)
        
        # Return the difference
        return current_angle - anchor_angle

    def _find_roi_at_point(self, point):
        """Find which saved ROI (if any) contains the given point.
        Returns the index of the ROI, or None if no ROI contains the point.
        """
        if not self._saved_rois:
            return None
        
        # Check saved ROIs in reverse order (last drawn on top)
        for idx in reversed(range(len(self._saved_rois))):
            roi = self._saved_rois[idx]
            xyxy = roi.get('xyxy')
            if xyxy is None:
                continue
                
            # Convert ROI to label coordinates
            lbbox = self._label_bbox_from_image_xyxy(xyxy)
            if lbbox is None:
                continue
                
            lx0, ly0, lw, lh = lbbox
            rotation_angle = roi.get('rotation', 0.0)
            
            # Check if point is inside the ellipse
            if self._point_in_ellipse(point, lx0, ly0, lw, lh, rotation_angle):
                return idx
                
        return None
    
    def _point_in_ellipse(self, point, lx0, ly0, lw, lh, rotation_angle=0.0):
        """Check if a point is inside an ellipse with given parameters."""
        cx = lx0 + lw / 2.0
        cy = ly0 + lh / 2.0
        rx = lw / 2.0
        ry = lh / 2.0
        
        # Translate point to ellipse center
        px = point.x() - cx
        py = point.y() - cy
        
        # If there's rotation, rotate the point back
        if rotation_angle != 0.0:
            cos_angle = math.cos(-rotation_angle)
            sin_angle = math.sin(-rotation_angle)
            px_rot = px * cos_angle - py * sin_angle
            py_rot = px * sin_angle + py * cos_angle
            px, py = px_rot, py_rot
        
        # Check if point is inside the ellipse
        return (px * px) / (rx * rx) + (py * py) / (ry * ry) <= 1.0

    def set_show_saved_rois(self, show: bool):
        """Toggle visibility of saved ROIs without modifying their data."""
        try:
            self._show_saved_rois = bool(show)
        except Exception:
            self._show_saved_rois = True
        self._paint_overlay()

    def set_show_stim_rois(self, show: bool):
        """Toggle visibility of stimulus ROIs without modifying their data."""
        try:
            self._show_stim_rois = bool(show)
        except Exception:
            self._show_stim_rois = True
        self._paint_overlay()

    def set_show_current_bbox(self, show: bool):
        """Toggle visibility of the current interactive bbox."""
        try:
            self._show_current_bbox = bool(show)
        except Exception:
            self._show_current_bbox = True
        self._paint_overlay()

    def set_show_labels(self, show: bool):
        """Toggle visibility of text labels within ROIs."""
        try:
            self._show_labels = bool(show)
        except Exception:
            self._show_labels = True
        self._paint_overlay()

    # --- Event filter for mouse handling and painting overlay ---

    def eventFilter(self, obj, event):
        if obj is not self._label:
            return False

        et = event.type()

        # Handle keyboard events for mode switching
        if et == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Y:
                # Only allow mode toggle when there's an active ROI
                if self._bbox is not None:
                    self.toggle_interaction_mode()
                    return True
                else:
                    print("Draw an ROI first before switching interaction modes")
                    return True

        if et == event.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton and self._in_draw_rect(event.position()):
                # Emit signal that ROI drawing has started
                self.roiDrawingStarted.emit()
                
                # Clear any existing bbox to ensure we're starting fresh
                self._bbox = None
                self._start_pos = event.position()  # QPointF
                self._current_pos = self._start_pos
                
                # Initialize new ROI with default settings
                self._mode = 'draw'
                self._dragging = True
                self._rotation_angle = 0.0
                self._interaction_mode = 'translate'
                
                # Clear any ROI selection in the list widget to prevent unintentional editing
                if hasattr(self.parent(), 'roi_list_component'):
                    self.parent().roi_list_component.clear_editing_state()
                    roi_list_widget = self.parent().roi_list_component.get_list_widget()
                    if roi_list_widget:
                        roi_list_widget.setCurrentRow(-1)  # Properly deselect by setting to invalid row
                        roi_list_widget.clearSelection()
                    print("Cleared ROI list selection - starting new ROI")
                
                self._update_bbox_from_points()
                self._paint_overlay()
                print(f"Started drawing NEW ROI (left-click always creates new)")
                return True

            # RIGHT CLICK: Used for editing existing ROIs (select, translate, rotate)
            if event.button() == Qt.MouseButton.RightButton:
                p = event.position()  # QPointF
                
                # First, check if we're clicking on any saved ROI
                roi_index = self._find_roi_at_point(p)
                if roi_index is not None:
                    # Emit signal to select this ROI in the list widget
                    self.roiSelected.emit(roi_index)
                    
                    # Also set up the clicked ROI as the current bbox for immediate manipulation
                    roi = self._saved_rois[roi_index]
                    xyxy = roi.get('xyxy')
                    rotation_angle = roi.get('rotation', 0.0)
                    if xyxy is not None:
                        # Convert to label coordinates and set as current bbox
                        lbbox = self._label_bbox_from_image_xyxy(xyxy)
                        if lbbox is not None:
                            lx0, ly0, lw, lh = lbbox
                            self._bbox = (lx0, ly0, lw, lh)
                            self._rotation_angle = rotation_angle
                            
                            # Now check if we can start manipulation on this bbox
                            left, top, w, h = self._bbox
                            right = left + w
                            bottom = top + h
                            # 1-pixel margin tolerance
                            if (left - 1 <= p.x() <= right + 1) and (top - 1 <= p.y() <= bottom + 1):
                                if self._interaction_mode == 'translate':
                                    self._mode = 'translate'
                                    self._dragging = True
                                    self._translate_anchor = p
                                    self._bbox_origin = (left, top, w, h)
                                else:  # rotation mode
                                    self._mode = 'rotate'
                                    self._dragging = True
                                    self._rotation_anchor = p
                                    self._rotation_origin = self._rotation_angle
                                return True
                    return True
                
                # If no saved ROI was clicked, check if we're manipulating current bbox
                if self._bbox is not None:
                    left, top, w, h = self._bbox
                    right = left + w
                    bottom = top + h
                    # 1-pixel margin tolerance
                    if (left - 1 <= p.x() <= right + 1) and (top - 1 <= p.y() <= bottom + 1):
                        if self._interaction_mode == 'translate':
                            self._mode = 'translate'
                            self._dragging = True
                            self._translate_anchor = p
                            self._bbox_origin = (left, top, w, h)
                        else:  # rotation mode
                            self._mode = 'rotate'
                            self._dragging = True
                            self._rotation_anchor = p
                            self._rotation_origin = self._rotation_angle
                        return True
                
                # If we reach here, user right-clicked on empty space
                # Clear any editing state and selection
                if hasattr(self.parent(), 'roi_list_component'):
                    self.parent().roi_list_component.clear_editing_state()
                    # Also clear selection in the ROI list widget
                    roi_list_widget = self.parent().roi_list_component.get_list_widget()
                    if roi_list_widget:
                        roi_list_widget.clearSelection()
                        roi_list_widget.setCurrentItem(None)
                print("Cleared ROI editing state - clicked on empty space")
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

            elif self._mode == 'rotate' and self._rotation_anchor is not None:
                # calculate rotation angle based on mouse movement around bbox center
                center = self._get_bbox_center()
                if center is not None:
                    angle_delta = self._calculate_rotation_angle(self._rotation_anchor, pos, center)
                    self._rotation_angle = self._rotation_origin + angle_delta
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

            if self._mode == 'rotate' and event.button() == Qt.MouseButton.RightButton:
                self._dragging = False
                # finalize rotation
                self._rotation_anchor = None
                self._rotation_origin = None
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

        # Calculate offsets when the pixmap is centered inside a larger label
        offset_x = float(self._draw_rect.left()) if self._draw_rect is not None else 0.0
        offset_y = float(self._draw_rect.top()) if self._draw_rect is not None else 0.0

        # Draw current interactive bbox if present and allowed
        if self._bbox is not None and getattr(self, '_show_current_bbox', True):
            try:
                left, top, w, h = self._bbox
                draw_left = float(left) - offset_x
                draw_top = float(top) - offset_y
                if self._rotation_angle != 0.0:
                    # Draw rotated ellipse
                    center_x = draw_left + w / 2.0
                    center_y = draw_top + h / 2.0
                    painter.save()
                    painter.translate(center_x, center_y)
                    painter.rotate(math.degrees(self._rotation_angle))
                    painter.drawEllipse(int(round(-w/2)), int(round(-h/2)), int(round(w)), int(round(h)))
                    painter.restore()
                else:
                    # Draw normal ellipse
                    painter.drawEllipse(int(round(draw_left)), int(round(draw_top)), int(round(w)), int(round(h)))
            except Exception:
                pass

        # Draw any saved ROIs on top of the overlay (if visible)
        if getattr(self, '_show_saved_rois', True):
            try:
                font = QFont()
                font.setPointSize(6)
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
                        px0 = float(lx0) - offset_x
                        py0 = float(ly0) - offset_y
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
                        
                        # Check if this saved ROI has rotation
                        rotation_angle = saved.get('rotation', 0.0)
                        if rotation_angle != 0.0:
                            # Draw rotated ellipse
                            center_x = px0 + lw / 2.0
                            center_y = py0 + lh / 2.0
                            painter.save()
                            painter.translate(center_x, center_y)
                            painter.rotate(math.degrees(rotation_angle))
                            painter.drawEllipse(int(round(-lw/2)), int(round(-lh/2)), int(round(lw)), int(round(lh)))
                            painter.restore()
                        else:
                            # Draw normal ellipse
                            painter.drawEllipse(int(round(px0)), int(round(py0)), int(round(lw)), int(round(lh)))
                        # draw label in middle (center text using font metrics) only if labels are enabled
                        if getattr(self, '_show_labels', True):
                            tx = float(px0 + lw / 2.0)
                            ty = float(py0 + lh / 2.0)
                            # Show full name if it starts with "S" (stimulated ROIs), otherwise extract number from ROI name
                            roi_name = saved.get('name', '')
                            if roi_name and roi_name.startswith('S'):
                                text = roi_name
                            elif roi_name and roi_name.startswith('ROI '):
                                # Extract the number from "ROI X" format
                                try:
                                    number = roi_name.split('ROI ')[1]
                                    text = number
                                except (IndexError, ValueError):
                                    # Fallback to index + 1 if name parsing fails
                                    text = str(idx + 1)
                            else:
                                # Fallback for non-standard names
                                text = str(idx + 1)
                            # choose text color that contrasts (white text)
                            text_col = QColor(255, 255, 255)
                            fm = painter.fontMetrics()
                            tw = fm.horizontalAdvance(text)
                            ascent = fm.ascent()
                            descent = fm.descent()
                            text_x = int(round(tx - tw / 2.0))
                            # baseline must be offset so text vertically centers on the ellipse
                            text_y = int(round(ty + (ascent - descent) / 2.0))
                            
                            # Draw black background rectangle for better contrast
                            bg_padding = 2
                            bg_rect_x = text_x - bg_padding
                            bg_rect_y = text_y - ascent - bg_padding
                            bg_rect_w = tw + 2 * bg_padding
                            bg_rect_h = ascent + descent + 2 * bg_padding
                            painter.fillRect(bg_rect_x, bg_rect_y, bg_rect_w, bg_rect_h, QColor(0, 0, 0, 180))
                            
                            painter.setPen(QPen(text_col))
                            painter.drawText(text_x, text_y, text)
                    except Exception:
                        continue
            except Exception:
                pass

        # Draw stimulus ROIs with distinctive styling (if visible)
        if getattr(self, '_show_stim_rois', True):
            try:
                font = QFont()
                font.setPointSize(6)
                font.setBold(True)
                painter.setFont(font)
                for stim_roi in list(self._stim_rois or []):
                    try:
                        xyxy = stim_roi.get('xyxy')
                        if xyxy is None:
                            continue
                        lbbox = self._label_bbox_from_image_xyxy(xyxy)
                        if lbbox is None:
                            continue
                        lx0, ly0, lw, lh = lbbox
                        px0 = float(lx0) - offset_x
                        py0 = float(ly0) - offset_y

                        # Use cyan color with dashed line style for stimulus ROIs
                        stim_pen = QPen(QColor(0, 200, 255, 220))  # Cyan color
                        stim_pen.setWidth(3)
                        stim_pen.setStyle(Qt.PenStyle.DashLine)  # Dashed line
                        painter.setPen(stim_pen)
                        painter.drawEllipse(int(round(px0)), int(round(py0)), int(round(lw)), int(round(lh)))

                        # Draw stimulus label (e.g., "S1", "S2") centered using font metrics only if labels are enabled
                        if getattr(self, '_show_labels', True):
                            tx = float(px0 + lw / 2.0)
                            ty = float(py0 + lh / 2.0)
                            text_col = QColor(255, 255, 255)  # White text
                            stim_name = stim_roi.get('name', f"S{stim_roi.get('id', '?')}")
                            fm = painter.fontMetrics()
                            tw = fm.horizontalAdvance(stim_name)
                            ascent = fm.ascent()
                            descent = fm.descent()
                            text_x = int(round(tx - tw / 2.0))
                            text_y = int(round(ty + (ascent - descent) / 2.0))
                            
                            # Draw black background rectangle for better contrast
                            bg_padding = 2
                            bg_rect_x = text_x - bg_padding
                            bg_rect_y = text_y - ascent - bg_padding
                            bg_rect_w = tw + 2 * bg_padding
                            bg_rect_h = ascent + descent + 2 * bg_padding
                            painter.fillRect(bg_rect_x, bg_rect_y, bg_rect_w, bg_rect_h, QColor(0, 0, 0, 180))
                            
                            painter.setPen(QPen(text_col))
                            painter.drawText(text_x, text_y, stim_name)
                    except Exception:
                        continue
            except Exception:
                pass

        # Draw mode indicator in the top-left corner
        if self._bbox is not None and getattr(self, '_show_mode_text', True):
            mode_text = f"Mode: {self._interaction_mode.title()} (Y to toggle)"
            painter.setPen(QPen(QColor(255, 255, 255, 200)))
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(10, 25, mode_text)

        painter.end()
        self._label.setPixmap(overlay)

    def show_bbox_image_coords(self, xyxy, rotation_angle=0.0):
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
        self._rotation_angle = rotation_angle
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

    def set_show_mode_text(self, show: bool):
        """Externally control whether the small mode text is shown in the overlay."""
        try:
            self._show_mode_text = bool(show)
        except Exception:
            self._show_mode_text = True
        # repaint overlay to apply the change
        if self._base_pixmap is not None:
            self._paint_overlay()

    def set_stim_rois(self, stim_rois):
        """Provide a list of stimulus ROI dicts (id, xyxy, name) to be drawn persistently."""
        try:
            if stim_rois is None:
                self._stim_rois = []
            else:
                # store a shallow copy
                self._stim_rois = list(stim_rois)
        except Exception:
            self._stim_rois = []

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
        
        # If there's rotation, we need to rotate the coordinate system
        if self._rotation_angle != 0.0:
            # Translate to center
            xx_centered = xx - cx
            yy_centered = yy - cy
            
            # Apply inverse rotation (rotate coordinates back to align with ellipse axes)
            cos_angle = math.cos(-self._rotation_angle)
            sin_angle = math.sin(-self._rotation_angle)
            
            xx_rotated = xx_centered * cos_angle - yy_centered * sin_angle
            yy_rotated = xx_centered * sin_angle + yy_centered * cos_angle
            
            # Normalize with respect to ellipse axes
            nx = xx_rotated / rx
            ny = yy_rotated / ry
        else:
            # No rotation, use original method
            nx = (xx - cx) / rx
            ny = (yy - cy) / ry
            
        mask = (nx * nx + ny * ny) <= 1.0
        mask = mask.T
        return (X0, Y0, X1, Y1, mask)
