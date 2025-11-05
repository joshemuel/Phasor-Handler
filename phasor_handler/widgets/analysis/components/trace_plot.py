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
from PyQt6.QtCore import Qt, pyqtSignal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


class TraceplotWidget(QWidget):
    """A widget that handles all trace plotting functionality."""
    
    # Signal emitted when trace plot needs to update due to user controls
    traceUpdateRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = None  # Will be set by parent
        self._show_time_in_seconds = False  # Track current display mode
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

        # Baseline percentage spinbox
        baseline_layout = QVBoxLayout()
        baseline_layout.setSpacing(0)  # Small spacing between label and spinbox
        baseline_layout.setContentsMargins(0, 0, 0, 0)
        baseline_label = QLabel("Baseline %:")
        baseline_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        baseline_layout.addWidget(baseline_label)
        self.base_spinbox = QSpinBox()
        self.base_spinbox.setRange(1, 99)
        self.base_spinbox.setValue(10)
        self.base_spinbox.setFixedWidth(60)
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
        self.time_display_button = QPushButton("Frames")
        self.time_display_button.setFixedWidth(100)
        self.time_display_button.setFixedHeight(20)
        self.time_display_button.setCheckable(True)
        self.time_display_button.setChecked(False)  # Default to frames
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
            def stack3d(a):
                a = np.asarray(a).squeeze()
                return a[None, ...] if a.ndim == 2 else a

            ch1 = stack3d(self.main_window._current_tif)
            sig1 = ch1[:, y0:y1, x0:x1].mean(axis=(1,2)) if (x1>x0 and y1>y0) else np.zeros((ch1.shape[0],), dtype=np.float32)

            ch2 = getattr(self.main_window, "_current_tif_chan2", None)
            sig2 = None
            if ch2 is not None:
                ch2 = stack3d(ch2)
                sig2 = ch2[:, y0:y1, x0:x1].mean(axis=(1,2))
        else:
            # Use ellipse mask for proper signal extraction
            X0, Y0, X1, Y1, mask = mask_result
            
            def stack3d(a):
                a = np.asarray(a).squeeze()
                return a[None, ...] if a.ndim == 2 else a

            ch1 = stack3d(self.main_window._current_tif)
            
            # Extract signal using the ellipse mask
            if mask.size > 0 and np.any(mask):
                # Apply mask to each frame
                sig1_frames = []
                for frame_idx in range(ch1.shape[0]):
                    frame = ch1[frame_idx, Y0:Y1, X0:X1]
                    if frame.shape == mask.shape:
                        masked_values = frame[mask]
                        sig1_frames.append(np.mean(masked_values) if len(masked_values) > 0 else 0.0)
                    else:
                        print(f"Warning: Frame shape {frame.shape} doesn't match mask shape {mask.shape}")
                        sig1_frames.append(0.0)
                sig1 = np.array(sig1_frames, dtype=np.float32)
            else:
                sig1 = np.zeros((ch1.shape[0],), dtype=np.float32)

            ch2 = getattr(self.main_window, "_current_tif_chan2", None)
            sig2 = None
            if ch2 is not None:
                ch2 = stack3d(ch2)
                if mask.size > 0 and np.any(mask):
                    # Apply mask to each frame of channel 2
                    sig2_frames = []
                    for frame_idx in range(ch2.shape[0]):
                        frame = ch2[frame_idx, Y0:Y1, X0:X1]
                        if frame.shape == mask.shape:
                            masked_values = frame[mask]
                            sig2_frames.append(np.mean(masked_values) if len(masked_values) > 0 else 0.0)
                        else:
                            sig2_frames.append(0.0)
                    sig2 = np.array(sig2_frames, dtype=np.float32)
                else:
                    sig2 = np.zeros((ch2.shape[0],), dtype=np.float32)

        # Compute Fo (baseline) as mean over first 10% of frames of sig1
        nframes = sig1.shape[0]
        if nframes <= 0:
            return
        # Determine baseline fraction from base_spinbox (percent).
        try:
            pct = int(self.base_spinbox.value()) if hasattr(self, 'base_spinbox') else 10
            # Clamp between 1 and 99
            pct = max(1, min(99, pct))
            frac = float(pct) / 100.0
        except Exception:
            frac = 0.10

        baseline_count = max(1, int(np.ceil(nframes * frac)))
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
        
        if show_time:
            # Try to get time stamps from experiment data
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
                                print(f"DEBUG: Found time stamps in dict key '{attr_name}', length: {len(time_stamps) if hasattr(time_stamps, '__len__') else 'unknown'}")
                                if hasattr(time_stamps, '__len__') and len(time_stamps) > 0:
                                    print(f"DEBUG: First few time stamps: {time_stamps[:min(5, len(time_stamps))]}")
                                break
                        else:
                            if hasattr(ed, attr_name):
                                time_stamps = getattr(ed, attr_name)
                                print(f"DEBUG: Found time stamps in attribute '{attr_name}', length: {len(time_stamps) if hasattr(time_stamps, '__len__') else 'unknown'}")
                                if hasattr(time_stamps, '__len__') and len(time_stamps) > 0:
                                    print(f"DEBUG: First few time stamps: {time_stamps[:min(5, len(time_stamps))]}")
                                break
                
                # Check if we have valid time stamps (not empty and has enough data)
                has_valid_timestamps = (time_stamps is not None and 
                                       hasattr(time_stamps, '__len__') and 
                                       len(time_stamps) > 0 and
                                       len(time_stamps) >= len(metric))
                
                if has_valid_timestamps:
                    # Parse time stamps - they could be numbers (ms or seconds) or datetime strings
                    time_array = np.array(time_stamps[:len(metric)])
                    
                    # Check if timestamps are strings (datetime format) or numbers
                    if isinstance(time_stamps[0], str):
                        # Parse datetime strings and convert to relative seconds
                        from datetime import datetime
                        try:
                            # Parse the datetime strings
                            dt_objects = []
                            for ts in time_stamps[:len(metric)]:
                                # Handle format like '2025-10-26 19:08:38.626'
                                dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S.%f')
                                dt_objects.append(dt)
                            
                            # Convert to seconds relative to first timestamp
                            first_dt = dt_objects[0]
                            x_values = np.array([(dt - first_dt).total_seconds() for dt in dt_objects])
                            print(f"DEBUG: Parsed datetime timestamps, duration: {x_values[-1]:.2f}s")
                        except Exception as e:
                            print(f"DEBUG: Error parsing datetime strings: {e}")
                            # Fall back to frame numbers
                            show_time = False
                            x_values = None
                    else:
                        # Numeric timestamps - detect if milliseconds or seconds
                        max_time = np.max(time_array) if len(time_array) > 0 else 0
                        
                        # Heuristic: if max time > 10000, assume milliseconds; otherwise seconds
                        if max_time > 10000:
                            # Data is in milliseconds, convert to seconds
                            x_values = time_array / 1000.0
                            print(f"DEBUG: Time stamps appear to be in milliseconds (max={max_time:.2f}), converting to seconds")
                        else:
                            # Data is already in seconds (or very short recording in ms)
                            x_values = time_array
                            print(f"DEBUG: Time stamps appear to be in seconds (max={max_time:.2f})")
                    
                    if x_values is not None:
                        x_label = "Time (s)"
                        
                        # Convert current frame position to time
                        if current_frame < len(x_values):
                            current_x_pos = x_values[current_frame]
                        else:
                            current_x_pos = x_values[-1] if len(x_values) > 0 else current_frame
                        
                        print(f"DEBUG: Using time stamps for x-axis, current position: {current_x_pos}s")
                else:
                    # Fallback: estimate time based on frame rate (if available)
                    frame_rate = getattr(ed, 'frame_rate', None) if ed else None
                    if frame_rate and frame_rate > 0:
                        x_values = np.arange(len(metric)) / frame_rate
                        x_label = "Time (s)"
                        current_x_pos = current_frame / frame_rate
                        print(f"DEBUG: Using estimated time from frame rate {frame_rate} Hz, current position: {current_x_pos}s")
                    else:
                        # No time data available, fall back to frames
                        show_time = False
                        print("DEBUG: No time stamp data or frame rate found, showing frames instead")
            except Exception as e:
                print(f"DEBUG: Error getting time stamps: {e}")
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
            if show_time and x_values is not None and time_stamps is not None:
                # Handle both datetime strings and numeric timestamps
                if isinstance(time_stamps[0], str):
                    # Parse datetime strings for stimulation times
                    from datetime import datetime
                    try:
                        first_dt = datetime.strptime(time_stamps[0], '%Y-%m-%d %H:%M:%S.%f')
                        for stim in stims:
                            stim_frame = int(stim)
                            if stim_frame < len(time_stamps):
                                stim_dt = datetime.strptime(time_stamps[stim_frame], '%Y-%m-%d %H:%M:%S.%f')
                                stim_x_pos = (stim_dt - first_dt).total_seconds()
                                print(f"DEBUG: Adding stimulation vline at time {stim_x_pos:.2f}s (frame {stim_frame})")
                                self.trace_ax.axvline(stim_x_pos, color='red', linestyle='--', zorder=15, linewidth=2)
                    except Exception as e:
                        print(f"DEBUG: Error parsing datetime for stimulation: {e}")
                else:
                    # Numeric timestamps - detect format
                    time_array = np.array(time_stamps)
                    max_time = np.max(time_array) if len(time_array) > 0 else 0
                    is_milliseconds = max_time > 10000
                    
                    # Convert stim frames to time positions
                    for stim in stims:
                        stim_frame = int(stim)
                        if stim_frame < len(time_stamps):
                            if is_milliseconds:
                                stim_x_pos = time_stamps[stim_frame] / 1000.0
                            else:
                                stim_x_pos = time_stamps[stim_frame]
                            print(f"DEBUG: Adding stimulation vline at time {stim_x_pos:.2f}s (frame {stim_frame})")
                            self.trace_ax.axvline(stim_x_pos, color='red', linestyle='--', zorder=15, linewidth=2)
            else:
                # Use frame numbers
                for stim in stims:
                    stim_frame = int(stim)
                    print(f"DEBUG: Adding stimulation vline at frame {stim_frame}")
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