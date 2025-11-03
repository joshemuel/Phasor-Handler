"""
Brightness & Contrast (BnC) Widget with histogram display.

Provides percentile-based contrast adjustment with live histogram visualization
showing min/max cutoff lines.
"""

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, 
    QPushButton, QDoubleSpinBox
)
from PyQt6.QtCore import pyqtSignal, QThread
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from ....workers import HistogramWorker


class BnCWidget(QWidget):
    """Brightness & Contrast widget with histogram display and percentile controls."""
    
    # Signal emitted when percentile values change
    percentileChanged = pyqtSignal()
    
    # Signal emitted when channel selection changes
    channelChanged = pyqtSignal(int)  # Emits 1 for Ch1, 2 for Ch2
    
    # Signal emitted when reset button is clicked
    resetRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ch1_data = None
        self._ch2_data = None
        self._active_channel = 1  # 1 for Ch1, 2 for Ch2
        
        # Thread management for histogram computation
        self._histogram_thread = None
        self._histogram_worker = None
        self._pending_histogram_update = False
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI components."""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create the group box
        self.group_box = QGroupBox("Brightness and Contrast")
        self.group_box.setObjectName('bnc_group')
        group_layout = QVBoxLayout()
        
        # Channel selection buttons (mutually exclusive)
        channel_buttons_layout = QHBoxLayout()
        
        self.channel1_button = QPushButton("Channel 1")
        self.channel1_button.setCheckable(True)
        self.channel1_button.setChecked(True)
        self.channel1_button.clicked.connect(lambda: self._on_channel_selected(1))
        self.channel1_button.setMaximumWidth(80)
        
        self.channel2_button = QPushButton("Channel 2")
        self.channel2_button.setCheckable(True)
        self.channel2_button.setChecked(False)
        self.channel2_button.setEnabled(False)
        self.channel2_button.clicked.connect(lambda: self._on_channel_selected(2))
        self.channel2_button.setMaximumWidth(80)
        
        channel_buttons_layout.addWidget(self.channel1_button)
        channel_buttons_layout.addWidget(self.channel2_button)
        
        # Labels
        labels_layout = QHBoxLayout()
        labels_layout.addWidget(QLabel("Min (pth):"))
        labels_layout.addWidget(QLabel("Max (pth):"))
        
        # Spinboxes
        spinbox_layout = QHBoxLayout()
        
        self.spinbox_min = QDoubleSpinBox()
        self.spinbox_min.setRange(0.0, 100.0)
        self.spinbox_min.setSingleStep(0.2)
        self.spinbox_min.setValue(0.5)
        self.spinbox_min.setMaximumWidth(80)
        self.spinbox_min.setToolTip("Lower percentile cutoff")
        self.spinbox_min.valueChanged.connect(self._on_percentile_changed)
        
        self.spinbox_max = QDoubleSpinBox()
        self.spinbox_max.setRange(0.0, 100.0)
        self.spinbox_max.setSingleStep(0.2)
        self.spinbox_max.setValue(99.5)
        self.spinbox_max.setMaximumWidth(80)
        self.spinbox_max.setToolTip("Upper percentile cutoff")
        self.spinbox_max.valueChanged.connect(self._on_percentile_changed)
        
        spinbox_layout.addWidget(self.spinbox_min)
        spinbox_layout.addWidget(self.spinbox_max)
        spinbox_layout.addStretch()
        
        # Reset button and histogram toggle
        buttons_layout = QHBoxLayout()
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.setMaximumWidth(80)
        self.reset_button.setToolTip("Reset to default range (0.5-99.5)")
        self.reset_button.clicked.connect(self._on_reset)
        
        self.histogram_toggle = QPushButton("Show Histogram")
        self.histogram_toggle.setCheckable(True)
        self.histogram_toggle.setChecked(False)
        self.histogram_toggle.setMaximumWidth(120)
        self.histogram_toggle.setToolTip("Toggle histogram display")
        self.histogram_toggle.clicked.connect(self._on_histogram_toggle)
        
        buttons_layout.addWidget(self.reset_button)
        buttons_layout.addWidget(self.histogram_toggle)
        buttons_layout.addStretch()
        
        # Histogram display - smaller size
        self.histogram_figure = Figure(figsize=(2.5, 0.8), dpi=80)
        self.histogram_figure.patch.set_facecolor('#31363b')  # Match dark theme
        self.histogram_canvas = FigureCanvas(self.histogram_figure)
        self.histogram_canvas.setMinimumHeight(60)
        self.histogram_canvas.setMaximumHeight(80)
        
        self.histogram_ax = self.histogram_figure.add_subplot(111)
        self.histogram_ax.set_facecolor('#232629')  # Darker background for plot area
        
        # Hide axes
        self.histogram_ax.set_xticks([])
        self.histogram_ax.set_yticks([])
        self.histogram_ax.spines['top'].set_visible(False)
        self.histogram_ax.spines['right'].set_visible(False)
        self.histogram_ax.spines['bottom'].set_visible(False)
        self.histogram_ax.spines['left'].set_visible(False)
        
        # Initialize histogram lines
        self._min_line = None
        self._max_line = None
        
        # Add components to group layout
        group_layout.addLayout(channel_buttons_layout)
        group_layout.addLayout(labels_layout)
        group_layout.addLayout(spinbox_layout)
        group_layout.addLayout(buttons_layout)
        group_layout.addWidget(self.histogram_canvas)
        
        # Initially hide the histogram
        self.histogram_canvas.setVisible(False)
        
        self.group_box.setLayout(group_layout)
        main_layout.addWidget(self.group_box)
        
        self.setLayout(main_layout)
        
        # Don't update histogram initially since it's hidden
        # self._update_histogram()
        
    def _on_channel_selected(self, channel):
        """Handle channel selection."""
        self._active_channel = channel
        
        # Update button states
        if channel == 1:
            self.channel1_button.setChecked(True)
            self.channel2_button.setChecked(False)
        else:
            self.channel1_button.setChecked(False)
            self.channel2_button.setChecked(True)
        
        # Update histogram only if it's visible
        if self.histogram_toggle.isChecked():
            self._update_histogram()
        
        # Emit signal
        self.channelChanged.emit(channel)
        
    def _on_percentile_changed(self):
        """Handle percentile value changes."""
        # Update histogram only if it's visible
        if self.histogram_toggle.isChecked():
            self._update_histogram()
        
        # Emit signal
        self.percentileChanged.emit()
        
    def _on_histogram_toggle(self):
        """Handle histogram visibility toggle."""
        is_visible = self.histogram_toggle.isChecked()
        
        # Update button text
        if is_visible:
            self.histogram_toggle.setText("Hide Histogram")
            self.histogram_canvas.setVisible(True)
            # Update histogram when showing
            self._update_histogram()
        else:
            self.histogram_toggle.setText("Show Histogram")
            self.histogram_canvas.setVisible(False)
            # Cancel any pending histogram update
            self._pending_histogram_update = False
        
    def _on_reset(self):
        """Reset percentile values to defaults."""
        self.spinbox_min.setValue(0.5)
        self.spinbox_max.setValue(99.5)
        
        # Emit signal
        self.resetRequested.emit()
        
    def enable_controls(self, enabled, has_channel2=True):
        """Enable or disable all BnC controls.
        
        Args:
            enabled: Whether to enable the controls
            has_channel2: Whether channel 2 is available
        """
        self.channel1_button.setEnabled(enabled)
        self.channel2_button.setEnabled(enabled and has_channel2)
        self.spinbox_min.setEnabled(enabled)
        self.spinbox_max.setEnabled(enabled)
        self.reset_button.setEnabled(enabled)
        
    def get_min_percentile(self):
        """Get the current minimum percentile value."""
        return self.spinbox_min.value()
        
    def get_max_percentile(self):
        """Get the current maximum percentile value."""
        return self.spinbox_max.value()
        
    def set_min_percentile(self, value):
        """Set the minimum percentile value."""
        self.spinbox_min.setValue(value)
        
    def set_max_percentile(self, value):
        """Set the maximum percentile value."""
        self.spinbox_max.setValue(value)
        
    def set_image_data(self, ch1_data, ch2_data=None):
        """Set image data for histogram display.
        
        Args:
            ch1_data: NumPy array for channel 1 (green)
            ch2_data: NumPy array for channel 2 (red), optional
        """
        self._ch1_data = ch1_data
        self._ch2_data = ch2_data
        
        # Enable/disable Channel 2 button based on data availability
        self.channel2_button.setEnabled(ch2_data is not None)
        
        # If Ch2 becomes unavailable, switch to Ch1
        if ch2_data is None and self._active_channel == 2:
            self._on_channel_selected(1)
        
        # Update histogram only if it's visible
        if self.histogram_toggle.isChecked():
            self._update_histogram()
        
    def _normalize_to_255(self, data):
        """Normalize data to 0-255 range for histogram display."""
        if data is None:
            return None
            
        data_flat = data.flatten()
        data_min = np.min(data_flat)
        data_max = np.max(data_flat)
        
        if data_max > data_min:
            normalized = ((data_flat - data_min) / (data_max - data_min) * 255.0).astype(np.float32)
            return normalized
        else:
            return np.zeros_like(data_flat, dtype=np.float32)
            
    def _update_histogram(self):
        """Update histogram display for current channel using background thread."""
        # If a histogram computation is already running, mark that we need another update
        if self._histogram_thread is not None and self._histogram_thread.isRunning():
            self._pending_histogram_update = True
            return
        
        # Get current channel data
        if self._active_channel == 1:
            current_data = self._ch1_data
            self._current_hist_color = 'green'
        else:
            current_data = self._ch2_data
            self._current_hist_color = 'red'
        
        if current_data is None:
            self._clear_histogram()
            return
        
        # Normalize data to 0-255
        norm_data = self._normalize_to_255(current_data)
        
        if norm_data is None:
            self._clear_histogram()
            return
        
        # Get percentile values
        min_percentile = self.spinbox_min.value()
        max_percentile = self.spinbox_max.value()
        
        # Create thread and worker
        self._histogram_thread = QThread()
        self._histogram_worker = HistogramWorker(norm_data, min_percentile, max_percentile)
        self._histogram_worker.moveToThread(self._histogram_thread)
        
        # Connect signals
        self._histogram_thread.started.connect(self._histogram_worker.run)
        self._histogram_worker.finished.connect(self._on_histogram_computed)
        self._histogram_worker.error.connect(self._on_histogram_error)
        
        # Cleanup on finish
        def cleanup():
            self._histogram_thread.quit()
            self._histogram_thread.wait()
            self._histogram_worker.deleteLater()
            self._histogram_thread.deleteLater()
            self._histogram_thread = None
            self._histogram_worker = None
            
            # If another update was requested while computing, trigger it now
            if self._pending_histogram_update:
                self._pending_histogram_update = False
                self._update_histogram()
        
        self._histogram_worker.finished.connect(cleanup)
        self._histogram_worker.error.connect(cleanup)
        
        # Start computation
        self._histogram_thread.start()
        
    def _clear_histogram(self):
        """Clear the histogram display."""
        self.histogram_ax.clear()
        
        # Hide axes
        self.histogram_ax.set_xticks([])
        self.histogram_ax.set_yticks([])
        self.histogram_ax.spines['top'].set_visible(False)
        self.histogram_ax.spines['right'].set_visible(False)
        self.histogram_ax.spines['bottom'].set_visible(False)
        self.histogram_ax.spines['left'].set_visible(False)
        
        self.histogram_canvas.draw()
        
    def _on_histogram_computed(self, counts, bins, min_val, max_val):
        """Handle histogram computation results from worker thread."""
        try:
            self.histogram_ax.clear()
            
            # Hide axes
            self.histogram_ax.set_xticks([])
            self.histogram_ax.set_yticks([])
            self.histogram_ax.spines['top'].set_visible(False)
            self.histogram_ax.spines['right'].set_visible(False)
            self.histogram_ax.spines['bottom'].set_visible(False)
            self.histogram_ax.spines['left'].set_visible(False)
            
            # Plot histogram using bar
            bin_centers = (bins[:-1] + bins[1:]) / 2
            self.histogram_ax.bar(
                bin_centers, counts, width=1.0,
                color=self._current_hist_color, alpha=0.7, edgecolor='none'
            )
            
            # Add vertical lines for min/max percentiles
            self._min_line = self.histogram_ax.axvline(
                min_val, color='cyan', linewidth=1.5, linestyle='--', alpha=0.8
            )
            self._max_line = self.histogram_ax.axvline(
                max_val, color='magenta', linewidth=1.5, linestyle='--', alpha=0.8
            )
            
            # Set limits
            self.histogram_ax.set_xlim(0, 255)
            
            # Adjust layout to prevent label cutoff
            self.histogram_figure.tight_layout(pad=0.05)
            
            # Redraw canvas
            self.histogram_canvas.draw()
            
        except Exception as e:
            print(f"Error drawing histogram: {e}")
            
    def _on_histogram_error(self, error_msg):
        """Handle histogram computation error."""
        print(f"Histogram computation error: {error_msg}")
        self._clear_histogram()
        
    def get_min_percentile(self):
        """Get current minimum percentile value."""
        return self.spinbox_min.value()
        
    def get_max_percentile(self):
        """Get current maximum percentile value."""
        return self.spinbox_max.value()
        
    def get_active_channel(self):
        """Get currently active channel (1 or 2)."""
        return self._active_channel
        
    def set_min_percentile(self, value):
        """Set minimum percentile value."""
        self.spinbox_min.setValue(value)
        
    def set_max_percentile(self, value):
        """Set maximum percentile value."""
        self.spinbox_max.setValue(value)
        
    def cleanup(self):
        """Cleanup resources, especially running threads."""
        # Stop any running histogram computation
        if self._histogram_thread is not None and self._histogram_thread.isRunning():
            self._histogram_thread.quit()
            self._histogram_thread.wait()
            if self._histogram_worker is not None:
                self._histogram_worker.deleteLater()
            self._histogram_thread.deleteLater()
            self._histogram_thread = None
            self._histogram_worker = None
