"""
SecondLevelWorker - Compute ROI traces in a background thread.

This worker processes ROI trace extraction to keep the UI responsive.
"""

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal


class SecondLevelWorker(QObject):
    """Worker to compute ROI traces in background thread."""
    
    # Signals
    finished = pyqtSignal(list)  # List of trace data for each ROI
    progress = pyqtSignal(int, int)  # (current, total)
    error = pyqtSignal(str)
    
    def __init__(self, saved_rois, tif, tif_chan2, formula_idx, baseline_seconds, 
                 frame_start, frame_end, page_rois_slice, time_stamps=None, frame_rate=None):
        """
        Initialize worker.
        
        Args:
            saved_rois: List of all saved ROIs
            tif: Channel 1 image data (3D numpy array)
            tif_chan2: Channel 2 image data (3D numpy array or None)
            formula_idx: Formula selection index (0-3)
            baseline_seconds: Baseline duration in seconds
            frame_start: Starting frame for display
            frame_end: Ending frame for display (or None for all)
            page_rois_slice: Tuple of (start_idx, end_idx) for current page
            time_stamps: Optional list of timestamps from metadata
            frame_rate: Optional frame rate from metadata
        """
        super().__init__()
        self.saved_rois = saved_rois
        self.tif = tif
        self.tif_chan2 = tif_chan2
        self.formula_idx = formula_idx
        self.baseline_seconds = float(baseline_seconds)
        self.frame_start = frame_start
        self.frame_end = frame_end
        self.page_rois_slice = page_rois_slice
        self.time_stamps = time_stamps
        self.frame_rate = frame_rate
        
    def run(self):
        """Extract traces for all ROIs on the current page."""
        try:
            start_idx, end_idx = self.page_rois_slice
            page_rois = self.saved_rois[start_idx:end_idx]
            
            trace_data_list = []
            total_rois = len(page_rois)
            
            for idx, roi_data in enumerate(page_rois):
                # Emit progress
                self.progress.emit(idx + 1, total_rois)
                
                # Extract trace for this ROI
                trace = self._extract_roi_trace(roi_data)
                
                # Store the trace data
                trace_data_list.append({
                    'roi_data': roi_data,
                    'roi_idx': start_idx + idx,
                    'trace': trace
                })
            
            # Emit finished signal with all trace data
            self.finished.emit(trace_data_list)
            
        except Exception as e:
            import traceback
            error_msg = f"Error computing traces: {e}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)

    def _seconds_to_frame_count(self, nframes):
        """Convert baseline_seconds to a frame count using available timing info."""
        seconds = self.baseline_seconds

        # --- Try timestamps first ---
        if self.time_stamps is not None and len(self.time_stamps) > 0:
            try:
                if isinstance(self.time_stamps[0], str):
                    from datetime import datetime
                    first_dt = datetime.strptime(self.time_stamps[0], '%Y-%m-%d %H:%M:%S.%f')
                    for idx in range(min(nframes, len(self.time_stamps))):
                        dt = datetime.strptime(self.time_stamps[idx], '%Y-%m-%d %H:%M:%S.%f')
                        elapsed = (dt - first_dt).total_seconds()
                        if elapsed >= seconds:
                            return max(1, idx)
                    return min(nframes, len(self.time_stamps))
                else:
                    ts_arr = np.asarray(self.time_stamps[:min(nframes, len(self.time_stamps))], dtype=float)
                    max_t = float(ts_arr[-1]) if len(ts_arr) > 0 else 0
                    if max_t > 10000:
                        target = seconds * 1000.0
                    else:
                        target = seconds
                    indices = np.where(ts_arr >= target)[0]
                    if len(indices) > 0:
                        return max(1, int(indices[0]))
                    return min(nframes, len(ts_arr))
            except Exception:
                pass

        # --- Fallback: frame_rate ---
        if self.frame_rate is not None and self.frame_rate != 'NA':
            try:
                fr = float(self.frame_rate)
                if fr > 0:
                    return max(1, int(np.ceil(fr * seconds)))
            except (ValueError, TypeError):
                pass

        # --- Last resort: 10% ---
        return max(1, nframes // 10)
    
    def _extract_roi_trace(self, roi_data):
        """Extract the mean signal trace for a given ROI with selected formula."""
        if self.tif is None:
            return None
        
        # Get ROI coordinates
        xyxy = roi_data.get('xyxy')
        if xyxy is None:
            return None
        
        x0, y0, x1, y1 = xyxy
        
        # Ensure 3D stack
        def stack3d(a):
            a = np.asarray(a).squeeze()
            return a[None, ...] if a.ndim == 2 else a
        
        tif = stack3d(self.tif)
        
        # Check bounds
        if x1 <= x0 or y1 <= y0:
            return None
        
        # Ensure coordinates are within image bounds
        height, width = tif.shape[1], tif.shape[2]
        x0 = max(0, min(x0, width - 1))
        x1 = max(x0 + 1, min(x1, width))
        y0 = max(0, min(y0, height - 1))
        y1 = max(y0 + 1, min(y1, height))
        
        # Extract mean signal across ROI for each frame
        try:
            sig1 = tif[:, y0:y1, x0:x1].mean(axis=(1, 2))
            
            # Get channel 2 if available
            sig2 = None
            if self.tif_chan2 is not None:
                tif_chan2 = stack3d(self.tif_chan2)
                sig2 = tif_chan2[:, y0:y1, x0:x1].mean(axis=(1, 2))
            
            # Compute baseline (Fo) from first N seconds of frames
            nframes = len(sig1)
            baseline_count = self._seconds_to_frame_count(nframes)
            baseline_count = max(1, min(baseline_count, nframes))
            Fog = float(np.mean(sig1[:baseline_count]))
            
            # Apply formula
            if sig2 is None:
                # Single channel - only show Fg formulas
                if self.formula_idx == 2:  # Fg only
                    return sig1
                else:  # Default to (Fg - Fog) / Fog
                    denom = Fog if Fog != 0 else 1e-6
                    return (sig1 - Fog) / denom
            else:
                # Dual channel
                if self.formula_idx == 0:  # Fg - Fog / Fr
                    Fog = float(np.mean(sig1[:baseline_count]))
                    For_vals = sig2
                    metric = (sig1 - Fog) / (For_vals + 1e-6)
                    return metric
                elif self.formula_idx == 1:  # Fg - Fog / Fog
                    denom = Fog if Fog != 0 else 1e-6
                    return (sig1 - Fog) / denom
                elif self.formula_idx == 2:  # Fg only
                    return sig1
                elif self.formula_idx == 3:  # Fr only
                    return sig2
                else:
                    return sig1
                    
        except Exception as e:
            print(f"Error extracting trace for ROI: {e}")
            return None
