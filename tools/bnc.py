"""
Brightness & Contrast (BnC) module with histogram display and ImageJ-style controls.

Handles both 8-bit and 16-bit images, normalizes histograms to 0-255 range for display,
and provides dual-channel support with live preview integration. Uses ImageJ-compatible
linear brightness/contrast adjustments with multi-threading support.
"""

import numpy as np
import threading
import queue
import time
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, 
    QComboBox, QGroupBox, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt


class BnCDialog(QDialog):
    """Brightness & Contrast dialog with histogram display and per-channel controls."""
    
    # Signal emitted when contrast/brightness settings change
    settings_changed = pyqtSignal(dict)  # Emits {'channel': int, 'min': float, 'max': float, 'brightness': float, 'contrast': float}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.setWindowTitle("Brightness & Contrast")
        self.setModal(False)
        self.resize(600, 600)
        
        # Data storage
        self._ch1_data = None
        self._ch2_data = None
        self._current_channel = 0  # 0 for Ch1, 1 for Ch2
        self._settings = {
            'ch1': {'min': 0, 'max': 255, 'brightness': 128.0, 'contrast': 128.0},
            'ch2': {'min': 0, 'max': 255, 'brightness': 128.0, 'contrast': 128.0}
        }
        
        # Multi-threading support
        self._update_queue = queue.Queue()
        self._processing_thread = None
        self._stop_processing = threading.Event()
        self._start_processing_thread()
        
        # Timer for delayed updates (debouncing)
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._queue_update)
        
        self._setup_ui()
        
    def _start_processing_thread(self):
        """Start the background processing thread."""
        self._processing_thread = threading.Thread(target=self._process_updates, daemon=True)
        self._processing_thread.start()
        
    def _process_updates(self):
        """Background thread for processing updates."""
        while not self._stop_processing.is_set():
            try:
                # Wait for update requests with timeout
                update_type = self._update_queue.get(timeout=0.1)
                if update_type == 'histogram':
                    # Process histogram update in background
                    self._update_histogram_data()
                elif update_type == 'settings':
                    # Process settings update
                    self._emit_settings_changed()
                self._update_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in processing thread: {e}")
                
    def _queue_update(self, update_type='histogram'):
        """Queue an update to be processed in background."""
        if not self._stop_processing.is_set():
            try:
                # Clear any pending updates of the same type
                temp_queue = queue.Queue()
                while not self._update_queue.empty():
                    try:
                        item = self._update_queue.get_nowait()
                        if item != update_type:
                            temp_queue.put(item)
                        self._update_queue.task_done()
                    except queue.Empty:
                        break
                
                # Restore non-duplicate items
                while not temp_queue.empty():
                    self._update_queue.put(temp_queue.get())
                
                # Add new update
                self._update_queue.put(update_type)
            except Exception as e:
                print(f"Error queuing update: {e}")
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        self._stop_processing.set()
        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=1.0)
        super().closeEvent(event)
        
    def _setup_ui(self):
        """Setup the UI components."""
        main_layout = QVBoxLayout()
        
        # Channel selection (only shown if dual-channel)
        self._setup_channel_selection(main_layout)
        
        # Histogram display
        self._setup_histogram(main_layout)
        
        # Controls
        self._setup_controls(main_layout)
        
        # Buttons
        self._setup_buttons(main_layout)
        
        self.setLayout(main_layout)
        
    def _setup_channel_selection(self, main_layout):
        """Setup channel selection dropdown."""
        channel_layout = QHBoxLayout()
        self.channel_label = QLabel("Channel:")
        self.channel_combo = QComboBox()
        self.channel_combo.addItem("Ch1 (Green)")
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        
        channel_layout.addWidget(self.channel_label)
        channel_layout.addWidget(self.channel_combo)
        channel_layout.addStretch()
        main_layout.addLayout(channel_layout)
        
    def _setup_histogram(self, main_layout):
        """Setup histogram display."""
        self.hist_fig, self.hist_ax = plt.subplots(figsize=(6, 3), dpi=80)
        self.hist_ax.set_facecolor('black')
        self.hist_fig.patch.set_facecolor('black')
        self.hist_canvas = FigureCanvas(self.hist_fig)
        self.hist_canvas.setMinimumHeight(200)
        main_layout.addWidget(self.hist_canvas)
        
        # Initialize histogram lines for min/max indicators
        self._min_line = None
        self._max_line = None
        
    def _setup_controls(self, main_layout):
        """Setup control sliders."""
        controls_group = QGroupBox("Brightness & Contrast Controls")
        controls_layout = QGridLayout()
        
        # Min slider
        self.min_label = QLabel("Min:")
        self.min_value_label = QLabel("0")
        self.min_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_slider.setMinimum(0)
        self.min_slider.setMaximum(255)
        self.min_slider.valueChanged.connect(self._on_min_changed)
        
        # Max slider
        self.max_label = QLabel("Max:")
        self.max_value_label = QLabel("255")
        self.max_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_slider.setMinimum(0)
        self.max_slider.setMaximum(255)
        self.max_slider.setValue(255)
        self.max_slider.valueChanged.connect(self._on_max_changed)
        
        # Brightness slider (ImageJ style)
        self.brightness_label = QLabel("Brightness:")
        self.brightness_value_label = QLabel("128")
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(255)
        self.brightness_slider.setValue(128)
        self.brightness_slider.valueChanged.connect(self._on_brightness_changed)
        
        # Contrast slider (ImageJ style)
        self.contrast_label = QLabel("Contrast:")
        self.contrast_value_label = QLabel("128")
        self.contrast_slider = QSlider(Qt.Orientation.Horizontal)
        self.contrast_slider.setMinimum(0)
        self.contrast_slider.setMaximum(255)
        self.contrast_slider.setValue(128)
        self.contrast_slider.valueChanged.connect(self._on_contrast_changed)
        
        # Layout controls
        controls_layout.addWidget(self.min_label, 0, 0)
        controls_layout.addWidget(self.min_slider, 0, 1)
        controls_layout.addWidget(self.min_value_label, 0, 2)
        
        controls_layout.addWidget(self.max_label, 1, 0)
        controls_layout.addWidget(self.max_slider, 1, 1)
        controls_layout.addWidget(self.max_value_label, 1, 2)
        
        controls_layout.addWidget(self.brightness_label, 2, 0)
        controls_layout.addWidget(self.brightness_slider, 2, 1)
        controls_layout.addWidget(self.brightness_value_label, 2, 2)
        
        controls_layout.addWidget(self.contrast_label, 3, 0)
        controls_layout.addWidget(self.contrast_slider, 3, 1)
        controls_layout.addWidget(self.contrast_value_label, 3, 2)
        
        controls_group.setLayout(controls_layout)
        main_layout.addWidget(controls_group)
        
    def _setup_buttons(self, main_layout):
        """Setup action buttons."""
        btn_layout = QHBoxLayout()
        
        self.reset_btn = QPushButton("Reset")
        self.auto_btn = QPushButton("Auto")
        self.close_btn = QPushButton("Close")
        
        self.reset_btn.clicked.connect(self._on_reset)
        self.auto_btn.clicked.connect(self._on_auto)
        self.close_btn.clicked.connect(self.close)
        
        btn_layout.addWidget(self.reset_btn)
        btn_layout.addWidget(self.auto_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(btn_layout)
        
    def set_image_data(self, ch1_data, ch2_data=None):
        """Set image data for histogram display and analysis.
        
        Args:
            ch1_data: NumPy array for channel 1 (green)
            ch2_data: NumPy array for channel 2 (red), optional
        """
        self._ch1_data = ch1_data
        self._ch2_data = ch2_data
        
        # Update channel combo based on available channels
        self.channel_combo.clear()
        self.channel_combo.addItem("Ch1 (Green)")
        if ch2_data is not None:
            self.channel_combo.addItem("Ch2 (Red)")
            
        # Initialize settings based on data
        self._initialize_settings()
        
        # Update display
        self._update_display()
        
    def _initialize_settings(self):
        """Initialize min/max/brightness/contrast settings based on image data."""
        for i, (key, data) in enumerate([('ch1', self._ch1_data), ('ch2', self._ch2_data)]):
            if data is not None:
                # Convert to 0-255 range for consistent UI
                norm_data = self._normalize_to_255(data)
                data_min = float(np.min(norm_data))
                data_max = float(np.max(norm_data))
                
                # ImageJ-style initialization
                self._settings[key] = {
                    'min': data_min,
                    'max': data_max,
                    'brightness': 128.0,  # Center value (0-255 range)
                    'contrast': 128.0     # Center value (0-255 range)
                }
                
    def _normalize_to_255(self, data):
        """Normalize data to 0-255 range for consistent histogram display."""
        if data is None:
            return None
            
        data_flat = data.flatten()
        data_min = np.min(data_flat)
        data_max = np.max(data_flat)
        
        if data_max > data_min:
            # Normalize to 0-255 range
            normalized = ((data_flat - data_min) / (data_max - data_min)) * 255
            return normalized.astype(np.uint8)
        else:
            # Constant image
            return np.full_like(data_flat, 128, dtype=np.uint8)
            
    def _get_current_data(self):
        """Get currently selected channel data."""
        if self._current_channel == 0:
            return self._ch1_data
        elif self._current_channel == 1 and self._ch2_data is not None:
            return self._ch2_data
        return None
        
    def _get_current_settings_key(self):
        """Get settings key for current channel."""
        return 'ch1' if self._current_channel == 0 else 'ch2'
        
    def _update_display(self):
        """Update histogram and slider positions."""
        self._update_histogram()
        self._update_sliders()
        
    def _update_histogram(self):
        """Update histogram display for current channel."""
        self.hist_ax.clear()
        
        current_data = self._get_current_data()
        if current_data is None:
            self.hist_canvas.draw()
            return
            
        # Normalize data to 0-255 for histogram display
        norm_data = self._normalize_to_255(current_data)
        
        # Create histogram
        counts, bins, patches = self.hist_ax.hist(
            norm_data, bins=256, range=(0, 255), 
            color='white', alpha=0.7, edgecolor='none'
        )
        
        # Style the histogram
        self.hist_ax.set_facecolor('black')
        self.hist_ax.set_xlabel('Intensity (0-255)', color='white')
        self.hist_ax.set_ylabel('Pixel Count', color='white')
        self.hist_ax.tick_params(colors='white')
        
        # Set axis limits
        self.hist_ax.set_xlim(0, 255)
        max_count = np.max(counts) if len(counts) > 0 else 1
        self.hist_ax.set_ylim(0, max_count * 1.1)
        
        # Add min/max indicator lines
        settings_key = self._get_current_settings_key()
        min_val = self._settings[settings_key]['min']
        max_val = self._settings[settings_key]['max']
        brightness = self._settings[settings_key]['brightness']
        contrast = self._settings[settings_key]['contrast']
        
        self._min_line = self.hist_ax.axvline(min_val, color='cyan', linewidth=2, label=f'Min: {min_val:.0f}')
        self._max_line = self.hist_ax.axvline(max_val, color='magenta', linewidth=2, label=f'Max: {max_val:.0f}')
        
        # Add linear transformation line (ImageJ style)
        if max_val > min_val:
            # Draw linear line from (min_val, 0) to (max_val, max_height)
            max_hist_height = max_count * 0.9  # Scale to 90% of max height
            
            # Linear line coordinates
            x_line = [min_val, max_val]
            y_line = [0, max_hist_height]
            
            # Draw the linear transformation line
            self.hist_ax.plot(x_line, y_line, color='yellow', linewidth=3, 
                            label=f'Linear Transform', alpha=0.8)
                            
            # Add brightness/contrast info to legend
            brightness_pct = (brightness - 128) / 128 * 100
            contrast_pct = (contrast - 128) / 128 * 100
            self.hist_ax.text(0.02, 0.98, f'Brightness: {brightness_pct:+.0f}%\nContrast: {contrast_pct:+.0f}%', 
                            transform=self.hist_ax.transAxes, verticalalignment='top',
                            bbox=dict(boxstyle='round', facecolor='black', alpha=0.7),
                            color='white', fontsize=10)
        
        # Add legend
        self.hist_ax.legend(facecolor='black', edgecolor='white', labelcolor='white', loc='upper right')
        
        self.hist_canvas.draw()
        
    def _update_sliders(self):
        """Update slider positions based on current settings."""
        settings_key = self._get_current_settings_key()
        settings = self._settings[settings_key]
        
        # Block signals to prevent recursive updates
        self.min_slider.blockSignals(True)
        self.max_slider.blockSignals(True)
        self.brightness_slider.blockSignals(True)
        self.contrast_slider.blockSignals(True)
        
        # Update slider values
        self.min_slider.setValue(int(settings['min']))
        self.max_slider.setValue(int(settings['max']))
        self.brightness_slider.setValue(int(settings['brightness']))
        self.contrast_slider.setValue(int(settings['contrast']))
        
        # Update labels
        self.min_value_label.setText(f"{settings['min']:.0f}")
        self.max_value_label.setText(f"{settings['max']:.0f}")
        self.brightness_value_label.setText(f"{settings['brightness']:.0f}")
        self.contrast_value_label.setText(f"{settings['contrast']:.0f}")
        
        # Re-enable signals
        self.min_slider.blockSignals(False)
        self.max_slider.blockSignals(False)
        self.brightness_slider.blockSignals(False)
        self.contrast_slider.blockSignals(False)
        
    def _on_channel_changed(self, index):
        """Handle channel selection change."""
        self._current_channel = index
        self._update_display()
        
    def _on_min_changed(self, value):
        """Handle min slider change."""
        settings_key = self._get_current_settings_key()
        
        # Ensure min doesn't exceed max-1
        max_val = self._settings[settings_key]['max']
        if value >= max_val:
            value = max_val - 1
            self.min_slider.setValue(value)
            
        self._settings[settings_key]['min'] = float(value)
        self.min_value_label.setText(f"{value}")
        
        # Update brightness/contrast based on new min/max
        self._update_brightness_contrast_from_minmax()
        
        # Delayed update
        self._update_timer.start(50)  # 50ms delay for debouncing
        
    def _on_max_changed(self, value):
        """Handle max slider change."""
        settings_key = self._get_current_settings_key()
        
        # Ensure max doesn't go below min+1
        min_val = self._settings[settings_key]['min']
        if value <= min_val:
            value = min_val + 1
            self.max_slider.setValue(value)
            
        self._settings[settings_key]['max'] = float(value)
        self.max_value_label.setText(f"{value}")
        
        # Update brightness/contrast based on new min/max
        self._update_brightness_contrast_from_minmax()
        
        # Delayed update
        self._update_timer.start(50)  # 50ms delay for debouncing
        
    def _update_brightness_contrast_from_minmax(self):
        """Update brightness/contrast sliders based on current min/max values."""
        settings_key = self._get_current_settings_key()
        current_data = self._get_current_data()
        
        if current_data is None:
            return
            
        # Get full data range
        norm_data = self._normalize_to_255(current_data)
        default_min = float(np.min(norm_data))
        default_max = float(np.max(norm_data))
        default_range = default_max - default_min
        
        if default_range <= 0:
            return
            
        # Get current values
        current_min = self._settings[settings_key]['min']
        current_max = self._settings[settings_key]['max']
        center = current_min + (current_max - current_min) / 2.0
        
        # Calculate brightness (reverse of the brightness calculation)
        normalized_center = (center - default_min) / default_range
        brightness = (1.0 - normalized_center) * 255.0
        brightness = max(0, min(255, brightness))
        
        # Calculate contrast (reverse of the contrast calculation)
        current_range = current_max - current_min
        if current_range > 0:
            # Use slope calculation to find contrast value
            slope = (default_range / 2.0) / (current_range / 2.0)
            
            # Reverse the slope calculation
            mid = 127.5  # 255/2
            if slope <= 1.0:
                contrast = slope * mid
            else:
                contrast = 255.0 - (mid / slope)
                
            contrast = max(0, min(255, contrast))
        else:
            contrast = 255  # Maximum contrast when range is 0
            
        # Update settings and UI
        self._settings[settings_key]['brightness'] = brightness
        self._settings[settings_key]['contrast'] = contrast
        
        self.brightness_slider.blockSignals(True)
        self.contrast_slider.blockSignals(True)
        self.brightness_slider.setValue(int(brightness))
        self.contrast_slider.setValue(int(contrast))
        self.brightness_value_label.setText(f"{brightness:.0f}")
        self.contrast_value_label.setText(f"{contrast:.0f}")
        self.brightness_slider.blockSignals(False)
        self.contrast_slider.blockSignals(False)
        
    def _on_brightness_changed(self, value):
        """Handle brightness slider change (ImageJ style)."""
        settings_key = self._get_current_settings_key()
        current_data = self._get_current_data()
        
        if current_data is None:
            return
            
        # Get full data range
        norm_data = self._normalize_to_255(current_data)
        default_min = float(np.min(norm_data))
        default_max = float(np.max(norm_data))
        default_range = default_max - default_min
        
        if default_range <= 0:
            return
            
        # ImageJ brightness calculation:
        # Brightness moves the center point while maintaining window width
        brightness = float(value)  # 0-255 range
        
        # Calculate normalized brightness: 1.0 - (brightness / 255.0)
        # This matches ImageJ's brightness behavior
        normalized_brightness = 1.0 - (brightness / 255.0)
        
        # Calculate center point
        center = default_min + (default_range * normalized_brightness)
        
        # Get current window width
        current_min = self._settings[settings_key]['min']
        current_max = self._settings[settings_key]['max']
        width = current_max - current_min
        
        # Apply brightness by moving center while maintaining width
        new_min = center - width / 2.0
        new_max = center + width / 2.0
        
        # Clamp to valid range
        new_min = max(default_min, min(new_min, default_max - width))
        new_max = min(default_max, max(new_max, default_min + width))
        
        # If clamping changed the width, adjust the other bound
        if new_max - new_min != width:
            if new_min == default_min:
                new_max = new_min + width
            elif new_max == default_max:
                new_min = new_max - width
        
        # Update settings
        self._settings[settings_key]['min'] = new_min
        self._settings[settings_key]['max'] = new_max
        self._settings[settings_key]['brightness'] = brightness
        
        # Update UI
        self.min_slider.blockSignals(True)
        self.max_slider.blockSignals(True)
        self.min_slider.setValue(int(new_min))
        self.max_slider.setValue(int(new_max))
        self.min_value_label.setText(f"{new_min:.0f}")
        self.max_value_label.setText(f"{new_max:.0f}")
        self.brightness_value_label.setText(f"{brightness:.0f}")
        self.min_slider.blockSignals(False)
        self.max_slider.blockSignals(False)
        
        # Delayed update
        self._update_timer.start(50)  # 50ms delay for debouncing
        
    def _on_contrast_changed(self, value):
        """Handle contrast slider change (ImageJ style)."""
        settings_key = self._get_current_settings_key()
        current_data = self._get_current_data()
        
        if current_data is None:
            return
            
        # Get full data range
        norm_data = self._normalize_to_255(current_data)
        default_min = float(np.min(norm_data))
        default_max = float(np.max(norm_data))
        default_range = default_max - default_min
        
        if default_range <= 0:
            return
            
        # ImageJ contrast calculation:
        # Contrast changes window width around center point
        contrast = float(value)  # 0-255 range
        
        # Get current center point
        current_min = self._settings[settings_key]['min']
        current_max = self._settings[settings_key]['max']
        center = current_min + (current_max - current_min) / 2.0
        
        # Calculate slope based on contrast value
        # ImageJ uses: slope = cvalue/mid if cvalue <= mid, else mid/(sliderRange-cvalue)
        slider_range = 255.0
        mid = slider_range / 2.0
        
        if contrast <= mid:
            slope = contrast / mid
        else:
            slope = mid / (slider_range - contrast)
            
        if slope > 0.0:
            # Calculate new min/max based on slope
            half_range = (default_range / 2.0) / slope
            new_min = center - half_range
            new_max = center + half_range
        else:
            # If slope is 0, use full range
            new_min = default_min
            new_max = default_max
        
        # Clamp to valid range
        new_min = max(default_min, min(new_min, default_max))
        new_max = min(default_max, max(new_max, default_min))
        
        # Ensure min < max
        if new_max <= new_min:
            new_max = new_min + 1
        
        # Update settings
        self._settings[settings_key]['min'] = new_min
        self._settings[settings_key]['max'] = new_max
        self._settings[settings_key]['contrast'] = contrast
        
        # Update UI
        self.min_slider.blockSignals(True)
        self.max_slider.blockSignals(True)
        self.min_slider.setValue(int(new_min))
        self.max_slider.setValue(int(new_max))
        self.min_value_label.setText(f"{new_min:.0f}")
        self.max_value_label.setText(f"{new_max:.0f}")
        self.contrast_value_label.setText(f"{contrast:.0f}")
        self.min_slider.blockSignals(False)
        self.max_slider.blockSignals(False)
        
        # Delayed update
        self._update_timer.start(50)  # 50ms delay for debouncing
        
    def _on_reset(self):
        """Reset current channel to default values."""
        current_data = self._get_current_data()
        if current_data is None:
            return
            
        settings_key = self._get_current_settings_key()
        
        # Reset to full range and default brightness/contrast
        norm_data = self._normalize_to_255(current_data)
        self._settings[settings_key] = {
            'min': float(np.min(norm_data)),
            'max': float(np.max(norm_data)),
            'brightness': 128.0,  # Center value
            'contrast': 128.0     # Center value
        }
        
        self._update_display()
        self._queue_update('settings')
        
    def _on_auto(self):
        """Auto-adjust current channel using percentile clipping."""
        current_data = self._get_current_data()
        if current_data is None:
            return
            
        settings_key = self._get_current_settings_key()
        
        # Use percentile clipping (0.35% on each end, similar to ImageJ)
        norm_data = self._normalize_to_255(current_data)
        sat = 0.35
        min_val = float(np.percentile(norm_data, sat))
        max_val = float(np.percentile(norm_data, 100.0 - sat))
        
        self._settings[settings_key]['min'] = min_val
        self._settings[settings_key]['max'] = max_val
        
        # Update brightness/contrast based on new min/max
        self._update_brightness_contrast_from_minmax()
        
        self._update_display()
        self._queue_update('settings')
        
    def _update_histogram_data(self):
        """Update histogram data in background thread."""
        # This method runs in background thread - just trigger UI update
        pass
        
    def _queue_update(self, update_type='histogram'):
        """Queue an update with debouncing.""" 
        if update_type == 'settings':
            self._emit_settings_changed()
        
        # Always update display
        self._update_display()
        
    def _emit_settings_changed(self):
        """Emit settings changed signal."""
        settings_key = self._get_current_settings_key()
        settings = self._settings[settings_key].copy()
        settings['channel'] = self._current_channel
        self.settings_changed.emit(settings)
        
    def get_settings(self):
        """Get current settings for both channels."""
        return self._settings.copy()
        
    def set_settings(self, settings):
        """Set settings for both channels."""
        if 'ch1' in settings:
            self._settings['ch1'].update(settings['ch1'])
        if 'ch2' in settings:
            self._settings['ch2'].update(settings['ch2'])
        self._update_display()


def apply_bnc_to_image(image_data, min_val, max_val, brightness=128.0, contrast=128.0):
    """Apply brightness/contrast adjustments to image data using ImageJ-style linear transformation.
    
    Args:
        image_data: NumPy array of image data
        min_val: Minimum intensity value (0-255 range)
        max_val: Maximum intensity value (0-255 range)  
        brightness: Brightness adjustment (0-255 range, 128 = no change)
        contrast: Contrast adjustment (0-255 range, 128 = no change)
        
    Returns:
        Adjusted image as uint8 array
    """
    if image_data is None:
        return None
        
    # Convert to float for processing
    img = image_data.astype(np.float32)
    
    # Normalize original data to 0-255 range if needed
    img_min = np.min(img)
    img_max = np.max(img)
    if img_max > img_min:
        img = ((img - img_min) / (img_max - img_min)) * 255
    else:
        img = np.full_like(img, 128)
    
    # ImageJ-style linear transformation with min/max window
    # Step 1: Apply min/max window (basic brightness/contrast)
    if max_val > min_val:
        # Linear mapping: map [min_val, max_val] -> [0, 255]
        img_adjusted = np.clip((img - min_val) / (max_val - min_val) * 255, 0, 255)
    else:
        img_adjusted = np.full_like(img, 128)
    
    # Step 2: Apply additional brightness/contrast adjustments (optional, for UI convenience)
    # This allows fine-tuning beyond the min/max window
    if brightness != 128.0 or contrast != 128.0:
        # Convert brightness from 0-255 to adjustment factor (-128 to +127)
        brightness_adj = brightness - 128.0
        
        # Convert contrast from 0-255 to multiplier (0.0 to 2.0, with 128 = 1.0 = no change)  
        contrast_mult = contrast / 128.0
        
        # Apply brightness (additive)
        img_adjusted = img_adjusted + brightness_adj
        
        # Apply contrast (multiplicative around midpoint)
        midpoint = 127.5
        img_adjusted = (img_adjusted - midpoint) * contrast_mult + midpoint
    
    # Clip to valid range and convert to uint8
    img_adjusted = np.clip(img_adjusted, 0, 255).astype(np.uint8)
    
    return img_adjusted


def create_qimage_from_array(arr):
    """Create QImage from numpy array.
    
    Args:
        arr: NumPy array (grayscale or RGB)
        
    Returns:
        QImage object
    """
    if arr is None:
        return QImage()
        
    # Ensure uint8
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    
    h, w = arr.shape[:2]
    
    if arr.ndim == 2:
        # Grayscale - convert to RGBA
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., 0] = arr  # R
        rgba[..., 1] = arr  # G
        rgba[..., 2] = arr  # B
        rgba[..., 3] = 255  # A
    elif arr.ndim == 3 and arr.shape[2] == 3:
        # RGB - add alpha channel
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., :3] = arr
        rgba[..., 3] = 255
    elif arr.ndim == 3 and arr.shape[2] == 4:
        # Already RGBA
        rgba = arr
    else:
        # Unknown format
        return QImage()
    
    return QImage(rgba.data, w, h, w * 4, QImage.Format.Format_RGBA8888)


def create_composite_image(ch1_data, ch2_data, ch1_settings, ch2_settings):
    """Create composite image from two channels with BnC applied.
    
    Args:
        ch1_data: Channel 1 data (green)
        ch2_data: Channel 2 data (red)
        ch1_settings: BnC settings for channel 1
        ch2_settings: BnC settings for channel 2
        
    Returns:
        Composite image as uint8 RGBA array
    """
    if ch1_data is None:
        return None
        
    # Apply BnC to channel 1 (green)
    ch1_adjusted = apply_bnc_to_image(
        ch1_data, 
        ch1_settings['min'], 
        ch1_settings['max'], 
        ch1_settings.get('brightness', 128.0),
        ch1_settings.get('contrast', 128.0)
    )
    
    h, w = ch1_adjusted.shape
    composite = np.zeros((h, w, 4), dtype=np.uint8)
    
    if ch2_data is not None:
        # Apply BnC to channel 2 (red)  
        ch2_adjusted = apply_bnc_to_image(
            ch2_data,
            ch2_settings['min'],
            ch2_settings['max'], 
            ch2_settings.get('brightness', 128.0),
            ch2_settings.get('contrast', 128.0)
        )
        
        # Ensure same size
        if ch2_adjusted.shape[:2] == (h, w):
            composite[..., 0] = ch2_adjusted  # Red
    
    composite[..., 1] = ch1_adjusted  # Green  
    composite[..., 3] = 255           # Alpha
    
    return composite
