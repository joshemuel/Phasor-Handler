import os
import numpy as np

def to_2d(a):
    if a is None:
        return None
    a = np.asarray(a)
    # Squeeze singleton dims first
    a = np.squeeze(a)
    # If still 3-D (H, W, C) keep the first channel
    if a.ndim == 3:
        # assume last dim is channels
        a = a[..., 0]
    # If shape is (C, H, W), after squeeze it could still be 3-D; handle that too
    if a.ndim == 3:
        a = a[0, ...]
    if a.ndim != 2:
        # As a last resort, flatten to 2-D
        a = a.reshape(a.shape[-2], a.shape[-1])
    return a


def detect_source_type(directory_path):
    """Detect microscope source type from directory contents.

    Returns:
        "i3" if 3i data detected (raw .npy files or YAML metadata files),
        "mini" if Mini2P/OPES data detected (CellVideo directories),
        None if source type cannot be determined.
    """
    try:
        contents = os.listdir(directory_path)
    except OSError:
        return None

    # 3i: raw .npy files or YAML metadata files
    if any(fname.endswith("000.npy") for fname in contents):
        return "i3"
    if any(fname in ("ImageRecord.yaml", "ElapsedTimes.yaml") for fname in contents):
        return "i3"
    # Mini2P: CellVideo directories
    if "CellVideo1" in contents:
        return "mini"
    return None


def resolve_timestamps(exp_data, num_frames):
    """Extract per-frame timestamps in seconds from experiment metadata.

    Tries multiple attribute/key names, auto-detects milliseconds vs seconds,
    handles datetime-string timestamps, and falls back to frame_rate estimation.

    Returns:
        list[float] of length *num_frames* (seconds), or None.
    """
    if exp_data is None or num_frames <= 0:
        return None

    _ATTR_NAMES = ('time_stamps', 'timeStamps', 'timestamps', 'ElapsedTimes')

    raw_ts = None
    for name in _ATTR_NAMES:
        if isinstance(exp_data, dict):
            if name in exp_data:
                raw_ts = exp_data[name]
                break
        else:
            if hasattr(exp_data, name):
                raw_ts = getattr(exp_data, name)
                break

    if raw_ts is not None and hasattr(raw_ts, '__len__') and len(raw_ts) > 0:
        try:
            if isinstance(raw_ts[0], str):
                from datetime import datetime
                dt_objects = []
                for ts in raw_ts:
                    dt_objects.append(datetime.strptime(ts, '%Y-%m-%d %H:%M:%S.%f'))
                first_dt = dt_objects[0]
                seconds = [(dt - first_dt).total_seconds() for dt in dt_objects]
            else:
                arr = np.array(raw_ts, dtype=float)
                # Detect ms vs s using median inter-frame interval:
                # at typical imaging rates (1-100 Hz), ms intervals are 10-1000
                # while second intervals are 0.01-1.0
                is_ms = False
                if len(arr) > 1:
                    median_interval = float(np.median(np.diff(arr)))
                    is_ms = median_interval > 5
                elif len(arr) == 1 and arr[0] > 10000:
                    is_ms = True
                if is_ms:
                    seconds = (arr / 1000.0).tolist()
                else:
                    seconds = arr.tolist()

            if len(seconds) >= num_frames:
                return seconds[:num_frames]
            return seconds + [seconds[-1]] * (num_frames - len(seconds))
        except Exception:
            pass

    # Fallback: estimate from frame_rate
    frame_rate = None
    if isinstance(exp_data, dict):
        frame_rate = exp_data.get('frame_rate', None)
    elif hasattr(exp_data, 'frame_rate'):
        frame_rate = getattr(exp_data, 'frame_rate', None)

    if frame_rate is not None:
        try:
            fr = float(frame_rate)
            if fr > 0:
                return [i / fr for i in range(num_frames)]
        except (TypeError, ValueError):
            pass

    return None