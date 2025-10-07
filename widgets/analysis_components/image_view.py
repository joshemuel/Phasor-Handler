"""
Image View Widget for Analysis Tab

This module contains the ImageViewWidget that handles image display functionality
for the analysis tab, including the reg_tif_label, image scaling with aspect ratio
preservation, and ROI tool integration.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
import numpy as np


class ImageViewWidget(QWidget):
    """
    Widget that handles image display with aspect ratio preservation and ROI integration.
    """
    
    # Signals to communicate with parent
    imageUpdated = pyqtSignal()  # Emitted when a new image is displayed
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()
        
        # Store references for image data
        self._current_image_np = None
        self._current_qimage = None
        
    def setupUI(self):
        """Set up the UI components."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create the main image display label
        self.reg_tif_label = QLabel("Select a directory to view registered images.")
        self.reg_tif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reg_tif_label.setMinimumSize(700, 629)
        self.reg_tif_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout.addWidget(self.reg_tif_label, 1)  # Give stretch factor of 1 to make it greedy
        self.setLayout(layout)
    
    def get_label(self):
        """Get the internal QLabel for ROI tool integration."""
        return self.reg_tif_label
    
    def set_text(self, text):
        """Set text message on the image label."""
        self.reg_tif_label.setText(text)
    
    def clear_pixmap(self):
        """Clear the current pixmap and show default text."""
        self.reg_tif_label.setPixmap(QPixmap())
        self.reg_tif_label.setText("Select a directory to view registered images.")
    
    def set_loading_message(self, message):
        """Set a loading message."""
        self.reg_tif_label.setText(message)
    
    def display_image(self, arr_uint8):
        """
        Display an image array with proper scaling and aspect ratio preservation.
        
        Args:
            arr_uint8: RGBA uint8 array with shape (height, width, 4)
        """
        if arr_uint8 is None or arr_uint8.size == 0:
            self.reg_tif_label.setText("Error: Image data is empty or corrupted.")
            return
        
        h, w, _ = arr_uint8.shape
        qimg = QImage(arr_uint8.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg)
        
        # Store a copy of the displayed image for external use (CNB, etc.)
        try:
            if arr_uint8.shape[2] == 4:
                rgb = arr_uint8[..., :3]
            else:
                rgb = arr_uint8
            self._current_image_np = rgb.copy()
            self._current_qimage = qimg.copy()
        except Exception:
            self._current_image_np = None
            self._current_qimage = None
        
        # Scale and display the final pixmap with aspect ratio preservation
        base_pix = pixmap.scaled(self.reg_tif_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.reg_tif_label.setFixedSize(base_pix.size())
        self.reg_tif_label.setPixmap(base_pix)
        self.reg_tif_label.setText("")
        
        # Emit signal to notify parent that image was updated
        self.imageUpdated.emit()
        
        return base_pix
    
    def display_image_with_bnc(self, arr_uint8, bnc_settings=None, img=None, img_chan2=None, composite_mode=False, active_channel=1):
        """
        Display an image with optional brightness/contrast adjustments.
        
        Args:
            arr_uint8: RGBA uint8 array with shape (height, width, 4)
            bnc_settings: Optional brightness/contrast settings dict
            img: Original single channel image for BnC processing
            img_chan2: Optional second channel image for BnC processing
            composite_mode: Whether composite mode is active
            active_channel: Which channel is active (1 or 2)
        """
        if arr_uint8 is None or arr_uint8.size == 0:
            self.reg_tif_label.setText("Error: Image data is empty or corrupted.")
            return
        
        h, w, _ = arr_uint8.shape
        qimg = QImage(arr_uint8.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg)
        
        # Store a copy of the displayed image
        try:
            if arr_uint8.shape[2] == 4:
                rgb = arr_uint8[..., :3]
            else:
                rgb = arr_uint8
            self._current_image_np = rgb.copy()
            self._current_qimage = qimg.copy()
        except Exception:
            self._current_image_np = None
            self._current_qimage = None
        
        # Apply BnC settings if provided and enabled
        if (bnc_settings and bnc_settings.get('enabled', False) and 
            img is not None):
            try:
                from tools.bnc import apply_bnc_to_image, create_qimage_from_array, create_composite_image
                
                # Apply BnC to current frame
                if img_chan2 is not None and composite_mode:
                    # Composite mode - apply BnC to both channels
                    bnc_img = create_composite_image(img, img_chan2, bnc_settings['ch1'], bnc_settings['ch2'])
                else:
                    # Single channel mode
                    if img_chan2 is not None and active_channel == 2:
                        # Channel 2
                        bnc_img = apply_bnc_to_image(img_chan2, bnc_settings['ch2']['min'], bnc_settings['ch2']['max'], bnc_settings['ch2']['contrast'])
                        # Convert to RGBA grayscale
                        if bnc_img.ndim == 2:
                            h_bnc, w_bnc = bnc_img.shape
                            rgba_bnc = np.zeros((h_bnc, w_bnc, 4), dtype=np.uint8)
                            rgba_bnc[..., :3] = bnc_img[..., None]
                            rgba_bnc[..., 3] = 255
                            bnc_img = rgba_bnc
                    else:
                        # Channel 1
                        bnc_img = apply_bnc_to_image(img, bnc_settings['ch1']['min'], bnc_settings['ch1']['max'], bnc_settings['ch1']['contrast'])
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
                print(f"DEBUG: Error applying BnC in ImageViewWidget: {e}")
                # Fall back to original pixmap if BnC fails
                pass
        
        # Scale and display the final pixmap with aspect ratio preservation
        base_pix = pixmap.scaled(self.reg_tif_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.reg_tif_label.setFixedSize(base_pix.size())
        self.reg_tif_label.setPixmap(base_pix)
        self.reg_tif_label.setText("")
        
        # Emit signal to notify parent that image was updated
        self.imageUpdated.emit()
        
        return base_pix
    
    def get_current_image_data(self):
        """Get the current image data for external processing."""
        return {
            'numpy_array': self._current_image_np,
            'qimage': self._current_qimage
        }
    
    def resize_for_new_image(self, new_width, new_height):
        """
        Resize the widget to accommodate a new image with different dimensions.
        
        Args:
            new_width: Width of the new image
            new_height: Height of the new image
        """
        # Reset the size policy to allow proper resizing
        self.reg_tif_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Set a reasonable minimum size that accommodates different image sizes
        # Use at least the original minimum size (700x629) or larger if needed
        min_width = max(new_width + 40, 700)  # Ensure at least original width or larger
        min_height = max(new_height + 40, 629)  # Ensure at least original height or larger
        
        # Cap at reasonable maximums to prevent huge widgets
        min_width = min(min_width, 1200)
        min_height = min(min_height, 1000)
        
        self.reg_tif_label.setMinimumSize(min_width, min_height)
        
        # Force an update of the layout
        self.reg_tif_label.updateGeometry()
        self.update()
        
        print(f"DEBUG: Resized widget for image {new_width}x{new_height} -> min size {min_width}x{min_height}")
    
    def compute_draw_rect_for_label(self, img_w: int, img_h: int):
        """
        Return the QRect inside the label where the image pixmap will be drawn
        when scaled with aspect ratio preserved.
        
        Args:
            img_w: Image width
            img_h: Image height
            
        Returns:
            QRect: Rectangle where the image is drawn within the label
        """
        lw, lh = self.reg_tif_label.width(), self.reg_tif_label.height()
        if img_w <= 0 or img_h <= 0 or lw <= 0 or lh <= 0:
            return QRect(0, 0, 0, 0)

        scale = min(lw / img_w, lh / img_h)
        sw = int(img_w * scale)  # scaled width
        sh = int(img_h * scale)  # scaled height
        x = (lw - sw) // 2
        y = (lh - sh) // 2

        return QRect(x, y, sw, sh)
    
    def get_label_size(self):
        """Get the current size of the image label."""
        return self.reg_tif_label.size()
    
    def set_error_message(self, message):
        """Display an error message."""
        self.reg_tif_label.setPixmap(QPixmap())
        self.reg_tif_label.setText(message)