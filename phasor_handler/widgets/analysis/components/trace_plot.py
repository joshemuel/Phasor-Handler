"""
TraceplotWidget - A standalone widget for trace plotting functionality.

This widget encapsulates all trace plotting logic including:
- Y-limit controls
- Formula selection dropdown
- Time display toggle
- Matplotlib figure and canvas
- Signal extraction and plotting methods
"""

import numpy as np
import matplotlib.pyplot as plt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QComboBox, QSizePolicy, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QLocale
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from phasor_handler.tools.lazy_stack import LazyFrameStack, to_stack3d


class TraceplotWidget(QWidget):
    """A widget that handles all trace plotting functionality."""
    
    # Signal emitted when trace plot needs to update due to user controls
    traceUpdateRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = None  # Will be set by parent
        self._show_time_in_seconds = True  # Track current display mode
        self._frame_vline = None  # Reference to the current frame line
        self._ylim_user_modified = False  # Track if user has manually changed y-limits
        
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the UI components for trace plotting."""
        # Main layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Left side: Controls
        controls_layout = QVBoxLayout()
        
        # Y limits inputs
        ylim_layout = QVBoxLayout()
        ylim_layout.setSpacing(2)
        ylim_layout.setContentsMargins(0, 0, 0, 0)

        ylim_label_inner = QHBoxLayout()
        ylim_label_inner.setContentsMargins(0, 0, 0, 0)

        ylim_label = QLabel("Y limits:")
        ylim_label.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        ylim_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.ylim_min_edit = QDoubleSpinBox()
        self.ylim_min_edit.setFixedWidth(70)
        self.ylim_min_edit.setFixedHeight(20)
        self.ylim_min_edit.setRange(-999999.99, 999999.99)
        self.ylim_min_edit.setSingleStep(0.01)
        self.ylim_min_edit.setDecimals(3)
        self.ylim_min_edit.setValue(-0.05)  # Start at a neutral value
        self.ylim_min_edit.setEnabled(False)  # Disabled until ROI is drawn
        self.ylim_min_edit.valueChanged.connect(self._on_ylim_changed)

        self.ylim_max_edit = QDoubleSpinBox()
        self.ylim_max_edit.setFixedWidth(70)
        self.ylim_max_edit.setFixedHeight(20)
        self.ylim_max_edit.setRange(-999999.99, 999999.99)
        self.ylim_max_edit.setSingleStep(0.01)
        self.ylim_max_edit.setDecimals(3)
        self.ylim_max_edit.setValue(0.5)  # Start at a neutral value
        self.ylim_max_edit.setEnabled(False)  # Disabled until ROI is drawn
        self.ylim_max_edit.valueChanged.connect(self._on_ylim_changed)

        ylim_label_inner.addWidget(self.ylim_min_edit)
        ylim_label_inner.addWidget(self.ylim_max_edit)
        ylim_label_inner.addStretch()

        self.reset_ylim_button = QPushButton("Auto")
        self.reset_ylim_button.setFixedWidth(50)
        self.reset_ylim_button.setFixedHeight(20)
        self.reset_ylim_button.clicked.connect(self._reset_ylim)

        ylim_layout.addWidget(ylim_label)
        ylim_layout.addLayout(ylim_label_inner)
        ylim_layout.addSpacing(4)
        ylim_layout.addWidget(self.reset_ylim_button)
        controls_layout.addLayout(ylim_layout)

        # Add spacing between sections
        controls_layout.addSpacing(10)

        # Baseline seconds spinbox
        baseline_layout = QVBoxLayout()
        baseline_layout.setSpacing(0)  # Small spacing between label and spinbox
        baseline_layout.setContentsMargins(0, 0, 0, 0)
        baseline_label = QLabel("Baseline (s):")
        baseline_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        baseline_layout.addWidget(baseline_label)
        self.base_spinbox = QDoubleSpinBox()
        c_locale = QLocale(QLocale.Language.C)
        c_locale.setNumberOptions(QLocale.NumberOption.RejectGroupSeparator)
        self.base_spinbox.setLocale(c_locale)
        self.base_spinbox.setRange(0.1, 9999.0)
        self.base_spinbox.setValue(5.0)
        self.base_spinbox.setSingleStep(0.5)
        self.base_spinbox.setDecimals(1)
        self.base_spinbox.setSuffix(" s")
        self.base_spinbox.setFixedWidth(80)
        self.base_spinbox.setFixedHeight(25)
        self.base_spinbox.valueChanged.connect(self._update_trace_from_roi)
        baseline_layout.addWidget(self.base_spinbox)
        controls_layout.addLayout(baseline_layout)

        # Add spacing between sections
        controls_layout.addSpacing(10)

        # Formula dropdown
        self.formula_dropdown = QComboBox()
        self.formula_dropdown.setFixedWidth(100)
        self.formula_dropdown.setStyleSheet("QComboBox { font-size: 8pt; }")
        self.formula_dropdown.addItem("Fg - Fog / Fr")
        self.formula_dropdown.addItem("Fg - Fog / Fog")
        self.formula_dropdown.addItem("Fg only")
        self.formula_dropdown.addItem("Fr only")
        self.formula_dropdown.setContentsMargins(0, 0, 0, 0)
        self.formula_dropdown.currentIndexChanged.connect(self._update_trace_from_roi)
        controls_layout.addWidget(self.formula_dropdown)

        controls_layout.addSpacing(15)

        # Time display toggle button
        self.time_display_button = QPushButton("Seconds")
        self.time_display_button.setFixedWidth(100)
        self.time_display_button.setFixedHeight(20)
        self.time_display_button.setCheckable(True)
        self.time_display_button.setChecked(True)  # Default to seconds
        self.time_display_button.setStyleSheet("QPushButton { font-size: 8pt; }")
        self.time_display_button.setToolTip("Toggle between frame numbers and time in seconds")
        self.time_display_button.clicked.connect(self._toggle_time_display)
        controls_layout.addWidget(self.time_display_button)
        
        main_layout.addLayout(controls_layout, 0) 

        # Right side: Figure and canvas
        self.trace_fig, self.trace_ax = plt.subplots(figsize=(12, 6), dpi=100)
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
        self.trace_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.trace_ax.xaxis.label.set_color('white')
        self.trace_ax.yaxis.label.set_color('white')
        self.trace_ax.tick_params(axis='x', colors='white')
        self.trace_ax.tick_params(axis='y', colors='white')
        for spine in self.trace_ax.spines.values():
            spine.set_color('white')
        self.trace_fig.tight_layout()
        
        main_layout.addWidget(self.trace_canvas, 1)  # Give stretch factor of 1 to make it expand

        self.setLayout(main_layout)
        
    def set_main_window(self, main_window):
        """Set reference to the main window for accessing data."""
        self.main_window = main_window
        
        # Store user overrides on main window for compatibility
        if not hasattr(main_window, '_ylim_min_user'):
            main_window._ylim_min_user = None
        if not hasattr(main_window, '_ylim_max_user'):
            main_window._ylim_max_user = None
            
    def get_widgets_for_compatibility(self):
        """Return a dict of widgets for backward compatibility."""
        return {
            'ylim_min_edit': self.ylim_min_edit,
            'ylim_max_edit': self.ylim_max_edit,
            'reset_ylim_button': self.reset_ylim_button,
            'formula_dropdown': self.formula_dropdown,
            'time_display_button': self.time_display_button,
            'trace_fig': self.trace_fig,
            'trace_ax': self.trace_ax,
            'trace_canvas': self.trace_canvas
        }

    def _mean_trace_for_region(self, stack, x0, y0, x1, y1, mask=None, chunk_size=256):
        """Compute a mean trace without materializing lazy split stacks."""
        stack = to_stack3d(stack)
        if stack is None:
            return None

        if isinstance(stack, LazyFrameStack):
            values = []
            for _, chunk in stack.iter_chunks(chunk_size):
                crop = chunk[:, y0:y1, x0:x1]
                if mask is not None and mask.size > 0 and np.any(mask) and crop.shape[1:] == mask.shape:
                    values.append(crop[:, mask].mean(axis=1))
                else:
                    values.append(crop.mean(axis=(1, 2)))
            return np.concatenate(values).astype(np.float32) if values else np.array([], dtype=np.float32)

        crop = stack[:, y0:y1, x0:x1]
        if mask is not None and mask.size > 0 and np.any(mask) and crop.shape[1:] == mask.shape:
            return crop[:, mask].mean(axis=1).astype(np.float32)
        return crop.mean(axis=(1, 2)).astype(np.float32)

    def _update_trace_from_roi(self, index=None):
        """Update the trace plot based on current ROI selection."""
        print(f"DEBUG: TraceplotWidget._update_trace_from_roi called with index={index}")
        
        # Check conditions
        has_main_window = self.main_window is not None
        has_current_tif = self.main_window._current_tif is not None if has_main_window else False
        has_roi_xyxy = getattr(self.main_window, '_last_roi_xyxy', None) is not None if has_main_window else False
        
        print(f"DEBUG: has_main_window={has_main_window}, has_current_tif={has_current_tif}, has_roi_xyxy={has_roi_xyxy}")
        
        if not has_main_window or not has_current_tif or not has_roi_xyxy:
            print("DEBUG: Early return - missing required data")
            # Disable y-limit spinboxes when no ROI is drawn
            if hasattr(self, 'ylim_min_edit'):
                self.ylim_min_edit.setEnabled(False)
            if hasattr(self, 'ylim_max_edit'):
                self.ylim_max_edit.setEnabled(False)
            if hasattr(self, 'reset_ylim_button'):
                self.reset_ylim_button.setEnabled(False)
            # Reset user modification flag when ROI is cleared
            self._ylim_user_modified = False
            return
        
        print(f"DEBUG: ROI xyxy: {self.main_window._last_roi_xyxy}")
        print(f"DEBUG: Image shape: {self.main_window._current_tif.shape}")
        
        # Get the ellipse mask from the ROI tool (handles rotation correctly)
        mask_result = None
        try:
            if hasattr(self.main_window, 'roi_tool'):
                mask_result = self.main_window.roi_tool.get_ellipse_mask()
                print(f"DEBUG: Got ellipse mask result: {mask_result is not None}")
        except Exception as e:
            print(f"Warning: Could not get ellipse mask: {e}")
        
        if mask_result is None:
            # Fallback to rectangular region
            print(f"DEBUG: No masks found. Using rectangular ROI for signal extraction")
            x0, y0, x1, y1 = self.main_window._last_roi_xyxy

            ch1 = to_stack3d(self.main_window._current_tif)
            sig1 = self._mean_trace_for_region(ch1, x0, y0, x1, y1) if (x1>x0 and y1>y0) else np.zeros((ch1.shape[0],), dtype=np.float32)

            ch2 = getattr(self.main_window, "_current_tif_chan2", None)
            sig2 = None
            if ch2 is not None:
                ch2 = to_stack3d(ch2)
                sig2 = self._mean_trace_for_region(ch2, x0, y0, x1, y1)
        else:
            # Use ellipse mask for proper signal extraction
            X0, Y0, X1, Y1, mask = mask_result

            ch1 = to_stack3d(self.main_window._current_tif)
            
            # Extract signal using the ellipse mask
            if mask.size > 0 and np.any(mask):
                sig1 = self._mean_trace_for_region(ch1, X0, Y0, X1, Y1, mask)
            else:
                sig1 = np.zeros((ch1.shape[0],), dtype=np.float32)

            ch2 = getattr(self.main_window, "_current_tif_chan2", None)
            sig2 = None
            if ch2 is not None:
                ch2 = to_stack3d(ch2)
                if mask.size > 0 and np.any(mask):
                    sig2 = self._mean_trace_for_region(ch2, X0, Y0, X1, Y1, mask)
                else:
                    sig2 = np.zeros((ch2.shape[0],), dtype=np.float32)

        if sig2 is not None and len(sig2) != len(sig1):
            common_len = min(len(sig1), len(sig2))
            sig1 = sig1[:common_len]
            sig2 = sig2[:common_len]

        # Compute Fo (baseline) as mean over first N seconds of frames of sig1
        nframes = sig1.shape[0]
        if nframes <= 0:
            return
        # Cap baseline spinbox to total recording duration
        self.update_baseline_max()
        # Determine baseline frame count from base_spinbox (seconds).
        try:
            baseline_seconds = float(self.base_spinbox.value()) if hasattr(self, 'base_spinbox') else 5.0
            baseline_seconds = max(0.1, baseline_seconds)
            baseline_count = self._seconds_to_frame_count(baseline_seconds, nframes)
        except Exception:
            baseline_count = max(1, nframes // 10)

        baseline_count = max(1, min(baseline_count, nframes))
        Fog = float(np.mean(sig1[:baseline_count]))

        self.trace_ax.cla()

        # Compute metric depending on available channels and selected formula
        # If red channel missing, show only single-channel formulas
        if sig2 is None:
            # Single-channel data: limit dropdown to (Fg - Fo)/Fo and raw Fg only
            # Only modify dropdown if it currently has more than 2 items (switching from dual to single channel)
            if self.formula_dropdown.count() > 2:
                self.formula_dropdown.blockSignals(True)
                current_index = self.formula_dropdown.currentIndex()
                
                # Clear and repopulate with single-channel options only
                self.formula_dropdown.clear()
                self.formula_dropdown.addItem("(Fg - Fog) / Fog")  # Index 0 for single channel
                self.formula_dropdown.addItem("Fg only")            # Index 1 for single channel
                
                # Set appropriate default selection based on previous selection
                if current_index == 2:  # Was "Fg only"
                    self.formula_dropdown.setCurrentIndex(1)
                else:  # Default to (Fg - Fog) / Fog
                    self.formula_dropdown.setCurrentIndex(0)
                
                self.formula_dropdown.blockSignals(False)
                print("DEBUG: Switched to single-channel formula dropdown")

            # Calculate metric based on selected formula
            formula_index = self.formula_dropdown.currentIndex() if index is None else index
            if formula_index == 1:  # Fg only (raw)
                metric = sig1
            else:  # (Fg - Fog) / Fog (default, index 0)
                denom_val = Fog if (Fog is not None and Fog != 0) else 1e-6
                metric = (sig1 - Fog) / denom_val
        else:
            # Two-channel data: restore all formula options
            # Only modify dropdown if it currently has 2 items (switching from single to dual channel)
            if self.formula_dropdown.count() == 2:
                self.formula_dropdown.blockSignals(True)
                current_index = self.formula_dropdown.currentIndex()
                
                # Clear and repopulate with all formula options
                self.formula_dropdown.clear()
                self.formula_dropdown.addItem("Fg - Fog / Fr")      # Index 0
                self.formula_dropdown.addItem("Fg - Fog / Fog")     # Index 1
                self.formula_dropdown.addItem("Fg only")            # Index 2
                self.formula_dropdown.addItem("Fr only")            # Index 3
                
                # Restore appropriate selection based on previous selection
                if current_index == 1:  # Was "Fg only" in single-channel mode
                    self.formula_dropdown.setCurrentIndex(2)  # Set to "Fg only" in two-channel mode
                else:  # Was "(Fg - Fog) / Fog"
                    self.formula_dropdown.setCurrentIndex(1)  # Keep as "(Fg - Fog) / Fog"
                
                self.formula_dropdown.blockSignals(False)
                print("DEBUG: Switched to dual-channel formula dropdown")
            
            formula_index = self.formula_dropdown.currentIndex() if index is None else index
            if formula_index == 0:
                denom = sig2.copy().astype(np.float32)
                denom[denom == 0] = 1e-6
                metric = (sig1 - Fog) / denom
            elif formula_index == 1:
                denom_val = Fog if (Fog is not None and Fog != 0) else 1e-6
                metric = (sig1 - Fog) / denom_val
            elif formula_index == 2:
                metric = sig1
            elif formula_index == 3:
                metric = sig2 if sig2 is not None else np.full_like(sig1, 0)
            else:
                # Default fallback for any unexpected formula_index
                denom_val = Fog if (Fog is not None and Fog != 0) else 1e-6
                metric = (sig1 - Fog) / denom_val

        current_frame = 0
        if hasattr(self.main_window, 'tif_slider'):
            try:
                current_frame = int(self.main_window.tif_slider.value())
            except Exception:
                current_frame = 0

        # Determine x-axis values and labels based on time display mode
        show_time = getattr(self, '_show_time_in_seconds', False)
        x_values = None
        x_label = "Frame"
        current_x_pos = current_frame
        resolved = None

        if show_time:
            from phasor_handler.tools.misc import resolve_timestamps
            ed = getattr(self.main_window, '_exp_data', None)
            resolved = resolve_timestamps(ed, len(metric))
            if resolved is not None:
                x_values = np.array(resolved[:len(metric)])
                x_label = "Time (s)"
                if current_frame < len(x_values):
                    current_x_pos = x_values[current_frame]
                else:
                    current_x_pos = x_values[-1] if len(x_values) > 0 else current_frame
            else:
                show_time = False

        # Plot metric with appropriate x-axis
        if x_values is not None:
            self.trace_ax.plot(x_values, metric, label="(F green - Fo green)/F red", color='white')
        else:
            self.trace_ax.plot(metric, label="(F green - Fo green)/F red", color='white')
        
        self.trace_ax.set_xlabel(x_label, color='white', labelpad=2)
        self.trace_ax.tick_params(axis='x', pad=1, labelsize=9)
        self._frame_vline = self.trace_ax.axvline(current_x_pos, color='yellow', linestyle='-', zorder=20, linewidth=2)
        
        # Store frame vline reference on main window for compatibility
        if self.main_window:
            self.main_window._frame_vline = self._frame_vline
        
        try:
            stims = []
            ed = getattr(self.main_window, '_exp_data', None)
            if ed is None:
                stims = []
            else:
                # Handle both dictionary and object metadata formats
                if isinstance(ed, dict):
                    stims = ed.get('stimulation_timeframes', [])
                else:
                    stims = getattr(ed, 'stimulation_timeframes', [])
                
                print(f"DEBUG: Found {len(stims)} stimulation timeframes: {stims}")

            # Convert stimulation timeframes to appropriate x-axis units
            if show_time and x_values is not None and resolved is not None:
                for stim in stims:
                    stim_frame = int(stim)
                    if stim_frame < len(resolved):
                        stim_x_pos = resolved[stim_frame]
                        self.trace_ax.axvline(stim_x_pos, color='red', linestyle='--', zorder=15, linewidth=2)
            else:
                for stim in stims:
                    stim_frame = int(stim)
                    self.trace_ax.axvline(stim_frame, color='red', linestyle='--', zorder=15, linewidth=2)
        except Exception as e:
            # keep plotting even if stim drawing fails
            print(f"DEBUG: Error adding stimulation vlines: {e}")
            pass

        # Get the data range for auto-populating y-limits
        data_min = np.min(metric) if len(metric) > 0 else 0.0
        data_max = np.max(metric) if len(metric) > 0 else 1.0
        
        # Add some padding (5%) to the data range for better visualization
        data_range = data_max - data_min
        if data_range > 0:
            data_min -= data_range * 0.05
            data_max += data_range * 0.05
        
        # Enable spinboxes since we have an ROI drawn
        # Only auto-set spinbox values if user hasn't manually modified them
        try:
            should_auto_populate = not getattr(self, '_ylim_user_modified', False)
            print(f"DEBUG: Y-limit auto-populate: {should_auto_populate}, user_modified flag: {getattr(self, '_ylim_user_modified', False)}")
            
            if hasattr(self, 'ylim_min_edit'):
                self.ylim_min_edit.setEnabled(True)
                # Only auto-populate when user hasn't manually set values
                if should_auto_populate:
                    self.ylim_min_edit.blockSignals(True)
                    self.ylim_min_edit.setValue(data_min)
                    self.ylim_min_edit.blockSignals(False)
                    
            if hasattr(self, 'ylim_max_edit'):
                self.ylim_max_edit.setEnabled(True)
                # Only auto-populate when user hasn't manually set values
                if should_auto_populate:
                    self.ylim_max_edit.blockSignals(True)
                    self.ylim_max_edit.setValue(data_max)
                    self.ylim_max_edit.blockSignals(False)
                
            if hasattr(self, 'reset_ylim_button'):
                self.reset_ylim_button.setEnabled(True)

            # Apply the y-limits to the plot
            # Use spinbox values if user has set them, otherwise use data range
            if should_auto_populate:
                # Auto mode - use calculated data range
                self.trace_ax.set_ylim(data_min, data_max)
            else:
                # User has set custom values - use spinbox values
                y_min = self.ylim_min_edit.value() if hasattr(self, 'ylim_min_edit') else data_min
                y_max = self.ylim_max_edit.value() if hasattr(self, 'ylim_max_edit') else data_max
                self.trace_ax.set_ylim(y_min, y_max)
        except Exception as e:
            print(f"DEBUG: Error setting y-limits: {e}")
            pass

        self.trace_fig.tight_layout()
        self.trace_canvas.draw_idle()

    def _update_trace_vline(self):
        """Lightweight: update only the vertical frame line on the existing trace."""
        if self.main_window is None:
            return
            
        # If the axes are empty, don't try to add a vline (use full update instead)
        try:
            current_frame = 0
            if hasattr(self.main_window, 'tif_slider'):
                current_frame = int(self.main_window.tif_slider.value())
        except Exception:
            return

        # Determine current position based on time display mode
        show_time = getattr(self, '_show_time_in_seconds', False)
        current_x_pos = current_frame
        
        if show_time:
            try:
                ed = getattr(self.main_window, '_exp_data', None)
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
                
                if time_stamps is not None and len(time_stamps) > 0 and current_frame < len(time_stamps):
                    # Handle both datetime strings and numeric timestamps
                    if isinstance(time_stamps[0], str):
                        # Parse datetime strings
                        from datetime import datetime
                        try:
                            first_dt = datetime.strptime(time_stamps[0], '%Y-%m-%d %H:%M:%S.%f')
                            current_dt = datetime.strptime(time_stamps[current_frame], '%Y-%m-%d %H:%M:%S.%f')
                            current_x_pos = (current_dt - first_dt).total_seconds()
                        except Exception:
                            # Fall back to frame rate if parsing fails
                            pass
                    else:
                        # Numeric timestamps - detect if milliseconds or seconds
                        max_time = np.max(time_stamps) if len(time_stamps) > 0 else 0
                        if max_time > 10000:
                            # Data is in milliseconds, convert to seconds
                            current_x_pos = time_stamps[current_frame] / 1000.0
                        else:
                            # Data is already in seconds
                            current_x_pos = time_stamps[current_frame]
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
                nframes = 1
                if (hasattr(self.main_window, '_current_tif') and 
                    self.main_window._current_tif is not None and 
                    self.main_window._current_tif.ndim >= 3):
                    nframes = self.main_window._current_tif.shape[0]
                
                # Set x-limits based on display mode
                if show_time:
                    # Try to get max time value
                    try:
                        ed = getattr(self.main_window, '_exp_data', None)
                        time_stamps = None
                        
                        if ed is not None:
                            for attr_name in ['time_stamps', 'timeStamps', 'timestamps', 'ElapsedTimes']:
                                if hasattr(ed, attr_name):
                                    time_stamps = getattr(ed, attr_name)
                                    break
                        
                        if time_stamps is not None and len(time_stamps) > 0:
                            # Handle both datetime strings and numeric timestamps
                            if isinstance(time_stamps[0], str):
                                # Parse datetime strings
                                from datetime import datetime
                                try:
                                    first_dt = datetime.strptime(time_stamps[0], '%Y-%m-%d %H:%M:%S.%f')
                                    last_idx = min(nframes, len(time_stamps)) - 1
                                    last_dt = datetime.strptime(time_stamps[last_idx], '%Y-%m-%d %H:%M:%S.%f')
                                    xmax = (last_dt - first_dt).total_seconds()
                                except Exception:
                                    xmax = max(1, nframes - 1)
                            else:
                                # Numeric timestamps - detect if milliseconds or seconds
                                time_array = np.array(time_stamps[:min(nframes, len(time_stamps))])
                                max_time = np.max(time_array) if len(time_array) > 0 else 0
                                
                                if max_time > 10000:
                                    # Data is in milliseconds, convert to seconds
                                    xmax = max(time_array / 1000.0)
                                else:
                                    # Data is already in seconds
                                    xmax = max(time_array)
                        elif ed is not None:
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
        if not hasattr(self, '_frame_vline') or self._frame_vline is None:
            self._frame_vline = self.trace_ax.axvline(current_x_pos, color='yellow', linestyle='-', zorder=10, linewidth=2)
            if self.main_window:
                self.main_window._frame_vline = self._frame_vline
        else:
            try:
                self._frame_vline.set_xdata([current_x_pos, current_x_pos])
            except Exception:
                # recreate fallback
                self._frame_vline = self.trace_ax.axvline(current_x_pos, color='yellow', linestyle='-', zorder=10, linewidth=2)
                if self.main_window:
                    self.main_window._frame_vline = self._frame_vline

        # Redraw canvas (fast)
        try:
            self.trace_canvas.draw_idle()
        except Exception:
            pass

    def _on_ylim_changed(self):
        """Handle manual changes to y-limit spinboxes - update plot without recalculating trace."""
        if not hasattr(self, 'ylim_min_edit') or not hasattr(self, 'ylim_max_edit'):
            return
        
        # Mark that user has manually modified the y-limits
        self._ylim_user_modified = True
        
        try:
            y_min = self.ylim_min_edit.value()
            y_max = self.ylim_max_edit.value()
            
            # Apply the new limits to the plot
            if hasattr(self, 'trace_ax') and self.trace_ax is not None:
                self.trace_ax.set_ylim(y_min, y_max)
                
            # Redraw the canvas
            if hasattr(self, 'trace_canvas') and self.trace_canvas is not None:
                self.trace_canvas.draw_idle()
        except Exception as e:
            print(f"DEBUG: Error updating y-limits: {e}")
    
    def _reset_ylim(self):
        """Reset y-limits to the current ROI's data range."""
        # Clear the user modification flag so values will auto-populate for new ROIs
        self._ylim_user_modified = False
        
        # Trigger a full trace update which will auto-reset to data min/max
        self._update_trace_from_roi()
    
    def _toggle_time_display(self):
        """Toggle between showing frame numbers and time in seconds on the trace plot."""
        self._show_time_in_seconds = not getattr(self, '_show_time_in_seconds', False)
        
        # Update button text to show current mode
        if self._show_time_in_seconds:
            self.time_display_button.setText("Seconds")
        else:
            self.time_display_button.setText("Frames")
        
        # Update the trace plot with new x-axis
        self._update_trace_from_roi()

    def _seconds_to_frame_count(self, seconds, nframes):
        """Convert a duration in seconds to a number of frames using metadata.

        Tries to use timestamps from experiment data; falls back to frame_rate,
        and finally to a simple 10 % heuristic if nothing is available.

        Args:
            seconds: baseline duration in seconds
            nframes: total number of frames in the recording

        Returns:
            int: number of frames that cover the requested duration
        """
        ed = getattr(self.main_window, '_exp_data', None) if self.main_window else None
        if ed is None:
            # No metadata – fall back to 10 % of frames
            return max(1, nframes // 10)

        # --- Try timestamps first ---
        time_stamps = None
        for attr_name in ['time_stamps', 'timeStamps', 'timestamps', 'ElapsedTimes']:
            if isinstance(ed, dict):
                if attr_name in ed:
                    time_stamps = ed[attr_name]
                    break
            else:
                if hasattr(ed, attr_name):
                    time_stamps = getattr(ed, attr_name)
                    break

        if time_stamps is not None and hasattr(time_stamps, '__len__') and len(time_stamps) > 0:
            try:
                if isinstance(time_stamps[0], str):
                    # Parse datetime strings
                    from datetime import datetime
                    first_dt = datetime.strptime(time_stamps[0], '%Y-%m-%d %H:%M:%S.%f')
                    for idx in range(min(nframes, len(time_stamps))):
                        dt = datetime.strptime(time_stamps[idx], '%Y-%m-%d %H:%M:%S.%f')
                        elapsed = (dt - first_dt).total_seconds()
                        if elapsed >= seconds:
                            return max(1, idx)
                    return min(nframes, len(time_stamps))
                else:
                    # Numeric timestamps – detect ms vs s
                    import numpy as _np
                    ts_arr = _np.asarray(time_stamps[:min(nframes, len(time_stamps))], dtype=float)
                    max_t = float(ts_arr[-1]) if len(ts_arr) > 0 else 0
                    if max_t > 10000:
                        # milliseconds
                        target_ms = seconds * 1000.0
                        indices = _np.where(ts_arr >= target_ms)[0]
                    else:
                        indices = _np.where(ts_arr >= seconds)[0]
                    if len(indices) > 0:
                        return max(1, int(indices[0]))
                    return min(nframes, len(ts_arr))
            except Exception:
                pass

        # --- Fallback: frame_rate ---
        frame_rate = None
        if isinstance(ed, dict):
            frame_rate = ed.get('frame_rate', None)
        else:
            frame_rate = getattr(ed, 'frame_rate', None)

        if frame_rate is not None and frame_rate != 'NA':
            try:
                fr = float(frame_rate)
                if fr > 0:
                    return max(1, int(np.ceil(fr * seconds)))
            except (ValueError, TypeError):
                pass

        # --- Last resort: 10 % ---
        return max(1, nframes // 10)

    def _get_total_recording_seconds(self, nframes):
        """Estimate total recording duration in seconds from metadata.

        Uses timestamps or frame_rate from experiment data.
        Returns None if the duration cannot be determined.
        """
        ed = getattr(self.main_window, '_exp_data', None) if self.main_window else None
        if ed is None:
            return None

        # --- Try timestamps ---
        time_stamps = None
        for attr_name in ['time_stamps', 'timeStamps', 'timestamps', 'ElapsedTimes']:
            if isinstance(ed, dict):
                if attr_name in ed:
                    time_stamps = ed[attr_name]
                    break
            else:
                if hasattr(ed, attr_name):
                    time_stamps = getattr(ed, attr_name)
                    break

        if time_stamps is not None and hasattr(time_stamps, '__len__') and len(time_stamps) > 0:
            try:
                if isinstance(time_stamps[0], str):
                    from datetime import datetime
                    first_dt = datetime.strptime(time_stamps[0], '%Y-%m-%d %H:%M:%S.%f')
                    last_idx = min(nframes, len(time_stamps)) - 1
                    last_dt = datetime.strptime(time_stamps[last_idx], '%Y-%m-%d %H:%M:%S.%f')
                    return (last_dt - first_dt).total_seconds()
                else:
                    import numpy as _np
                    ts_arr = _np.asarray(time_stamps[:min(nframes, len(time_stamps))], dtype=float)
                    max_t = float(ts_arr[-1]) if len(ts_arr) > 0 else 0
                    if max_t > 10000:
                        return max_t / 1000.0  # ms -> s
                    else:
                        return max_t
            except Exception:
                pass

        # --- Fallback: frame_rate ---
        frame_rate = None
        if isinstance(ed, dict):
            frame_rate = ed.get('frame_rate', None)
        else:
            frame_rate = getattr(ed, 'frame_rate', None)

        if frame_rate is not None and frame_rate != 'NA':
            try:
                fr = float(frame_rate)
                if fr > 0:
                    return nframes / fr
            except (ValueError, TypeError):
                pass

        return None

    def update_baseline_max(self):
        """Update baseline spinbox maximum based on total recording time."""
        if self.main_window is None:
            return
        current_tif = getattr(self.main_window, '_current_tif', None)
        if current_tif is None:
            return
        nframes = current_tif.shape[0] if current_tif.ndim == 3 else 1
        total_s = self._get_total_recording_seconds(nframes)
        if total_s is not None and total_s > 0:
            self.base_spinbox.setMaximum(round(total_s, 1))
        else:
            self.base_spinbox.setMaximum(9999.0)

    def clear_trace(self):
        """Clear the trace plot and reset it to initial state."""
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
        
        # Disable and reset y-limit spinboxes when trace is cleared
        if hasattr(self, 'ylim_min_edit'):
            self.ylim_min_edit.setEnabled(False)
            
        if hasattr(self, 'ylim_max_edit'):
            self.ylim_max_edit.setEnabled(False)
            
        if hasattr(self, 'reset_ylim_button'):
            self.reset_ylim_button.setEnabled(False)
        
        # Reset user modification flag when trace is cleared
        self._ylim_user_modified = False
                
        # Clear the frame vline reference
        if hasattr(self, '_frame_vline'):
            self._frame_vline = None
        if self.main_window and hasattr(self.main_window, '_frame_vline'):
            self.main_window._frame_vline = None
            
        # Redraw the trace canvas
        if hasattr(self, 'trace_canvas') and self.trace_canvas is not None:
            self.trace_fig.tight_layout()
            self.trace_canvas.draw()
