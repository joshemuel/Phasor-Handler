import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

class HistogramWorker(QObject):
    finished = pyqtSignal(object, object, float, float)  # (counts, bins, min_val, max_val)
    error = pyqtSignal(str)

    def __init__(self, data, min_percentile, max_percentile):
        super().__init__()
        self.data = data
        self.min_percentile = float(min_percentile)
        self.max_percentile = float(max_percentile)

    def run(self):
        try:
            if self.data is None:
                self.error.emit("No data to compute histogram")
                return

            # Flatten once; remove NaNs/Infs if any
            a = np.ravel(self.data)
            if a.size == 0:
                self.error.emit("No data to compute histogram")
                return
            if not np.isfinite(a).all():
                a = a[np.isfinite(a)]

            # Fast path: 8-bit histogram via bincount
            # (If your array is already uint8 this is zero-copy.)
            if a.dtype != np.uint8:
                # Clip to [0,255] and cast without extra copy when possible
                a = np.clip(a, 0, 255).astype(np.uint8, copy=False)

            counts = np.bincount(a, minlength=256).astype(np.int64, copy=False)
            bins = np.arange(257, dtype=np.int32)  # 0..256 edges

            # Percentiles from CDF
            cdf = counts.cumsum()
            total = int(cdf[-1])
            if total == 0:
                self.error.emit("All pixels are masked/empty")
                return

            # rank in [0, total-1], then find first bin where cdf >= rank
            def p2v(p):
                rank = (p / 100.0) * (total - 1)
                return int(np.searchsorted(cdf, rank, side="left"))

            min_val = float(p2v(self.min_percentile))
            max_val = float(p2v(self.max_percentile))

            self.finished.emit(counts, bins, min_val, max_val)

        except Exception as e:
            self.error.emit(f"Histogram computation error: {e}")
