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