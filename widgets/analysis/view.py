# TODO Implement better ROI drawing
# TODO read Mini2P data
# TODO Compartmentalize the image functionalities better
# TODO Fix dimensionality bug

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QListWidget,
    QPushButton, QSlider, QSizePolicy, QFileDialog, QMessageBox, 
    QCheckBox, QLabel, QDoubleSpinBox
)
from PyQt6.QtCore import Qt

import os
import datetime
import matplotlib.pyplot as plt
import numpy as np

from .components import ImageViewWidget, TraceplotWidget, CircleRoiTool, RoiListWidget, MetadataViewer


class AnalysisWidget(QWidget):
    """Encapsulated Analysis tab widget.

    Accepts the main window instance so it can call helper methods and
    exposes compatible attributes on the main window (e.g., analysis_list_widget,
    reg_tif_label, tif_slider) so existing MainWindow methods continue to work.
    """

    def __init__(self, main_window):
        super().__init__()
        self.window = main_window
        
        # Make the widget focusable to receive keyboard events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Ensure parent's ROI state exists
        try:
            self.window._init_roi_state()
        except Exception:
            pass

        # Initialize CNB attributes on window
        if not hasattr(self.window, '_cnb_active'):
            self.window._cnb_active = True
        if not hasattr(self.window, '_cnb_contrast'):
            self.window._cnb_contrast = 1.0
        if not hasattr(self.window, '_cnb_min'):
            self.window._cnb_min = None
        if not hasattr(self.window, '_cnb_max'):
            self.window._cnb_max = None
        if not hasattr(self.window, '_cnb_window'):
            self.window._cnb_window = None

        # Track which saved ROI is currently being edited (delegated to ROI component)
        self._editing_roi_index = None
        
        # Initialize text visibility state (for CTRL+Y toggle)
        self._text_visible = True
        
        # Initialize percentile values for persistence
        self._ch1_percentile_min = 1.0
        self._ch1_percentile_max = 99.5
        self._ch2_percentile_min = 1.0
        self._ch2_percentile_max = 99.5

        widget = self
        main_vbox = QVBoxLayout()
        main_hbox = QHBoxLayout()

        # --- Left VBox: Directories ---
        left_vbox = QVBoxLayout()
        dir_group = QGroupBox("Registered Directories")
        dir_layout = QVBoxLayout()
        self.analysis_list_widget = QListWidget()
        self.analysis_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        reg_button_layout = QHBoxLayout()
        add_dir_btn = QPushButton("Add Directories...")
        add_dir_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add_dir_btn.clicked.connect(lambda: self.window.add_dirs_dialog('analysis'))
        remove_dir_btn = QPushButton("Remove Selected")
        remove_dir_btn.clicked.connect(lambda: self.window.remove_selected_dirs('analysis'))
        remove_dir_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        reg_button_layout.addWidget(add_dir_btn)
        reg_button_layout.addWidget(remove_dir_btn)
        reg_button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.analysis_list_widget.setMinimumWidth(220)
        # Populate using the dir_manager's display names
        from PyQt6.QtWidgets import QListWidgetItem
        for full_path, display_name in getattr(self.window.dir_manager, 'get_display_names', lambda: [])():
            item = QListWidgetItem(display_name)
            item.setToolTip(full_path)
            item.setData(Qt.ItemDataRole.UserRole, full_path)
            self.analysis_list_widget.addItem(item)
        dir_layout.addWidget(self.analysis_list_widget)
        dir_layout.addLayout(reg_button_layout)
        dir_group.setLayout(dir_layout)
        left_vbox.addWidget(dir_group)

        # --- Mid HBox: Buttons to change the view of the image ---
        midl_vbox = QVBoxLayout()
        midr_vbox = QVBoxLayout()

        self.channel_button = QPushButton("Show Channel 2")
        self.channel_button.setEnabled(False)
        self.channel_button.clicked.connect(self.toggle_channel)

        self.file_type_button = QPushButton("Show Raw")
        self.file_type_button.setEnabled(False)
        self.file_type_button.clicked.connect(self.toggle_file_type)
        self._using_registered = True  

        self.cnb_button = QPushButton("BnC (IN PROGRESS)")
        self.cnb_button.setEnabled(False)
        self.cnb_button.clicked.connect(self.open_contrast_dialog)

        self.stimulation_area_button = QPushButton("Show Stimulation")
        self.stimulation_area_button.setEnabled(False)
        self.stimulation_area_button.setCheckable(True)
        self.stimulation_area_button.setChecked(False)
        self.stimulation_area_button.clicked.connect(self.toggle_stim_rois)

        self.composite_button = QPushButton("Show Composite")
        self.composite_button.setEnabled(False)
        self.composite_button.setCheckable(True)
        self.composite_button.setChecked(True)
        self.composite_button.clicked.connect(lambda _checked: (self.update_tif_frame(), self._sync_channel_button_state()))

        self.view_metadata_button = QPushButton("View Metadata")
        self.view_metadata_button.setEnabled(False)
        self.view_metadata_button.clicked.connect(self.open_metadata_viewer)

        self.save_img = QPushButton("Save Current View")
        self.save_img.setEnabled(False)
        self.save_img.clicked.connect(self._save_current_view)

        self.scale_bar_checkbox = QCheckBox("Show Scale Bar")
        self.scale_bar_checkbox.setChecked(False)
        self.scale_bar_checkbox.setEnabled(False)  # Initially disabled
        self.scale_bar_checkbox.stateChanged.connect(self.toggle_scale_bar)

        # --- Z-Projections Group ---
        zproj_group = QGroupBox("Z-Projections")
        zproj_layout = QVBoxLayout()
        
        self.zproj_std_button = QPushButton("Standard Deviation")
        self.zproj_std_button.setEnabled(False)
        self.zproj_std_button.setCheckable(True)
        self.zproj_std_button.setChecked(False)
        self._zproj_std = False
        self.zproj_std_button.toggled.connect(lambda checked, m='std': self._on_zproj_toggled(m, checked))

        self.zproj_max_button = QPushButton("Max")
        self.zproj_max_button.setEnabled(False)
        self.zproj_max_button.setCheckable(True)
        self.zproj_max_button.setChecked(False)
        self._zproj_max = False
        self.zproj_max_button.toggled.connect(lambda checked, m='max': self._on_zproj_toggled(m, checked))

        self.zproj_mean_button = QPushButton("Mean")
        self.zproj_mean_button.setEnabled(False)
        self.zproj_mean_button.setCheckable(True)
        self.zproj_mean_button.setChecked(False)
        self._zproj_mean = False
        self.zproj_mean_button.toggled.connect(lambda checked, m='mean': self._on_zproj_toggled(m, checked))

        zproj_layout.addWidget(self.zproj_std_button)
        zproj_layout.addWidget(self.zproj_max_button)
        zproj_layout.addWidget(self.zproj_mean_button)
        zproj_group.setLayout(zproj_layout)

        # --- BnC Group ---
        self.bnc_group = QGroupBox("Brightness and Contrast")
        self.bnc_group.setObjectName('bnc_group')
        bnc_layout = QVBoxLayout()
        bnc_labels = QHBoxLayout()

        # Channel selection buttons (mutually exclusive)
        channel_buttons_layout = QHBoxLayout()
        
        self.bnc_channel1_button = QPushButton("Channel 1")
        self.bnc_channel1_button.setCheckable(True)
        self.bnc_channel1_button.setChecked(True)  # Default to Channel 1
        self.bnc_channel1_button.clicked.connect(lambda: self._on_bnc_channel_selected(1))
        self.bnc_channel1_button.setMaximumWidth(80)
        
        self.bnc_channel2_button = QPushButton("Channel 2")
        self.bnc_channel2_button.setCheckable(True)
        self.bnc_channel2_button.setChecked(False)
        self.bnc_channel2_button.setEnabled(False)  # Initially disabled
        self.bnc_channel2_button.clicked.connect(lambda: self._on_bnc_channel_selected(2))
        self.bnc_channel2_button.setMaximumWidth(80)
        
        channel_buttons_layout.addWidget(self.bnc_channel1_button)
        channel_buttons_layout.addWidget(self.bnc_channel2_button)

        # Controls layout (minimal spinboxes + auto button)
        controls_layout = QHBoxLayout()
        
        # Minimal spinboxes
        self.bnc_spinbox_min = QDoubleSpinBox()
        self.bnc_spinbox_min.setRange(0.0, 100.0)
        self.bnc_spinbox_min.setSingleStep(0.5)
        self.bnc_spinbox_min.setValue(0.5)
        self.bnc_spinbox_min.setMaximumWidth(80)  # Minimal width
        self.bnc_spinbox_min.setToolTip("Lower percentile cutoff")
        self.bnc_spinbox_min.valueChanged.connect(self._on_bnc_percentile_changed)

        self.bnc_spinbox_max = QDoubleSpinBox()
        self.bnc_spinbox_max.setRange(0.0, 100.0)
        self.bnc_spinbox_max.setSingleStep(0.5)
        self.bnc_spinbox_max.setValue(99.5)
        self.bnc_spinbox_max.setMaximumWidth(80)  # Minimal width
        self.bnc_spinbox_max.setToolTip("Upper percentile cutoff")
        self.bnc_spinbox_max.valueChanged.connect(self._on_bnc_percentile_changed)

        # Reset and Normalize buttons
        buttons_layout = QHBoxLayout()
        
        self.bnc_reset_button = QPushButton("Reset")
        self.bnc_reset_button.setMaximumWidth(80)
        self.bnc_reset_button.setToolTip("Reset to default range (0-100)")
        self.bnc_reset_button.clicked.connect(self._on_bnc_reset)
        
        buttons_layout.addWidget(self.bnc_reset_button)
        buttons_layout.addStretch()

        bnc_labels.addWidget(QLabel("Min (pth):"))
        bnc_labels.addWidget(QLabel("Max (pth):"))

        controls_layout.addWidget(self.bnc_spinbox_min)
        controls_layout.addWidget(self.bnc_spinbox_max)
        controls_layout.addStretch()  # Push everything to the left

        bnc_layout.addLayout(channel_buttons_layout)
        bnc_layout.addLayout(bnc_labels)
        bnc_layout.addLayout(controls_layout)
        bnc_layout.addLayout(buttons_layout)
        self.bnc_group.setLayout(bnc_layout)

        # Track which channel is currently selected for BnC
        self._bnc_active_channel = 1

        midl_vbox.addWidget(self.file_type_button)
        midl_vbox.addWidget(self.channel_button)
        midl_vbox.addWidget(self.stimulation_area_button)
        midl_vbox.addWidget(self.composite_button)
        midl_vbox.addWidget(self.view_metadata_button)

        midr_vbox.addWidget(zproj_group)
        midr_vbox.addWidget(self.bnc_group)
        

        midl_vbox.addStretch(0.5)
        midr_vbox.addStretch(0.5)
        
        midl_vbox.addWidget(self.save_img)
        midl_vbox.addWidget(self.scale_bar_checkbox)

        # --- Display panel: reg_tif image display and slider ---
        display_panel = QVBoxLayout()
        
        # Create the image view widget that encapsulates reg_tif_label
        self.image_view = ImageViewWidget()
        self.reg_tif_label = self.image_view.get_label()  # Maintain backward compatibility
        
        # Connect image update signal
        self.image_view.imageUpdated.connect(self._on_image_updated)
        
        display_panel.addWidget(self.image_view, 1)  # Give stretch factor of 1 to make it greedy

        # --- ROI Tool Integration ---
        self.roi_tool = CircleRoiTool(self.reg_tif_label)
        self.roi_tool.roiFinalized.connect(self._on_roi_finalized)
        self.roi_tool.roiSelected.connect(self._on_roi_selected_by_click)
        self.roi_tool.roiDrawingStarted.connect(self._on_roi_drawing_started)
        print("DEBUG: ROI tool signals connected")

        self.tif_slider = QSlider(Qt.Orientation.Horizontal)
        self.tif_slider.setMinimum(0)
        self.tif_slider.setMaximum(0)
        self.tif_slider.setValue(0)
        self.tif_slider.setEnabled(True)
        self.tif_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # Changed to Fixed vertical policy
        self.tif_slider.setMaximumHeight(25)
        self.tif_slider.valueChanged.connect(self.update_tif_frame)
        display_panel.addWidget(self.tif_slider, 0)  # Keep stretch factor 0 to minimize space

        # Connect selection change to widget-local handlers
        self.analysis_list_widget.currentItemChanged.connect(self._on_item_changed_with_roi_preservation)

        # --- Bottom panel: Plot the signal of a given area ---
        bottom_panel = QHBoxLayout()
        bottom_panel.addStretch(0)

        # Create the trace plot widget
        self.trace_plot_widget = TraceplotWidget()
        self.trace_plot_widget.set_main_window(self.window)
        bottom_panel.addWidget(self.trace_plot_widget, 1)

        # Get widgets for backward compatibility
        trace_widgets = self.trace_plot_widget.get_widgets_for_compatibility()
        self.ylim_min_edit = trace_widgets['ylim_min_edit']
        self.ylim_max_edit = trace_widgets['ylim_max_edit']
        self.reset_ylim_button = trace_widgets['reset_ylim_button']
        self.formula_dropdown = trace_widgets['formula_dropdown']
        self.time_display_button = trace_widgets['time_display_button']
        self.trace_fig = trace_widgets['trace_fig']
        self.trace_ax = trace_widgets['trace_ax']
        self.trace_canvas = trace_widgets['trace_canvas']
        
        # Maintain internal compatibility for display mode tracking
        self._show_time_in_seconds = False

        # --- Create ROI List Component ---
        self.roi_list_component = RoiListWidget(self.window)
        
        # Connect ROI component signals
        self.roi_list_component.roiSelected.connect(self._on_roi_component_selected)
        self.roi_list_component.roiAdded.connect(self._on_roi_component_added)
        
        # Expose the internal list widget for backward compatibility
        self.roi_list_widget = self.roi_list_component.get_list_widget()

        # --- Assemble layouts ---
        main_hbox.addLayout(left_vbox, 1) 
        main_hbox.addLayout(midl_vbox, 0)
        main_hbox.addLayout(display_panel, 2)
        main_hbox.addLayout(midr_vbox, 0)
        main_hbox.addWidget(self.roi_list_component, 0)


        main_vbox.addLayout(main_hbox)
        main_vbox.setStretch(0, 75)
        main_vbox.addLayout(bottom_panel) 
        main_vbox.setStretch(1, 25)
        widget.setLayout(main_vbox)

        # Store loaded tiff data placeholders on window for compatibility
        self.window._current_tif = None
        self.window._current_tif_chan2 = None
        self._active_channel = 1
        self.channel_button.setText("Show Channel 2")

        # Expose key widgets on the main window for backward compatibility
        try:
            self.window.analysis_list_widget = self.analysis_list_widget
            self.window.channel_button = self.channel_button
            self.window.file_type_button = self.file_type_button
            self.window.cnb_button = self.cnb_button
            self.window.composite_button = self.composite_button
            self.window.zproj_std_button = self.zproj_std_button
            self.window.zproj_max_button = self.zproj_max_button
            self.window.zproj_mean_button = self.zproj_mean_button
            self.window.view_metadata_button = self.view_metadata_button
            self.window.reg_tif_label = self.reg_tif_label
            self.window.image_view = self.image_view  # Expose the new image view widget
            self.window.roi_tool = self.roi_tool
            self.window.tif_slider = self.tif_slider
            self.window.ylim_min_edit = self.ylim_min_edit
            self.window.ylim_max_edit = self.ylim_max_edit
            self.window.reset_ylim_button = self.reset_ylim_button
            self.window.formula_dropdown = self.formula_dropdown
            self.window.time_display_button = self.time_display_button
            self.window.trace_fig = self.trace_fig
            self.window.trace_ax = self.trace_ax
            self.window.trace_canvas = self.trace_canvas
            self.window.trace_plot_widget = self.trace_plot_widget  # Expose the new trace plot widget
            self.window.roi_list_widget = self.roi_list_widget
            # Expose moved analysis methods for backward compatibility
            self.window.display_reg_tif_image = self.display_reg_tif_image
            self.window.update_tif_frame = self.update_tif_frame
        except Exception:
            pass

        # Allow MainWindow to refresh the list on tab change
        try:
            self.window.analysis_list_widget.currentItemChanged.connect(self._on_item_changed_with_roi_preservation)
        except Exception:
            pass

    def _on_item_changed_with_roi_preservation(self, current, previous=None):
        """Handle item changes while preserving ROI information across selections."""
        # Store current ROI and rotation if they exist
        stored_roi = getattr(self.window, '_last_roi_xyxy', None)
        stored_rotation = getattr(self.roi_tool, '_rotation_angle', 0.0) if hasattr(self, 'roi_tool') else 0.0
        
        # Store rotation angle persistently
        if hasattr(self, 'roi_tool'):
            self.window._last_roi_rotation = stored_rotation
        
        # Load the new image/data
        self.display_reg_tif_image(current, previous)
        
        # If we had an ROI and the new image loaded successfully, restore and update trace
        if stored_roi is not None and getattr(self.window, '_current_tif', None) is not None:
            # Validate ROI coordinates against new image dimensions
            if hasattr(self.window, '_last_img_wh'):
                img_w, img_h = self.window._last_img_wh
                x0, y0, x1, y1 = stored_roi
                
                # Ensure ROI coordinates are within image bounds
                if (x1 <= img_w and y1 <= img_h and x0 >= 0 and y0 >= 0 and x1 > x0 and y1 > y0):
                    # Restore the ROI coordinates
                    self.window._last_roi_xyxy = stored_roi
                    
                    # Show the ROI overlay on the new image with preserved rotation
                    try:
                        # Use stored rotation if available, otherwise use the currently stored rotation
                        rotation_to_use = getattr(self.window, '_last_roi_rotation', stored_rotation)
                        self.roi_tool.show_bbox_image_coords(stored_roi, rotation_to_use)
                    except Exception:
                        pass
                    
                    # Update the trace with the restored ROI
                    try:
                        self._update_trace_from_roi()
                    except Exception:
                        # Fallback to just showing the vline
                        self._update_trace_vline()
                else:
                    # ROI is out of bounds for this image, clear it
                    self.window._last_roi_xyxy = None

    def _on_bnc_channel_selected(self, channel):
        """Handle BnC channel selection (mutually exclusive buttons)."""
        self._bnc_active_channel = channel
        
        # Ensure only one button is checked at a time
        if channel == 1:
            self.bnc_channel1_button.setChecked(True)
            self.bnc_channel2_button.setChecked(False)
            # Load Channel 1 percentiles
            self.bnc_spinbox_min.setValue(self._ch1_percentile_min)
            self.bnc_spinbox_max.setValue(self._ch1_percentile_max)
        else:
            self.bnc_channel1_button.setChecked(False)
            self.bnc_channel2_button.setChecked(True)
            # Load Channel 2 percentiles
            self.bnc_spinbox_min.setValue(self._ch2_percentile_min)
            self.bnc_spinbox_max.setValue(self._ch2_percentile_max)
        
        # Update the image display
        if getattr(self.window, '_current_tif', None) is not None:
            self.update_tif_frame()

    def _on_bnc_percentile_changed(self):
        """Handle changes to the BnC percentile spinboxes and update the image."""
        # Only update if we have image data loaded
        if getattr(self.window, '_current_tif', None) is not None:
            # Get current values
            min_val = self.bnc_spinbox_min.value()
            max_val = self.bnc_spinbox_max.value()
            
            # Ensure min < max
            if min_val >= max_val:
                self.bnc_spinbox_max.setValue(min_val + 0.1)
                max_val = min_val + 0.1
            
            # Store values for the active channel
            if self._bnc_active_channel == 1:
                self._ch1_percentile_min = min_val
                self._ch1_percentile_max = max_val
            else:
                self._ch2_percentile_min = min_val
                self._ch2_percentile_max = max_val
            
            # Update the current frame display
            self.update_tif_frame()

    def _on_bnc_reset(self):
        """Reset BnC values to default range (0-99.65)."""
        self.bnc_spinbox_min.setValue(1.0)
        self.bnc_spinbox_max.setValue(99.5)
        
    def _on_percentile_changed(self):
        """Handle changes to the percentile spinboxes and update the image."""
        # Only update if we have image data loaded
        if getattr(self.window, '_current_tif', None) is not None:
            # Validate that min < max for each channel
            ch1_min = self.channel_1_spinbox_min.value()
            ch1_max = self.channel_1_spinbox_max.value()
            ch2_min = self.channel_2_spinbox_min.value()
            ch2_max = self.channel_2_spinbox_max.value()
            
            # Ensure min < max for channel 1
            if ch1_min >= ch1_max:
                self.channel_1_spinbox_max.setValue(ch1_min + 0.1)
                ch1_max = ch1_min + 0.1
            
            # Ensure min < max for channel 2
            if ch2_min >= ch2_max:
                self.channel_2_spinbox_max.setValue(ch2_min + 0.1)
                ch2_max = ch2_min + 0.1
            
            # Store values persistently
            self._ch1_percentile_min = ch1_min
            self._ch1_percentile_max = ch1_max
            self._ch2_percentile_min = ch2_min
            self._ch2_percentile_max = ch2_max
            
            # Update the current frame display
            self.update_tif_frame()

    def _on_zproj_toggled(self, mode, checked):
        """Handle toggling of the z-projection buttons so only one projection
        mode is active at a time. mode is one of 'std', 'max', 'mean'.
        """
        # Prevent recursion while we change other buttons
        try:
            # Turn off other modes
            if mode != 'std' and getattr(self, 'zproj_std_button', None) is not None:
                self.zproj_std_button.blockSignals(True)
                self.zproj_std_button.setChecked(False)
                self.zproj_std_button.blockSignals(False)
                self._zproj_std = False

            if mode != 'max' and getattr(self, 'zproj_max_button', None) is not None:
                self.zproj_max_button.blockSignals(True)
                self.zproj_max_button.setChecked(False)
                self.zproj_max_button.blockSignals(False)
                self._zproj_max = False

            if mode != 'mean' and getattr(self, 'zproj_mean_button', None) is not None:
                self.zproj_mean_button.blockSignals(True)
                self.zproj_mean_button.setChecked(False)
                self.zproj_mean_button.blockSignals(False)
                self._zproj_mean = False

            # Set the requested mode flag based on the 'checked' state
            if mode == 'std':
                self._zproj_std = bool(checked)
            elif mode == 'max':
                self._zproj_max = bool(checked)
            elif mode == 'mean':
                self._zproj_mean = bool(checked)

            # If the user turned on one mode, ensure others are off at the flag level
            if self._zproj_std:
                self._zproj_max = False
                self._zproj_mean = False
            if self._zproj_max:
                self._zproj_std = False
                self._zproj_mean = False
            if self._zproj_mean:
                self._zproj_std = False
                self._zproj_max = False

            # Refresh view
            try:
                self.update_tif_frame()
            except Exception:
                pass
            
            # Enable/disable BnC controls based on Z projection state
            self._update_bnc_controls_for_zproj()
        except Exception:
            pass

    def _update_bnc_controls_for_zproj(self):
        """Enable/disable BnC controls based on Z projection state."""
        # Check if any Z projection is active
        z_projection_active = (getattr(self, '_zproj_std', False) or 
                              getattr(self, '_zproj_max', False) or 
                              getattr(self, '_zproj_mean', False))
        
        # Enable/disable BnC controls - they should be disabled when Z projections are active
        controls_enabled = not z_projection_active and getattr(self.window, '_current_tif', None) is not None
        
        try:
            # Toggle enabled state for controls
            self.bnc_channel1_button.setEnabled(controls_enabled)
            # Only enable channel 2 if it exists and Z projections are not active
            has_channel2 = getattr(self.window, '_current_tif_chan2', None) is not None
            self.bnc_channel2_button.setEnabled(controls_enabled and has_channel2)
            self.bnc_spinbox_min.setEnabled(controls_enabled)
            self.bnc_spinbox_max.setEnabled(controls_enabled)
            self.bnc_reset_button.setEnabled(controls_enabled)

            # Also update the main BnC QPushButton (dialog launcher) to reflect disabled state
            self.cnb_button.setEnabled(controls_enabled)

            # If the bnc_group exists, set a dynamic property so stylesheet can grey it out
            try:
                bnc_group = getattr(self, 'bnc_group', None)
                # Fallback to searching by objectName on the widget tree
                if bnc_group is None:
                    # The local variable was set during init; try to find it via findChild
                    bnc_group = self.findChild(QGroupBox, 'bnc_group')
                if bnc_group is not None:
                    bnc_group.setProperty('zprojActive', z_projection_active)
                    # disable child widgets for visual clarity as well
                    for child in bnc_group.findChildren((QPushButton, QDoubleSpinBox)):
                        child.setEnabled(controls_enabled and (not z_projection_active))
                    # Refresh style
                    bnc_group.style().unpolish(bnc_group)
                    bnc_group.style().polish(bnc_group)
            except Exception:
                pass

            if z_projection_active:
                print("DEBUG: Z projection active - BnC controls disabled")
            else:
                print("DEBUG: No Z projection - BnC controls enabled")
        except Exception as e:
            print(f"DEBUG: Error updating BnC controls: {e}")

    def display_reg_tif_image(self, current, previous=None):
        """Load registered tif(s) for the selected directory and initialize slider/view."""
        if not current:
            self._clear_experiment_state()
            return

        # Store previous image dimensions before loading new image
        previous_img_wh = getattr(self.window, '_last_img_wh', None)

        # Get the full path from UserRole, fallback to text for compatibility
        reg_dir = current.data(Qt.ItemDataRole.UserRole)
        if reg_dir is None:
            reg_dir = current.text()

        # Load experiment data using ImageViewWidget
        data = self.image_view.load_experiment_data(reg_dir, getattr(self, '_using_registered', True))
        
        if not data['success']:
            error_msg = data['error'] or "Unknown error loading experiment data"
            self.image_view.set_error_message(f"Error loading {reg_dir}: {error_msg}")
            self._clear_experiment_state()
            return

        # Store loaded data on window for compatibility
        self.window._current_tif = data['tif']
        self.window._current_tif_chan2 = data['tif_chan2']
        self.window._exp_data = data['metadata']

        # Update metadata viewer if it's open
        self._update_metadata_viewer_if_open(reg_dir)

        # Update UI state based on loaded data
        self._update_ui_from_experiment_data(data, previous_img_wh)
        
        # Display the first frame
        self.update_tif_frame()

        self.save_img.setEnabled(True)

    def _clear_experiment_state(self):
        """Clear all experiment-related state."""
        self.image_view.clear_experiment()
        self.tif_slider.setEnabled(False)
        self.tif_slider.setMaximum(0)
        self.window._current_tif = None
        self.window._current_tif_chan2 = None
        self.window._exp_data = None
        self.file_type_button.setEnabled(False)
        self.channel_button.setEnabled(False)
        self.composite_button.setEnabled(False)
        self.stimulation_area_button.setEnabled(False)
        self.cnb_button.setEnabled(False)
        self.zproj_std_button.setEnabled(False)
        self.zproj_max_button.setEnabled(False)
        self.zproj_mean_button.setEnabled(False)
        self.view_metadata_button.setEnabled(False)
        self.scale_bar_checkbox.setEnabled(False)
        self.save_img.setEnabled(False)
        
        # Disable BnC controls when no data is loaded
        self.bnc_channel1_button.setEnabled(False)
        self.bnc_channel2_button.setEnabled(False)
        self.bnc_spinbox_min.setEnabled(False)
        self.bnc_spinbox_max.setEnabled(False)
        self.bnc_reset_button.setEnabled(False)

    def _update_ui_from_experiment_data(self, data, previous_img_wh):
        """Update UI state based on loaded experiment data."""
        nframes = data['nframes']
        has_registered_tif = data['has_registered_tif']
        has_raw_numpy = data['has_raw_numpy']
        tif = data['tif']
        tif_chan2 = data['tif_chan2']
        
        print(f"DEBUG: Detected {nframes} frames from tif.shape: {tif.shape}")
        print(f"DEBUG: tif.ndim = {tif.ndim}")
        
        # Configure slider
        self.tif_slider.setEnabled(nframes > 1)
        self.tif_slider.setMaximum(nframes - 1)
        self.tif_slider.setValue(0)
        
        print(f"DEBUG: Slider configured - max: {nframes-1}, enabled: {nframes > 1}")
        
        # Enable file type toggle if both file types are available
        self.file_type_button.setEnabled(has_registered_tif and has_raw_numpy)
        
        # Update file type button text
        try:
            use_registered = getattr(self, '_using_registered', True)
            if use_registered:
                self.file_type_button.setText("Show Raw" if has_raw_numpy else "Show Raw (N/A)")
            else:
                self.file_type_button.setText("Show Registered" if has_registered_tif else "Show Registered (N/A)")
        except Exception:
            pass

        # Configure channel and composite buttons
        has_channel2 = tif_chan2 is not None
        if has_channel2:
            self.channel_button.setEnabled(False)
            self.composite_button.setEnabled(True)
            # Ensure composite mode is active for dual-channel data by default
            if not self.composite_button.isChecked():
                self.composite_button.setChecked(True)
            print(f"DEBUG: Dual-channel data detected, composite enabled and checked: {self.composite_button.isChecked()}")
        else:
            self.channel_button.setEnabled(False)
            self.composite_button.setEnabled(False)
            print("DEBUG: Single-channel data, composite disabled")
            
        # Enable z-projection buttons when an image is loaded
        self.zproj_std_button.setEnabled(True)
        self.zproj_max_button.setEnabled(True)
        self.zproj_mean_button.setEnabled(True)
            
        # Enable contrast & brightness when an image is loaded
        self.cnb_button.setEnabled(True)
        
        # Enable BnC controls when an image is loaded
        self.bnc_channel1_button.setEnabled(True)
        self.bnc_spinbox_min.setEnabled(True)
        self.bnc_spinbox_max.setEnabled(True)
        self.bnc_reset_button.setEnabled(True)
        
        # Enable/disable Channel 2 button based on availability
        if has_channel2:
            self.bnc_channel2_button.setEnabled(True)
        else:
            self.bnc_channel2_button.setEnabled(False)
            # Ensure Channel 1 is selected if Channel 2 becomes unavailable
            if self._bnc_active_channel == 2:
                self._on_bnc_channel_selected(1)
        
        # Update BnC controls based on current Z projection state
        self._update_bnc_controls_for_zproj()
            
        # Enable stimulus ROI button if experiment data contains stimulus locations
        self._configure_stimulus_button(data['metadata'])
        
        # Enable metadata viewer button when experiment data is loaded
        self.view_metadata_button.setEnabled(True)
        
        # Enable scale bar checkbox when experiment data is loaded
        self.scale_bar_checkbox.setEnabled(True)
        
        # Restore BnC values for the currently selected channel
        if self._bnc_active_channel == 1:
            self.bnc_spinbox_min.setValue(self._ch1_percentile_min)
            self.bnc_spinbox_max.setValue(self._ch1_percentile_max)
        else:
            self.bnc_spinbox_min.setValue(self._ch2_percentile_min)
            self.bnc_spinbox_max.setValue(self._ch2_percentile_max)
        
        # Check if image dimensions changed and resize if needed
        self._check_and_resize_for_image_change(tif, previous_img_wh)
            
        # Update trace if there's an active ROI to reflect new data
        try:
            if getattr(self.window, '_last_roi_xyxy', None) is not None:
                self._update_trace_from_roi()
        except Exception:
            pass

    def _on_image_updated(self):
        """Handle when the ImageViewWidget emits imageUpdated signal.
        
        This method is called whenever a new image is displayed in the ImageViewWidget.
        It updates any image-dependent components like the ROI tool.
        """
        try:
            # Get the current pixmap from the image view
            current_pixmap = self.reg_tif_label.pixmap()
            if current_pixmap is not None and hasattr(self, 'roi_tool'):
                # Update the ROI tool with the new pixmap
                from PyQt6.QtCore import QRect
                self.roi_tool.set_pixmap(current_pixmap)
                self.roi_tool.set_draw_rect(QRect(0, 0, current_pixmap.width(), current_pixmap.height()))
                
                # Update image size if we have the window's image dimensions
                if hasattr(self.window, '_last_img_wh') and self.window._last_img_wh:
                    self.roi_tool.set_image_size(self.window._last_img_wh[0], self.window._last_img_wh[1])
                
                # Update saved ROIs so they display persistently
                if hasattr(self.window, '_saved_rois'):
                    self.roi_tool.set_saved_rois(self.window._saved_rois)
                
                # Update stimulus ROIs if they should be shown
                try:
                    if hasattr(self, 'stimulation_area_button') and self.stimulation_area_button.isChecked():
                        self.toggle_stim_rois()
                except Exception:
                    pass
        except Exception as e:
            print(f"DEBUG: Error in _on_image_updated: {e}")

    def _configure_stimulus_button(self, metadata):
        """Configure the stimulus ROI button based on experiment metadata."""
        try:
            has_stim_data = False
            if metadata:
                # Check for stimulus data in various formats
                if hasattr(metadata, 'stimulated_roi_location'):
                    stim_data = getattr(metadata, 'stimulated_roi_location', None)
                    has_stim_data = stim_data is not None and len(stim_data) > 0
                elif isinstance(metadata, dict) and 'stimulated_roi_location' in metadata:
                    stim_data = metadata['stimulated_roi_location']
                    has_stim_data = stim_data is not None and len(stim_data) > 0
                
                print(f"DEBUG: Stimulus data detected: {has_stim_data}")
                if metadata and hasattr(metadata, '__dict__'):
                    print(f"DEBUG: Experiment data attributes: {[attr for attr in dir(metadata) if not attr.startswith('_')]}")
                    
            self.stimulation_area_button.setEnabled(has_stim_data)
            # Ensure the button remains checkable when enabled
            if has_stim_data:
                self.stimulation_area_button.setCheckable(True)
        except Exception as e:
            print(f"DEBUG: Exception in stimulus detection: {e}")
            self.stimulation_area_button.setEnabled(False)

    def update_tif_frame(self, *args):
        """Render the current tif frame (or z-projection) into the label and update ROI tool."""
        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QImage, QPixmap
        import numpy as np
        import matplotlib
        from tools import misc

        # frame_idx uses widget slider
        frame_idx = int(self.tif_slider.value())

        if getattr(self.window, '_current_tif', None) is None:
            return

        tif = self.window._current_tif
        tif_chan2 = getattr(self.window, "_current_tif_chan2", None)

        # Handle z-projections
        if getattr(self, '_zproj_std', False) and tif.ndim >= 3:
            self.zproj_mean_button.setChecked(False)
            self.zproj_max_button.setChecked(False)
            # Ensure only std flag is active
            self._zproj_max = False
            self._zproj_mean = False

            img = np.std(tif, axis=0)
            if tif_chan2 is not None:
                img_chan2 = np.std(tif_chan2, axis=0)
            else:
                img_chan2 = None
            self.tif_slider.setEnabled(False)
        elif getattr(self, '_zproj_max', False) and tif.ndim >= 3:
            self.zproj_std_button.setChecked(False)
            self.zproj_mean_button.setChecked(False)
            self._zproj_std = False
            self._zproj_mean = False

            img = np.max(tif, axis=0)
            if tif_chan2 is not None:
                img_chan2 = np.max(tif_chan2, axis=0)
            else:
                img_chan2 = None
            self.tif_slider.setEnabled(False)
        elif getattr(self, '_zproj_mean', False) and tif.ndim >= 3:
            self.zproj_std_button.setChecked(False)
            self.zproj_max_button.setChecked(False)
            self._zproj_std = False
            self._zproj_max = False

            img = np.mean(tif, axis=0)
            if tif_chan2 is not None:
                img_chan2 = np.mean(tif_chan2, axis=0)
            else:
                img_chan2 = None
            self.tif_slider.setEnabled(False)
        else:
            if tif.ndim >= 3:
                frame_idx = max(0, min(frame_idx, tif.shape[0]-1))
                img = tif[frame_idx]
                
                # Handle channel 2 with proper bounds checking
                if tif_chan2 is not None and tif_chan2.ndim >= 3:
                    # Check if frame exists in channel 2
                    if frame_idx < tif_chan2.shape[0]:
                        img_chan2 = tif_chan2[frame_idx]
                    else:
                        # Use last available frame in channel 2
                        print(f"Warning: Channel 2 only has {tif_chan2.shape[0]} frames, using frame {tif_chan2.shape[0]-1} instead of {frame_idx}")
                        img_chan2 = tif_chan2[tif_chan2.shape[0]-1]
                else:
                    img_chan2 = tif_chan2
                    
                self.tif_slider.setEnabled(True)
            else:
                img = tif
                img_chan2 = tif_chan2

        # Coerce to 2-D
        img = misc.to_2d(img)
        img_chan2 = misc.to_2d(img_chan2)

        # Safety check
        if img is None or img.size == 0:
            self.image_view.set_error_message(f"Error: Frame {frame_idx} is empty or corrupted.")
            return

        # Normalize base channel (green) using robust percentile clipping
        g = img.astype(np.float32)

        # Check if any Z projection is active
        z_projection_active = (getattr(self, '_zproj_std', False) or 
                              getattr(self, '_zproj_max', False) or 
                              getattr(self, '_zproj_mean', False))

        if z_projection_active:
            # For Z projections, use raw values without percentile clipping
            print("DEBUG: Z projection active - using raw values without thresholding")
            g_view = g / float(g.max()) if g.max() > 0 else g  # Simple normalization to [0,1]
        else:
            # Use BnC spinbox values for percentile clipping
            if self._bnc_active_channel == 1:
                g_low_percentile = self.bnc_spinbox_min.value()
                g_high_percentile = self.bnc_spinbox_max.value()
            else:
                g_low_percentile = self._ch1_percentile_min
                g_high_percentile = self._ch1_percentile_max
            
            g_low = np.percentile(g, g_low_percentile)
            g_high = np.percentile(g, g_high_percentile)
            # Ensure sensible ordering
            if g_high <= g_low:
                g_high = float(g.max())

            g_clipped = np.clip(g, g_low, g_high)

            # Always normalize the clipped data to [0,1] (default behavior)
            g_min_view = float(np.min(g_clipped))
            g_ptp_view = float(np.ptp(g_clipped))
            g_view = (g_clipped - g_min_view) / (g_ptp_view if g_ptp_view > 0 else 1.0)

        if img_chan2 is not None and self.composite_button.isChecked():
            print("DEBUG: Applying composite mode")
            self.zproj_std_button.setEnabled(True)
            self.zproj_max_button.setEnabled(True)
            self.zproj_mean_button.setEnabled(True)

            r = img_chan2.astype(np.float32)
            
            if z_projection_active:
                # For Z projections in composite mode, use raw values without percentile clipping
                print("DEBUG: Z projection active - using raw values for composite channels")
                r_view = r / float(r.max()) if r.max() > 0 else r  # Simple normalization to [0,1]
                # Also use raw values for green channel in composite mode
                g_view = g / float(g.max()) if g.max() > 0 else g
            else:
                # Use BnC spinbox values for percentile clipping for red channel
                if self._bnc_active_channel == 2:
                    r_low_percentile = self.bnc_spinbox_min.value()
                    r_high_percentile = self.bnc_spinbox_max.value()
                else:
                    r_low_percentile = self._ch2_percentile_min
                    r_high_percentile = self._ch2_percentile_max
                
                r_low = np.percentile(r, r_low_percentile)
                r_high = np.percentile(r, r_high_percentile)
                if r_high <= r_low:
                    r_high = float(r.max())
                
                # Apply user-specified percentile clipping for red channel
                r_clipped = np.clip(r, r_low, r_high)
                
                # Always normalize the clipped data to [0,1] (default behavior)
                r_min_view = float(np.min(r_clipped))
                r_ptp_view = float(np.ptp(r_clipped))
                r_view = (r_clipped - r_min_view) / (r_ptp_view if r_ptp_view > 0 else 1.0)

                # Set any values above the user-specified high percentile to maximum intensity (1.0)
                r_threshold = np.percentile(r_view, r_high_percentile)
                print(f"DEBUG: Red channel - {r_high_percentile}%ile threshold: {r_threshold:.4f}")
                r_view = np.where(r_view > r_threshold, 1.0, r_view)
                
                # Apply the same logic to green channel
                g_threshold = np.percentile(g_view, g_high_percentile)
                print(f"DEBUG: Green channel - {g_high_percentile}%ile threshold: {g_threshold:.4f}")
                g_view = np.where(g_view > g_threshold, 1.0, g_view)

            h, w = g.shape
            composite_rgba = np.zeros((h, w, 4), dtype=np.uint8)
            composite_rgba[..., 0] = (r_view * 255).astype(np.uint8)
            composite_rgba[..., 1] = (g_view * 255).astype(np.uint8)
            composite_rgba[..., 3] = 255
            arr_uint8 = composite_rgba
        else:
            active_ch = getattr(self, "_active_channel", 1)
            if img_chan2 is not None and active_ch == 2:
                r = img_chan2.astype(np.float32)
                
                # Apply contrast enhancement using BnC spinbox values
                if self._bnc_active_channel == 2:
                    r_low_percentile = self.bnc_spinbox_min.value()
                    r_high_percentile = self.bnc_spinbox_max.value()
                else:
                    r_low_percentile = self._ch2_percentile_min
                    r_high_percentile = self._ch2_percentile_max
                
                r_low = np.percentile(r, r_low_percentile)
                r_high = np.percentile(r, r_high_percentile)
                if r_high <= r_low:
                    r_high = float(r.max())
                r_clipped = np.clip(r, r_low, r_high)
                
                # Always normalize the clipped data to [0,1] (default behavior)
                r_min_view = float(np.min(r_clipped))
                r_ptp_view = float(np.ptp(r_clipped))
                r_view = (r_clipped - r_min_view) / (r_ptp_view if r_ptp_view > 0 else 1.0)

                cmap = matplotlib.colormaps.get('gray')
                colored_arr = cmap(r_view)
                arr_uint8 = (colored_arr * 255).astype(np.uint8)
            else:
                cmap = matplotlib.colormaps.get('gray')
                colored_arr = cmap(g_view)
                arr_uint8 = (colored_arr * 255).astype(np.uint8)

        # Display the image using the image view widget (preserves aspect ratio and sizing)
        bnc_settings = None
        if (hasattr(self.window, '_global_bnc_settings') and 
            self.window._global_bnc_settings.get('enabled', False)):
            bnc_settings = self.window._global_bnc_settings
        
        # Determine if composite mode is active and which channel is active
        composite_mode = self.composite_button.isChecked() if hasattr(self, 'composite_button') else False
        active_channel = getattr(self, "_active_channel", 1)
        
        base_pix = self.image_view.display_image_with_bnc(
            arr_uint8, 
            bnc_settings, 
            img=img, 
            img_chan2=img_chan2, 
            composite_mode=composite_mode, 
            active_channel=active_channel,
            show_scale_bar=self.scale_bar_checkbox.isChecked(),
            metadata=getattr(self.window, '_exp_data', None)
        )
        
        # Store current image data for backward compatibility
        self.window._current_image_np = self.image_view.get_current_image_data()['numpy_array']
        self.window._current_qimage = self.image_view.get_current_image_data()['qimage']

        # --- Update ROI Tool with new image view ---
        if hasattr(self.window, '_last_img_wh'):
            self.roi_tool.set_pixmap(base_pix)
            self.roi_tool.set_draw_rect(QRect(0, 0, base_pix.width(), base_pix.height()))
            self.roi_tool.set_image_size(self.window._last_img_wh[0], self.window._last_img_wh[1])

            # Update saved ROIs so they display persistently
            if hasattr(self.window, '_saved_rois'):
                self.roi_tool.set_saved_rois(self.window._saved_rois)

            # Use the central toggle handler to (show/hide) stimulus ROIs
            try:
                # toggle_stim_rois will read experiment data and respect the button state
                self.toggle_stim_rois()
            except Exception:
                pass

            if getattr(self.window, '_last_roi_xyxy', None) is not None:
                try:
                    # Preserve rotation angle when updating frame
                    stored_rotation = getattr(self.window, '_last_roi_rotation', 0.0)
                    current_rotation = getattr(self.roi_tool, '_rotation_angle', stored_rotation)
                    self.roi_tool.show_bbox_image_coords(self.window._last_roi_xyxy, current_rotation)
                except Exception:
                    pass
                self._update_trace_vline()

    def _on_roi_finalized(self, xyxy):
        """xyxy is (x0, y0, x1, y1) in IMAGE coordinates."""
        print(f"DEBUG: ROI finalized with xyxy={xyxy}")
        self.window._last_roi_xyxy = xyxy
        print(f"DEBUG: Set self.window._last_roi_xyxy = {xyxy}")
        # Only clear editing state when drawing a completely new ROI (not when modifying existing one)
        # The editing state should be preserved if we're modifying a saved ROI
        # Store rotation angle persistently
        current_rotation = getattr(self.roi_tool, '_rotation_angle', 0.0)
        self.window._last_roi_rotation = current_rotation
        print(f"DEBUG: Current rotation={current_rotation}")
        
        # Check if we have image data
        has_image = hasattr(self.window, '_current_tif') and self.window._current_tif is not None
        print(f"DEBUG: Has image data: {has_image}")
        if has_image:
            print(f"DEBUG: Image shape: {self.window._current_tif.shape}")
        
        # Ensure overlay is painted on the current pixmap immediately
        try:
            # Preserve the current rotation angle when finalizing ROI
            self.roi_tool.show_bbox_image_coords(xyxy, current_rotation)
        except Exception as e:
            print(f"DEBUG: Error showing bbox: {e}")
        # Full redraw: recompute trace and recreate the vline after plotting
        try:
            print("DEBUG: Calling _update_trace_from_roi")
            self._update_trace_from_roi()
            print("DEBUG: _update_trace_from_roi completed")
        except Exception as e:
            print(f"DEBUG: Error in _update_trace_from_roi: {e}")
            # As a last resort ensure vline exists
            self._update_trace_vline()

    def _on_roi_selected_by_click(self, roi_index):
        """Handle ROI selection by right-clicking on the image."""
        # Delegate to the ROI component
        if hasattr(self, 'roi_list_component'):
            self.roi_list_component.auto_select_roi_by_click(roi_index)

    def _on_roi_drawing_started(self):
        """Handle when user starts drawing a new ROI."""
        # Only clear editing state if we're not currently editing an existing ROI
        # Check if there's an active editing session
        current_editing_index = None
        if hasattr(self, 'roi_list_component'):
            current_editing_index = self.roi_list_component.get_editing_roi_index()
        
        if current_editing_index is not None:
            print("DEBUG: ROI drawing started but we're editing an existing ROI - preserving editing state")
            return
            
        # Clear editing state to ensure new ROI creation instead of updating existing ROI
        if hasattr(self, 'roi_list_component'):
            self.roi_list_component.clear_editing_state()
            # Also clear any selection in the ROI list widget
            roi_list_widget = self.roi_list_component.get_list_widget()
            if roi_list_widget:
                roi_list_widget.clearSelection()
            print("DEBUG: Cleared editing state and ROI selection when starting new ROI drawing")

    def toggle_file_type(self):
        """Toggle between registered TIFF files and raw numpy files."""
        # Flip the file type preference
        self._using_registered = not getattr(self, '_using_registered', True)
        
        # Update button text to show what you'll switch to next
        if self._using_registered:
            self.file_type_button.setText("Show Raw")
        else:
            self.file_type_button.setText("Show Registration")
        
        # Reload the current directory with the new file type preference
        current_item = self.analysis_list_widget.currentItem()
        if current_item:
            self.display_reg_tif_image(current_item)

    def toggle_stim_rois(self):
        """Show/hide the stimulus ROIs on the image."""
        if self.stimulation_area_button.isChecked():
            # Extract stimulus ROI data from experiment metadata
            stim_rois = self._get_stim_rois_from_experiment()
            if stim_rois:
                # Pass stimulus ROIs to the ROI tool for display
                if hasattr(self.roi_tool, 'set_stim_rois'):
                    self.roi_tool.set_stim_rois(stim_rois)
                    self.roi_tool._paint_overlay()
            else:
                # No stimulus data found, uncheck the button
                self.stimulation_area_button.setChecked(False)
        else:
            # Hide stimulus ROIs
            if hasattr(self.roi_tool, 'set_stim_rois'):
                self.roi_tool.set_stim_rois([])
                self.roi_tool._paint_overlay()

    def toggle_scale_bar(self):
        """Toggle the display of scale bar on the image."""
        # Update the current frame to show/hide scale bar
        self.update_tif_frame()

    def _toggle_text_visibility(self):
        """Toggle visibility of all text labels and overlays using H hotkey."""
        try:
            # Initialize text visibility state if it doesn't exist
            if not hasattr(self, '_text_visible'):
                self._text_visible = True
            
            # Toggle the state
            self._text_visible = not self._text_visible
            
            # Apply to ROI tool if it exists
            if hasattr(self, 'roi_tool') and self.roi_tool is not None:
                
                # Toggle mode text visibility
                if hasattr(self.roi_tool, 'set_show_mode_text'):
                    self.roi_tool.set_show_mode_text(self._text_visible)
                # Force redraw of overlay to apply changes
                if hasattr(self.roi_tool, '_paint_overlay'):
                    self.roi_tool._paint_overlay()
            
            # Print debug message
            state_msg = "visible" if self._text_visible else "hidden"
            print(f"DEBUG: Text/labels toggled to {state_msg}")
            
        except Exception as e:
            print(f"ERROR in _toggle_text_visibility: {e}")

    def _on_hide_rois_toggled(self, state):
        """Hide or show saved/stim ROIs when checkbox toggled."""
        show = False if state else True
        try:
            # hide saved ROIs and stimulus ROIs when checkbox is checked
            self.roi_tool.set_show_saved_rois(show)
            # also hide the interactive bbox if ROIs are hidden to reduce clutter
            self.roi_tool.set_show_current_bbox(show)
        except Exception:
            pass

    def _on_hide_labels_toggled(self, state):
        """Show or hide text labels within ROIs when checkbox toggled."""
        show = False if state else True
        try:
            # Toggle label visibility within ROIs
            self.roi_tool.set_show_labels(show)
        except Exception:
            pass

    def _get_stim_rois_from_experiment(self):
        """Extract stimulus ROI locations from experiment metadata.
        
        Only processes 'stimulated_roi_location' fields and deduplicates 
        overlapping ROIs by ROI ID. Returns a list of unique stimulus ROIs.
        """
        stim_rois = []
        roi_dict = {}  # Use dict to deduplicate by ROI ID
        
        # Check if we have experiment data
        exp_data = getattr(self.window, '_exp_data', None)
        if exp_data is None:
            return stim_rois
            
        # Handle different formats of stimulus data
        if isinstance(exp_data, dict):
            # Only process stimulated_roi_location
            if 'stimulated_roi_location' in exp_data:
                roi_locations = exp_data['stimulated_roi_location']
                
                # Handle the nested list structure
                if isinstance(roi_locations, list) and len(roi_locations) > 0:
                    # Process all stimulation events
                    for event_idx, event_data in enumerate(roi_locations):
                        if isinstance(event_data, list):
                            for roi_data in event_data:
                                self._process_roi_data(roi_data, roi_dict, event_idx)
            
        # Try pickle format (from experiment_summary.pkl)
        elif hasattr(exp_data, 'stimulated_roi_location'):
            # Handle pandas DataFrame or similar object - only process stimulated_roi_location
            roi_locations = getattr(exp_data, 'stimulated_roi_location', None)
            if roi_locations is not None:
                try:
                    # Check if it's a list directly
                    if isinstance(roi_locations, list) and len(roi_locations) > 0:
                        for event_idx, event_data in enumerate(roi_locations):
                            if isinstance(event_data, list):
                                for roi_data in event_data:
                                    self._process_roi_data(roi_data, roi_dict, event_idx)
                    
                    # Handle DataFrame format
                    elif hasattr(roi_locations, 'iloc') and len(roi_locations) > 0:
                        for event_idx, event_data in enumerate(roi_locations):
                            if hasattr(event_data, '__iter__'):
                                for roi_data in event_data:
                                    self._process_roi_data(roi_data, roi_dict, event_idx)
                except Exception as e:
                    print(f"DEBUG: Exception processing stimulated_roi_location: {e}")
        
        # Convert deduplicated dict back to list
        stim_rois = list(roi_dict.values())
        print(f"DEBUG: Returning {len(stim_rois)} unique stimulus ROIs")
        return stim_rois
    
    def _process_roi_data(self, roi_data, roi_dict, event_idx=None):
        """Process individual ROI data entry and add to roi_dict for deduplication."""
        try:
            if len(roi_data) >= 3:
                roi_id = roi_data[0]
                start_pos = roi_data[1]
                end_pos = roi_data[2]
                
                # Convert to xyxy format (x0, y0, x1, y1)
                x0, y0 = int(start_pos[0]), int(start_pos[1])
                x1, y1 = int(end_pos[0]), int(end_pos[1])
                
                # Create unique name with event info if available
                if event_idx is not None:
                    name = f'S{roi_id}E{event_idx}'
                else:
                    name = f'S{roi_id}'
                
                # Use roi_id as key for deduplication (same ID = same ROI)
                # If roi_id already exists, keep the first occurrence
                if roi_id not in roi_dict:
                    roi_dict[roi_id] = {
                        'id': roi_id,
                        'xyxy': (x0, y0, x1, y1),
                        'name': f'S{roi_id}'  # Simplified name for display
                    }
        except (IndexError, ValueError, TypeError) as e:
            print(f"DEBUG: Error processing ROI data {roi_data}: {e}")

    def toggle_channel(self):
        """Flip between showing Ch1 or Ch2 in non-composite view and update the button text."""
        # Nothing to do if there is no second channel loaded
        if getattr(self.window, "_current_tif_chan2", None) is None:
            return
        # Flip active channel
        self._active_channel = 2 if getattr(self, "_active_channel", 1) == 1 else 1
        # Button text shows what you'll switch to next
        try:
            self.channel_button.setText("Show Channel 1" if self._active_channel == 2 else "Show Channel 2")
        except Exception:
            pass
        # Refresh displayed frame
        try:
            self.update_tif_frame()
        except Exception:
            pass

    def _sync_channel_button_state(self):
        """Enable/disable the channel toggle depending on composite and availability of Ch2."""
        # Only allow toggling channels when a second channel exists and
        # the view is NOT in composite mode (composite shows both channels).
        has_ch2 = getattr(self.window, "_current_tif_chan2", None) is not None
        try:
            is_composite = bool(getattr(self, 'composite_button', None) and self.composite_button.isChecked())
        except Exception:
            is_composite = False
        self.channel_button.setEnabled(has_ch2 and not is_composite)
        # CNB button should be enabled when there's any image loaded
        has_img = getattr(self.window, '_current_tif', None) is not None
        self.cnb_button.setEnabled(has_img)

    def open_contrast_dialog(self):
        """Open enhanced brightness/contrast dialog with histogram display and per-channel controls."""
        print("DEBUG: BnC button clicked!")

        # Check if we have image data
        tif = getattr(self.window, '_current_tif', None)
        tif_chan2 = getattr(self.window, '_current_tif_chan2', None)
        
        print(f"DEBUG: tif is None: {tif is None}")
        if tif is not None:
            print(f"DEBUG: tif shape: {tif.shape}")
        
        if tif is None:
            print("DEBUG: No image data, returning")
            return

        # If already open, raise existing dialog
        if getattr(self.window, '_cnb_window', None) and self.window._cnb_window.isVisible():
            print("DEBUG: Dialog already open, raising")
            self.window._cnb_window.raise_()
            return

        try:
            # Get current frame data for histogram
            frame_idx = int(self.tif_slider.value()) if hasattr(self, 'tif_slider') else 0
            print(f"DEBUG: frame_idx: {frame_idx}")
            
            # Extract current frame data
            if tif.ndim >= 3:
                ch1_data = tif[frame_idx] if tif.ndim >= 3 else tif
                ch2_data = tif_chan2[frame_idx] if tif_chan2 is not None and tif_chan2.ndim >= 3 else tif_chan2
            else:
                ch1_data = tif
                ch2_data = tif_chan2
                
            print(f"DEBUG: ch1_data shape: {ch1_data.shape if ch1_data is not None else None}")
            print(f"DEBUG: ch2_data shape: {ch2_data.shape if ch2_data is not None else None}")
            
            # Import and create the BnC dialog
            print("DEBUG: Importing BnC dialog...")
            from components.bnc import BnCDialog, apply_bnc_to_image, create_qimage_from_array, create_composite_image
            print("DEBUG: Import successful")
            
            # Initialize global BnC settings if they don't exist
            if not hasattr(self.window, '_global_bnc_settings'):
                self.window._global_bnc_settings = {
                    'ch1': {'min': 0, 'max': 255, 'contrast': 1.0},
                    'ch2': {'min': 0, 'max': 255, 'contrast': 1.0},
                    'enabled': True
                }
                print("DEBUG: Initialized global BnC settings")
            
            # Create and setup dialog
            print("DEBUG: Creating BnC dialog...")
            dlg = BnCDialog(self)
            print("DEBUG: Dialog created")
            
            print("DEBUG: Setting image data...")
            dlg.set_image_data(ch1_data, ch2_data)
            
            # Load existing global settings into dialog
            dlg.set_settings(self.window._global_bnc_settings)
            print("DEBUG: Loaded existing settings into dialog")
            
            print("DEBUG: Image data set")
            
            # Connect settings changes to live preview and global storage
            print("DEBUG: Connecting signals...")
            dlg.settings_changed.connect(self._on_bnc_settings_changed)
            print("DEBUG: Signals connected")
            
            # Store reference and show
            print("DEBUG: Showing dialog...")
            self.window._cnb_window = dlg
            dlg.show()
            print("DEBUG: Dialog should be visible now")
            
        except Exception as e:
            print(f"DEBUG: Exception in open_contrast_dialog: {e}")
            import traceback
            traceback.print_exc()

    def _on_bnc_settings_changed(self, settings):
        """Handle BnC settings changes and update live preview."""
        try:
            # Store settings globally for persistence across frames/directories
            if not hasattr(self.window, '_global_bnc_settings'):
                self.window._global_bnc_settings = {
                    'ch1': {'min': 0, 'max': 255, 'contrast': 1.0},
                    'ch2': {'min': 0, 'max': 255, 'contrast': 1.0},
                    'enabled': True
                }
            
            channel_key = 'ch1' if settings['channel'] == 0 else 'ch2'
            self.window._global_bnc_settings[channel_key] = {
                'min': settings['min'],
                'max': settings['max'], 
                'contrast': settings['contrast']
            }
            self.window._global_bnc_settings['enabled'] = True
            
            print(f"DEBUG: Updated global BnC settings for {channel_key}: {self.window._global_bnc_settings[channel_key]}")
            
            # Apply live preview
            self._apply_bnc_live_preview()
        except Exception as e:
            print(f"DEBUG: Error in BnC settings changed: {e}")

    def _apply_bnc_live_preview(self):
        """Apply BnC settings to create live preview of the image."""
        from components.bnc import apply_bnc_to_image, create_qimage_from_array, create_composite_image
        from PyQt6.QtGui import QPixmap
        
        try:
            tif = getattr(self.window, '_current_tif', None)
            tif_chan2 = getattr(self.window, '_current_tif_chan2', None)
            
            if tif is None:
                return
                
            # Get current frame data
            frame_idx = int(self.tif_slider.value()) if hasattr(self, 'tif_slider') else 0
            
            if tif.ndim >= 3:
                ch1_data = tif[frame_idx]
                ch2_data = tif_chan2[frame_idx] if tif_chan2 is not None and tif_chan2.ndim >= 3 else tif_chan2
            else:
                ch1_data = tif
                ch2_data = tif_chan2
                
            # Get global BnC settings
            settings = getattr(self.window, '_global_bnc_settings', {
                'ch1': {'min': 0, 'max': 255, 'contrast': 1.0},
                'ch2': {'min': 0, 'max': 255, 'contrast': 1.0},
                'enabled': True
            })
            
            if not settings.get('enabled', True):
                return
            
            # Create preview image
            if ch2_data is not None and hasattr(self, 'composite_button') and self.composite_button.isChecked():
                # Composite mode
                preview_img = create_composite_image(ch1_data, ch2_data, settings['ch1'], settings['ch2'])
            else:
                # Single channel mode
                active_ch = getattr(self, "_active_channel", 1)
                if ch2_data is not None and active_ch == 2:
                    # Show channel 2
                    preview_img = apply_bnc_to_image(ch2_data, settings['ch2']['min'], settings['ch2']['max'], settings['ch2']['contrast'])
                    # Convert to RGBA grayscale
                    if preview_img.ndim == 2:
                        h, w = preview_img.shape
                        rgba = np.zeros((h, w, 4), dtype=np.uint8)
                        rgba[..., :3] = preview_img[..., None]
                        rgba[..., 3] = 255
                        preview_img = rgba
                else:
                    # Show channel 1
                    preview_img = apply_bnc_to_image(ch1_data, settings['ch1']['min'], settings['ch1']['max'], settings['ch1']['contrast'])
                    # Convert to RGBA grayscale
                    if preview_img.ndim == 2:
                        h, w = preview_img.shape
                        rgba = np.zeros((h, w, 4), dtype=np.uint8)
                        rgba[..., :3] = preview_img[..., None]
                        rgba[..., 3] = 255
                        preview_img = rgba
            
            # Convert to QImage and display
            if preview_img is not None:
                qimg = create_qimage_from_array(preview_img)
                pixmap = QPixmap.fromImage(qimg)
                scaled_pixmap = pixmap.scaled(
                    self.image_view.get_label_size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.reg_tif_label.setPixmap(scaled_pixmap)
                
        except Exception as e:
            print(f"DEBUG: Error applying BnC live preview: {e}")

    def _apply_cnb_adjustments(self):
        """Legacy method - redirects to new BnC live preview system."""
        # If the new BnC dialog system is active, use that
        if hasattr(self.window, '_global_bnc_settings') and self.window._global_bnc_settings.get('enabled', False):
            self._apply_bnc_live_preview()
            return

        # Fallback to old system if no new settings exist
        from PyQt6.QtGui import QPixmap
        
        if getattr(self.window, '_current_image_np', None) is None:
            return

        # Use basic contrast/brightness adjustment
        img = self.window._current_image_np
        contrast = float(getattr(self.window, '_cnb_contrast', 1.0))
        
        # Apply simple contrast adjustment
        if img.dtype == np.uint8:
            adjusted = img.astype(np.float32)
            adjusted = ((adjusted - 128) * contrast) + 128
            adjusted = np.clip(adjusted, 0, 255).astype(np.uint8)
        else:
            adjusted = img
            
        if adjusted.ndim == 2:
            h, w = adjusted.shape
            rgba = np.zeros((h, w, 4), dtype=np.uint8)
            rgba[..., :3] = adjusted[..., None]
            rgba[..., 3] = 255
            adjusted = rgba
        elif adjusted.ndim == 3 and adjusted.shape[2] == 3:
            h, w = adjusted.shape[:2]
            rgba = np.zeros((h, w, 4), dtype=np.uint8)
            rgba[..., :3] = adjusted
            rgba[..., 3] = 255
            adjusted = rgba

        try:
            from PyQt6.QtGui import QImage
            qimg = QImage(adjusted.data, adjusted.shape[1], adjusted.shape[0], adjusted.shape[1] * 4, QImage.Format.Format_RGBA8888)
            pix = QPixmap.fromImage(qimg)
            self.reg_tif_label.setPixmap(pix.scaled(self.image_view.get_label_size(), Qt.AspectRatioMode.KeepAspectRatio))
        except Exception as e:
            print(f"DEBUG: Error in legacy CNB adjustment: {e}")

    def open_metadata_viewer(self):
        """Open the metadata viewer dialog with current experiment data."""
        print("DEBUG: Metadata viewer button clicked!")
        
        # Check if we have experiment data
        exp_data = getattr(self.window, '_exp_data', None)
        if exp_data is None:
            print("DEBUG: No experiment data available")
            QMessageBox.information(self, "No Data", "No experiment metadata available. Please select a directory with experiment data.")
            return
        
        # Get current directory path for display
        current_item = self.analysis_list_widget.currentItem()
        directory_path = None
        if current_item:
            directory_path = current_item.data(Qt.ItemDataRole.UserRole)
            if directory_path is None:
                directory_path = current_item.text()
        
        # Create or update the metadata viewer
        if not hasattr(self.window, '_metadata_viewer') or self.window._metadata_viewer is None:
            print("DEBUG: Creating new metadata viewer")
            self.window._metadata_viewer = MetadataViewer(self)
        
        # Update with current data
        print(f"DEBUG: Setting metadata in viewer. Type: {type(exp_data)}")
        self.window._metadata_viewer.set_metadata(exp_data, directory_path)
        
        # Show the dialog
        if not self.window._metadata_viewer.isVisible():
            self.window._metadata_viewer.show()
        else:
            # Bring to front if already open
            self.window._metadata_viewer.raise_()
            self.window._metadata_viewer.activateWindow()
        
        print("DEBUG: Metadata viewer should be visible now")

    def _update_metadata_viewer_if_open(self, directory_path):
        """Update the metadata viewer with new data if it's currently open."""
        try:
            if (hasattr(self.window, '_metadata_viewer') and 
                self.window._metadata_viewer is not None and 
                self.window._metadata_viewer.isVisible()):
                
                print("DEBUG: Updating open metadata viewer with new data")
                exp_data = getattr(self.window, '_exp_data', None)
                self.window._metadata_viewer.set_metadata(exp_data, directory_path)
        except Exception as e:
            print(f"DEBUG: Error updating metadata viewer: {e}")

    def _update_trace_from_roi(self, index=None):
        """Update the trace plot based on current ROI selection - delegated to trace plot widget."""
        self.trace_plot_widget._update_trace_from_roi(index)
        
        # Sync the internal time display flag
        self._show_time_in_seconds = self.trace_plot_widget._show_time_in_seconds

    def _update_trace_vline(self):
        """Lightweight: update only the vertical frame line on the existing trace - delegated to trace plot widget."""
        self.trace_plot_widget._update_trace_vline()

    def _reset_ylim(self):
        """Clear any user-set y-limits and revert to autoscaling - delegated to trace plot widget."""
        self.trace_plot_widget._reset_ylim()
    
    def _toggle_time_display(self):
        """Toggle between showing frame numbers and time in seconds - delegated to trace plot widget."""
        self.trace_plot_widget._toggle_time_display()
        # Sync the internal flag
        self._show_time_in_seconds = self.trace_plot_widget._show_time_in_seconds

    def _save_current_view(self):
        """Save the current displayed image with ROIs as a PNG or JPG file."""
        try:
            # Get the current pixmap from the image label (this includes all overlays)
            current_pixmap = self.reg_tif_label.pixmap()
            if current_pixmap is None:
                QMessageBox.warning(self, "No Image", "No image is currently displayed to save.")
                return
            
            # Generate default filename with timestamp and directory info
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Get current directory name for filename
            current_item = self.analysis_list_widget.currentItem()
            dir_name = "image"
            if current_item:
                full_path = current_item.data(Qt.ItemDataRole.UserRole)
                if full_path:
                    dir_name = os.path.basename(full_path)
                else:
                    dir_name = current_item.text()
                # Clean up directory name for filename
                dir_name = "".join(c for c in dir_name if c.isalnum() or c in ('-', '_')).rstrip()
            
            # Get current frame info
            frame_idx = int(self.tif_slider.value()) if hasattr(self, 'tif_slider') else 0
            
            # Generate default filename (without extension)
            default_filename = f"{dir_name}_frame{frame_idx:04d}_{timestamp}"
            
            # Open save file dialog with format selection
            file_path, selected_filter = QFileDialog.getSaveFileName(
                self,
                "Save Current View",
                default_filename,
                "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
            )
            
            if not file_path:
                return  # User cancelled
            
            # Determine format from selected filter or file extension
            format_type = "PNG"  # Default
            if selected_filter.startswith("JPEG") or file_path.lower().endswith(('.jpg', '.jpeg')):
                format_type = "JPEG"
            elif selected_filter.startswith("PNG") or file_path.lower().endswith('.png'):
                format_type = "PNG"
            
            # Ensure proper file extension
            if format_type == "JPEG" and not file_path.lower().endswith(('.jpg', '.jpeg')):
                file_path += '.jpg'
            elif format_type == "PNG" and not file_path.lower().endswith('.png'):
                file_path += '.png'
            
            # Save the pixmap in the selected format
            success = current_pixmap.save(file_path, format_type)
            
            if success:
                QMessageBox.information(
                    self, 
                    "Image Saved", 
                    f"Image saved successfully to:\n{file_path}"
                )
                print(f"DEBUG: Image saved to {file_path} as {format_type}")
            else:
                QMessageBox.critical(
                    self, 
                    "Save Failed", 
                    f"Failed to save image to:\n{file_path}"
                )
                print(f"DEBUG: Failed to save image to {file_path}")
                
        except Exception as e:
            print(f"DEBUG: Error saving current view: {e}")
            QMessageBox.critical(
                self, 
                "Save Error", 
                f"An error occurred while saving the image:\n{str(e)}"
            )
    
    # --- ROI Component Signal Handlers ---
    def _on_roi_component_selected(self, roi_data):
        """Handle when a ROI is selected from the ROI component."""
        try:
            self._update_trace_from_roi()
        except Exception as e:
            print(f"Error updating trace after ROI selection: {e}")
    
    def _on_roi_component_added(self, roi_data):
        """Handle when a new ROI is added through the ROI component."""
        try:
            self._update_trace_from_roi()
        except Exception as e:
            print(f"Error updating trace after ROI addition: {e}")
    
    
    def keyPressEvent(self, event):
        """Handle key press events. Escape clears the current ROI selection and trace plot."""
        from PyQt6.QtCore import Qt
        
        if event.key() == Qt.Key.Key_Escape:
            # Clear only the current interactive selection and trace; keep saved ROIs visible
            # Also clear editing state
            self._editing_roi_index = None
            
            # Clear ROI list selection
            if hasattr(self, 'roi_list_component'):
                self.roi_list_component.clear_editing_state()
                roi_list_widget = self.roi_list_component.get_list_widget()
                if roi_list_widget:
                    roi_list_widget.setCurrentRow(-1)
                    roi_list_widget.clearSelection()
                print("Cleared ROI list selection (Escape key)")
            
            try:
                if hasattr(self, 'roi_tool') and self.roi_tool is not None and hasattr(self.roi_tool, 'clear_selection'):
                    self.roi_tool.clear_selection()
                else:
                    # fallback to legacy clear which clears selection too
                    self._clear_roi_and_trace()
            except Exception:
                try:
                    self._clear_roi_and_trace()
                except Exception:
                    pass
            event.accept()
        # Else if R is pressed and an ROI box is drawn
        elif event.key() == Qt.Key.Key_R:
            # Only add ROI if there's actually a current ROI drawn and user is not currently drawing
            roi_tool_dragging = (hasattr(self, 'roi_tool') and 
                                getattr(self.roi_tool, '_dragging', False))
            
            has_roi_component = hasattr(self, 'roi_list_component')
            has_last_roi = hasattr(self.window, '_last_roi_xyxy')  # Fixed: check window object
            last_roi_value = getattr(self.window, '_last_roi_xyxy', None)  # Fixed: get from window object
            
            print(f"DEBUG: R key pressed - has_roi_component: {has_roi_component}, has_last_roi: {has_last_roi}, last_roi_value: {last_roi_value}, dragging: {roi_tool_dragging}")
            
            if (has_roi_component and 
                has_last_roi and 
                last_roi_value is not None and
                not roi_tool_dragging):
                print("DEBUG: R key pressed - adding current ROI")
                self.roi_list_component._on_add_roi_clicked()
            else:
                if roi_tool_dragging:
                    print("DEBUG: R key pressed but user is currently drawing ROI - ignoring")
                elif not has_last_roi or last_roi_value is None:
                    print("DEBUG: R key pressed but no _last_roi_xyxy available")
                else:
                    print("DEBUG: R key pressed but conditions not met")
            event.accept()
        elif event.key() == Qt.Key.Key_Delete:
            # Delegate to the ROI component
            if hasattr(self, 'roi_list_component'):
                self.roi_list_component._on_remove_roi_clicked()
            event.accept()
        elif event.key() == Qt.Key.Key_S and event.modifiers() == Qt.KeyboardModifier.AltModifier:
            self._load_stimulated_rois()
            event.accept()
        elif event.key() == Qt.Key.Key_H:
            self._toggle_text_visibility()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _clear_roi_and_trace(self):
        """Clear the current ROI selection and restart the trace plot."""
        # Clear editing state in both places for consistency
        self._editing_roi_index = None
        if hasattr(self, 'roi_list_component'):
            self.roi_list_component.clear_editing_state()
        
        # Clear the ROI selection
        if hasattr(self, 'roi_tool') and self.roi_tool is not None:
            # Use clear_selection to preserve saved ROIs; clear() removes everything
            try:
                if hasattr(self.roi_tool, 'clear_selection'):
                    self.roi_tool.clear_selection()
                else:
                    self.roi_tool.clear()
            except Exception:
                try:
                    self.roi_tool.clear()
                except Exception:
                    pass
        
        # Clear the stored ROI coordinates and rotation
        if hasattr(self.window, '_last_roi_xyxy'):
            print(f"DEBUG: Clearing _last_roi_xyxy (was: {self.window._last_roi_xyxy})")
            self.window._last_roi_xyxy = None
        if hasattr(self.window, '_last_roi_rotation'):
            self.window._last_roi_rotation = 0.0
        
        # Clear the trace plot using the trace plot widget
        self.trace_plot_widget.clear_trace()

    def _load_stimulated_rois(self):
        """Load stimulated ROIs from the current folder and add them as S1, S2, etc."""
        # Get current directory
        current_item = self.analysis_list_widget.currentItem()
        if not current_item:
            return
        
        # Get the full path from UserRole, fallback to text for compatibility
        reg_dir = current_item.data(Qt.ItemDataRole.UserRole)
        if reg_dir is None:
            reg_dir = current_item.text()
        
        # Remove any existing stimulated ROIs (S1, S2, etc.)
        self._clear_stimulated_rois()
        
        # Get stimulated ROIs from experiment data
        stim_rois = self._get_stim_rois_from_experiment()
        if not stim_rois:
            return
        
        # Add each stimulated ROI to the saved ROIs list
        for i, roi_info in enumerate(stim_rois, 1):
            roi_name = f"S{i}"
            xyxy = roi_info.get('xyxy')
            if xyxy:
                # Add to saved ROIs list with a distinctive color
                roi_data = {
                    'name': roi_name,
                    'xyxy': xyxy,
                    'color': (255, 0, 255, 180)  # Magenta color for stimulated ROIs
                }
                
                # Add to window's saved ROIs if it exists
                if not hasattr(self.window, '_saved_rois'):
                    self.window._saved_rois = []
                self.window._saved_rois.append(roi_data)
                
                # Add to ROI list widget
                from PyQt6.QtWidgets import QListWidgetItem
                from PyQt6.QtGui import QColor
                item = QListWidgetItem(roi_name)
                item.setData(Qt.ItemDataRole.UserRole, roi_data)
                # Set text color to match ROI color
                item.setForeground(QColor(255, 0, 255))
                self.roi_list_widget.addItem(item)
        
        # Update ROI tool with new saved ROIs
        if hasattr(self, 'roi_tool') and self.roi_tool:
            try:
                self.roi_tool.set_saved_rois(getattr(self.window, '_saved_rois', []))
            except Exception:
                pass
        
        print(f"Loaded {len(stim_rois)} stimulated ROIs from {reg_dir}")

    def _clear_stimulated_rois(self):
        """Remove all stimulated ROIs (S1, S2, etc.) from the saved ROIs list."""
        # Remove from window's saved ROIs
        if hasattr(self.window, '_saved_rois'):
            self.window._saved_rois = [roi for roi in self.window._saved_rois 
                                     if not roi.get('name', '').startswith('S')]
        
        # Remove from ROI list widget
        items_to_remove = []
        for i in range(self.roi_list_widget.count()):
            item = self.roi_list_widget.item(i)
            if item and item.text().startswith('S') and item.text()[1:].isdigit():
                items_to_remove.append(i)
        
        # Remove items in reverse order to maintain indices
        for i in reversed(items_to_remove):
            self.roi_list_widget.takeItem(i)
        
        # Update ROI tool
        if hasattr(self, 'roi_tool') and self.roi_tool:
            try:
                self.roi_tool.set_saved_rois(getattr(self.window, '_saved_rois', []))
            except Exception:
                pass

    def _check_and_resize_for_image_change(self, tif, previous_img_wh):
        """Check if image dimensions changed and resize widget if needed.
        
        Args:
            tif: The loaded image array
            previous_img_wh: Previous image (width, height) or None
        """
        # Calculate new image dimensions
        if tif.ndim == 3:
            new_img_wh = (tif.shape[2], tif.shape[1])
        else:
            new_img_wh = (tif.shape[1], tif.shape[0])
        
        # Check if dimensions changed
        if previous_img_wh is None or previous_img_wh != new_img_wh:
            print(f"DEBUG: Image size changed from {previous_img_wh} to {new_img_wh}")
            self.image_view.resize_for_new_image(new_img_wh[0], new_img_wh[1])
        else:
            print(f"DEBUG: Image size unchanged: {new_img_wh}")
        
        # Store the new dimensions
        self.window._last_img_wh = new_img_wh

    def _update_trace_vline(self):
        """Lightweight: update only the vertical frame line on the existing trace.
        This assumes the metric plot already exists; if not, it does nothing.
        """
        # If the axes are empty, don't try to add a vline (use full update instead)
        try:
            current_frame = int(self.tif_slider.value()) if hasattr(self, 'tif_slider') else 0
        except Exception:
            return

        # Determine current position based on time display mode
        show_time = getattr(self, '_show_time_in_seconds', False)
        current_x_pos = current_frame
        
        if show_time:
            try:
                ed = getattr(self.window, '_exp_data', None)
                time_stamps = None
                
                if ed is not None:
                    # Try different possible attribute names for time stamps
                    # Handle both dictionary and object metadata formats
                    for attr_name in ['time_stamps', 'timeStamps', 'timestamps', 'ElapsedTimes']:
                        if isinstance(ed, dict):
                            if attr_name in ed:
                                time_stamps = ed[attr_name]
                                break
                        else:
                            if hasattr(ed, attr_name):
                                time_stamps = getattr(ed, attr_name)
                                break
                
                if time_stamps is not None and current_frame < len(time_stamps):
                    current_x_pos = time_stamps[current_frame] / 1000.0
                elif ed is not None:
                    # Fallback: estimate time based on frame rate
                    if isinstance(ed, dict):
                        frame_rate = ed.get('frame_rate', None)
                    else:
                        frame_rate = getattr(ed, 'frame_rate', None)
                    if frame_rate and frame_rate > 0:
                        current_x_pos = current_frame / frame_rate
            except Exception:
                pass

        # If there's no existing metric plotted, set sensible x-limits so a
        # standalone vline will be visible (use number of frames when available).
        if not self.trace_ax.lines:
            try:
                nframes = self.window._current_tif.shape[0] if getattr(self.window, '_current_tif', None) is not None and getattr(self.window, '_current_tif', None).ndim >= 3 else 1
                
                # Set x-limits based on display mode
                if show_time:
                    # Try to get max time value
                    try:
                        ed = getattr(self.window, '_exp_data', None)
                        time_stamps = None
                        
                        if ed is not None:
                            # Handle both dictionary and object metadata formats
                            for attr_name in ['time_stamps', 'timeStamps', 'timestamps', 'ElapsedTimes']:
                                if isinstance(ed, dict):
                                    if attr_name in ed:
                                        time_stamps = ed[attr_name]
                                        break
                                else:
                                    if hasattr(ed, attr_name):
                                        time_stamps = getattr(ed, attr_name)
                                        break
                        
                        if time_stamps is not None and len(time_stamps) > 0:
                            xmax = max(np.array(time_stamps[:min(nframes, len(time_stamps))]) / 1000.0)
                        elif ed is not None:
                            if isinstance(ed, dict):
                                frame_rate = ed.get('frame_rate', None)
                            else:
                                frame_rate = getattr(ed, 'frame_rate', None)
                            if frame_rate and frame_rate > 0:
                                xmax = (nframes - 1) / frame_rate
                            else:
                                xmax = max(1, nframes - 1)
                        else:
                            xmax = max(1, nframes - 1)
                    except Exception:
                        xmax = max(1, nframes - 1)
                else:
                    xmax = max(1, nframes - 1)
                    
                self.trace_ax.set_xlim(0, xmax)
            except Exception:
                pass

        # Ensure we have a persistent vline and move it (create if missing)
        if not hasattr(self.window, '_frame_vline') or self.window._frame_vline is None:
            self.window._frame_vline = self.trace_ax.axvline(current_x_pos, color='yellow', linestyle='-', zorder=10, linewidth=2)
        else:
            try:
                self.window._frame_vline.set_xdata([current_x_pos, current_x_pos])
            except Exception:
                # recreate fallback
                self.window._frame_vline = self.trace_ax.axvline(current_x_pos, color='yellow', linestyle='-', zorder=10, linewidth=2)

        # Redraw canvas (fast)
        try:
            self.trace_canvas.draw_idle()
        except Exception:
            pass
