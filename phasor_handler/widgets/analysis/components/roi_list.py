"""
ROI List Widget Component

This component handles all ROI list management including:
- Display of saved ROIs in a list widget
- Add/Remove ROI functionality
- Save/Load ROI positions to/from JSON files
- Export ROI traces to text files
- ROI selection and editing
- Support for both circular and freehand ROI types
"""

import json
import os
import random
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QListWidget, QPushButton, 
    QGridLayout, QFileDialog, QMessageBox, QProgressDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF


class RoiListWidget(QWidget):
    """Widget for managing a list of saved ROIs with add/remove/save/load/export functionality."""
    
    # Signals
    roiSelected = pyqtSignal(dict)  # Emitted when a ROI is selected from the list
    roiAdded = pyqtSignal(dict)     # Emitted when a new ROI is added
    roiRemoved = pyqtSignal(int)    # Emitted when a ROI is removed (index)
    roiUpdated = pyqtSignal(int, dict)  # Emitted when an existing ROI is updated
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._editing_roi_index = None
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI components."""
        # Main layout
        layout = QVBoxLayout()
        
        # Group box for ROI list
        roi_group = QGroupBox("Saved ROIs")
        roi_vbox = QVBoxLayout()
        
        # ROI list widget
        self.roi_list_widget = QListWidget()
        self.roi_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.roi_list_widget.setMinimumWidth(220)
        self.roi_list_widget.currentItemChanged.connect(self._on_saved_roi_selected)
        roi_vbox.addWidget(self.roi_list_widget)
        
        # Button grid layout
        roi_grid_layout = QGridLayout()
        
        # Create buttons
        self.add_roi_btn = QPushButton("Add ROI")
        self.remove_roi_btn = QPushButton("Remove ROI")
        self.export_trace_btn = QPushButton("Export Trace...")
        self.save_roi_btn = QPushButton("Save ROIs...")
        self.load_roi_btn = QPushButton("Load ROIs...")
        
        # Set button sizes
        for btn in [self.add_roi_btn, self.remove_roi_btn,
                    self.save_roi_btn, self.load_roi_btn,
                    self.export_trace_btn]:
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Arrange buttons in grid
        roi_grid_layout.addWidget(self.add_roi_btn, 0, 0)
        roi_grid_layout.addWidget(self.remove_roi_btn, 0, 1)
        roi_grid_layout.addWidget(self.save_roi_btn, 1, 0)
        roi_grid_layout.addWidget(self.load_roi_btn, 1, 1)
        roi_grid_layout.addWidget(self.export_trace_btn, 2, 0, 1, 2)

        from PyQt6.QtWidgets import QCheckBox
        self.hide_rois_checkbox = QCheckBox("Hide ROIs")
        self.hide_rois_checkbox.stateChanged.connect(self._on_hide_rois_toggled)
        roi_grid_layout.addWidget(self.hide_rois_checkbox, 3, 0)
        
        self.display_labels_checkbox = QCheckBox("Hide Labels")
        self.display_labels_checkbox.stateChanged.connect(self._on_hide_labels_toggled)
        roi_grid_layout.addWidget(self.display_labels_checkbox, 3, 1)
        
        roi_vbox.addLayout(roi_grid_layout)
        roi_group.setLayout(roi_vbox)
        layout.addWidget(roi_group)
        
        # Connect button signals
        self.add_roi_btn.clicked.connect(self._on_add_roi_clicked)
        self.remove_roi_btn.clicked.connect(self._on_remove_roi_clicked)
        self.save_roi_btn.clicked.connect(self._on_save_roi_positions_clicked)
        self.load_roi_btn.clicked.connect(self._on_load_roi_positions_clicked)
        self.export_trace_btn.clicked.connect(self._on_export_roi_clicked)
        
        self.setLayout(layout)
    
    def get_list_widget(self):
        """Return the internal list widget for external access."""
        return self.roi_list_widget
    
    def set_editing_roi_index(self, index):
        """Set which ROI is currently being edited."""
        self._editing_roi_index = index
    
    def get_editing_roi_index(self):
        """Get which ROI is currently being edited."""
        return self._editing_roi_index
    
    def clear_editing_state(self):
        """Clear the editing state."""
        self._editing_roi_index = None
    
    def _on_add_roi_clicked(self):
        """Save the current ROI (if any) into an in-memory list and the list widget."""
        print(f"DEBUG: _on_add_roi_clicked called - editing_index: {self._editing_roi_index}")
        
        if getattr(self.main_window, '_last_roi_xyxy', None) is None:
            print("DEBUG: No _last_roi_xyxy found, returning")
            return
        
        print(f"DEBUG: Current _last_roi_xyxy: {self.main_window._last_roi_xyxy}")
        
        # Ensure storage exists on window
        if not hasattr(self.main_window, '_saved_rois'):
            self.main_window._saved_rois = []
        
        # Check if this ROI already exists (same coordinates), but only if we're NOT editing an existing ROI
        if self._editing_roi_index is None:  # Only check for duplicates when creating new ROIs
            current_xyxy = tuple(self.main_window._last_roi_xyxy)
            for existing_roi in self.main_window._saved_rois:
                existing_xyxy = existing_roi.get('xyxy')
                if existing_xyxy and tuple(existing_xyxy) == current_xyxy:
                    print(f"DEBUG: ROI with coordinates {current_xyxy} already exists - skipping")
                    return
        else:
            print(f"DEBUG: In editing mode for ROI {self._editing_roi_index} - allowing coordinate updates")
        
        # Get rotation angle and drawing mode from ROI tool
        roi_tool = getattr(self.main_window, 'roi_tool', None)
        rotation_angle = getattr(roi_tool, '_rotation_angle', 0.0) if roi_tool else 0.0
        drawing_mode = getattr(roi_tool, '_drawing_mode', 'circular') if roi_tool else 'circular'
        
        # Get freehand points if in freehand mode
        freehand_points = None
        if drawing_mode == 'freehand' and roi_tool:
            freehand_points = roi_tool.get_freehand_points_image_coords()
            if freehand_points and len(freehand_points) >= 3:
                print(f"DEBUG: Freehand ROI with {len(freehand_points)} points")
            else:
                print("DEBUG: Invalid freehand ROI (< 3 points)")
                return
        
        # Check if we're editing an existing ROI
        if self._editing_roi_index is not None and 0 <= self._editing_roi_index < len(self.main_window._saved_rois):
            # Update existing ROI
            existing_roi = self.main_window._saved_rois[self._editing_roi_index]
            existing_roi['xyxy'] = tuple(self.main_window._last_roi_xyxy)
            
            # Update based on drawing mode
            if drawing_mode == 'freehand' and freehand_points:
                existing_roi['type'] = 'freehand'
                existing_roi['points'] = freehand_points
                # Remove rotation for freehand ROIs
                existing_roi.pop('rotation', None)
            elif drawing_mode == 'rectangular':
                existing_roi['type'] = 'rectangular'
                existing_roi['rotation'] = rotation_angle
                # Remove points for rectangular ROIs
                existing_roi.pop('points', None)
            else:  # circular
                existing_roi['type'] = 'circular'
                existing_roi['rotation'] = rotation_angle
                # Remove points for circular ROIs
                existing_roi.pop('points', None)
            
            print(f"DEBUG: Updated {existing_roi['name']} as {existing_roi['type']} ROI")
            print(f"DEBUG: New xyxy: {existing_roi['xyxy']}")
            # Emit update signal
            self.roiUpdated.emit(self._editing_roi_index, existing_roi)
            # After updating an ROI, clear editing state and deselect the item so it's no longer "active"
            try:
                # Clear internal editing index
                self._editing_roi_index = None
                # Deselect the list widget selection
                lw = self.get_list_widget()
                if lw is not None:
                    lw.clearSelection()
                    lw.setCurrentItem(None)
                # Update ROI tool display
                if hasattr(self.main_window, 'roi_tool') and self.main_window.roi_tool:
                    self.main_window.roi_tool.set_saved_rois(self.main_window._saved_rois)
                    self.main_window.roi_tool._paint_overlay()
                print("DEBUG: Cleared editing state and deselected ROI after update")
            except Exception:
                pass
        else:
            # Find the first available ROI number starting from 1
            import re
            existing_numbers = set()
            for existing_roi in self.main_window._saved_rois:
                roi_name = existing_roi.get('name', '')
                match = re.search(r'\d+', roi_name)
                if match:
                    existing_numbers.add(int(match.group()))
            
            # Find first available number starting from 1
            next_num = 1
            while next_num in existing_numbers:
                next_num += 1
            
            name = f"ROI {next_num}"
            
            color = (
                random.randint(100, 255),  # R
                random.randint(100, 255),  # G
                random.randint(100, 255),  # B
                200  # Alpha
            )
            
            roi_data = {
                'name': name, 
                'xyxy': tuple(self.main_window._last_roi_xyxy),
                'color': color,
            }
            
            # Add type-specific data
            if drawing_mode == 'freehand' and freehand_points:
                roi_data['type'] = 'freehand'
                roi_data['points'] = freehand_points
                print(f"Created new {name} as freehand ROI with {len(freehand_points)} points")
            elif drawing_mode == 'rectangular':
                roi_data['type'] = 'rectangular'
                roi_data['rotation'] = rotation_angle
                print(f"Created new {name} as rectangular ROI")
            else:  # circular
                roi_data['type'] = 'circular'
                roi_data['rotation'] = rotation_angle
                print(f"Created new {name} as circular ROI")
            
            self.main_window._saved_rois.append(roi_data)
            self.roi_list_widget.addItem(name)
            print(f"Created new {name}")
            
            # Emit added signal
            self.roiAdded.emit(roi_data)
        
        # Always clear editing state after any ROI operation
        self._editing_roi_index = None
        
        # Update the ROI tool with all saved ROIs so they display persistently
        if hasattr(self.main_window, 'roi_tool') and self.main_window.roi_tool:
            self.main_window.roi_tool.set_saved_rois(self.main_window._saved_rois)
            # Repaint overlay to show all saved ROIs
            self.main_window.roi_tool._paint_overlay()
    
    def _on_remove_roi_clicked(self):
        """Remove selected saved ROI from widget and in-memory store."""
        item = self.roi_list_widget.currentItem()
        if not item:
            return
        row = self.roi_list_widget.row(item)
        self.roi_list_widget.takeItem(row)
        
        try:
            if hasattr(self.main_window, '_saved_rois'):
                del self.main_window._saved_rois[row]
                # Update the ROI tool with remaining saved ROIs
                if hasattr(self.main_window, 'roi_tool') and self.main_window.roi_tool:
                    self.main_window.roi_tool.set_saved_rois(self.main_window._saved_rois)
                    # Repaint overlay to show updated ROIs
                    self.main_window.roi_tool._paint_overlay()
                
                # Emit removal signal
                self.roiRemoved.emit(row)
        except Exception:
            pass
    
    def _on_saved_roi_selected(self, current, previous=None):
        """Restore the selected saved ROI onto the image/roi tool and update trace."""
        if current is None:
            return
            
        row = self.roi_list_widget.row(current)
        saved = None
        if hasattr(self.main_window, '_saved_rois') and 0 <= row < len(self.main_window._saved_rois):
            saved = self.main_window._saved_rois[row]
        if saved is None:
            return
            
        xyxy = saved.get('xyxy')
        if xyxy is None:
            return
        
        # Set editing mode for this ROI
        self._editing_roi_index = row
        print(f"DEBUG: Set editing_roi_index to {row} for ROI: {saved.get('name', 'Unknown')}")
        
        # Restore and update
        try:
            self.main_window._last_roi_xyxy = xyxy
            
            # Determine ROI type
            roi_type = saved.get('type', 'circular')
            
            if roi_type == 'freehand':
                # Restore freehand ROI
                freehand_points = saved.get('points')
                if freehand_points and hasattr(self.main_window, 'roi_tool') and self.main_window.roi_tool:
                    # Set drawing mode to freehand
                    self.main_window.roi_tool.set_drawing_mode('freehand')
                    
                    # Convert image points back to label coordinates for display
                    label_points = []
                    for img_x, img_y in freehand_points:
                        # This is the inverse of _label_point_to_image_coords
                        if self.main_window.roi_tool._draw_rect and self.main_window.roi_tool._img_w and self.main_window.roi_tool._img_h:
                            norm_x = img_x / self.main_window.roi_tool._img_w
                            norm_y = img_y / self.main_window.roi_tool._img_h
                            pw = float(self.main_window.roi_tool._draw_rect.width())
                            ph = float(self.main_window.roi_tool._draw_rect.height())
                            label_x = self.main_window.roi_tool._draw_rect.left() + norm_x * pw
                            label_y = self.main_window.roi_tool._draw_rect.top() + norm_y * ph
                            label_points.append(QPointF(label_x, label_y))
                    
                    # Restore freehand points and bbox
                    self.main_window.roi_tool._freehand_points = label_points
                    self.main_window.roi_tool._update_bbox_from_freehand_points()
                    self.main_window.roi_tool._rotation_angle = 0.0
                    self.main_window.roi_tool._paint_overlay()
                    
                    # Update UI toggle buttons to match the freehand mode
                    self._sync_ui_toggle_buttons('freehand')
                    
                    print(f"Selected freehand ROI {row + 1} with {len(freehand_points)} points for editing")
            elif roi_type == 'rectangular':
                # Restore rectangular ROI
                rotation = saved.get('rotation', 0.0)
                if hasattr(self.main_window, 'roi_tool') and self.main_window.roi_tool:
                    # Set drawing mode to rectangular
                    self.main_window.roi_tool.set_drawing_mode('rectangular')
                    self.main_window.roi_tool.show_bbox_image_coords(xyxy, rotation)
                    self.main_window.roi_tool._rotation_angle = rotation
                    self.main_window.roi_tool._freehand_points = []  # Clear any freehand points
                    
                    # Update UI toggle buttons to match the rectangular mode
                    self._sync_ui_toggle_buttons('rectangular')
                    
                print(f"Selected rectangular ROI {row + 1} for editing")
                print(f"DEBUG: Restored xyxy: {xyxy}, rotation: {rotation}")
            else:
                # Restore circular ROI
                rotation = saved.get('rotation', 0.0)
                if hasattr(self.main_window, 'roi_tool') and self.main_window.roi_tool:
                    # Set drawing mode to circular
                    self.main_window.roi_tool.set_drawing_mode('circular')
                    self.main_window.roi_tool.show_bbox_image_coords(xyxy, rotation)
                    self.main_window.roi_tool._rotation_angle = rotation
                    self.main_window.roi_tool._freehand_points = []  # Clear any freehand points
                    
                    # Update UI toggle buttons to match the circular mode
                    self._sync_ui_toggle_buttons('circular')
                    
                print(f"Selected circular ROI {row + 1} for editing")
                print(f"DEBUG: Restored xyxy: {xyxy}, rotation: {rotation}")
            
            # Emit selection signal
            self.roiSelected.emit(saved)
        except Exception as e:
            print(f"Error restoring ROI: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_load_roi_positions_clicked(self):
        """Load ROI positions from a JSON file."""
        # Get the current directory path from the analysis widget
        default_dir = None
        if hasattr(self.main_window, '_get_current_directory_path'):
            default_dir = self.main_window._get_current_directory_path()
        
        # Open file dialog to choose file to import
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Load ROI Positions")
        file_dialog.setNameFilter("JSON files (*.json)")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        
        # Set the default directory if available
        if default_dir:
            file_dialog.setDirectory(default_dir)
        
        if not file_dialog.exec():
            return
            
        filename = file_dialog.selectedFiles()[0]
        
        try:
            with open(filename, 'r') as f:
                loaded_rois = json.load(f)
            
            # Clear existing ROIs
            if not hasattr(self.main_window, '_saved_rois'):
                self.main_window._saved_rois = []
            
            self.roi_list_widget.clear()
            self.main_window._saved_rois.clear()
            
            # Add loaded ROIs
            for roi in loaded_rois:
                # Ensure required fields exist with defaults
                if 'name' not in roi:
                    roi['name'] = f"ROI {len(self.main_window._saved_rois) + 1}"
                if 'color' not in roi:
                    roi['color'] = (255, 255, 0, 200)  # Default yellow
                
                # Handle ROI type - determine if circular or freehand
                if 'type' not in roi:
                    # Auto-detect type based on presence of 'points' or 'rotation'
                    if 'points' in roi and roi['points']:
                        roi['type'] = 'freehand'
                    else:
                        roi['type'] = 'circular'
                        if 'rotation' not in roi:
                            roi['rotation'] = 0.0
                    
                self.main_window._saved_rois.append(roi)
                self.roi_list_widget.addItem(roi['name'])
            
            # Update ROI tool
            if hasattr(self.main_window, 'roi_tool') and self.main_window.roi_tool:
                self.main_window.roi_tool.set_saved_rois(self.main_window._saved_rois)
                self.main_window.roi_tool._paint_overlay()
            
            QMessageBox.information(self, "Load Complete", 
                                  f"Successfully loaded {len(loaded_rois)} ROIs from:\n{filename}")
                                  
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load ROIs:\n{str(e)}")
    
    def _on_save_roi_positions_clicked(self):
        """Save ROI positions to a JSON file."""
        if not hasattr(self.main_window, '_saved_rois') or not self.main_window._saved_rois:
            QMessageBox.warning(self, "No ROIs", "No ROIs to save.")
            return
        
        # Get the current directory path from the analysis widget
        default_dir = None
        if hasattr(self.main_window, '_get_current_directory_path'):
            default_dir = self.main_window._get_current_directory_path()
        
        # Generate default filename
        default_filename = "roi_positions.json"
        
        # Combine directory and filename for full default path
        if default_dir:
            default_path = os.path.join(default_dir, default_filename)
        else:
            default_path = default_filename
            
        # Open file dialog to choose save location
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Save ROI Positions")
        file_dialog.setNameFilter("JSON files (*.json)")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDefaultSuffix("json")
        
        # Set the default directory if available
        if default_dir and default_path:
            file_dialog.selectFile(default_path)
        
        if not file_dialog.exec():
            return
            
        filename = file_dialog.selectedFiles()[0]
        
        try:
            # Prepare data for JSON serialization
            roi_data = []
            for roi in self.main_window._saved_rois:
                roi_copy = roi.copy()
                # Ensure xyxy is a list for JSON serialization
                if 'xyxy' in roi_copy:
                    roi_copy['xyxy'] = list(roi_copy['xyxy'])
                roi_data.append(roi_copy)
            
            with open(filename, 'w') as f:
                json.dump(roi_data, f, indent=2)
            
            QMessageBox.information(self, "Save Complete", 
                                  f"Successfully saved {len(roi_data)} ROIs to:\n{filename}")
                                  
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save ROIs:\n{str(e)}")
    
    def _on_export_roi_clicked(self):
        """Export all saved ROIs for all timepoints to a tab-separated text file."""
        if not hasattr(self.main_window, '_saved_rois') or not self.main_window._saved_rois:
            QMessageBox.information(self, "No ROIs", "No ROIs to export. Please add some ROIs first.")
            return
            
        # Check if we have image data
        if not hasattr(self.main_window, '_current_tif') or self.main_window._current_tif is None:
            QMessageBox.warning(self, "No Image Data", "No image data loaded. Please load a dataset first.")
            return
        
        # Get the current directory path from the analysis widget
        default_dir = None
        if hasattr(self.main_window, '_get_current_directory_path'):
            default_dir = self.main_window._get_current_directory_path()
        
        # Generate default filename
        default_filename = "roi_traces.txt"
        
        # Combine directory and filename for full default path
        if default_dir:
            default_path = os.path.join(default_dir, default_filename)
        else:
            default_path = default_filename
            
        # Open file dialog to choose save location
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Export ROIs")
        file_dialog.setNameFilter("Text files (*.txt)")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDefaultSuffix("txt")
        
        # Set the default directory if available
        if default_dir and default_path:
            file_dialog.selectFile(default_path)
        
        if not file_dialog.exec():
            return
            
        filename = file_dialog.selectedFiles()[0]
        
        try:
            # Get image data dimensions
            tif = self.main_window._current_tif
            tif_chan2 = getattr(self.main_window, '_current_tif_chan2', None)
            
            # Determine number of frames
            if tif.ndim == 3:
                nframes = tif.shape[0]
            else:
                nframes = 1
                tif = tif[None, ...]  # Add frame dimension
                if tif_chan2 is not None:
                    tif_chan2 = tif_chan2[None, ...]
            
            # Get current formula selection
            formula_index = getattr(self.main_window, 'formula_dropdown', None)
            if formula_index is not None:
                formula_index = formula_index.currentIndex()
            else:
                formula_index = 0  # Default to first formula
            
            # Progress tracking for large datasets
            total_work = nframes * len(self.main_window._saved_rois)
            if total_work > 1000:
                progress = QProgressDialog("Extracting ROI data...", "Cancel", 0, total_work, self)
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.show()
            else:
                progress = None
            
            # Extract ROI numbers from names and handle duplicates
            import re
            headers = ["Frame", "Time"]
            roi_numbers = []
            seen_numbers = {}
            
            for i, roi in enumerate(self.main_window._saved_rois):
                roi_name = roi.get('name', f'ROI {i + 1}')
                
                # Extract number from ROI name using regex
                # Matches patterns like "ROI14", "S14", "ROI 14", etc.
                match = re.search(r'\d+', roi_name)
                if match:
                    roi_num = int(match.group())
                else:
                    # Fallback to index if no number found
                    roi_num = i + 1
                
                # Handle duplicates by incrementing until unique
                original_num = roi_num
                while roi_num in seen_numbers:
                    roi_num += 1
                
                seen_numbers[roi_num] = True
                roi_numbers.append(roi_num)
                
                if roi_num != original_num:
                    print(f"Warning: Duplicate ROI number {original_num} detected, using {roi_num} instead")
                
                headers.extend([
                    f"Green_Mean_ROI{roi_num}",
                    f"Red_Mean_ROI{roi_num}",
                    f"Trace_ROI{roi_num}"
                ])
            
            # Pre-calculate baseline (Fog) for each ROI using first 10% of frames
            roi_baselines = {}
            baseline_count = max(1, int(np.ceil(nframes * 0.10)))
            
            for i, roi in enumerate(self.main_window._saved_rois):
                xyxy = roi.get('xyxy')
                if xyxy is None:
                    roi_baselines[i] = 0
                    continue
                
                x0, y0, x1, y1 = xyxy
                roi_height = y1 - y0
                roi_width = x1 - x0
                
                if roi_height > 0 and roi_width > 0:
                    # Extract green values from baseline frames using appropriate mask
                    green_baseline_values = []
                    try:
                        roi_type = roi.get('type', 'circular')
                        
                        # Create mask based on ROI type
                        if roi_type == 'freehand':
                            freehand_points = roi.get('points')
                            if freehand_points and len(freehand_points) >= 3:
                                from matplotlib.path import Path
                                y_coords, x_coords = np.meshgrid(np.arange(y0, y1), np.arange(x0, x1))
                                points = np.column_stack((x_coords.ravel(), y_coords.ravel()))
                                polygon_path = Path(freehand_points)
                                mask_flat = polygon_path.contains_points(points)
                                mask = mask_flat.reshape(roi_width, roi_height).T
                            else:
                                mask = np.ones((roi_height, roi_width), dtype=bool)
                        else:
                            cy, cx = (y0 + y1) / 2.0, (x0 + x1) / 2.0
                            ry, rx = roi_height / 2.0, roi_width / 2.0
                            rotation_angle = roi.get('rotation', 0.0)
                            
                            y_coords, x_coords = np.ogrid[y0:y1, x0:x1]
                            
                            if rotation_angle != 0.0:
                                x_centered = x_coords - cx
                                y_centered = y_coords - cy
                                cos_angle = np.cos(-rotation_angle)
                                sin_angle = np.sin(-rotation_angle)
                                x_rotated = x_centered * cos_angle - y_centered * sin_angle
                                y_rotated = x_centered * sin_angle + y_centered * cos_angle
                                mask = ((x_rotated / rx) ** 2 + (y_rotated / ry) ** 2) <= 1
                            else:
                                mask = ((x_coords - cx) / rx) ** 2 + ((y_coords - cy) / ry) ** 2 <= 1
                        
                        # Extract baseline values using mask
                        for frame_idx in range(baseline_count):
                            green_frame = tif[frame_idx]
                            if mask.any():
                                green_roi_pixels = green_frame[y0:y1, x0:x1][mask]
                                green_baseline_values.append(np.mean(green_roi_pixels))
                            else:
                                green_baseline_values.append(np.mean(green_frame[y0:y1, x0:x1]))
                        
                        roi_baselines[i] = float(np.mean(green_baseline_values))
                    except Exception as e:
                        print(f"Error calculating baseline for ROI {i+1} ({roi.get('type', 'circular')}): {e}")
                        roi_baselines[i] = 0
                else:
                    roi_baselines[i] = 0
            
            # Extract data for all frames and all ROIs
            export_data = []
            
            for frame_idx in range(nframes):
                if progress is not None:
                    if progress.wasCanceled():
                        return
                    progress.setValue(frame_idx * len(self.main_window._saved_rois))
                
                # Get frames for this timepoint
                green_frame = tif[frame_idx]
                red_frame = tif_chan2[frame_idx] if tif_chan2 is not None else None
                
                # Get time information
                time_s = 0.0
                if hasattr(self.main_window, '_exp_data') and self.main_window._exp_data:
                    try:
                        ed = self.main_window._exp_data
                        timestamps = None
                        
                        # Handle both dictionary and object metadata formats
                        if isinstance(ed, dict):
                            timestamps = ed.get('time_stamps', [])
                        else:
                            if hasattr(ed, 'time_stamps'):
                                timestamps = getattr(ed, 'time_stamps', [])
                        
                        if timestamps and frame_idx < len(timestamps):
                            time_s = float(timestamps[frame_idx]) / 1000.0  # Convert ms to seconds
                    except Exception:
                        pass
                
                # Start row with frame number (0-indexed) and time
                row_data = [str(frame_idx), f"{time_s:.6f}"]
                
                # Process each ROI
                for i, roi in enumerate(self.main_window._saved_rois):
                    xyxy = roi.get('xyxy')
                    if xyxy is None:
                        row_data.extend(["N/A", "N/A", "N/A"])
                        continue
                    
                    x0, y0, x1, y1 = xyxy
                    
                    # Determine ROI type and create appropriate mask
                    roi_type = roi.get('type', 'circular')
                    
                    # Extract green channel mean for this ROI using appropriate mask
                    try:
                        roi_height = y1 - y0
                        roi_width = x1 - x0
                        
                        if roi_height > 0 and roi_width > 0:
                            if roi_type == 'freehand':
                                # Create polygon mask for freehand ROI
                                freehand_points = roi.get('points')
                                if freehand_points and len(freehand_points) >= 3:
                                    from matplotlib.path import Path
                                    
                                    # Create a grid of points within the bounding box
                                    y_coords, x_coords = np.meshgrid(np.arange(y0, y1), np.arange(x0, x1))
                                    points = np.column_stack((x_coords.ravel(), y_coords.ravel()))
                                    
                                    # Create polygon path
                                    polygon_path = Path(freehand_points)
                                    
                                    # Check which points are inside the polygon
                                    mask_flat = polygon_path.contains_points(points)
                                    mask = mask_flat.reshape(roi_width, roi_height).T
                                else:
                                    # Fallback to rectangular mask if points are invalid
                                    mask = np.ones((roi_height, roi_width), dtype=bool)
                            else:
                                # Create ellipse mask for circular ROI
                                cy, cx = (y0 + y1) / 2.0, (x0 + x1) / 2.0
                                ry, rx = roi_height / 2.0, roi_width / 2.0
                                
                                # Handle rotation if present
                                rotation_angle = roi.get('rotation', 0.0)
                                
                                y_grid, x_grid = np.ogrid[y0:y1, x0:x1]
                                
                                if rotation_angle != 0.0:
                                    # Rotate coordinates
                                    x_centered = x_grid - cx
                                    y_centered = y_grid - cy
                                    
                                    cos_angle = np.cos(-rotation_angle)
                                    sin_angle = np.sin(-rotation_angle)
                                    
                                    x_rotated = x_centered * cos_angle - y_centered * sin_angle
                                    y_rotated = x_centered * sin_angle + y_centered * cos_angle
                                    
                                    mask = ((x_rotated / rx) ** 2 + (y_rotated / ry) ** 2) <= 1
                                else:
                                    mask = ((x_grid - cx) / rx) ** 2 + ((y_grid - cy) / ry) ** 2 <= 1
                            
                            # Extract green values using the mask
                            if mask.any():
                                green_roi_pixels = green_frame[y0:y1, x0:x1][mask]
                                green_mean = float(np.mean(green_roi_pixels))
                            else:
                                # Fallback to rectangular mean if mask is empty
                                green_mean = float(np.mean(green_frame[y0:y1, x0:x1]))
                        else:
                            green_mean = "N/A"
                    except Exception as e:
                        print(f"Error extracting green values for ROI {i+1} ({roi_type}), frame {frame_idx}: {e}")
                        green_mean = "N/A"
                    
                    # Extract red channel mean using the same mask
                    try:
                        if red_frame is not None and roi_height > 0 and roi_width > 0:
                            if mask.any():
                                red_roi_pixels = red_frame[y0:y1, x0:x1][mask]
                                red_mean = float(np.mean(red_roi_pixels))
                            else:
                                red_mean = float(np.mean(red_frame[y0:y1, x0:x1]))
                        else:
                            red_mean = "N/A"
                    except Exception as e:
                        print(f"Error extracting red values for ROI {i+1} ({roi_type}), frame {frame_idx}: {e}")
                        red_mean = "N/A"
                    
                    # Calculate trace value based on formula index
                    try:
                        Fog = roi_baselines[i]  # Get baseline for this ROI
                        
                        if isinstance(green_mean, (int, float)) and isinstance(red_mean, (int, float)):
                            if formula_index == 0:  # (Fg - Fog) / Fr
                                if red_mean != 0:
                                    trace_value = (green_mean - Fog) / red_mean
                                else:
                                    trace_value = (green_mean - Fog) / (red_mean + 1e-6)  # Avoid division by zero
                            elif formula_index == 1:  # (Fg - Fog) / Fog
                                if Fog != 0:
                                    trace_value = (green_mean - Fog) / Fog
                                else:
                                    trace_value = (green_mean - Fog) / (Fog + 1e-6)  # Avoid division by zero
                            elif formula_index == 2:  # Fg only
                                trace_value = green_mean
                            elif formula_index == 3:  # Fr only
                                if red_mean != "N/A":
                                    trace_value = red_mean
                                else:
                                    trace_value = 0
                            else:
                                trace_value = green_mean - red_mean if red_mean != "N/A" else green_mean
                        elif isinstance(green_mean, (int, float)):
                            if formula_index == 0:  # (Fg - Fog) / Fr but no red
                                trace_value = 0
                            elif formula_index == 1:  # (Fg - Fog) / Fog
                                if Fog != 0:
                                    trace_value = (green_mean - Fog) / Fog
                                else:
                                    trace_value = (green_mean - Fog) / (Fog + 1e-6)
                            elif formula_index == 2:  # Fg only
                                trace_value = green_mean
                            elif formula_index == 3:  # Fr only but no red
                                trace_value = 0
                            else:
                                trace_value = green_mean
                        else:
                            trace_value = 0
                    except Exception as e:
                        print(f"Error calculating trace for ROI {i+1}, frame {frame_idx}: {e}")
                        trace_value = 0
                    
                    # Format values for export
                    green_str = f"{green_mean:.6f}" if isinstance(green_mean, (int, float)) else str(green_mean)
                    red_str = f"{red_mean:.6f}" if isinstance(red_mean, (int, float)) else str(red_mean)
                    trace_str = f"{trace_value:.6f}" if isinstance(trace_value, (int, float)) else str(trace_value)
                    
                    row_data.extend([green_str, red_str, trace_str])
                
                export_data.append(row_data)
            
            if progress is not None:
                progress.setValue(total_work)
                progress.close()
            
            # Write to file
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                # Write header
                f.write('\t'.join(headers) + '\n')
                
                # Write data rows
                for row in export_data:
                    f.write('\t'.join(row) + '\n')
            
            QMessageBox.information(self, "Export Complete", 
                                  f"Successfully exported {len(self.main_window._saved_rois)} ROIs across {nframes} frames to:\n{filename}")
                                  
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export ROIs:\n{str(e)}")
            import traceback
            print("Full error traceback:")
            traceback.print_exc()
    
    def _on_hide_rois_toggled(self, state):
        """Hide or show saved/stim ROIs when checkbox toggled."""
        show = False if state else True
        try:
            # hide saved ROIs and stimulus ROIs when checkbox is checked
            if hasattr(self.main_window, 'roi_tool') and self.main_window.roi_tool:
                self.main_window.roi_tool.set_show_saved_rois(show)
                # also hide the interactive bbox if ROIs are hidden to reduce clutter
                self.main_window.roi_tool.set_show_current_bbox(show)
        except Exception:
            pass
    
    def _on_hide_labels_toggled(self, state):
        """Show or hide text labels within ROIs when checkbox toggled."""
        show = False if state else True
        try:
            # Toggle label visibility within ROIs
            if hasattr(self.main_window, 'roi_tool') and self.main_window.roi_tool:
                self.main_window.roi_tool.set_show_labels(show)
        except Exception:
            pass
    
    def _sync_ui_toggle_buttons(self, mode):
        """Sync the UI toggle buttons to match the given mode.
        
        Args:
            mode: One of 'circular', 'rectangular', or 'freehand'
        """
        try:
            # Get the analysis widget (parent of this component)
            analysis_widget = None
            
            # Try to find the analysis widget through the main window
            if hasattr(self.main_window, 'analysis_widget'):
                analysis_widget = self.main_window.analysis_widget
            else:
                # Fallback: navigate through parent hierarchy
                parent = self.parent()
                while parent is not None:
                    if hasattr(parent, 'circular_roi_button'):
                        analysis_widget = parent
                        break
                    parent = parent.parent()
            
            if analysis_widget is None:
                print("DEBUG: Could not find analysis widget to sync toggle buttons")
                return
            
            # Block signals to prevent triggering the toggled event
            if hasattr(analysis_widget, 'circular_roi_button'):
                analysis_widget.circular_roi_button.blockSignals(True)
                analysis_widget.circular_roi_button.setChecked(mode == 'circular')
                analysis_widget.circular_roi_button.blockSignals(False)
                analysis_widget._circular_roi = (mode == 'circular')
            
            if hasattr(analysis_widget, 'rectangular_roi_button'):
                analysis_widget.rectangular_roi_button.blockSignals(True)
                analysis_widget.rectangular_roi_button.setChecked(mode == 'rectangular')
                analysis_widget.rectangular_roi_button.blockSignals(False)
                analysis_widget._rectangular_roi = (mode == 'rectangular')
            
            if hasattr(analysis_widget, 'freehand_roi_button'):
                analysis_widget.freehand_roi_button.blockSignals(True)
                analysis_widget.freehand_roi_button.setChecked(mode == 'freehand')
                analysis_widget.freehand_roi_button.blockSignals(False)
                analysis_widget._freehand_roi = (mode == 'freehand')
            
            print(f"DEBUG: Synced UI toggle buttons to {mode} mode")
            
        except Exception as e:
            print(f"DEBUG: Error syncing UI toggle buttons: {e}")
            import traceback
            traceback.print_exc()
    
    def auto_select_roi_by_click(self, roi_index):
        """Automatically select a ROI from the list when clicked on the image."""
        try:
            # Select the corresponding item in the ROI list widget
            if 0 <= roi_index < self.roi_list_widget.count():
                self.roi_list_widget.setCurrentRow(roi_index)
                print(f"Auto-selected ROI {roi_index + 1} by right-click")
        except Exception as e:
            print(f"Error selecting ROI by click: {e}")
    
    def refresh_roi_display(self):
        """Refresh the ROI display in the ROI tool."""
        if hasattr(self.main_window, 'roi_tool') and self.main_window.roi_tool:
            self.main_window.roi_tool.set_saved_rois(getattr(self.main_window, '_saved_rois', []))
            self.main_window.roi_tool._paint_overlay()