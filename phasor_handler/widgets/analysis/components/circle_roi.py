from PyQt6.QtCore import QObject, pyqtSignal, Qt, QRect, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QPainterPath, QPolygonF
from PyQt6.QtWidgets import QLabel
from typing import Optional
import numpy as np
import math


class CircleRoiTool(QObject):
    """Ellipse/Freehand/Rectangular ROI tool attached to a QLabel showing a scaled pixmap.

    Internal bbox is stored as a float tuple (left, top, width, height).
    Translation uses QPointF anchor and bbox_origin floats so moving does
    not introduce rounding drift that changes size.
    
    Supports three drawing modes:
    - 'circular': Draw elliptical ROIs (default)
    - 'rectangular': Draw rectangular ROIs (bounding box)
    - 'freehand': Draw freeform polygonal ROIs by tracking mouse path
    """
    roiChanged = pyqtSignal(tuple)   # (x0, y0, x1, y1) in image coords (during drag)
    roiFinalized = pyqtSignal(tuple) # (x0, y0, x1, y1) in image coords (on release)
    roiSelected = pyqtSignal(int)    # index of ROI selected by right-click
    roiSelectionToggled = pyqtSignal(int) # index of ROI to toggle selection for (Shift+Click)
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
        
        # Margin in pixels to allow ROIs to extend beyond the visible frame
        # NOT IMPLEMENTED YET
        self._boundary_margin = 0.0  # pixels

        # ROI/drawing state
        self._start_pos = None   # QPointF (press)
        self._current_pos = None # QPointF (current mouse)
        # bbox stored as float tuple: (left, top, width, height)
        self._bbox = None
        self._dragging = False
        self._rotation_angle = 0.0  # rotation angle in radians
        
        # Drawing mode: 'circular' (default) or 'freehand'
        self._drawing_mode = 'circular'
        
        # Freehand path tracking
        self._freehand_points = []  # List of QPointF for freehand path

        # persistent saved ROIs: list of dicts with keys 'name','xyxy','color'
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
        self._rotation_center_origin = None  # QPointF - fixed center point for rotation
        self._freehand_points_origin = None  # List of original freehand points for transformations
        # whether to show the small mode text in the overlay (can be toggled by view)
        self._show_mode_text = True
        
        # Multi-selection support for moving multiple ROIs simultaneously
        self._selected_roi_indices = []  # List of indices of selected ROIs
        self._multi_roi_origins = None  # Dict storing original positions during multi-ROI drag
        self._multi_roi_drag_offset = None # QPointF storing current drag offset

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

    def set_drawing_mode(self, mode: str):
        """Set the drawing mode: 'circular', 'rectangular', or 'freehand'."""
        if mode in ('circular', 'rectangular', 'freehand'):
            self._drawing_mode = mode
            print(f"Drawing mode set to: {mode}")
        else:
            print(f"Warning: Invalid drawing mode '{mode}', keeping '{self._drawing_mode}'")

    def get_drawing_mode(self) -> str:
        """Get the current drawing mode."""
        return self._drawing_mode

    def clear(self):
        """Clear the ROI overlay and internal state."""
        self._start_pos = None
        self._current_pos = None
        self._bbox = None
        self._rotation_angle = 0.0
        self._dragging = False
        self._freehand_points = []
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
        self._freehand_points = []
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

    def finalize_multi_roi_movement(self):
        """Finalize the multi-ROI movement by applying the offset to saved ROIs."""
        if self._multi_roi_origins is not None and self._multi_roi_drag_offset is not None:
            dx = self._multi_roi_drag_offset.x()
            dy = self._multi_roi_drag_offset.y()
            
            # Apply changes to all selected ROIs
            for idx, origin in self._multi_roi_origins.items():
                if 0 <= idx < len(self._saved_rois):
                    roi = self._saved_rois[idx]
                    ox, oy, ow, oh = origin['bbox']
                    new_left = ox + dx
                    new_top = oy + dy
                    
                    # Convert back to image coordinates
                    if self._draw_rect and self._img_w and self._img_h:
                        scale_x = self._img_w / float(self._draw_rect.width())
                        scale_y = self._img_h / float(self._draw_rect.height())
                        
                        img_x0 = (new_left - self._draw_rect.left()) * scale_x
                        img_y0 = (new_top - self._draw_rect.top()) * scale_y
                        img_x1 = img_x0 + (ow * scale_x)
                        img_y1 = img_y0 + (oh * scale_y)
                        
                        # Update the ROI's xyxy coordinates (convert to int for array slicing)
                        roi['xyxy'] = (int(round(img_x0)), int(round(img_y0)), 
                                       int(round(img_x1)), int(round(img_y1)))
                        
                        # If this ROI has freehand points, translate them too
                        if origin.get('freehand_points'):
                            original_points = origin['freehand_points']
                            translated_points = []
                            for pt in original_points:
                                # Points are stored in image coordinates
                                # Convert to label coordinates, translate, convert back
                                label_x = self._draw_rect.left() + (pt[0] / scale_x)
                                label_y = self._draw_rect.top() + (pt[1] / scale_y)
                                new_label_x = label_x + dx
                                new_label_y = label_y + dy
                                new_img_x = (new_label_x - self._draw_rect.left()) * scale_x
                                new_img_y = (new_label_y - self._draw_rect.top()) * scale_y
                                translated_points.append((new_img_x, new_img_y))
                            roi['points'] = translated_points

            # Clear the origin state
            self._multi_roi_origins = None
            self._multi_roi_drag_offset = None
            self._paint_overlay()
            print(f"DEBUG: Multi-ROI movement finalized for {len(self._selected_roi_indices)} ROIs")
            return True
        return False

    def revert_multi_roi_movement(self):
        """Revert the multi-ROI movement back to original positions."""
        if self._multi_roi_origins is not None and len(self._multi_roi_origins) > 0:
            # Restore original positions for all moved ROIs
            for idx, origin in self._multi_roi_origins.items():
                if 0 <= idx < len(self._saved_rois):
                    roi = self._saved_rois[idx]
                    ox, oy, ow, oh = origin['bbox']
                    
                    # Convert original bbox back to image coordinates
                    if self._draw_rect and self._img_w and self._img_h:
                        scale_x = self._img_w / float(self._draw_rect.width())
                        scale_y = self._img_h / float(self._draw_rect.height())
                        
                        img_x0 = (ox - self._draw_rect.left()) * scale_x
                        img_y0 = (oy - self._draw_rect.top()) * scale_y
                        img_x1 = img_x0 + (ow * scale_x)
                        img_y1 = img_y0 + (oh * scale_y)
                        
                        # Restore original xyxy (convert to int for array slicing)
                        roi['xyxy'] = (int(round(img_x0)), int(round(img_y0)), 
                                       int(round(img_x1)), int(round(img_y1)))
                        
                        # Restore original freehand points if they existed
                        if origin.get('freehand_points'):
                            roi['points'] = origin['freehand_points']
            
            # Clear the origin state
            self._multi_roi_origins = None
            self._multi_roi_drag_offset = None
            self._paint_overlay()
            print(f"DEBUG: Multi-ROI movement reverted for {len(self._selected_roi_indices)} ROIs")
            return True
        return False

    def is_multi_roi_preview_active(self):
        """Check if there's a pending multi-ROI movement preview."""
        return self._multi_roi_origins is not None and len(self._multi_roi_origins) > 0

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
            elif event.key() == Qt.Key.Key_R:
                # Finalize multi-ROI movement if active
                if self._multi_roi_drag_offset is not None and self._multi_roi_origins:
                    self.finalize_multi_roi_movement()
                    # End the drag operation
                    self._dragging = False
                    self._mode = None
                    self._translate_anchor = None
                    return True

        if et == event.Type.MouseButtonPress:
            # Check for pending multi-ROI preview and cancel it if clicking elsewhere to start new drawing
            if self._multi_roi_origins is not None:
                 print("DEBUG: Cancelling multi-ROI preview due to new Left Click")
                 self.revert_multi_roi_movement()
            
            if event.button() == Qt.MouseButton.LeftButton and self._in_draw_rect(event.position()):
                # Emit signal that ROI drawing has started
                self.roiDrawingStarted.emit()
                
                # Clear any existing bbox to ensure we're starting fresh
                self._bbox = None
                self._freehand_points = []
                self._start_pos = event.position()  # QPointF
                self._current_pos = self._start_pos
                
                # Initialize new ROI with default settings
                self._mode = 'draw'
                self._dragging = True
                self._rotation_angle = 0.0
                self._interaction_mode = 'translate'
                
                # For freehand mode, start collecting points
                if self._drawing_mode == 'freehand':
                    self._freehand_points = [QPointF(self._start_pos)]
                    print(f"Started freehand drawing at ({self._start_pos.x():.1f}, {self._start_pos.y():.1f})")
                else:
                    # Circular mode - update bbox as before
                    self._update_bbox_from_points()
                
                # Clear any ROI selection in the list widget to prevent unintentional editing
                if hasattr(self.parent(), 'roi_list_component'):
                    self.parent().roi_list_component.clear_editing_state()
                    roi_list_widget = self.parent().roi_list_component.get_list_widget()
                    if roi_list_widget:
                        roi_list_widget.setCurrentRow(-1)  # Properly deselect by setting to invalid row
                        roi_list_widget.clearSelection()
                    print("Cleared ROI list selection - starting new ROI")
                
                self._paint_overlay()
                print(f"Started drawing NEW ROI in {self._drawing_mode} mode (left-click always creates new)")
                return True

            # RIGHT CLICK: Used for editing existing ROIs (select, translate, rotate)
            if event.button() == Qt.MouseButton.RightButton and self._mode != 'draw':
                p = event.position()  # QPointF
                
                # Check if we clicked on an ROI
                clicked_roi_index = self._find_roi_at_point(p)
                
                # Check for pending multi-ROI preview
                if self._multi_roi_origins is not None:
                    # If we click right button again, we might want to cancel the previous preview
                    # UNLESS we are clicking on the ghost? But ghosts aren't clickable objects yet.
                    # User said "reset translate from original", so cancel is appropriate.
                    print("DEBUG: Cancelling multi-ROI preview due to new Right Click")
                    self.revert_multi_roi_movement()
                
                # Check for Shift+Click (Multi-selection toggle or add)
                # User Requirement: "The Shift button needs to be HOLD DOWN... It's not just a toggle"
                # This implies explicit check for modifier. 
                if clicked_roi_index is not None and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    print(f"DEBUG: Shift+RightClick on ROI {clicked_roi_index} - toggling selection")
                    self.roiSelectionToggled.emit(clicked_roi_index)
                    return True
                
                # Check if multiple ROIs are selected AND we clicked on one of them
                if len(self._selected_roi_indices) > 1 and clicked_roi_index is not None and clicked_roi_index in self._selected_roi_indices:
                    # Multi-selection mode - move all selected ROIs together
                    print(f"DEBUG: Multi-ROI drag started - moving {len(self._selected_roi_indices)} ROIs")
                    self._mode = 'translate'
                    self._dragging = True
                    self._translate_anchor = p
                    self._multi_roi_drag_offset = QPointF(0, 0)
                    
                    # Store original positions of all selected ROIs
                    self._multi_roi_origins = {}
                    for idx in self._selected_roi_indices:
                        if 0 <= idx < len(self._saved_rois):
                            roi = self._saved_rois[idx]
                            xyxy = roi.get('xyxy')
                            if xyxy:
                                lbbox = self._label_bbox_from_image_xyxy(xyxy)
                                if lbbox:
                                    self._multi_roi_origins[idx] = {
                                        'bbox': lbbox,
                                        'rotation': roi.get('rotation', 0.0),
                                        'freehand_points': roi.get('points', None)
                                    }
                    return True
                
                # If multiple ROIs are selected but we clicked on a DIFFERENT ROI
                # (not in selection) without Shift, exit multi-select and select only that ROI
                if len(self._selected_roi_indices) > 1 and clicked_roi_index is not None and clicked_roi_index not in self._selected_roi_indices:
                    print(f"DEBUG: RightClick on ROI {clicked_roi_index} (not in selection) - exiting multi-select")
                    # Clear multi-selection and select only the clicked ROI
                    self._selected_roi_indices = [clicked_roi_index]
                    self.roiSelected.emit(clicked_roi_index)
                    return True
                
                # Single selection mode - original behavior
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
                                    # Save original freehand points for transformation
                                    if self._freehand_points:
                                        self._freehand_points_origin = [QPointF(pt.x(), pt.y()) for pt in self._freehand_points]
                                else:  # rotation mode
                                    self._mode = 'rotate'
                                    self._dragging = True
                                    self._rotation_anchor = p
                                    self._rotation_origin = self._rotation_angle
                                    # Save the original center point for consistent rotation
                                    self._rotation_center_origin = self._get_bbox_center()
                                    # Save original freehand points for transformation
                                    if self._freehand_points:
                                        self._freehand_points_origin = [QPointF(pt.x(), pt.y()) for pt in self._freehand_points]
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
                            # Save original freehand points for transformation
                            if self._freehand_points:
                                self._freehand_points_origin = [QPointF(pt.x(), pt.y()) for pt in self._freehand_points]
                        else:  # rotation mode
                            self._mode = 'rotate'
                            self._dragging = True
                            self._rotation_anchor = p
                            self._rotation_origin = self._rotation_angle
                            # Save the original center point for consistent rotation
                            self._rotation_center_origin = self._get_bbox_center()
                            # Save original freehand points for transformation
                            if self._freehand_points:
                                self._freehand_points_origin = [QPointF(pt.x(), pt.y()) for pt in self._freehand_points]
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
                
                # Handle freehand drawing
                if self._drawing_mode == 'freehand':
                    # Add point to the path if it's far enough from the last point
                    if len(self._freehand_points) == 0 or \
                       (pos - self._freehand_points[-1]).manhattanLength() > 2.0:
                        self._freehand_points.append(QPointF(pos))
                    # Update bbox to encompass all freehand points
                    self._update_bbox_from_freehand_points()
                else:
                    # Circular and rectangular modes - update bbox from start/current points
                    self._update_bbox_from_points()
                
                self._paint_overlay()
                # Emit live ROI (image coords)
                xyxy = self._current_roi_image_coords()
                if xyxy is not None:
                    self.roiChanged.emit(xyxy)
                return True

            elif self._mode == 'translate' and self._translate_anchor is not None:
                # Check if we're in multi-ROI mode
                if self._multi_roi_origins is not None and len(self._multi_roi_origins) > 0:
                    # Multi-ROI translation mode - PREVIEW ONLY
                    anchor = self._translate_anchor
                    dx = pos.x() - anchor.x()
                    dy = pos.y() - anchor.y()
                    
                    # Update offset
                    self._multi_roi_drag_offset = QPointF(dx, dy)
                    
                    # Repaint to show preview
                    self._paint_overlay()
                    return True
                
                # Single ROI translation (original behavior)
                if self._bbox_origin is not None:
                    # compute delta and move bbox using float math to avoid size drift
                    anchor = self._translate_anchor
                    dx = pos.x() - anchor.x()
                    dy = pos.y() - anchor.y()
                    ox, oy, ow, oh = self._bbox_origin
                    new_left = ox + dx
                    new_top = oy + dy
                    
                    self._bbox = (new_left, new_top, ow, oh)
                    
                    # Also translate freehand points if they exist
                    if self._freehand_points_origin:
                        self._freehand_points = []
                        for pt in self._freehand_points_origin:
                            new_pt = QPointF(pt.x() + dx, pt.y() + dy)
                            self._freehand_points.append(new_pt)
                        
                        # Recalculate bbox from translated points to ensure center alignment
                        self._update_bbox_from_freehand_points()
                    
                    self._paint_overlay()
                    xyxy = self._current_roi_image_coords()
                    if xyxy is not None:
                        self.roiChanged.emit(xyxy)
                return True

            elif self._mode == 'rotate' and self._rotation_anchor is not None:
                # Use the fixed original center for rotation, not the dynamically changing bbox center
                center = self._rotation_center_origin if self._rotation_center_origin is not None else self._get_bbox_center()
                if center is not None:
                    angle_delta = self._calculate_rotation_angle(self._rotation_anchor, pos, center)
                    proposed_angle = self._rotation_origin + angle_delta
                    
                    self._rotation_angle = proposed_angle
                    
                    # Also rotate freehand points if they exist
                    if self._freehand_points_origin:
                        self._freehand_points = []
                        cx = center.x()
                        cy = center.y()
                        
                        for pt in self._freehand_points_origin:
                            # Translate to origin (using ORIGINAL center)
                            px = pt.x() - cx
                            py = pt.y() - cy
                            
                            # Rotate
                            cos_angle = math.cos(angle_delta)
                            sin_angle = math.sin(angle_delta)
                            px_rot = px * cos_angle - py * sin_angle
                            py_rot = px * sin_angle + py * cos_angle
                            
                            # Translate back
                            new_pt = QPointF(px_rot + cx, py_rot + cy)
                            self._freehand_points.append(new_pt)
                        
                        # Recalculate bbox from rotated points to properly encompass the rotated polygon
                        self._update_bbox_from_freehand_points()
                    
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
                
                # For freehand mode, close the path by connecting to start
                if self._drawing_mode == 'freehand':
                    if len(self._freehand_points) > 2:
                        # Close the path by adding the first point to the end
                        # This creates a uniform solid line all around the polygon
                        if self._freehand_points[0] != self._freehand_points[-1]:
                            self._freehand_points.append(QPointF(self._freehand_points[0]))
                        self._update_bbox_from_freehand_points()
                        print(f"Freehand ROI completed with {len(self._freehand_points)} points")
                    else:
                        print("Freehand ROI too small (need at least 3 points), discarding")
                        self._freehand_points = []
                        self._bbox = None
                        self._mode = None
                        self._paint_overlay()
                        return True
                else:
                    # Circular/rectangular mode
                    self._update_bbox_from_points()
                
                # Check if ROI is entirely outside the image - if so, restart drawing
                if self._is_entirely_outside_image():
                    print("ROI is entirely outside the image - discarding and restarting")
                    self._freehand_points = []
                    self._bbox = None
                    self._mode = None
                    self._start_pos = None
                    self._current_pos = None
                    self._paint_overlay()
                    return True
                
                self._paint_overlay(final=True)
                xyxy = self._current_roi_image_coords()
                if xyxy is not None:
                    self.roiFinalized.emit(xyxy)
                self._mode = None
                return True

            if self._mode == 'translate' and event.button() == Qt.MouseButton.RightButton:
                self._dragging = False
                
                # Check if we're in multi-ROI mode
                # Check if we're in multi-ROI mode
                if self._multi_roi_origins is not None and len(self._multi_roi_origins) > 0:
                    # Mouse released -> KEEP PREVIEW
                    self._translate_anchor = None
                    self._mode = None
                    self._dragging = False # Stop dragging but keep state
                    
                    # Repaint to keep preview visible
                    self._paint_overlay()
                    print(f"DEBUG: Multi-ROI drag released - preview kept. Press 'R' to commit, click elsewhere to cancel.")
                    return True
                
                # Single ROI translation finalization (original behavior)
                # finalize translation
                self._translate_anchor = None
                self._bbox_origin = None
                self._freehand_points_origin = None
                
                # Check if ROI is entirely outside the image after translation - if so, restart
                if self._is_entirely_outside_image():
                    print("ROI moved entirely outside the image - discarding and restarting")
                    self._freehand_points = []
                    self._bbox = None
                    self._mode = None
                    self._start_pos = None
                    self._current_pos = None
                    self._rotation_angle = 0.0
                    self._paint_overlay()
                    return True
                
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
                self._rotation_center_origin = None
                self._freehand_points_origin = None
                
                # Check if ROI is entirely outside the image after rotation - if so, restart
                if self._is_entirely_outside_image():
                    print("ROI rotated entirely outside the image - discarding and restarting")
                    self._freehand_points = []
                    self._bbox = None
                    self._mode = None
                    self._start_pos = None
                    self._current_pos = None
                    self._rotation_angle = 0.0
                    self._paint_overlay()
                    return True
                
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

    def _is_entirely_outside_image(self):
        """Check if the current ROI is entirely outside the image bounds.
        Returns True if the ROI has no overlap with the image at all."""
        if self._bbox is None or self._draw_rect is None:
            return False
        
        left, top, w, h = self._bbox
        right = left + w
        bottom = top + h
        
        dl = float(self._draw_rect.left())
        dt = float(self._draw_rect.top())
        dr = float(self._draw_rect.left() + self._draw_rect.width())
        db = float(self._draw_rect.top() + self._draw_rect.height())
        
        # Check if bbox is completely outside the draw_rect
        if right <= dl or left >= dr or bottom <= dt or top >= db:
            return True
        
        return False

    def _constrain_to_draw_rect(self, posf):
        # No longer constraining - just return the position as-is
        return posf

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

    def _update_bbox_from_freehand_points(self):
        """Compute bounding box from freehand points list."""
        if not self._freehand_points or len(self._freehand_points) < 2:
            self._bbox = None
            return
        
        # Find min/max coordinates
        min_x = min(p.x() for p in self._freehand_points)
        max_x = max(p.x() for p in self._freehand_points)
        min_y = min(p.y() for p in self._freehand_points)
        max_y = max(p.y() for p in self._freehand_points)
        
        left = float(min_x)
        top = float(min_y)
        w = max(1.0, float(max_x - min_x))
        h = max(1.0, float(max_y - min_y))
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

        # Draw current interactive bbox/path if present and allowed
        if self._bbox is not None and getattr(self, '_show_current_bbox', True):
            try:
                # For freehand mode, draw the polygon path
                if self._drawing_mode == 'freehand' and self._freehand_points:
                    # Create a polygon from the freehand points
                    polygon = QPolygonF()
                    for point in self._freehand_points:
                        adjusted_point = QPointF(point.x() - offset_x, point.y() - offset_y)
                        polygon.append(adjusted_point)
                    
                    # Draw the polygon path (solid lines)
                    if len(polygon) > 2:
                        for i in range(len(polygon) - 1):
                            painter.drawLine(polygon[i], polygon[i + 1])
                        
                        # Draw the closing line with dashed style
                        dashed_pen = QPen(QColor(255, 255, 0, 180))
                        dashed_pen.setWidth(1.5)
                        dashed_pen.setStyle(Qt.PenStyle.DashLine)
                        painter.setPen(dashed_pen)
                        painter.drawLine(polygon[len(polygon) - 1], polygon[0])
                        
                        # Draw the axis-aligned bounding box for reference (lighter color)
                        # For freehand ROIs, bbox is always axis-aligned and encompasses the polygon
                        left, top, w, h = self._bbox
                        draw_left = float(left) - offset_x
                        draw_top = float(top) - offset_y
                        bbox_pen = QPen(QColor(255, 255, 0, 80))
                        bbox_pen.setWidth(1)
                        bbox_pen.setStyle(Qt.PenStyle.DashLine)
                        painter.setPen(bbox_pen)
                        
                        # Draw axis-aligned bounding box (no rotation for freehand)
                        painter.drawRect(int(round(draw_left)), int(round(draw_top)), 
                                       int(round(w)), int(round(h)))
                        # Restore main pen
                        pen = QPen(QColor(255, 255, 0, 180))
                        pen.setWidth(3)
                        painter.setPen(pen)
                elif self._drawing_mode == 'rectangular':
                    # Rectangular mode - draw rectangle (bounding box)
                    left, top, w, h = self._bbox
                    draw_left = float(left) - offset_x
                    draw_top = float(top) - offset_y
                    if self._rotation_angle != 0.0:
                        # Draw rotated rectangle
                        center_x = draw_left + w / 2.0
                        center_y = draw_top + h / 2.0
                        painter.save()
                        painter.translate(center_x, center_y)
                        painter.rotate(math.degrees(self._rotation_angle))
                        painter.drawRect(int(round(-w/2)), int(round(-h/2)), int(round(w)), int(round(h)))
                        painter.restore()
                    else:
                        # Draw normal rectangle
                        painter.drawRect(int(round(draw_left)), int(round(draw_top)), int(round(w)), int(round(h)))
                else:
                    # Circular mode - draw ellipse
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
            except Exception as e:
                print(f"Error painting current ROI: {e}")
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
                        
                        # Check if this ROI is selected
                        is_selected = idx in self._selected_roi_indices
                        
                        # determine color - use brighter/thicker pen for selected ROIs
                        col = saved.get('color')
                        if isinstance(col, QColor):
                            qcol = col
                        elif isinstance(col, (tuple, list)) and len(col) >= 3:
                            a = col[3] if len(col) > 3 else 200
                            qcol = QColor(int(col[0]), int(col[1]), int(col[2]), int(a))
                        else:
                            qcol = QColor(200, 100, 10, 200)
                        
                        # Highlight selected ROIs with thicker, brighter border
                        if is_selected:
                            # Use a brighter version of the ROI's own color
                            spen = QPen(qcol.lighter(150))
                            spen.setColor(QColor(spen.color().red(), spen.color().green(), spen.color().blue(), 255)) # Ensure opaque
                            spen.setWidth(5)
                        else:
                            spen = QPen(qcol)
                            spen.setWidth(3)
                        painter.setPen(spen)
                        
                        # Check ROI type
                        roi_type = saved.get('type', 'circular')
                        
                        if roi_type == 'freehand':
                            # Draw freehand polygon
                            freehand_points = saved.get('points')
                            if freehand_points and len(freehand_points) >= 3:
                                polygon = QPolygonF()
                                for img_x, img_y in freehand_points:
                                    # Convert image coords to label coords (same logic as _label_bbox_from_image_xyxy)
                                    if self._draw_rect and self._img_w and self._img_h:
                                        norm_x = img_x / self._img_w
                                        norm_y = img_y / self._img_h
                                        pw = float(self._draw_rect.width())
                                        ph = float(self._draw_rect.height())
                                        # Add offset to get to label coords, then subtract to get to pixmap coords
                                        label_x = float(self._draw_rect.left() + norm_x * pw) - offset_x
                                        label_y = float(self._draw_rect.top() + norm_y * ph) - offset_y
                                        polygon.append(QPointF(label_x, label_y))
                                
                                if len(polygon) >= 3:
                                    painter.drawPolygon(polygon)
                        elif roi_type == 'rectangular':
                            # Draw rectangular ROI
                            rotation_angle = saved.get('rotation', 0.0)
                            if rotation_angle != 0.0:
                                # Draw rotated rectangle
                                center_x = px0 + lw / 2.0
                                center_y = py0 + lh / 2.0
                                painter.save()
                                painter.translate(center_x, center_y)
                                painter.rotate(math.degrees(rotation_angle))
                                painter.drawRect(int(round(-lw/2)), int(round(-lh/2)), int(round(lw)), int(round(lh)))
                                painter.restore()
                            else:
                                # Draw normal rectangle
                                painter.drawRect(int(round(px0)), int(round(py0)), int(round(lw)), int(round(lh)))
                        else:
                            # Draw circular/elliptical ROI
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

        # Draw Multi-ROI Drag Preview (Ghosts)
        if self._multi_roi_origins is not None and self._multi_roi_drag_offset is not None:
            try:
                dx = self._multi_roi_drag_offset.x()
                dy = self._multi_roi_drag_offset.y()
                
                # Use a distinct pen for ghosts
                ghost_pen = QPen(QColor(255, 255, 0, 200)) # Yellow
                ghost_pen.setWidth(2)
                ghost_pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(ghost_pen)
                
                for idx, origin in self._multi_roi_origins.items():
                    ox, oy, ow, oh = origin['bbox']
                    
                    # Apply offset
                    ghost_left = ox + dx
                    ghost_top = oy + dy
                    
                    # Draw ghost based on type
                    if 0 <= idx < len(self._saved_rois):
                        roi = self._saved_rois[idx]
                        roi_type = roi.get('type', 'circular')
                        rotation = roi.get('rotation', 0.0)
                        
                        if roi_type == 'freehand' and origin.get('freehand_points'):
                            # Draw freehand ghost
                            if self._draw_rect and self._img_w and self._img_h:
                                polygon = QPolygonF()
                                scale_x = self._img_w / float(self._draw_rect.width())
                                scale_y = self._img_h / float(self._draw_rect.height())
                                
                                for pt in origin['freehand_points']:
                                    # Image -> Label
                                    lx = self._draw_rect.left() + (pt[0] / scale_x)
                                    ly = self._draw_rect.top() + (pt[1] / scale_y)
                                    # Apply drag offset
                                    lx += dx
                                    ly += dy
                                    # Label -> Pixmap
                                    px = lx - offset_x
                                    py = ly - offset_y
                                    polygon.append(QPointF(px, py))
                                painter.drawPolygon(polygon)
                        else:
                            # Draw Rect/Ellipse ghost
                            px = ghost_left - offset_x
                            py = ghost_top - offset_y
                            
                            if rotation != 0.0:
                                center_x = px + ow / 2.0
                                center_y = py + oh / 2.0
                                painter.save()
                                painter.translate(center_x, center_y)
                                painter.rotate(math.degrees(rotation))
                                if roi_type == 'rectangular':
                                    painter.drawRect(int(round(-ow/2)), int(round(-oh/2)), int(round(ow)), int(round(oh)))
                                else:
                                    painter.drawEllipse(int(round(-ow/2)), int(round(-oh/2)), int(round(ow)), int(round(oh)))
                                painter.restore()
                            else:
                                if roi_type == 'rectangular':
                                    painter.drawRect(int(round(px)), int(round(py)), int(round(ow)), int(round(oh)))
                                else:
                                    painter.drawEllipse(int(round(px)), int(round(py)), int(round(ow)), int(round(oh)))

            except Exception as e:
                print(f"Error drawing multi-ROI preview: {e}")

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
        
        # Draw multi-selection indicator when multiple ROIs are selected
        if len(self._selected_roi_indices) > 1 and getattr(self, '_show_mode_text', True):
            # Check if we're in preview mode (after drag, before finalize)
            if self._multi_roi_origins is not None and len(self._multi_roi_origins) > 0:
                multi_text = f"Preview: {len(self._selected_roi_indices)} ROIs moved - Press 'R' to finalize, Escape to revert"
                painter.setPen(QPen(QColor(255, 165, 0, 255)))  # Orange for preview
            else:
                multi_text = f"Selected: {len(self._selected_roi_indices)} ROIs (right-click drag to move all)"
                painter.setPen(QPen(QColor(255, 255, 0, 255)))  # Bright yellow
            font = QFont()
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(10, 50, multi_text)

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
        for pixels inside the ROI in image coordinates. Returns None if
        ROI is not available or mapping info missing.
        
        For freehand ROIs, returns a mask for pixels inside the polygon.
        For rectangular ROIs, returns a mask for pixels inside the rectangle.
        For circular ROIs, returns a mask for pixels inside the ellipse.
        """
        # Check if this is a freehand ROI
        if self._drawing_mode == 'freehand' and self._freehand_points:
            return self._get_freehand_mask()
        
        # Check if this is a rectangular ROI
        if self._drawing_mode == 'rectangular':
            return self._get_rectangular_mask()
        
        # Otherwise use ellipse mask
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

    def _get_freehand_mask(self):
        """Return (X0,Y0,X1,Y1, mask) for freehand polygon ROI."""
        if not self._freehand_points or len(self._freehand_points) < 3:
            return None
        
        # Convert freehand points from label coords to image coords
        img_points = []
        for point in self._freehand_points:
            img_point = self._label_point_to_image_coords(point)
            if img_point is not None:
                img_points.append(img_point)
        
        if len(img_points) < 3:
            return None
        
        # Get bounding box in image coordinates
        img_coords = self._current_roi_image_coords()
        if img_coords is None:
            return None
        X0, Y0, X1, Y1 = img_coords
        H = Y1 - Y0
        W = X1 - X0
        if H <= 0 or W <= 0:
            return None
        
        # Create mask using polygon
        from matplotlib.path import Path
        
        # Create a grid of points within the bounding box
        y_coords, x_coords = np.meshgrid(np.arange(Y0, Y1), np.arange(X0, X1))
        points = np.column_stack((x_coords.ravel(), y_coords.ravel()))
        
        # Create polygon path
        polygon_path = Path(img_points)
        
        # Check which points are inside the polygon
        mask_flat = polygon_path.contains_points(points)
        mask = mask_flat.reshape(W, H).T
        
        return (X0, Y0, X1, Y1, mask)

    def _get_rectangular_mask(self):
        """Return (X0,Y0,X1,Y1, mask) for rectangular ROI."""
        img_coords = self._current_roi_image_coords()
        if img_coords is None:
            return None
        X0, Y0, X1, Y1 = img_coords
        H = Y1 - Y0
        W = X1 - X0
        if H <= 0 or W <= 0:
            return None
        
        # For rectangular ROI without rotation, all pixels in bbox are included
        if self._rotation_angle == 0.0:
            mask = np.ones((H, W), dtype=bool)
            return (X0, Y0, X1, Y1, mask)
        
        # For rotated rectangle, need to check which pixels are inside
        cx = (X0 + X1) / 2.0
        cy = (Y0 + Y1) / 2.0
        half_w = (X1 - X0) / 2.0
        half_h = (Y1 - Y0) / 2.0
        
        # Create a grid of points
        ys = np.arange(Y0, Y1, dtype=float)
        xs = np.arange(X0, X1, dtype=float)
        yy, xx = np.meshgrid(ys, xs, indexing='xy')
        
        # Translate to center
        xx_centered = xx - cx
        yy_centered = yy - cy
        
        # Apply inverse rotation to align with rectangle axes
        cos_angle = math.cos(-self._rotation_angle)
        sin_angle = math.sin(-self._rotation_angle)
        
        xx_rotated = xx_centered * cos_angle - yy_centered * sin_angle
        yy_rotated = xx_centered * sin_angle + yy_centered * cos_angle
        
        # Check if points are inside the rectangle
        mask = (np.abs(xx_rotated) <= half_w) & (np.abs(yy_rotated) <= half_h)
        mask = mask.T
        
        return (X0, Y0, X1, Y1, mask)

    def _label_point_to_image_coords(self, point):
        """Convert a point from label coordinates to image coordinates."""
        if self._draw_rect is None or self._img_w is None or self._img_h is None:
            return None
        
        # Get point position relative to draw_rect
        rel_x = float(point.x() - self._draw_rect.left())
        rel_y = float(point.y() - self._draw_rect.top())
        
        # Normalize to [0, 1]
        pw = float(self._draw_rect.width())
        ph = float(self._draw_rect.height())
        norm_x = rel_x / max(1.0, pw)
        norm_y = rel_y / max(1.0, ph)
        
        # Scale to image coordinates
        img_x = norm_x * self._img_w
        img_y = norm_y * self._img_h
        
        # Clamp to image bounds
        img_x = max(0.0, min(float(self._img_w), img_x))
        img_y = max(0.0, min(float(self._img_h), img_y))
        
        return (img_x, img_y)

    def get_freehand_points_image_coords(self):
        """Return the freehand points in image coordinates.
        Returns a list of (x, y) tuples or None if not in freehand mode."""
        if self._drawing_mode != 'freehand' or not self._freehand_points:
            return None
        
        img_points = []
        for point in self._freehand_points:
            img_point = self._label_point_to_image_coords(point)
            if img_point is not None:
                img_points.append(img_point)
        
        return img_points if img_points else None
