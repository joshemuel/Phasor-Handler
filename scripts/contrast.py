"""Contrast and brightness helpers (ImageJ-style).

Public functions:
- ij_auto_contrast(img, saturated=0.35) -> np.ndarray (float32 0..1)
- compute_cnb_min_max(img) -> (min, max)
- apply_cnb_to_uint8(img, lo, hi, contrast=1.0) -> np.ndarray (uint8)
- qimage_from_uint8(img_u8) -> QImage

Notes:
- ImageJ’s “Auto” = clip ~saturated% at each tail, then linear map to [0..1].
- For composites: call ij_auto_contrast() per channel, then compose RGB yourself.
"""
from typing import Tuple
import numpy as np


def _finite(a: np.ndarray) -> np.ndarray:
    """Return a flattened view of finite values only (ignore NaN/inf)."""
    a = np.asarray(a)
    if not np.issubdtype(a.dtype, np.number):
        a = a.astype(np.float32, copy=False)
    a = a.ravel()
    if np.issubdtype(a.dtype, np.floating):
        a = a[np.isfinite(a)]
    return a


def ij_auto_contrast(img, saturated: float = 0.35) -> np.ndarray:
    """ImageJ-like auto contrast for a SINGLE-channel image.
    Returns a float32 array scaled to 0..1.

    Implementation detail:
    - Uses percentiles (saturated% low, saturated% high) to set lo/hi.
    - Works for 8/16-bit integers and floats (NaN/inf ignored).
    """
    a = np.asarray(img)
    if a.size == 0:
        return a.astype(np.float32)

    vals = _finite(a)
    if vals.size == 0:
        return np.zeros_like(a, dtype=np.float32)

    # Symmetric tail clip (ImageJ “Auto” default ≈ 0.35% each tail)
    low_p = float(saturated)
    high_p = 100.0 - float(saturated)

    lo, hi = np.percentile(vals, [low_p, high_p])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        # Degenerate data (flat image, NaNs, etc.)
        out = np.zeros_like(a, dtype=np.float32)
        return out

    out = (a.astype(np.float32) - float(lo)) / (float(hi) - float(lo))
    np.clip(out, 0.0, 1.0, out=out)
    return out


def compute_cnb_min_max(img: np.ndarray) -> Tuple[float, float]:
    """Compute min/max display window from data (handles grayscale or RGB).
    For RGB, uses luminance (like a typical preview), but in ImageJ you’d
    normally calculate per channel. Use this mainly for a default guess.
    """
    if img is None:
        return 0.0, 255.0
    a = np.asarray(img)
    if a.size == 0:
        return 0.0, 0.0

    if a.ndim == 3 and a.shape[2] >= 3:
        # Perceived luminance (ITU-R BT.601)
        lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]).ravel()
        vals = _finite(lum)
    else:
        vals = _finite(a)

    if vals.size == 0:
        return 0.0, 0.0

    return float(vals.min()), float(vals.max())


def apply_cnb_to_uint8(img: np.ndarray, lo: float, hi: float, contrast: float = 1.0) -> np.ndarray:
    """Apply min/max (window) mapping and contrast around mid-gray; return uint8.

    - img: input array (H,W) or (H,W,C). For ImageJ behavior, pass a SINGLE channel
      (e.g., green or red) and compose RGB yourself afterwards.
    - lo, hi: display window [lo..hi] in source units (like ImageJ’s min/max).
    - contrast: multiplier around 0.5 after normalization (1.0 = no change).

    Returns uint8 of same shape (alpha dropped if present).
    """
    a = np.asarray(img).astype(np.float32, copy=False)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        # fallback to trivial map
        if a.size == 0:
            return np.zeros_like(a, dtype=np.uint8)
        vmin, vmax = float(np.nanmin(a)), float(np.nanmax(a))
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
            out = np.zeros_like(a, dtype=np.uint8)
            return out
        lo, hi = vmin, vmax

    # Window/level mapping
    out = (a - float(lo)) / (float(hi) - float(lo))
    # Contrast around midpoint (display-domain, same feel as IJ slider)
    out = 0.5 + (out - 0.5) * float(contrast)
    np.clip(out, 0.0, 1.0, out=out)

    img_u8 = (out * 255.0).astype(np.uint8)
    if img_u8.ndim == 3 and img_u8.shape[2] >= 4:
        img_u8 = img_u8[..., :3]  # drop alpha if any
    return img_u8


def qimage_from_uint8(img_u8):
    """Build a PyQt6 QImage from a uint8 numpy array without channel swapping.
    Accepts 2D (grayscale) or 3D (RGB) arrays. Caller owns array lifetime while QImage lives.
    """
    from PyQt6.QtGui import QImage

    img_u8 = np.ascontiguousarray(img_u8)  # ensure row stride is compact/consistent
    h, w = img_u8.shape[:2]

    if img_u8.ndim == 2 or (img_u8.ndim == 3 and img_u8.shape[2] == 1):
        fmt = QImage.Format.Format_Grayscale8
        return QImage(img_u8.data, w, h, img_u8.strides[0], fmt)
    else:
        # Expect RGB order; no BGR swap!
        fmt = QImage.Format.Format_RGB888
        return QImage(img_u8.data, w, h, img_u8.strides[0], fmt)
