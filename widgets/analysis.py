# TODO Quick save of stimulated ROIs
# TODO Scale Bar
# TODO Quick view of metadata: scale information pixel n FOV, XYZ position, stim events inf with ROIS (dutycycle format 0.5s20Hz5ms)
# TODO single trace plotter, timepoint/framenumber selection
# TODO read Mini2P data
# TODO Save the display as a PNG
# TODO BnC

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QListWidget,
    QPushButton, QLabel, QSlider, QLineEdit, QComboBox, QSizePolicy,
    QFileDialog, QMessageBox, QGridLayout
)
from PyQt6.QtCore import Qt

import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import numpy as np
from tools import CircleRoiTool
import sys


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
        add_dir_btn.clicked.connect(lambda: self.window.add_dirs_dialog('analysis'))
        remove_dir_btn = QPushButton("Remove Selected")
        remove_dir_btn.clicked.connect(lambda: self.window.remove_selected_dirs('analysis'))
        add_dir_btn.setFixedWidth(105)
        remove_dir_btn.setFixedWidth(105)
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
        mid_vbox = QVBoxLayout()
        self.channel_button = QPushButton("Show Channel 2")
        self.channel_button.setEnabled(False)
        # Use the widget's toggle implementation
        self.channel_button.clicked.connect(self.toggle_channel)

        self.file_type_button = QPushButton("Show Raw")
        self.file_type_button.setEnabled(False)
        self.file_type_button.clicked.connect(self.toggle_file_type)
        self._using_registered = True  

        self.cnb_button = QPushButton("BnC")
        self.cnb_button.setEnabled(False)
        self.cnb_button.clicked.connect(self.open_contrast_dialog)

        self.stimulation_area_button = QPushButton("Show stim ROIs")
        self.stimulation_area_button.setEnabled(False)
        self.stimulation_area_button.setCheckable(True)
        self.stimulation_area_button.setChecked(False)
        self.stimulation_area_button.clicked.connect(self.toggle_stim_rois)

        self.composite_button = QPushButton("Show Composite")
        self.composite_button.setEnabled(False)
        self.composite_button.setCheckable(True)
        self.composite_button.setChecked(True)
        # When composite toggles, refresh the image and sync channel button state
        self.composite_button.clicked.connect(lambda _checked: (self.update_tif_frame(), self._sync_channel_button_state()))

        self.zproj_std_button = QPushButton("SD Z projection")
        self.zproj_std_button.setEnabled(False)
        self.zproj_std_button.setCheckable(True)
        self.zproj_std_button.setChecked(False)
        self._zproj_std = False
        self.zproj_std_button.toggled.connect(lambda checked, m='std': self._on_zproj_toggled(m, checked))

        self.zproj_max_button = QPushButton("Max Z projection")
        self.zproj_max_button.setEnabled(False)
        self.zproj_max_button.setCheckable(True)
        self.zproj_max_button.setChecked(False)
        self._zproj_max = False
        self.zproj_max_button.toggled.connect(lambda checked, m='max': self._on_zproj_toggled(m, checked))

        self.zproj_mean_button = QPushButton("Mean Z projection")
        self.zproj_mean_button.setEnabled(False)
        self.zproj_mean_button.setCheckable(True)
        self.zproj_mean_button.setChecked(False)
        self._zproj_mean = False
        self.zproj_mean_button.toggled.connect(lambda checked, m='mean': self._on_zproj_toggled(m, checked))

        mid_vbox.addWidget(self.file_type_button)
        mid_vbox.addWidget(self.channel_button)
        mid_vbox.addWidget(self.cnb_button)
        mid_vbox.addWidget(self.stimulation_area_button)
        mid_vbox.addWidget(self.composite_button)
        mid_vbox.addWidget(self.zproj_std_button)
        mid_vbox.addWidget(self.zproj_max_button)
        mid_vbox.addWidget(self.zproj_mean_button)
        mid_vbox.addStretch(1)

        # --- Display panel: reg_tif image display and slider ---
        display_panel = QVBoxLayout()
        self.reg_tif_label = QLabel("Select a directory to view registered images.")
        self.reg_tif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reg_tif_label.setFixedSize(700, 629)
        display_panel.addWidget(self.reg_tif_label, 0)

        # --- ROI Tool Integration ---
        self.roi_tool = CircleRoiTool(self.reg_tif_label)
        self.roi_tool.roiChanged.connect(self._on_roi_changed)
        self.roi_tool.roiFinalized.connect(self._on_roi_finalized)

        self.tif_slider = QSlider(Qt.Orientation.Horizontal)
        self.tif_slider.setMinimum(0)
        self.tif_slider.setMaximum(0)
        self.tif_slider.setValue(0)
        self.tif_slider.setEnabled(True)
        self.tif_slider.valueChanged.connect(self.update_tif_frame)
        display_panel.addWidget(self.tif_slider)

        # Connect selection change to widget-local handlers
        self.analysis_list_widget.currentItemChanged.connect(self._on_item_changed_with_roi_preservation)

        # ROI Items (Right panel)
        self.roi_list_widget = QListWidget()
        self.roi_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.roi_list_widget.setMinimumWidth(220)

        # --- Bottom panel: Plot the signal of a given area ---
        bottom_panel = QHBoxLayout()
        bottom_panel.addStretch(0)

        # Toggles for plot
        plot_toggle_layout = QVBoxLayout()

        # Y limits inputs
        ylim_layout = QVBoxLayout()
        ylim_layout.setSpacing(2)
        ylim_layout.setContentsMargins(0, 0, 0, 0)

        ylim_label = QLabel("Y limits:")
        ylim_label.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        ylim_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.ylim_min_edit = QLineEdit()
        self.ylim_min_edit.setFixedWidth(50)
        self.ylim_min_edit.setFixedHeight(20)
        self.ylim_min_edit.setPlaceholderText("Min")
        self.ylim_min_edit.editingFinished.connect(self._update_trace_from_roi)

        self.ylim_max_edit = QLineEdit()
        self.ylim_max_edit.setFixedWidth(50)
        self.ylim_max_edit.setFixedHeight(20)
        self.ylim_max_edit.setPlaceholderText("Max")
        self.ylim_max_edit.editingFinished.connect(self._update_trace_from_roi)

        self.reset_ylim_button = QPushButton("Reset")
        self.reset_ylim_button.setFixedWidth(50)
        self.reset_ylim_button.clicked.connect(self._reset_ylim)

        ylim_layout.addWidget(ylim_label)
        ylim_layout.addWidget(self.ylim_max_edit)
        ylim_layout.addWidget(self.ylim_min_edit)
        ylim_layout.addWidget(self.reset_ylim_button)
        plot_toggle_layout.addLayout(ylim_layout)

        self.formula_dropdown = QComboBox()
        self.formula_dropdown.setFixedWidth(100)
        self.formula_dropdown.setStyleSheet("QComboBox { font-size: 8pt; }")
        self.formula_dropdown.addItem("Fg - Fog / Fr")
        self.formula_dropdown.addItem("Fg - Fog / Fog")
        self.formula_dropdown.addItem("Fg only")
        self.formula_dropdown.addItem("Fr only")
        self.formula_dropdown.setContentsMargins(0, 0, 0, 0)
        self.formula_dropdown.currentIndexChanged.connect(self._update_trace_from_roi)
        plot_toggle_layout.addWidget(self.formula_dropdown)

        bottom_panel.addLayout(plot_toggle_layout)

        # Figure of ROI signal
        self.trace_fig, self.trace_ax = plt.subplots(figsize=(8, 4), dpi=100)
        self.trace_ax.set_xticks([])
        self.trace_ax.set_yticks([])
        self.trace_ax.set_xlabel("")
        self.trace_ax.set_ylabel("")
        for spine in self.trace_ax.spines.values():
            spine.set_visible(True)
        self.trace_fig.patch.set_alpha(0.0)
        self.trace_ax.set_facecolor('none')
        self.trace_canvas = FigureCanvas(self.trace_fig)
        self.trace_canvas.setStyleSheet("background:transparent; border: 1px solid #888;")
        self.trace_canvas.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.trace_ax.xaxis.label.set_color('white')
        self.trace_ax.yaxis.label.set_color('white')
        self.trace_ax.tick_params(axis='x', colors='white')
        self.trace_ax.tick_params(axis='y', colors='white')
        for spine in self.trace_ax.spines.values():
            spine.set_color('white')
        self.trace_fig.tight_layout()
        bottom_panel.addWidget(self.trace_canvas, 1)

        # store user overrides
        self.window._ylim_min_user = None
        self.window._ylim_max_user = None

        # --- Assemble layouts ---
        main_hbox.addLayout(left_vbox, 1)  # Allow directory list to expand
        main_hbox.addLayout(mid_vbox, 0)
        main_hbox.addLayout(display_panel, 0)  # Keep image display fixed
        # Wrap ROI list in a group similar to Registered Directories
        roi_group = QGroupBox("Saved ROIs")
        roi_vbox = QVBoxLayout()
        roi_vbox.addWidget(self.roi_list_widget)

        roi_grid_layout = QGridLayout()
        add_roi_btn = QPushButton("Add ROI")
        remove_roi_btn = QPushButton("Remove ROI")
        export_trace_btn = QPushButton("Export Trace...")
        self.hide_rois_checkbox = None
        try:
            from PyQt6.QtWidgets import QCheckBox
            self.hide_rois_checkbox = QCheckBox("Hide ROIs")
            self.hide_rois_checkbox.setChecked(False)
            self.hide_rois_checkbox.setToolTip("Hide saved and drawn ROIs from the image view")
            self.hide_rois_checkbox.stateChanged.connect(lambda s: self._on_hide_rois_toggled(s))
        except Exception:
            self.hide_rois_checkbox = None
        save_roi_btn = QPushButton("Save ROIs...")
        load_roi_btn = QPushButton("Load ROIs...")
        add_roi_btn.setFixedWidth(110)
        remove_roi_btn.setFixedWidth(110)
        export_trace_btn.setFixedWidth(110)
        save_roi_btn.setFixedWidth(110)
        load_roi_btn.setFixedWidth(110)
        roi_grid_layout.addWidget(add_roi_btn, 0, 0)       # Row 0, Column 0
        roi_grid_layout.addWidget(remove_roi_btn, 0, 1)    # Row 0, Column 1
        roi_grid_layout.addWidget(save_roi_btn, 1, 0)      # Row 1, Column 0
        roi_grid_layout.addWidget(load_roi_btn, 1, 1)      # Row 1, Column 1
        roi_grid_layout.addWidget(export_trace_btn, 2, 0, 1, 2)  # Row 2, spanning 2 columns
        # Place the hide checkbox under the export button (spanning 2 columns)
        if self.hide_rois_checkbox is not None:
            roi_grid_layout.addWidget(self.hide_rois_checkbox, 3, 0, 1, 2)

        roi_vbox.addLayout(roi_grid_layout)
        roi_group.setLayout(roi_vbox)
        main_hbox.addWidget(roi_group, 1)  # Allow ROI list to expand too

        # Connect buttons to handlers (local handlers implemented below)
        add_roi_btn.clicked.connect(self._on_add_roi_clicked)
        remove_roi_btn.clicked.connect(self._on_remove_roi_clicked)
        save_roi_btn.clicked.connect(self._on_save_roi_positions_clicked)
        load_roi_btn.clicked.connect(self._on_load_roi_positions_clicked)
        export_trace_btn.clicked.connect(self._on_export_roi_clicked)
        # Ensure checkbox initial visibility state sync with ROI tool
        if self.hide_rois_checkbox is not None:
            try:
                # default: show ROIs
                self.roi_tool.set_show_saved_rois(True)
                self.roi_tool.set_show_stim_rois(True)
            except Exception:
                pass
        # Selection change should restore saved ROI
        self.roi_list_widget.currentItemChanged.connect(self._on_saved_roi_selected)


        main_vbox.addLayout(main_hbox, 0)
        main_vbox.addLayout(bottom_panel, 0)
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
            self.window.reg_tif_label = self.reg_tif_label
            self.window.roi_tool = self.roi_tool
            self.window.tif_slider = self.tif_slider
            self.window.ylim_min_edit = self.ylim_min_edit
            self.window.ylim_max_edit = self.ylim_max_edit
            self.window.reset_ylim_button = self.reset_ylim_button
            self.window.formula_dropdown = self.formula_dropdown
            self.window.trace_fig = self.trace_fig
            self.window.trace_ax = self.trace_ax
            self.window.trace_canvas = self.trace_canvas
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
        # Store current ROI if it exists
        stored_roi = getattr(self.window, '_last_roi_xyxy', None)
        
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
                    
                    # Show the ROI overlay on the new image
                    try:
                        self.roi_tool.show_bbox_image_coords(stored_roi)
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
        except Exception:
            pass

    def display_reg_tif_image(self, current, previous=None):
        """Load registered tif(s) for the selected directory and initialize slider/view."""
        from PyQt6.QtGui import QImage, QPixmap
        import tifffile
        import os
        import pickle
        import subprocess
        from PyQt6.QtWidgets import QApplication
        
        if not current:
            self.reg_tif_label.setPixmap(QPixmap())
            self.reg_tif_label.setText("Select a directory to view registered images.")
            self.tif_slider.setEnabled(False)
            self.tif_slider.setMaximum(0)
            self.window._current_tif = None
            self.file_type_button.setEnabled(False)
            return

        # Get the full path from UserRole, fallback to text for compatibility
        reg_dir = current.data(Qt.ItemDataRole.UserRole)
        if reg_dir is None:
            reg_dir = current.text()
        reg_tif_path = os.path.join(reg_dir, "Ch1-reg.tif")
        reg_tif_chan2_path = os.path.join(reg_dir, "Ch2-reg.tif")
        exp_details = os.path.join(reg_dir, "experiment_summary.pkl")
        exp_json = os.path.join(reg_dir, "experiment_summary.json")

        # Initialize variables
        tif = None
        tif_chan2 = None

        # Determine file paths based on user preference
        npy_ch0_path = os.path.join(reg_dir, "ImageData_Ch0_TP0000000.npy")
        npy_ch1_path = os.path.join(reg_dir, "ImageData_Ch1_TP0000000.npy")
        
        # Check what files are available
        has_registered_tif = os.path.isfile(reg_tif_path)
        has_raw_numpy = os.path.isfile(npy_ch0_path)
        
        # Determine which files to use based on preference and availability
        use_registered = getattr(self, '_using_registered', True)
        
        if use_registered and has_registered_tif:
            # Load registered TIFF files
            self.reg_tif_label.setText("Loading registered TIFF files...")
            try:
                tif = tifffile.imread(reg_tif_path)
                if os.path.isfile(reg_tif_chan2_path):
                    self.reg_tif_label.setText("Loading registered TIFF files (Channel 2)...")
                    tif_chan2 = tifffile.imread(reg_tif_chan2_path)
                else:
                    tif_chan2 = None
                self.window._current_tif = tif
                self.window._current_tif_chan2 = tif_chan2
                # DEBUG: print dtype and inferred bit depth for loaded images
                try:
                    dt = tif.dtype
                    bits = dt.itemsize * 8
                    print(f"DEBUG: Ch1 loaded dtype={dt}, inferred bits={bits}")
                except Exception:
                    print("DEBUG: Ch1 loaded, but couldn't determine dtype/bits")
                try:
                    if tif_chan2 is not None:
                        dt2 = tif_chan2.dtype
                        bits2 = dt2.itemsize * 8
                        print(f"DEBUG: Ch2 loaded dtype={dt2}, inferred bits={bits2}")
                    else:
                        print("DEBUG: Ch2 not present")
                except Exception:
                    print("DEBUG: Ch2 loaded, but couldn't determine dtype/bits")
                # Store last image width and height for ROI tools
                if tif.ndim == 3:
                    self.window._last_img_wh = (tif.shape[2], tif.shape[1])
                else:
                    self.window._last_img_wh = (tif.shape[1], tif.shape[0])
            except Exception as e:
                self.reg_tif_label.setText(f"Failed to load registered TIFF: {e}")
                self.reg_tif_label.setPixmap(QPixmap())
                self.tif_slider.setEnabled(False)
                self.tif_slider.setMaximum(0)
                self.window._current_tif = None
                return
        elif not use_registered and has_raw_numpy:
            # Load raw numpy files
            self.reg_tif_label.setPixmap(QPixmap())
            self.reg_tif_label.setText("Loading raw numpy files...")
            
            try:
                if os.path.isfile(npy_ch0_path):
                    self.reg_tif_label.setText("Loading Channel 1 numpy data...")
                    tif = np.load(npy_ch0_path)
                    self.window._current_tif = tif
                else:
                    raise FileNotFoundError(f"Ch0 numpy file not found: {npy_ch0_path}")
                    
                if os.path.isfile(npy_ch1_path):
                    self.reg_tif_label.setText("Loading Channel 2 numpy data...")
                    tif_chan2 = np.load(npy_ch1_path)
                    self.window._current_tif_chan2 = tif_chan2
                else:
                    self.window._current_tif_chan2 = None
                # DEBUG: print dtype and inferred bit depth for raw numpy files
                try:
                    dt = tif.dtype
                    bits = dt.itemsize * 8
                    print(f"DEBUG: Raw Ch1 loaded dtype={dt}, inferred bits={bits}")
                except Exception:
                    print("DEBUG: Raw Ch1 loaded, but couldn't determine dtype/bits")
                try:
                    if tif_chan2 is not None:
                        dt2 = tif_chan2.dtype
                        bits2 = dt2.itemsize * 8
                        print(f"DEBUG: Raw Ch2 loaded dtype={dt2}, inferred bits={bits2}")
                    else:
                        print("DEBUG: Raw Ch2 not present")
                except Exception:
                    print("DEBUG: Raw Ch2 loaded, but couldn't determine dtype/bits")
                    
                # Store last image width and height for ROI tools
                if tif.ndim == 3:
                    self.window._last_img_wh = (tif.shape[2], tif.shape[1])
                else:
                    self.window._last_img_wh = (tif.shape[1], tif.shape[0])
                    
            except Exception as e:
                self.reg_tif_label.setText(f"Failed to load numpy files: {e}")
                self.reg_tif_label.setPixmap(QPixmap())
                self.tif_slider.setEnabled(False)
                self.tif_slider.setMaximum(0)
                self.window._current_tif = None
                return
        elif use_registered and not has_registered_tif and has_raw_numpy:
            # Fallback to numpy files if user wants registered but they don't exist
            self.reg_tif_label.setPixmap(QPixmap())
            self.reg_tif_label.setText("No registered TIFF files found. Loading raw numpy files...")
            
            try:
                if os.path.isfile(npy_ch0_path):
                    self.reg_tif_label.setText("Loading Channel 1 numpy data...")
                    tif = np.load(npy_ch0_path)
                    self.window._current_tif = tif
                else:
                    raise FileNotFoundError(f"Ch0 numpy file not found: {npy_ch0_path}")
                    
                if os.path.isfile(npy_ch1_path):
                    self.reg_tif_label.setText("Loading Channel 2 numpy data...")
                    tif_chan2 = np.load(npy_ch1_path)
                    self.window._current_tif_chan2 = tif_chan2
                else:
                    self.window._current_tif_chan2 = None
                    
                # Store last image width and height for ROI tools
                if tif.ndim == 3:
                    self.window._last_img_wh = (tif.shape[2], tif.shape[1])
                else:
                    self.window._last_img_wh = (tif.shape[1], tif.shape[0])
                    
            except Exception as e:
                self.reg_tif_label.setText(f"Failed to load numpy files: {e}")
                self.reg_tif_label.setPixmap(QPixmap())
                self.tif_slider.setEnabled(False)
                self.tif_slider.setMaximum(0)
                self.window._current_tif = None
                return
        elif not use_registered and not has_raw_numpy and has_registered_tif:
            # Fallback to registered files if user wants raw but they don't exist
            self.reg_tif_label.setText("No raw numpy files found. Loading registered TIFF files...")
            try:
                tif = tifffile.imread(reg_tif_path)
                if os.path.isfile(reg_tif_chan2_path):
                    self.reg_tif_label.setText("Loading registered TIFF files (Channel 2)...")
                    tif_chan2 = tifffile.imread(reg_tif_chan2_path)
                else:
                    tif_chan2 = None
                self.window._current_tif = tif
                self.window._current_tif_chan2 = tif_chan2
                # Store last image width and height for ROI tools
                if tif.ndim == 3:
                    self.window._last_img_wh = (tif.shape[2], tif.shape[1])
                else:
                    self.window._last_img_wh = (tif.shape[1], tif.shape[0])
            except Exception as e:
                self.reg_tif_label.setText(f"Failed to load registered TIFF: {e}")
                self.reg_tif_label.setPixmap(QPixmap())
                self.tif_slider.setEnabled(False)
                self.tif_slider.setMaximum(0)
                self.window._current_tif = None
                return
        else:
            # Neither file type is available - show clear message to user
            self.reg_tif_label.setPixmap(QPixmap())  # Clear any existing image
            self.reg_tif_label.setText("No image files found in this directory.\n\nThis directory doesn't contain:\n• Ch1-reg.tif (registered files)\n• ImageData_Ch0_TP0000000.npy (raw files)")
            self.tif_slider.setEnabled(False)
            self.tif_slider.setMaximum(0)
            self.window._current_tif = None
            self.window._current_tif_chan2 = None
            self.file_type_button.setEnabled(False)
            return

        # Reading the experiment summary/metadata
        self.window._exp_data = None
        
        # First try to read existing pickle file
        if os.path.isfile(exp_details):
            self.reg_tif_label.setText("Loading experiment metadata...")
            try:
                with open(exp_details, 'rb') as f:
                    exp_data = pickle.load(f)
                class ExpData:
                    def __init__(self, data):
                        for k, v in data.items():
                            setattr(self, k, v)
                self.window._exp_data = ExpData(exp_data)
            except Exception as e:
                self.reg_tif_label.setText("Failed to load existing metadata. Attempting to read from raw files...")
                self.stimulation_area_button.setEnabled(False)
        
        # If no metadata exists or failed to load, try to read metadata from raw files
        if self.window._exp_data is None:
            self.reg_tif_label.setText("Reading metadata from raw files...")
            QApplication.processEvents()
            try:
                meta_cmd = [sys.executable, "scripts/meta_reader.py", "-f", str(reg_dir)]
                meta_proc = subprocess.Popen(
                    meta_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                
                # Initialize conv_log if it doesn't exist
                if not hasattr(self, 'conv_log'):
                    self.conv_log = []
                
                for line in meta_proc.stdout:
                    self.conv_log.append(line.rstrip())
                    
                meta_retcode = meta_proc.wait()
                if meta_retcode != 0:
                    self.conv_log.append(f"FAILED to read metadata: {reg_dir}\n")
                    self.reg_tif_label.setText("Failed to read metadata from raw files.")
                else:
                    self.conv_log.append("--- Metadata read done ---\n")
                    self.reg_tif_label.setText("Metadata reading completed. Loading experiment summary...")
                    
                    # Try to load the newly created pickle file
                    if os.path.isfile(exp_details):
                        try:
                            with open(exp_details, 'rb') as f:
                                exp_data = pickle.load(f)
                            class ExpData:
                                def __init__(self, data):
                                    for k, v in data.items():
                                        setattr(self, k, v)
                            self.window._exp_data = ExpData(exp_data)
                        except Exception as e:
                            self.reg_tif_label.setText("Metadata read but failed to load experiment summary.")
                            self.window._exp_data = None
                            
            except Exception as e:
                if not hasattr(self, 'conv_log'):
                    self.conv_log = []
                self.conv_log.append(f"FAILED to read metadata: {reg_dir} (Error: {e})\n")
                self.reg_tif_label.setText(f"Exception during metadata reading: {e}")

        # Finalize loading and display image
        self.reg_tif_label.setText("Preparing image display...")
        
        nframes = tif.shape[0] if tif.ndim == 3 else 1
        self.tif_slider.setEnabled(nframes > 1)
        self.tif_slider.setMaximum(nframes-1)
        self.tif_slider.setValue(0)
        
        # Show final status before displaying image
        self.reg_tif_label.setText("Loading image frames...")
        
        self.update_tif_frame()

        # Enable file type toggle if both file types are available
        self.file_type_button.setEnabled(has_registered_tif and has_raw_numpy)
        # If there's no registered TIFF, make the button default indicate that
        try:
            if not has_registered_tif:
                # Keep an explicit message when registration is absent
                self.file_type_button.setText("No Registration")
            else:
                # When registration exists, ensure the button reflects current preference
                if getattr(self, '_using_registered', True):
                    self.file_type_button.setText("Show Raw")
                else:
                    self.file_type_button.setText("Show Registration")
        except Exception:
            pass

        # Make the channel and composite buttons active if channel 2 exists
        # Check for registered tiff first, then numpy file
        has_channel2 = False
        if os.path.isfile(reg_tif_chan2_path):
            has_channel2 = True
        elif tif_chan2 is not None:
            has_channel2 = True
            
        if has_channel2:
            self.composite_button.setEnabled(True)
            self._sync_channel_button_state()
        else:
            self.composite_button.setEnabled(False)
            self.channel_button.setEnabled(False)
            
        # Enable z-projection buttons when an image is loaded
        self.zproj_std_button.setEnabled(True)
        self.zproj_max_button.setEnabled(True)
        self.zproj_mean_button.setEnabled(True)
            
        # enable contrast & brightness when an image is loaded
        self.cnb_button.setEnabled(True)
            
        # Enable stimulus ROI button if experiment data contains stimulus locations
        try:
            stim_rois = self._get_stim_rois_from_experiment()
            has_stim_data = len(stim_rois) > 0
            print(f"DEBUG: Found {len(stim_rois)} stimulus ROIs")
            if hasattr(self.window, '_exp_data') and self.window._exp_data:
                print(f"DEBUG: Experiment data attributes: {[attr for attr in dir(self.window._exp_data) if not attr.startswith('_')]}")
            self.stimulation_area_button.setEnabled(has_stim_data)
            # Ensure the button remains checkable when enabled
            if has_stim_data:
                self.stimulation_area_button.setCheckable(True)
        except Exception as e:
            print(f"DEBUG: Exception in stimulus detection: {e}")
            self.stimulation_area_button.setEnabled(False)
            
        # Update trace if there's an active ROI to reflect new data
        try:
            if getattr(self.window, '_last_roi_xyxy', None) is not None:
                self._update_trace_from_roi()
        except Exception:
            pass

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
                img_chan2 = tif_chan2[frame_idx] if tif_chan2 is not None and tif_chan2.ndim >= 3 else tif_chan2
                self.tif_slider.setEnabled(True)
            else:
                img = tif
                img_chan2 = tif_chan2

        # Coerce to 2-D
        img = misc.to_2d(img)
        img_chan2 = misc.to_2d(img_chan2)

        # Safety check
        if img is None or img.size == 0:
            self.reg_tif_label.setText(f"Error: Frame {frame_idx} is empty or corrupted.")
            return

        # Normalize base channel (green) using robust percentile clipping
        g = img.astype(np.float32)

        # Use lower and upper percentiles to avoid single-pixel outliers
        g_low = np.percentile(g, 5)
        g_high = np.percentile(g, 99.5)
        # Ensure sensible ordering
        if g_high <= g_low:
            g_high = float(g.max())

        g_clipped = np.clip(g, g_low, g_high)

        # Now, normalize the clipped data to [0,1]
        g_min_view = float(np.min(g_clipped))
        g_ptp_view = float(np.ptp(g_clipped))
        g_view = (g_clipped - g_min_view) / (g_ptp_view if g_ptp_view > 0 else 1.0)

        if img_chan2 is not None and self.composite_button.isChecked():
            self.zproj_std_button.setEnabled(True)
            self.zproj_max_button.setEnabled(True)
            self.zproj_mean_button.setEnabled(True)

            r = img_chan2.astype(np.float32)
            # Use robust percentile clipping for red channel as well
            r_low = np.percentile(r, 5)
            r_high = np.percentile(r, 99.5)
            if r_high <= r_low:
                r_high = float(r.max())
            r_clipped = np.clip(r, r_low, r_high)
            r_min_view = float(np.min(r_clipped))
            r_ptp_view = float(np.ptp(r_clipped))
            r_view = (r_clipped - r_min_view) / (r_ptp_view if r_ptp_view > 0 else 1.0)

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
                
                # Apply the same robust contrast enhancement as composite path
                r_low = np.percentile(r, 5)
                r_high = np.percentile(r, 99.5)
                if r_high <= r_low:
                    r_high = float(r.max())
                r_clipped = np.clip(r, r_low, r_high)
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

        h, w, _ = arr_uint8.shape
        qimg = QImage(arr_uint8.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg)
        
        # store a copy of the displayed image for CNB (as grayscale or RGB uint8)
        try:
            if arr_uint8.shape[2] == 4:
                rgb = arr_uint8[..., :3]
            else:
                rgb = arr_uint8
            self.window._current_image_np = rgb.copy()
            self.window._current_qimage = qimg.copy()
        except Exception:
            self.window._current_image_np = None
            self.window._current_qimage = None
            
        # Apply global BnC settings if they exist and are enabled
        if (hasattr(self.window, '_global_bnc_settings') and 
            self.window._global_bnc_settings.get('enabled', False)):
            try:
                # Apply BnC directly to the raw image data before display
                from tools.bnc import apply_bnc_to_image, create_qimage_from_array, create_composite_image
                
                # Get BnC settings
                settings = self.window._global_bnc_settings
                
                # Apply BnC to current frame
                if img_chan2 is not None and self.composite_button.isChecked():
                    # Composite mode - apply BnC to both channels
                    bnc_img = create_composite_image(img, img_chan2, settings['ch1'], settings['ch2'])
                else:
                    # Single channel mode
                    active_ch = getattr(self, "_active_channel", 1)
                    if img_chan2 is not None and active_ch == 2:
                        # Channel 2
                        bnc_img = apply_bnc_to_image(img_chan2, settings['ch2']['min'], settings['ch2']['max'], settings['ch2']['contrast'])
                        # Convert to RGBA grayscale
                        if bnc_img.ndim == 2:
                            h_bnc, w_bnc = bnc_img.shape
                            rgba_bnc = np.zeros((h_bnc, w_bnc, 4), dtype=np.uint8)
                            rgba_bnc[..., :3] = bnc_img[..., None]
                            rgba_bnc[..., 3] = 255
                            bnc_img = rgba_bnc
                    else:
                        # Channel 1
                        bnc_img = apply_bnc_to_image(img, settings['ch1']['min'], settings['ch1']['max'], settings['ch1']['contrast'])
                        # Convert to RGBA grayscale  
                        if bnc_img.ndim == 2:
                            h_bnc, w_bnc = bnc_img.shape
                            rgba_bnc = np.zeros((h_bnc, w_bnc, 4), dtype=np.uint8)
                            rgba_bnc[..., :3] = bnc_img[..., None]
                            rgba_bnc[..., 3] = 255
                            bnc_img = rgba_bnc
                
                # Create new QImage and pixmap with BnC applied
                if bnc_img is not None:
                    qimg = create_qimage_from_array(bnc_img)
                    pixmap = QPixmap.fromImage(qimg)
                    
            except Exception as e:
                print(f"DEBUG: Error applying global BnC in update_tif_frame: {e}")
                # Fall back to original pixmap if BnC fails
                pass
        
        # Scale and display the final pixmap
        try:
            base_pix = pixmap.scaled(
                self.reg_tif_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.reg_tif_label.setFixedSize(base_pix.size())
            self.reg_tif_label.setPixmap(base_pix)
        except Exception:
            self.reg_tif_label.setPixmap(pixmap.scaled(self.reg_tif_label.size(), Qt.AspectRatioMode.KeepAspectRatio))
        self.reg_tif_label.setText("")

        # --- Update ROI Tool with new image view ---
        scaled_pixmap = self.reg_tif_label.pixmap()
        if scaled_pixmap is not None and hasattr(self.window, '_last_img_wh'):
            self.roi_tool.set_pixmap(scaled_pixmap)
            label_size = self.reg_tif_label.size()
            pixmap_size = scaled_pixmap.size()
            x_offset = (label_size.width() - pixmap_size.width()) // 2
            y_offset = (label_size.height() - pixmap_size.height()) // 2
            draw_rect = QRect(x_offset, y_offset, pixmap_size.width(), pixmap_size.height())
            self.roi_tool.set_draw_rect(draw_rect)
            self._img_draw_rect = draw_rect
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
                    self.roi_tool.show_bbox_image_coords(self.window._last_roi_xyxy)
                except Exception:
                    pass
                self._update_trace_vline()

    def _on_roi_changed(self, xyxy):
        """Live preview; you can skip computing anything heavy here."""
        pass

    def _on_roi_finalized(self, xyxy):
        """xyxy is (x0, y0, x1, y1) in IMAGE coordinates."""
        self.window._last_roi_xyxy = xyxy
        # Ensure overlay is painted on the current pixmap immediately
        try:
            self.roi_tool.show_bbox_image_coords(xyxy)
        except Exception:
            pass
        # Full redraw: recompute trace and recreate the vline after plotting
        try:
            self._update_trace_from_roi()
        except Exception:
            # As a last resort ensure vline exists
            self._update_trace_vline()

    # --- Simple ROI save/remove handlers ---
    def _on_add_roi_clicked(self):
        """Save the current ROI (if any) into an in-memory list and the list widget."""
        if getattr(self.window, '_last_roi_xyxy', None) is None:
            return
        # Ensure storage exists on window
        if not hasattr(self.window, '_saved_rois'):
            self.window._saved_rois = []
        
        # Generate random color for this ROI
        import random
        color = (
            random.randint(100, 255),  # R
            random.randint(100, 255),  # G
            random.randint(100, 255),  # B
            200  # Alpha
        )
        
        name = f"ROI {len(self.window._saved_rois) + 1}"
        roi_data = {
            'name': name, 
            'xyxy': tuple(self.window._last_roi_xyxy),
            'color': color
        }
        self.window._saved_rois.append(roi_data)
        self.roi_list_widget.addItem(name)
        
        # Update the ROI tool with all saved ROIs so they display persistently
        self.roi_tool.set_saved_rois(self.window._saved_rois)
        # Repaint overlay to show all saved ROIs
        self.roi_tool._paint_overlay()

    def _on_remove_roi_clicked(self):
        """Remove selected saved ROI from widget and in-memory store."""
        item = self.roi_list_widget.currentItem()
        if not item:
            return
        row = self.roi_list_widget.row(item)
        self.roi_list_widget.takeItem(row)
        try:
            if hasattr(self.window, '_saved_rois'):
                del self.window._saved_rois[row]
                # Update the ROI tool with remaining saved ROIs
                self.roi_tool.set_saved_rois(self.window._saved_rois)
                # Repaint overlay to show updated ROIs
                self.roi_tool._paint_overlay()
        except Exception:
            pass

    def _on_saved_roi_selected(self, current, previous=None):
        """Restore the selected saved ROI onto the image/roi tool and update trace."""
        if current is None:
            return
        row = self.roi_list_widget.row(current)
        saved = None
        if hasattr(self.window, '_saved_rois') and 0 <= row < len(self.window._saved_rois):
            saved = self.window._saved_rois[row]
        if saved is None:
            return
        xyxy = saved.get('xyxy')
        if xyxy is None:
            return
        # Restore and update
        try:
            self.window._last_roi_xyxy = tuple(xyxy)
            self.roi_tool.show_bbox_image_coords(self.window._last_roi_xyxy)
            self._update_trace_from_roi()
        except Exception:
            try:
                self._update_trace_vline()
            except Exception:
                pass

    def _on_load_roi_positions_clicked(self):
        """Load ROI positions from a JSON file."""
        # Open file dialog to choose file to import
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Load ROI Positions")
        file_dialog.setNameFilter("JSON files (*.json)")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        
        if not file_dialog.exec():
            return
            
        filename = file_dialog.selectedFiles()[0]
        
        try:
            import json
            with open(filename, 'r') as f:
                roi_data = json.load(f)
            
            # Clear existing ROIs first
            self.roi_list_widget.clear()
            if hasattr(self.window, '_saved_rois'):
                self.window._saved_rois = []
            else:
                self.window._saved_rois = []
            
            # Load the imported ROIs
            for roi in roi_data:
                roi_entry = {
                    'name': roi['name'],
                    'xyxy': tuple(roi['xyxy']),
                    'color': tuple(roi['color'])
                }
                self.window._saved_rois.append(roi_entry)
                self.roi_list_widget.addItem(roi['name'])
            
            # Update the ROI tool with imported ROIs
            if hasattr(self.roi_tool, 'set_saved_rois'):
                self.roi_tool.set_saved_rois(self.window._saved_rois)
                self.roi_tool._paint_overlay()
            
            QMessageBox.information(self, "Load Complete", 
                                  f"Successfully loaded {len(roi_data)} ROI positions from:\n{filename}")
                                  
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load ROI positions:\n{str(e)}")
            print(f"Load error: {e}")

    def _on_save_roi_positions_clicked(self):
        """Save ROI positions to a JSON file."""
        if not hasattr(self.window, '_saved_rois') or not self.window._saved_rois:
            QMessageBox.information(self, "No ROIs", "No ROIs to save. Please add some ROIs first.")
            return
            
        # Open file dialog to choose save location
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Save ROI Positions")
        file_dialog.setNameFilter("JSON files (*.json)")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDefaultSuffix("json")
        
        if not file_dialog.exec():
            return
            
        filename = file_dialog.selectedFiles()[0]
        
        try:
            # Prepare ROI data for JSON serialization
            roi_data = []
            for roi in self.window._saved_rois:
                roi_data.append({
                    'name': roi['name'],
                    'xyxy': list(roi['xyxy']),
                    'color': list(roi['color'])
                })
            
            # Save to file
            import json
            with open(filename, 'w') as f:
                json.dump(roi_data, f, indent=2)
            
            QMessageBox.information(self, "Save Complete", 
                                  f"Successfully saved {len(roi_data)} ROI positions to:\n{filename}")
                                  
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save ROI positions:\n{str(e)}")
            print(f"Save error: {e}")

    def _on_export_roi_clicked(self):
        """Export all saved ROIs for all timepoints to a tab-separated text file."""
        if not hasattr(self.window, '_saved_rois') or not self.window._saved_rois:
            QMessageBox.information(self, "No ROIs", "No ROIs to export. Please add some ROIs first.")
            return
            
        # Check if we have image data
        if not hasattr(self.window, '_current_tif') or self.window._current_tif is None:
            QMessageBox.warning(self, "No Image Data", "No image data loaded. Please load a dataset first.")
            return
            
        # Open file dialog to choose save location
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Export ROIs")
        file_dialog.setNameFilter("Text files (*.txt)")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDefaultSuffix("txt")
        
        if not file_dialog.exec():
            return
            
        filename = file_dialog.selectedFiles()[0]
        
        try:
            # Get image data dimensions
            tif = self.window._current_tif
            tif_chan2 = getattr(self.window, '_current_tif_chan2', None)
            
            # Determine number of frames
            if tif.ndim == 3:
                nframes = tif.shape[0]
            else:
                nframes = 1
                tif = tif[None, ...]  # Add frame dimension
                if tif_chan2 is not None:
                    tif_chan2 = tif_chan2[None, ...]
            
            # Get current formula selection
            formula_index = self.formula_dropdown.currentIndex()
            
            # Progress tracking for large datasets
            total_work = nframes * len(self.window._saved_rois)
            if total_work > 1000:
                from PyQt6.QtWidgets import QProgressDialog
                progress = QProgressDialog("Extracting ROI data...", "Cancel", 0, total_work, self)
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.show()
            else:
                progress = None
            
            # Prepare headers: Frame, then for each ROI: Green_Mean_ROI#, Red_Mean_ROI#, Trace_ROI#
            headers = ["Frame"]
            for i, roi in enumerate(self.window._saved_rois):
                roi_num = i + 1
                headers.extend([
                    f"Green_Mean_ROI{roi_num}",
                    f"Red_Mean_ROI{roi_num}",
                    f"Trace_ROI{roi_num}"
                ])
            
            # Pre-calculate baseline (Fog) for each ROI using first 10% of frames
            roi_baselines = {}
            baseline_count = max(1, int(np.ceil(nframes * 0.10)))
            
            for i, roi in enumerate(self.window._saved_rois):
                xyxy = roi.get('xyxy')
                if xyxy is None:
                    roi_baselines[i] = 0
                    continue
                
                x0, y0, x1, y1 = xyxy
                roi_height = y1 - y0
                roi_width = x1 - x0
                
                if roi_height > 0 and roi_width > 0:
                    # Extract green values from baseline frames
                    green_baseline_values = []
                    try:
                        cy, cx = (y0 + y1) / 2.0, (x0 + x1) / 2.0
                        ry, rx = roi_height / 2.0, roi_width / 2.0
                        y_coords, x_coords = np.ogrid[y0:y1, x0:x1]
                        mask = ((x_coords - cx) / rx) ** 2 + ((y_coords - cy) / ry) ** 2 <= 1
                        
                        for frame_idx in range(baseline_count):
                            green_frame = tif[frame_idx]
                            if mask.any():
                                green_roi_pixels = green_frame[y0:y1, x0:x1][mask]
                                green_baseline_values.append(np.mean(green_roi_pixels))
                            else:
                                green_baseline_values.append(np.mean(green_frame[y0:y1, x0:x1]))
                        
                        roi_baselines[i] = float(np.mean(green_baseline_values))
                    except Exception as e:
                        print(f"Error calculating baseline for ROI {i+1}: {e}")
                        roi_baselines[i] = 0
                else:
                    roi_baselines[i] = 0
            
            # Extract data for all frames and all ROIs
            export_data = []
            
            for frame_idx in range(nframes):
                if progress is not None:
                    if progress.wasCanceled():
                        return
                    progress.setValue(frame_idx * len(self.window._saved_rois))
                
                # Get frames for this timepoint
                green_frame = tif[frame_idx]
                red_frame = tif_chan2[frame_idx] if tif_chan2 is not None else None
                
                # Start row with frame number (1-indexed)
                row_data = [str(frame_idx + 1)]
                
                # Process each ROI
                for i, roi in enumerate(self.window._saved_rois):
                    xyxy = roi.get('xyxy')
                    if xyxy is None:
                        row_data.extend(["N/A", "N/A", "N/A"])
                        continue
                    
                    x0, y0, x1, y1 = xyxy
                    
                    # Extract green channel mean for this ROI
                    try:
                        # Create ellipse mask for this ROI
                        roi_height = y1 - y0
                        roi_width = x1 - x0
                        
                        if roi_height > 0 and roi_width > 0:
                            # Create ellipse mask
                            cy, cx = (y0 + y1) / 2.0, (x0 + x1) / 2.0
                            ry, rx = roi_height / 2.0, roi_width / 2.0
                            
                            y_coords, x_coords = np.ogrid[y0:y1, x0:x1]
                            mask = ((x_coords - cx) / rx) ** 2 + ((y_coords - cy) / ry) ** 2 <= 1
                            
                            # Extract green values
                            if mask.any():
                                green_roi_pixels = green_frame[y0:y1, x0:x1][mask]
                                green_mean = float(np.mean(green_roi_pixels))
                            else:
                                # Fallback to rectangular mean
                                green_mean = float(np.mean(green_frame[y0:y1, x0:x1]))
                        else:
                            green_mean = "N/A"
                    except Exception as e:
                        print(f"Error extracting green values for ROI {i+1}, frame {frame_idx}: {e}")
                        green_mean = "N/A"
                    
                    # Extract red channel mean for this ROI
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
                        print(f"Error extracting red values for ROI {i+1}, frame {frame_idx}: {e}")
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
                                  f"Successfully exported {len(self.window._saved_rois)} ROIs across {nframes} frames to:\n{filename}")
                                  
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export ROIs:\n{str(e)}")
            import traceback
            print("Full error traceback:")
            traceback.print_exc()

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
            from tools.bnc import BnCDialog, apply_bnc_to_image, create_qimage_from_array, create_composite_image
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
        from tools.bnc import apply_bnc_to_image, create_qimage_from_array, create_composite_image
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
                    self.reg_tif_label.size(),
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
            self.reg_tif_label.setPixmap(pix.scaled(self.reg_tif_label.size(), Qt.AspectRatioMode.KeepAspectRatio))
        except Exception as e:
            print(f"DEBUG: Error in legacy CNB adjustment: {e}")

    def _update_trace_from_roi(self, index=None):
        if self.window._current_tif is None or getattr(self.window, '_last_roi_xyxy', None) is None:
            # clear your plot if you want
            return
        x0, y0, x1, y1 = self.window._last_roi_xyxy

        def stack3d(a):
            a = np.asarray(a).squeeze()
            return a[None, ...] if a.ndim == 2 else a

        ch1 = stack3d(self.window._current_tif)
        sig1 = ch1[:, y0:y1, x0:x1].mean(axis=(1,2)) if (x1>x0 and y1>y0) else np.zeros((ch1.shape[0],), dtype=np.float32)

        ch2 = getattr(self.window, "_current_tif_chan2", None)
        sig2 = None
        if ch2 is not None:
            ch2 = stack3d(ch2)
            sig2 = ch2[:, y0:y1, x0:x1].mean(axis=(1,2))

        # Compute Fo (baseline) as mean over first 10% of frames of sig1
        nframes = sig1.shape[0]
        if nframes <= 0:
            return
        baseline_count = max(1, int(np.ceil(nframes * 0.10)))
        Fog = float(np.mean(sig1[:baseline_count]))

        self.trace_ax.cla()

        # Compute metric: (F_green - Fo_green) / F_red
        # If red channel missing, avoid division by zero by plotting NaNs
        if sig2 is None:
            metric = np.full_like(sig1, np.nan)
            self.formula_dropdown.setEnabled(False)
        else:
            self.formula_dropdown.setEnabled(True)
            formula_index = self.formula_dropdown.currentIndex() if index is None else index
            if formula_index == 0:
                denom = sig2.copy().astype(np.float32)
                denom[denom == 0] = 0 + 1e-6
                metric = (sig1 - Fog) / denom
            elif formula_index == 1:
                metric = (sig1 - Fog) / Fog
            elif formula_index == 2:
                metric = sig1
            elif formula_index == 3:
                if sig2 is None:
                    metric = np.full_like(sig1, 0)
                else:
                    metric = sig2


        current_frame = int(self.tif_slider.value()) if hasattr(self, 'tif_slider') else 0

        # Plot metric first, then create/move vline so it renders above plotted lines.
        self.trace_ax.plot(metric, label="(F green - Fo green)/F red", color='white')
        self.trace_ax.set_xlabel("Frame", color='white')
        self.window._frame_vline = self.trace_ax.axvline(current_frame, color='yellow', linestyle='-', zorder=20, linewidth=2)
        try:
            stims = []
            ed = getattr(self.window, '_exp_data', None)
            if ed is None:
                stims = []
            else:
                stims = getattr(ed, 'stimulation_timeframes', [])

            [self.trace_ax.axvline(int(stim), color='red', linestyle='--', zorder=15, linewidth=2) for stim in stims]
        except Exception:
            # keep plotting even if stim drawing fails
            pass

        # Parse y-limits from the QLineEdits (if present) and apply them
        try:
            def _parse(txt):
                try:
                    s = str(txt).strip()
                    return float(s) if s != '' else None
                except Exception:
                    return None

            ymin = None
            ymax = None
            if hasattr(self, 'ylim_min_edit'):
                ymin = _parse(self.ylim_min_edit.text())
            if hasattr(self, 'ylim_max_edit'):
                ymax = _parse(self.ylim_max_edit.text())

            # If both provided and inverted, swap
            if ymin is not None and ymax is not None and ymin > ymax:
                ymin, ymax = ymax, ymin

            if ymin is not None or ymax is not None:
                # If one side missing, keep current autoscaled value for that side
                cur = self.trace_ax.get_ylim()
                if ymin is None:
                    ymin = cur[0]
                if ymax is None:
                    ymax = cur[1]
                self.trace_ax.set_ylim(ymin, ymax)
        except Exception:
            pass

        self.trace_fig.tight_layout()
        self.trace_canvas.draw_idle()

    def _update_trace_vline(self):
        """Lightweight: update only the vertical frame line on the existing trace.
        This assumes the metric plot already exists; if not, it does nothing.
        """
        # If the axes are empty, don't try to add a vline (use full update instead)
        try:
            current_frame = int(self.tif_slider.value()) if hasattr(self, 'tif_slider') else 0
        except Exception:
            return

        # If there's no existing metric plotted, set sensible x-limits so a
        # standalone vline will be visible (use number of frames when available).
        if not self.trace_ax.lines:
            try:
                nframes = self.window._current_tif.shape[0] if getattr(self.window, '_current_tif', None) is not None and getattr(self.window, '_current_tif', None).ndim >= 3 else 1
            except Exception:
                nframes = 1
            # ensure at least 1 on the x-axis
            xmax = max(1, nframes - 1)
            try:
                self.trace_ax.set_xlim(0, xmax)
            except Exception:
                pass

        # Ensure we have a persistent vline and move it (create if missing)
        if not hasattr(self.window, '_frame_vline') or self.window._frame_vline is None:
            self.window._frame_vline = self.trace_ax.axvline(current_frame, color='yellow', linestyle='-', zorder=10, linewidth=2)
        else:
            try:
                self.window._frame_vline.set_xdata([current_frame, current_frame])
            except Exception:
                # recreate fallback
                self.window._frame_vline = self.trace_ax.axvline(current_frame, color='yellow', linestyle='-', zorder=10, linewidth=2)

        # Redraw canvas (fast)
        try:
            self.trace_canvas.draw_idle()
        except Exception:
            pass

    def _reset_ylim(self):
        """Clear any user-set y-limits and revert to autoscaling."""
        if hasattr(self, 'ylim_min_edit'):
            self.ylim_min_edit.setText("")
        if hasattr(self, 'ylim_max_edit'):
            self.ylim_max_edit.setText("")
        self._update_trace_from_roi()
    
    def _compute_draw_rect_for_label(self, label, img_w: int, img_h: int):
        """Return the QRect inside `label` where the image pixmap will be drawn
        when scaled with aspect ratio preserved."""
        lw, lh = label.width(), label.height()
        if img_w <= 0 or img_h <= 0 or lw <= 0 or lh <= 0:
            from PyQt6.QtCore import QRect
            return QRect(0, 0, 0, 0)

        scale = min(lw / img_w, lh / img_h)
        sw = int(img_w * scale)  # scaled width
        sh = int(img_h * scale)  # scaled height
        x = (lw - sw) // 2
        y = (lh - sh) // 2

        from PyQt6.QtCore import QRect
        return QRect(x, y, sw, sh)

    def keyPressEvent(self, event):
        """Handle key press events. Escape clears the current ROI selection and trace plot."""
        from PyQt6.QtCore import Qt
        
        if event.key() == Qt.Key.Key_Escape:
            # Clear only the current interactive selection and trace; keep saved ROIs visible
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
            self._on_add_roi_clicked()
            event.accept()
        elif event.key() == Qt.Key.Key_Delete:
            self._on_remove_roi_clicked()
            event.accept()
        elif event.key() == Qt.Key.Key_S and event.modifiers() == Qt.KeyboardModifier.AltModifier:
            self._load_stimulated_rois()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _clear_roi_and_trace(self):
        """Clear the current ROI selection and restart the trace plot."""
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
        
        # Clear the stored ROI coordinates
        if hasattr(self.window, '_last_roi_xyxy'):
            self.window._last_roi_xyxy = None
        
        # Clear the trace plot
        if hasattr(self, 'trace_ax') and self.trace_ax is not None:
            self.trace_ax.cla()
            
            # Reset the plot appearance
            self.trace_ax.set_xticks([])
            self.trace_ax.set_yticks([])
            self.trace_ax.set_xlabel("")
            self.trace_ax.set_ylabel("")
            for spine in self.trace_ax.spines.values():
                spine.set_visible(True)
            self.trace_ax.set_facecolor('none')
            self.trace_ax.xaxis.label.set_color('white')
            self.trace_ax.yaxis.label.set_color('white')
            self.trace_ax.tick_params(axis='x', colors='white')
            self.trace_ax.tick_params(axis='y', colors='white')
            for spine in self.trace_ax.spines.values():
                spine.set_color('white')
                
        # Clear the frame vline reference
        if hasattr(self.window, '_frame_vline'):
            self.window._frame_vline = None
            
        # Redraw the trace canvas
        if hasattr(self, 'trace_canvas') and self.trace_canvas is not None:
            self.trace_fig.tight_layout()
            self.trace_canvas.draw()

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
