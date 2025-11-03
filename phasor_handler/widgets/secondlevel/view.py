"""
SecondLevelWidget - Display all ROI traces in a grid layout.

This widget displays all saved ROI traces from the First Level analysis
in a responsive grid layout that maintains aspect ratios.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QScrollArea, QGridLayout, QSizePolicy,
    QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread
from phasor_handler.workers.secondlevel_worker import SecondLevelWorker


class SecondLevelWidget(QWidget):
    """Second Level Analysis tab - displays all ROI traces in a grid layout."""

    def __init__(self, main_window):
        super().__init__()
        self.window = main_window
        
        # Store reference in main window
        self.window.second_level_widget = self
        
        # Make the widget focusable
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Store plot references
        self.plot_widgets = []
        
        # Pagination state
        self.current_page = 0
        self.plots_per_page = 15  # Maximum plots per page to prevent window expansion
        
        # Set white background only for plot area, keep toolbar with theme
        self.setStyleSheet("")  # Don't override theme
        
        # Flag to prevent recursive updates
        self._updating = False
        
        # Worker thread management
        self.worker = None
        self.worker_thread = None
        
        # Build UI
        self._build_ui()
        
    def _build_ui(self):
        """Build the second level UI with controls and grid of plots."""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # --- Control Panel ---
        control_group = QGroupBox("Display Controls")
        # Don't override theme for control panel
        control_layout = QHBoxLayout()
        
        # Y-axis limits (auto-adjusted based on formula)
        ylim_group = QGroupBox("Y-Axis Limits")
        ylim_layout = QHBoxLayout()
        ylim_layout.addWidget(QLabel("Min:"))
        self.ylim_min_edit = QDoubleSpinBox()
        self.ylim_min_edit.setRange(-999999.99, 999999.99)
        self.ylim_min_edit.setDecimals(3)
        self.ylim_min_edit.setSingleStep(0.1)
        self.ylim_min_edit.setValue(-0.1)
        self.ylim_min_edit.setMaximumWidth(100)
        self.ylim_min_edit.valueChanged.connect(self._on_parameter_changed)
        ylim_layout.addWidget(self.ylim_min_edit)
        
        ylim_layout.addWidget(QLabel("Max:"))
        self.ylim_max_edit = QDoubleSpinBox()
        self.ylim_max_edit.setRange(-999999.99, 999999.99)
        self.ylim_max_edit.setDecimals(3)
        self.ylim_max_edit.setSingleStep(0.1)
        self.ylim_max_edit.setValue(0.5)
        self.ylim_max_edit.setMaximumWidth(100)
        self.ylim_max_edit.valueChanged.connect(self._on_parameter_changed)
        ylim_layout.addWidget(self.ylim_max_edit)
        ylim_group.setLayout(ylim_layout)
        
        # Frame range
        frame_group = QGroupBox("Frame Range")
        frame_layout = QHBoxLayout()
        frame_layout.addWidget(QLabel("Start:"))
        self.frame_start_edit = QSpinBox()
        self.frame_start_edit.setRange(0, 999999)
        self.frame_start_edit.setValue(0)
        self.frame_start_edit.setMaximumWidth(100)
        self.frame_start_edit.valueChanged.connect(self._on_parameter_changed)
        frame_layout.addWidget(self.frame_start_edit)
        
        frame_layout.addWidget(QLabel("End:"))
        self.frame_end_edit = QSpinBox()
        self.frame_end_edit.setRange(0, 999999)
        self.frame_end_edit.setValue(999999)
        self.frame_end_edit.setSpecialValueText("All")
        self.frame_end_edit.setMaximumWidth(100)
        self.frame_end_edit.valueChanged.connect(self._on_parameter_changed)
        frame_layout.addWidget(self.frame_end_edit)
        frame_group.setLayout(frame_layout)
        
        # Formula selection
        formula_group = QGroupBox("Formula")
        formula_layout = QHBoxLayout()
        self.formula_dropdown = QComboBox()
        self.formula_dropdown.addItem("Fg - Fog / Fr")
        self.formula_dropdown.addItem("Fg - Fog / Fog")
        self.formula_dropdown.addItem("Fg only")
        self.formula_dropdown.addItem("Fr only")
        self.formula_dropdown.setCurrentIndex(1)  # Default to (Fg - Fog) / Fog
        self.formula_dropdown.currentIndexChanged.connect(self._on_formula_changed)
        formula_layout.addWidget(self.formula_dropdown)
        formula_group.setLayout(formula_layout)
        
        # Baseline percentage
        baseline_group = QGroupBox("Baseline")
        baseline_layout = QHBoxLayout()
        baseline_layout.addWidget(QLabel("Baseline %:"))
        self.baseline_spinbox = QSpinBox()
        self.baseline_spinbox.setRange(1, 99)
        self.baseline_spinbox.setValue(10)
        self.baseline_spinbox.setMaximumWidth(80)
        self.baseline_spinbox.valueChanged.connect(self._on_parameter_changed)
        baseline_layout.addWidget(self.baseline_spinbox)
        baseline_group.setLayout(baseline_layout)
        
        # Stimulation toggle
        self.show_stim_checkbox = QCheckBox("Show Stimulation")
        self.show_stim_checkbox.setChecked(False)
        self.show_stim_checkbox.stateChanged.connect(self._on_parameter_changed)
        
        # Buttons
        self.refresh_button = QPushButton("Refresh Plots")
        self.refresh_button.clicked.connect(self.refresh_plots)
        self.refresh_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 5px; font-weight: bold; }")
        self.refresh_button.setVisible(False)  # Hide since we have auto-update now
        
        self.reset_button = QPushButton("Reset Limits")
        self.reset_button.clicked.connect(self._reset_limits)
        self.reset_button.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 5px; font-weight: bold; }")
        
        # Pagination buttons
        self.prev_page_button = QPushButton("◀ Previous")
        self.prev_page_button.clicked.connect(self._prev_page)
        self.prev_page_button.setStyleSheet("QPushButton { background-color: #FF9800; color: white; padding: 5px; font-weight: bold; }")
        self.prev_page_button.setEnabled(False)
        
        self.page_label = QLabel("Page 1")
        self.page_label.setStyleSheet("QLabel { font-weight: bold; padding: 5px; }")
        
        self.next_page_button = QPushButton("Next ▶")
        self.next_page_button.clicked.connect(self._next_page)
        self.next_page_button.setStyleSheet("QPushButton { background-color: #FF9800; color: white; padding: 5px; font-weight: bold; }")
        self.next_page_button.setEnabled(False)
        
        # Progress bar for loading
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Computing traces: %v/%m")
        
        # Assemble control layout
        control_layout.addWidget(ylim_group)
        control_layout.addWidget(frame_group)
        control_layout.addWidget(formula_group)
        control_layout.addWidget(baseline_group)
        control_layout.addWidget(self.show_stim_checkbox)
        # control_layout.addWidget(self.refresh_button)  # Hidden since we have auto-update
        control_layout.addWidget(self.reset_button)
        control_layout.addStretch()
        control_layout.addWidget(self.prev_page_button)
        control_layout.addWidget(self.page_label)
        control_layout.addWidget(self.next_page_button)
        
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)
        
        # Progress bar
        main_layout.addWidget(self.progress_bar)
        
        # --- Grid of Plots (no scrolling - fit everything on screen) ---
        # Container for the grid
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("QWidget { background-color: white; }")
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(5)  # Reduced spacing for plots next to each other
        self.grid_layout.setContentsMargins(5, 5, 5, 5)
        self.grid_container.setLayout(self.grid_layout)
        
        main_layout.addWidget(self.grid_container, 1)  # Give it stretch to fill space
        
        self.setLayout(main_layout)
        
        # Initial plot generation (will also set default frame range)
        self.refresh_plots()
    
    def _on_parameter_changed(self):
        """Called when any parameter changes - auto-refresh plots."""
        if not self._updating:
            self.refresh_plots()
    
    def _get_frame_range(self):
        """Parse frame range from user input."""
        start = self.frame_start_edit.value()
        end = self.frame_end_edit.value()
        
        # If end is at max (999999), treat as "All"
        if end >= 999999:
            end = None
        
        return start, end
    
    def _get_ylim(self):
        """Parse y-axis limits from user input."""
        ymin = self.ylim_min_edit.value()
        ymax = self.ylim_max_edit.value()
        
        # If values are at extremes, treat as auto
        if ymin <= -999999:
            ymin = None
        if ymax >= 999999:
            ymax = None
        
        return ymin, ymax
    
    def _on_formula_changed(self):
        """Update ylim when formula changes."""
        if self._updating:
            return
            
        self._updating = True
        formula_idx = self.formula_dropdown.currentIndex()
        
        # Adjust ylim based on formula type
        if formula_idx in [0, 1]:  # Normalized formulas (ΔF/F₀)
            self.ylim_min_edit.setValue(-0.1)
            self.ylim_max_edit.setValue(0.5)
        else:  # Raw signals (Fg only, Fr only)
            self.ylim_min_edit.setValue(0)
            self.ylim_max_edit.setValue(1000)
        
        self._updating = False
        self.refresh_plots()
    
    def _reset_limits(self):
        """Reset all limit controls to defaults."""
        self._updating = True
        self.ylim_min_edit.setValue(-0.1)
        self.ylim_max_edit.setValue(0.5)
        self.frame_start_edit.setValue(0)
        
        # Set frame end to actual recording length
        current_tif = getattr(self.window, '_current_tif', None)
        if current_tif is not None:
            nframes = current_tif.shape[0] if current_tif.ndim == 3 else 1
            self.frame_end_edit.setMaximum(nframes)
            self.frame_end_edit.setValue(nframes)
        else:
            self.frame_end_edit.setValue(999999)
            
        self.baseline_spinbox.setValue(10)
        self.formula_dropdown.setCurrentIndex(1)
        self._updating = False
        self.refresh_plots()
    
    def _prev_page(self):
        """Go to previous page of plots."""
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh_plots()
    
    def _next_page(self):
        """Go to next page of plots."""
        saved_rois = getattr(self.window, '_saved_rois', [])
        total_pages = max(1, (len(saved_rois) + self.plots_per_page - 1) // self.plots_per_page)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.refresh_plots()
    
    def refresh_plots(self):
        """Update all ROI trace plots in the grid."""
        # Stop any existing worker
        self._stop_worker()
        
        # Clear existing plots
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.plot_widgets.clear()
        
        # Get saved ROIs from main window
        saved_rois = getattr(self.window, '_saved_rois', [])
        if not saved_rois:
            # Display a message if no ROIs
            label = QLabel("No ROIs defined.\n\nPlease draw and save ROIs in the First Level tab.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("QLabel { color: #666; font-size: 14pt; background-color: white; padding: 50px; }")
            self.grid_layout.addWidget(label, 0, 0, 1, 5)
            self.plot_widgets.append(label)
            return
        
        # Get current image data
        current_tif = getattr(self.window, '_current_tif', None)
        current_tif_chan2 = getattr(self.window, '_current_tif_chan2', None)
        
        if current_tif is None:
            label = QLabel("No image data loaded.\n\nPlease select an experiment in the First Level tab.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("QLabel { color: #666; font-size: 14pt; background-color: white; padding: 50px; }")
            self.grid_layout.addWidget(label, 0, 0, 1, 5)
            self.plot_widgets.append(label)
            return
        
        # Set default frame range based on actual recording length (only on first load)
        nframes = current_tif.shape[0] if current_tif.ndim == 3 else 1
        if self.frame_end_edit.value() == 999999 and not self._updating:
            self._updating = True
            self.frame_end_edit.setMaximum(nframes)
            self.frame_end_edit.setValue(nframes)
            self.frame_start_edit.setMaximum(nframes - 1)
            self._updating = False
        
        # Get frame range and y-limits
        frame_start, frame_end = self._get_frame_range()
        ymin, ymax = self._get_ylim()
        
        # Pagination: determine which ROIs to show on current page
        total_rois = len(saved_rois)
        total_pages = max(1, (total_rois + self.plots_per_page - 1) // self.plots_per_page)
        
        # Ensure current_page is valid
        if self.current_page >= total_pages:
            self.current_page = total_pages - 1
        if self.current_page < 0:
            self.current_page = 0
        
        # Update pagination buttons
        self.prev_page_button.setEnabled(self.current_page > 0)
        self.next_page_button.setEnabled(self.current_page < total_pages - 1)
        self.page_label.setText(f"Page {self.current_page + 1} of {total_pages}")
        
        # Get ROIs for current page
        start_idx = self.current_page * self.plots_per_page
        end_idx = min(start_idx + self.plots_per_page, total_rois)
        num_rois = end_idx - start_idx
        
        print(f"DEBUG: Starting worker to compute {num_rois} traces (page {self.current_page + 1}/{total_pages})")
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(num_rois)
        self.progress_bar.setValue(0)
        
        # Store parameters for rendering
        self._render_params = {
            'frame_start': frame_start,
            'frame_end': frame_end,
            'ymin': ymin,
            'ymax': ymax,
            'current_tif': current_tif,
            'current_tif_chan2': current_tif_chan2,
            'num_cols': 5  # Always use 5 columns for consistent layout
        }
        
        # Start worker thread to compute traces
        self.worker_thread = QThread()
        self.worker = SecondLevelWorker(
            saved_rois=saved_rois,
            tif=current_tif,
            tif_chan2=current_tif_chan2,
            formula_idx=self.formula_dropdown.currentIndex(),
            baseline_pct=self.baseline_spinbox.value(),
            frame_start=frame_start,
            frame_end=frame_end,
            page_rois_slice=(start_idx, end_idx)
        )
        
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.error.connect(self._on_worker_error)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self._cleanup_worker)
        
        self.worker_thread.start()
    
    def _stop_worker(self):
        """Stop any running worker thread."""
        try:
            if self.worker_thread is not None and self.worker_thread.isRunning():
                # Disconnect signals to prevent callbacks during shutdown
                try:
                    self.worker_thread.started.disconnect()
                except:
                    pass
                try:
                    self.worker.finished.disconnect()
                except:
                    pass
                try:
                    self.worker.progress.disconnect()
                except:
                    pass
                try:
                    self.worker.error.disconnect()
                except:
                    pass
                
                # Stop the thread
                self.worker_thread.quit()
                self.worker_thread.wait(1000)  # Wait up to 1 second
        except RuntimeError:
            # Thread already deleted, ignore
            pass
        finally:
            self.worker = None
            self.worker_thread = None
    
    def _cleanup_worker(self):
        """Clean up worker and thread after completion."""
        if self.worker is not None:
            self.worker.deleteLater()
        if self.worker_thread is not None:
            self.worker_thread.deleteLater()
        self.worker = None
        self.worker_thread = None
    
    def _on_worker_progress(self, current, total):
        """Update progress bar as worker processes ROIs."""
        self.progress_bar.setValue(current)
    
    def _on_worker_error(self, error_msg):
        """Handle worker error."""
        print(f"Worker error: {error_msg}")
        self.progress_bar.setVisible(False)
        
        # Show error message
        label = QLabel(f"Error computing traces:\n\n{error_msg}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("QLabel { color: #d32f2f; font-size: 12pt; background-color: white; padding: 50px; }")
        self.grid_layout.addWidget(label, 0, 0, 1, 5)
    
    def _on_worker_finished(self, trace_data_list):
        """Render plots after worker completes trace extraction."""
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Get render parameters
        params = self._render_params
        frame_start = params['frame_start']
        frame_end = params['frame_end']
        ymin = params['ymin']
        ymax = params['ymax']
        num_cols = params['num_cols']
        
        num_rois = len(trace_data_list)
        print(f"DEBUG: Rendering {num_rois} plots in {num_cols} columns")
        
        # Always use 5 columns for consistent layout
        num_cols = 5
        
        # Create plots in calculated grid
        for plot_idx, trace_data in enumerate(trace_data_list):
            roi_data = trace_data['roi_data']
            roi_idx = trace_data['roi_idx']
            trace = trace_data['trace']
            
            row = plot_idx // num_cols
            col = plot_idx % num_cols
            
            # Create plot widget for this ROI
            plot_widget = self._create_roi_plot_from_trace(
                roi_data, roi_idx, trace, frame_start, frame_end, ymin, ymax
            )
            self.grid_layout.addWidget(plot_widget, row, col)
            self.plot_widgets.append(plot_widget)
        
        # Add stretch to empty cells if last row is not full
        last_row_cols = num_rois % num_cols
        if last_row_cols > 0:
            last_row = num_rois // num_cols
            for col in range(last_row_cols, num_cols):
                spacer = QWidget()
                spacer.setStyleSheet("QWidget { background-color: white; }")
                self.grid_layout.addWidget(spacer, last_row, col)
    
    def _create_roi_plot_from_trace(self, roi_data, roi_idx, trace, frame_start, frame_end, ymin, ymax):
        """Create a single matplotlib plot for an ROI trace (from pre-computed trace)."""
        # Create a container widget
        container = QWidget()
        container.setStyleSheet("QWidget { background-color: white; border: none; }")
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Create matplotlib figure with white background - smaller for fitting on screen
        fig = Figure(figsize=(3, 2), dpi=80, facecolor='white')
        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background-color: white;")
        ax = fig.add_subplot(111, facecolor='white')
        
        # ROI name will be added as title in matplotlib
        roi_name = roi_data.get('name', f'ROI {roi_idx + 1}')
        
        if trace is not None and len(trace) > 0:
            # Apply frame range
            if frame_end is None or frame_end > len(trace):
                frame_end = len(trace)
            
            frame_start = max(0, frame_start)
            frame_end = max(frame_start + 1, min(frame_end, len(trace)))
            
            x_values = np.arange(frame_start, frame_end)
            y_values = trace[frame_start:frame_end]
            
            # Plot the trace with transparency like in notebook
            ax.plot(x_values, y_values, linewidth=1.2, color='#2E86AB', alpha=0.8)
            
            # Add stimulation line if enabled
            if self.show_stim_checkbox.isChecked():
                # Get stimulation timeframes from metadata
                stim_frames = self._get_stimulation_frames()
                if stim_frames:
                    # Draw a dashed line for each stimulation frame within the current view range
                    for stim_frame in stim_frames:
                        if frame_start <= stim_frame < frame_end:
                            ax.axvline(x=stim_frame, color='red', linestyle='--', alpha=0.7, linewidth=1.5)
            
            # Determine ylabel based on formula
            formula_idx = self.formula_dropdown.currentIndex()
            if formula_idx in [0, 1]:
                ylabel = 'ΔF/F₀'
            elif formula_idx == 2:
                ylabel = 'Green (a.u.)'
            elif formula_idx == 3:
                ylabel = 'Red (a.u.)'
            else:
                ylabel = 'Signal'
            
            # Add ROI name as title (smaller font)
            ax.set_title(roi_name, fontsize=7, fontweight='bold', color='#333', pad=3)
            
            # Set labels with smaller fonts for compact display
            ax.set_xlabel('Frame', fontsize=6, color='#333')
            ax.set_ylabel(ylabel, fontsize=6, color='#333')
            ax.tick_params(labelsize=5, colors='#333')
            
            # Set y-limits if specified
            if ymin is not None and ymax is not None and ymax > ymin:
                ax.set_ylim(ymin, ymax)
            
            # No background grid
            ax.grid(False)
            
            # Show only left (y-axis) and bottom (x-axis) spines
            ax.spines['left'].set_visible(True)
            ax.spines['left'].set_color('#333')
            ax.spines['left'].set_linewidth(0.8)
            ax.spines['bottom'].set_visible(True)
            ax.spines['bottom'].set_color('#333')
            ax.spines['bottom'].set_linewidth(0.8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
        else:
            ax.text(0.5, 0.5, 'No data', 
                   ha='center', va='center', 
                   transform=ax.transAxes,
                   fontsize=8, color='#999')
            ax.set_title(roi_name, fontsize=7, fontweight='bold', color='#333', pad=3)
            ax.set_xticks([])
            ax.set_yticks([])
            # Show only left and bottom spines
            ax.spines['left'].set_visible(True)
            ax.spines['left'].set_color('#333')
            ax.spines['left'].set_linewidth(0.8)
            ax.spines['bottom'].set_visible(True)
            ax.spines['bottom'].set_color('#333')
            ax.spines['bottom'].set_linewidth(0.8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
        
        fig.tight_layout(pad=0.3)
        layout.addWidget(canvas)
        
        container.setLayout(layout)
        # Set even smaller sizes to prevent window expansion
        container.setMinimumSize(150, 120)
        container.setMaximumSize(350, 250)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        return container
    
    def _get_stimulation_frames(self):
        """Get stimulation frame indices from experiment metadata."""
        try:
            # Get metadata from the main window
            exp_data = getattr(self.window, '_exp_data', None)
            
            if exp_data is None:
                return []
            
            # Handle different metadata formats
            stim_frames = []
            
            # Check if it's a dict-like object
            if isinstance(exp_data, dict):
                stim_frames = exp_data.get('stimulation_timeframes', [])
            # Check if it has the attribute directly (pickle format)
            elif hasattr(exp_data, 'stimulation_timeframes'):
                stim_frames = getattr(exp_data, 'stimulation_timeframes', [])
            # Try accessing as dict keys (some formats store as dict-like)
            else:
                try:
                    stim_frames = exp_data['stimulation_timeframes']
                except (KeyError, TypeError):
                    pass
            
            # Ensure we have a valid list
            if stim_frames and len(stim_frames) > 0:
                print(f"DEBUG: Found {len(stim_frames)} stimulation frames: {stim_frames}")
                return stim_frames
            else:
                print(f"DEBUG: No stimulation frames found in metadata")
                return []
                
        except Exception as e:
            print(f"DEBUG: Error getting stimulation frames: {e}")
            import traceback
            traceback.print_exc()
        
        return []
    
    def showEvent(self, event):
        """Called when the tab is shown - refresh plots and update frame range."""
        super().showEvent(event)
        
        # Update frame range based on current data (without triggering refresh)
        current_tif = getattr(self.window, '_current_tif', None)
        if current_tif is not None:
            nframes = current_tif.shape[0] if current_tif.ndim == 3 else 1
            self._updating = True
            self.frame_end_edit.setMaximum(nframes)
            self.frame_start_edit.setMaximum(nframes - 1)
            # Only update the value if it's at the default or exceeds the actual frame count
            if self.frame_end_edit.value() >= 999999 or self.frame_end_edit.value() > nframes:
                self.frame_end_edit.setValue(nframes)
            self._updating = False
        
        # Only refresh if we don't have plots yet or ROIs changed
        if not self.plot_widgets or len(self.plot_widgets) == 0:
            self.refresh_plots()
