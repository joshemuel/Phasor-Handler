"""
Image View Widget for Analysis Tab

This module contains the ImageViewWidget that handles image display functionality
for the analysis tab, including the reg_tif_label, image scaling with aspect ratio
preservation, and ROI tool integration.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QFont, QColor
import numpy as np
import os
import pickle
import subprocess
import tifffile


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
        self.reg_tif_label.setMinimumSize(700, 700)
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
    
    def display_image(self, arr_uint8, show_scale_bar=False, metadata=None):
        """
        Display an image array with proper scaling and aspect ratio preservation.
        
        Args:
            arr_uint8: RGBA uint8 array with shape (height, width, 4)
            show_scale_bar: Whether to draw scale bar on the image
            metadata: Experiment metadata for scale bar calculations
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
        
        # Add scale bar if requested
        if show_scale_bar and metadata is not None:
            pixel_size = self.get_pixel_size_from_metadata(metadata)
            if pixel_size is not None:
                base_pix = self.draw_scale_bar(base_pix, pixel_size, w, h)
        
        self.reg_tif_label.setFixedSize(base_pix.size())
        self.reg_tif_label.setPixmap(base_pix)
        self.reg_tif_label.setText("")
        
        # Emit signal to notify parent that image was updated
        self.imageUpdated.emit()
        
        return base_pix
    
    def display_image_with_bnc(self, arr_uint8, bnc_settings=None, img=None, img_chan2=None, composite_mode=False, active_channel=1, show_scale_bar=False, metadata=None):
        """
        Display an image with optional brightness/contrast adjustments.
        
        Args:
            arr_uint8: RGBA uint8 array with shape (height, width, 4)
            bnc_settings: Optional brightness/contrast settings dict
            img: Original single channel image for BnC processing
            img_chan2: Optional second channel image for BnC processing
            composite_mode: Whether composite mode is active
            active_channel: Which channel is active (1 or 2)
            show_scale_bar: Whether to draw scale bar on the image
            metadata: Experiment metadata for scale bar calculations
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
                from .bnc import apply_bnc_to_image, create_qimage_from_array, create_composite_image
                
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
        
        # Add scale bar if requested
        if show_scale_bar and metadata is not None:
            pixel_size = self.get_pixel_size_from_metadata(metadata)
            if pixel_size is not None:
                base_pix = self.draw_scale_bar(base_pix, pixel_size, w, h)
        
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

    def load_experiment_data(self, directory_path, use_registered=True):
        """
        Load experiment image data from directory.
        
        Args:
            directory_path (str): Path to the experiment directory
            use_registered (bool): Whether to prefer registered TIFF files over raw numpy
            
        Returns:
            dict: {
                'tif': numpy array or None,
                'tif_chan2': numpy array or None, 
                'metadata': dict or None,
                'nframes': int,
                'has_registered_tif': bool,
                'has_raw_numpy': bool,
                'success': bool,
                'error': str or None
            }
        """
        result = {
            'tif': None,
            'tif_chan2': None,
            'metadata': None,
            'nframes': 0,
            'has_registered_tif': False,
            'has_raw_numpy': False,
            'success': False,
            'error': None
        }
        
        try:
            # Define file paths
            reg_tif_path = os.path.join(directory_path, "Ch1-reg.tif")
            reg_tif_chan2_path = os.path.join(directory_path, "Ch2-reg.tif")
            npy_ch0_path = os.path.join(directory_path, "ImageData_Ch0_TP0000000.npy")
            npy_ch1_path = os.path.join(directory_path, "ImageData_Ch1_TP0000000.npy")
            exp_details = os.path.join(directory_path, "experiment_summary.pkl")
            exp_json = os.path.join(directory_path, "experiment_summary.json")
            
            # Check what files are available
            result['has_registered_tif'] = os.path.isfile(reg_tif_path)
            result['has_raw_numpy'] = os.path.isfile(npy_ch0_path)
            
            # Load image data based on preference and availability
            if use_registered and result['has_registered_tif']:
                self._load_registered_tiffs(reg_tif_path, reg_tif_chan2_path, result)
            elif not use_registered and result['has_raw_numpy']:
                self._load_raw_numpy(npy_ch0_path, npy_ch1_path, result)
            elif use_registered and not result['has_registered_tif'] and result['has_raw_numpy']:
                # Fallback to raw numpy if registered not available
                self._load_raw_numpy(npy_ch0_path, npy_ch1_path, result)
            elif not use_registered and not result['has_raw_numpy'] and result['has_registered_tif']:
                # Fallback to registered if raw not available
                self._load_registered_tiffs(reg_tif_path, reg_tif_chan2_path, result)
            else:
                result['error'] = "No suitable image files found in directory"
                return result
            
            # Load metadata
            result['metadata'] = self._load_experiment_metadata(exp_details, exp_json, directory_path)
            
            # Calculate number of frames
            if result['tif'] is not None:
                result['nframes'] = result['tif'].shape[0] if result['tif'].ndim == 3 else 1
                # If we have channel 2, limit frames to the minimum of both channels
                if result['tif_chan2'] is not None and result['tif_chan2'].ndim == 3:
                    ch2_frames = result['tif_chan2'].shape[0]
                    result['nframes'] = min(result['nframes'], ch2_frames)
                
                result['success'] = True
            else:
                result['error'] = "Failed to load image data"
                
        except Exception as e:
            result['error'] = str(e)
            
        return result

    def _load_registered_tiffs(self, reg_tif_path, reg_tif_chan2_path, result):
        """Load registered TIFF files with robust error handling."""
        self.set_loading_message("Loading registered TIFF files...")
        
        try:
            # Load Channel 1
            file_size = os.path.getsize(reg_tif_path) / (1024*1024)  # MB
            print(f"DEBUG: TIFF file size: {file_size:.1f} MB at {reg_tif_path}")
            
            result['tif'] = self._robust_tiff_load(reg_tif_path, "Ch1")
            
            # Load Channel 2 if available
            if os.path.isfile(reg_tif_chan2_path):
                self.set_loading_message("Loading registered TIFF files (Channel 2)...")
                file_size_ch2 = os.path.getsize(reg_tif_chan2_path) / (1024*1024)  # MB
                print(f"DEBUG: Ch2 TIFF file size: {file_size_ch2:.1f} MB at {reg_tif_chan2_path}")
                
                result['tif_chan2'] = self._robust_tiff_load(reg_tif_chan2_path, "Ch2")
                
        except Exception as e:
            raise Exception(f"Failed to load registered TIFF files: {e}")

    def _load_raw_numpy(self, npy_ch0_path, npy_ch1_path, result):
        """Load raw numpy files."""
        self.set_loading_message("Loading raw numpy files...")
        
        try:
            # Load Channel 0 (usually Channel 1 in the UI)
            print(f"DEBUG: Loading raw numpy from {npy_ch0_path}")
            result['tif'] = np.load(npy_ch0_path)
            print(f"DEBUG: Ch0 shape: {result['tif'].shape}, dtype: {result['tif'].dtype}")
            
            # Load Channel 1 (usually Channel 2 in the UI) if available
            if os.path.isfile(npy_ch1_path):
                print(f"DEBUG: Loading Ch1 from {npy_ch1_path}")
                result['tif_chan2'] = np.load(npy_ch1_path)
                print(f"DEBUG: Ch1 shape: {result['tif_chan2'].shape}, dtype: {result['tif_chan2'].dtype}")
                
        except Exception as e:
            raise Exception(f"Failed to load raw numpy files: {e}")

    def _robust_tiff_load(self, tiff_path, channel_name):
        """Load TIFF file with multiple fallback methods."""
        # Get page count for validation
        page_count = None
        try:
            with tifffile.TiffFile(tiff_path) as tiff:
                page_count = len(tiff.pages)
                print(f"DEBUG: {channel_name} TIFF file contains {page_count} pages/frames")
                if page_count > 0:
                    first_page = tiff.pages[0]
                    print(f"DEBUG: {channel_name} first page shape: {first_page.shape}")
        except Exception as page_error:
            print(f"DEBUG: Could not examine {channel_name} TIFF pages: {page_error}")
        
        # Try multiple loading methods
        loading_methods = [
            ("tifffile.imread", lambda: tifffile.imread(tiff_path)),
            ("tifffile.imread(memmap=False)", lambda: tifffile.imread(tiff_path, memmap=False)),
            ("page-by-page", lambda: self._load_tiff_page_by_page(tiff_path))
        ]
        
        for method_name, load_func in loading_methods:
            try:
                print(f"DEBUG: {channel_name} Method - {method_name}...")
                tif_data = load_func()
                print(f"DEBUG: {channel_name} Method SUCCESS - shape: {tif_data.shape}, dtype: {tif_data.dtype}")
                
                # Validate frame count if we have page count
                actual_frames = tif_data.shape[0] if tif_data.ndim >= 3 else 1
                if page_count and actual_frames != page_count:
                    print(f"DEBUG: {channel_name} WARNING - Loaded {actual_frames} frames but TIFF has {page_count} pages!")
                    if method_name != "page-by-page":  # Try next method
                        continue
                
                print(f"DEBUG: {channel_name} successfully loaded using: {method_name}")
                return tif_data
                
            except Exception as method_error:
                print(f"DEBUG: {channel_name} Method {method_name} FAILED: {method_error}")
                continue
        
        raise Exception(f"All loading methods failed for {channel_name} TIFF: {tiff_path}")

    def _load_tiff_page_by_page(self, tiff_path):
        """Load TIFF file page by page as fallback method."""
        with tifffile.TiffFile(tiff_path) as tiff:
            if len(tiff.pages) == 0:
                raise ValueError("No pages found in TIFF file")
            
            # Get dimensions from first page
            first_page_array = tiff.pages[0].asarray()
            page_shape = first_page_array.shape
            total_pages = len(tiff.pages)
            
            print(f"DEBUG: Creating array for {total_pages} pages of shape {page_shape}")
            tif_data = np.zeros((total_pages,) + page_shape, dtype=first_page_array.dtype)
            
            # Load each page
            for i, page in enumerate(tiff.pages):
                tif_data[i] = page.asarray()
                if i % 500 == 0 or i < 5 or i >= total_pages - 3:
                    print(f"DEBUG: Loaded page {i}/{total_pages}")
            
            return tif_data

    def _load_experiment_metadata(self, exp_details, exp_json, directory_path):
        """Load experiment metadata from pickle or JSON files."""
        metadata = None
        
        # First try to read existing pickle file
        if os.path.isfile(exp_details):
            try:
                print(f"DEBUG: Loading experiment metadata from {exp_details}")
                with open(exp_details, 'rb') as f:
                    metadata = pickle.load(f)
                print(f"DEBUG: Loaded experiment metadata type: {type(metadata)}")
            except Exception as e:
                print(f"DEBUG: Failed to load pickle metadata: {e}")
        
        # If no metadata exists or failed to load, try JSON
        if metadata is None and os.path.isfile(exp_json):
            try:
                print(f"DEBUG: Loading experiment metadata from {exp_json}")
                import json
                with open(exp_json, 'r') as f:
                    metadata = json.load(f)
                print(f"DEBUG: Loaded JSON metadata")
            except Exception as e:
                print(f"DEBUG: Failed to load JSON metadata: {e}")
        
        # If still no metadata, try to read from raw files
        if metadata is None:
            try:
                print(f"DEBUG: Attempting to read metadata from raw files in {directory_path}")
                result = subprocess.run([
                    'python', 'scripts/meta_reader.py', '-f', directory_path
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    print("DEBUG: meta_reader.py executed successfully")
                    # Try loading the newly created files
                    if os.path.isfile(exp_details):
                        with open(exp_details, 'rb') as f:
                            metadata = pickle.load(f)
                        print("DEBUG: Successfully loaded newly created metadata")
                    elif os.path.isfile(exp_json):
                        import json
                        with open(exp_json, 'r') as f:
                            metadata = json.load(f)
                        print("DEBUG: Successfully loaded newly created JSON metadata")
                else:
                    print(f"DEBUG: meta_reader.py failed: {result.stderr}")
            except Exception as e:
                print(f"DEBUG: Failed to run meta_reader.py: {e}")
        
        return metadata

    def clear_experiment(self):
        """Clear all experiment data and reset display."""
        self.clear_pixmap()
        self._current_image_np = None
        self._current_qimage = None

    def draw_scale_bar(self, pixmap, pixel_size_microns, img_width, img_height):
        """
        Draw a scale bar on the given pixmap.
        
        Args:
            pixmap: QPixmap to draw on
            pixel_size_microns: Size of one pixel in microns (from metadata)
            img_width: Original image width in pixels
            img_height: Original image height in pixels
            
        Returns:
            QPixmap with scale bar drawn
        """
        if pixel_size_microns is None or pixel_size_microns <= 0:
            print("DEBUG: Invalid pixel size for scale bar")
            return pixmap
        
        # Create a copy to draw on
        pixmap_with_scale = QPixmap(pixmap)
        painter = QPainter(pixmap_with_scale)
        
        try:
            # Calculate scale factor between original image and displayed pixmap
            scale_factor = min(pixmap.width() / img_width, pixmap.height() / img_height)
            
            # Calculate appropriate scale bar length
            # Aim for ~10% of image width, rounded to nice values
            desired_length_pixels = img_width * 0.1
            desired_length_microns = desired_length_pixels * pixel_size_microns
            
            # Round to nice values (1, 2, 5, 10, 20, 50, 100, etc.)
            scale_bar_microns = self._round_to_nice_value(desired_length_microns)
            scale_bar_pixels = scale_bar_microns / pixel_size_microns
            
            # Scale to displayed pixmap size
            display_scale_bar_pixels = scale_bar_pixels * scale_factor
            
            # Position scale bar at bottom right
            margin = 20
            bar_height = 10
            text_height = 15
            
            # Ensure scale bar fits within image bounds
            min_margin = 10
            max_bar_width = pixmap.width() - (2 * min_margin)
            if display_scale_bar_pixels > max_bar_width:
                # If calculated scale bar is too long, recalculate with smaller size
                display_scale_bar_pixels = max_bar_width
                scale_bar_pixels = display_scale_bar_pixels / scale_factor
                scale_bar_microns = scale_bar_pixels * pixel_size_microns
            
            # Scale bar rectangle
            bar_x = pixmap.width() - display_scale_bar_pixels - margin
            bar_y = pixmap.height() - margin - bar_height - text_height - 5
            
            # Ensure minimum margins
            bar_x = max(min_margin, bar_x)
            bar_y = max(min_margin, bar_y)
            
            # Draw scale bar
            painter.setPen(QPen(QColor(Qt.GlobalColor.white), 2))  # White, 2px wide
            painter.drawLine(int(bar_x),              # Start X
                 int(bar_y + bar_height), # Start Y (bottom of where rect would be)
                 int(bar_x + display_scale_bar_pixels), # End X
                 int(bar_y + bar_height))
            
            # Draw text label
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(QColor(Qt.GlobalColor.white), 1))  # Black text
            
            # Format label
            if scale_bar_microns >= 1000:
                label = f"{scale_bar_microns/1000:.0f} mm"
            elif scale_bar_microns >= 1:
                label = f"{scale_bar_microns:.0f} μm"
            else:
                label = f"{scale_bar_microns:.1f} μm"
            
            text_x = bar_x + (display_scale_bar_pixels / 2) - (len(label) * 3)  # Rough centering
            text_y = bar_y + bar_height + text_height
            painter.drawText(int(text_x), int(text_y), label)
            
        finally:
            painter.end()
        
        return pixmap_with_scale

    def _round_to_nice_value(self, value):
        """
        Round a value to a nice scale bar length (1, 2, 5, 10, 20, 50, 100, etc.)
        """
        if value <= 0:
            return 1
        
        # Find the appropriate order of magnitude
        magnitude = 10 ** np.floor(np.log10(value))
        normalized = value / magnitude
        
        # Choose nice values
        if normalized <= 1:
            nice_value = 1
        elif normalized <= 2:
            nice_value = 2
        elif normalized <= 5:
            nice_value = 5
        else:
            nice_value = 10
        
        return nice_value * magnitude

    def get_pixel_size_from_metadata(self, metadata):
        """
        Extract pixel size in microns from experiment metadata.
        
        Args:
            metadata: Experiment metadata dict or object
            
        Returns:
            float: Pixel size in microns per pixel, or None if not found
        """
        if metadata is None:
            return None
        
        try:
            # Try different possible locations for pixel size
            if isinstance(metadata, dict):
                # Check direct key
                if 'pixel_size' in metadata:
                    return float(metadata['pixel_size'])
                
                # Check nested structure from ImageRecord.yaml
                if ('ImageRecord.yaml' in metadata and 
                    'CLensDef70' in metadata['ImageRecord.yaml'] and
                    'mMicronPerPixel' in metadata['ImageRecord.yaml']['CLensDef70']):
                    return float(metadata['ImageRecord.yaml']['CLensDef70']['mMicronPerPixel'])
                    
            # Try as object with attributes
            elif hasattr(metadata, 'pixel_size'):
                return float(metadata.pixel_size)
            elif hasattr(metadata, 'mMicronPerPixel'):
                return float(metadata.mMicronPerPixel)
                
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            print(f"DEBUG: Could not extract pixel size from metadata: {e}")
        
        return None