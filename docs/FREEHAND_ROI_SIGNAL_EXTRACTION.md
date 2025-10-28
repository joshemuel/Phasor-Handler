# Freehand ROI Signal Extraction

## Overview

The freehand ROI functionality in `CircleRoiTool` fully supports signal extraction from irregularly shaped regions. The tool generates boolean masks that precisely identify which pixels are inside the drawn polygon, enabling accurate signal calculations including integrals (sums).

## How It Works

### 1. Mask Generation

When you draw a freehand ROI, the tool:
- Tracks the mouse path as a list of (x, y) coordinates
- Closes the polygon by connecting the last point to the first
- Generates a boolean mask using matplotlib's Path.contains_points()
- Returns mask where `True` = pixel inside polygon, `False` = outside

### 2. Signal Calculation Methods

The boolean mask enables various signal calculations:

**Mean Signal** - Average intensity inside ROI:
```python
mask_result = roi_tool.get_ellipse_mask()
X0, Y0, X1, Y1, mask = mask_result
roi_data = image[Y0:Y1, X0:X1]
values = roi_data[mask]
mean_signal = values.mean()
```

**Integral (Sum)** - Total signal inside ROI:
```python
total_signal = values.sum()  # Sum of all pixel values
```

**Other Statistics**:
```python
median = np.median(values)
std = values.std()
min_val = values.min()
max_val = values.max()
```

### 3. Time Series Extraction

For multi-frame data (e.g., calcium imaging):

```python
# Extract mean signal over time
num_frames = tif_stack.shape[0]
trace = np.zeros(num_frames)

for i in range(num_frames):
    roi_data = tif_stack[i, Y0:Y1, X0:X1]
    values = roi_data[mask]
    trace[i] = values.mean()

# Now trace contains the mean signal at each time point
```

## Using the Helper Functions

Import the helper module:
```python
from phasor_handler.utils.roi_signal_extraction import (
    extract_roi_signal,
    extract_roi_timeseries,
    extract_multichannel_roi_timeseries,
    get_freehand_polygon_area
)
```

### Single Frame Statistics
```python
# Get comprehensive statistics from current frame
stats = extract_roi_signal(image_data, roi_tool)

if stats:
    print(f"Mean: {stats['mean']:.2f}")
    print(f"Integral: {stats['sum']:.0f}")
    print(f"Pixels in ROI: {stats['pixels']}")
    print(f"Mode: {stats['mode']}")  # 'circular' or 'freehand'
```

### Time Series (Single Channel)
```python
# Extract mean signal over time
trace = extract_roi_timeseries(tif_stack, roi_tool, aggregation='mean')

# Or extract total signal (integral) over time
integral_trace = extract_roi_timeseries(tif_stack, roi_tool, aggregation='sum')

# Plot the trace
import matplotlib.pyplot as plt
plt.plot(trace)
plt.xlabel('Frame')
plt.ylabel('Mean Intensity')
plt.title('ROI Signal Over Time')
plt.show()
```

### Multi-Channel Time Series
```python
# Extract signals from both channels
signals = extract_multichannel_roi_timeseries(dual_channel_stack, roi_tool)

ch1_trace = signals['channel_0']
ch2_trace = signals['channel_1']

# Calculate ratio
ratio = ch1_trace / ch2_trace

# Plot both channels
plt.figure(figsize=(10, 6))
plt.plot(ch1_trace, label='Channel 1', color='green')
plt.plot(ch2_trace, label='Channel 2', color='red')
plt.plot(ratio, label='Ch1/Ch2 Ratio', color='blue', linestyle='--')
plt.legend()
plt.show()
```

### Polygon Area
```python
# For freehand ROIs, calculate the geometric area
area = get_freehand_polygon_area(roi_tool)
if area:
    print(f"Polygon area: {area:.2f} square pixels")
```

## Integration with Existing Analysis Code

The freehand ROI works seamlessly with the existing analysis workflow. The `get_ellipse_mask()` method works for both circular and freehand ROIs:

```python
def analyze_roi(image_stack, roi_tool):
    """Analyze ROI regardless of shape (circular or freehand)."""
    
    # Get mask (works for both modes)
    mask_result = roi_tool.get_ellipse_mask()
    
    if mask_result is None:
        print("No ROI defined")
        return None
    
    X0, Y0, X1, Y1, mask = mask_result
    
    # Extract signals
    num_frames = image_stack.shape[0]
    signals = []
    
    for frame_idx in range(num_frames):
        frame = image_stack[frame_idx]
        roi_region = frame[Y0:Y1, X0:X1]
        
        # Apply mask - only pixels inside polygon/ellipse
        values_inside = roi_region[mask]
        
        # Calculate metric (mean, sum, etc.)
        frame_signal = values_inside.mean()
        signals.append(frame_signal)
    
    return np.array(signals)
```

## Mathematical Details

### Polygon Point-in-Polygon Test

The mask generation uses the **ray casting algorithm** (via matplotlib's Path):
1. For each pixel, cast a ray from the pixel to infinity
2. Count how many times the ray crosses the polygon edges
3. If odd number of crossings → inside
4. If even number of crossings → outside

This is very accurate for irregular, non-convex polygons.

### Integral Calculation

The integral is simply the sum of all pixel values inside the mask:

$$
\text{Integral} = \sum_{(x,y) \in \text{ROI}} I(x,y)
$$

Where:
- $I(x,y)$ is the intensity at pixel $(x,y)$
- The sum is over all pixels where `mask[x,y] == True`

For normalized calculations (e.g., average intensity per unit area):

$$
\text{Mean} = \frac{1}{N_{\text{pixels}}} \sum_{(x,y) \in \text{ROI}} I(x,y)
$$

### Polygon Area (Shoelace Formula)

For freehand ROIs, the geometric area is calculated using:

$$
A = \frac{1}{2} \left| \sum_{i=0}^{n-1} (x_i y_{i+1} - x_{i+1} y_i) \right|
$$

Where the polygon has vertices $(x_0, y_0), (x_1, y_1), \ldots, (x_{n-1}, y_{n-1})$

## Examples and Demos

### Run the Interactive Demo
```bash
python demo_freehand_signal_extraction.py
```

This demo:
- Displays a test image with known gradient
- Allows you to draw freehand ROIs
- Calculates and displays all statistics in real-time
- Shows comparison with full image statistics

### Run the Basic Test
```bash
python test_freehand_roi.py
```

This test:
- Demonstrates mode switching
- Shows coordinate output
- Verifies mask generation

## Performance Considerations

- **Point sampling**: The tool samples mouse positions every ~2 pixels to balance accuracy and performance
- **Mask generation**: Uses efficient numpy vectorization
- **Memory**: Mask is only created for the bounding box region, not the full image
- **Speed**: Typical mask generation takes <10ms for ROIs up to 500x500 pixels

## Comparison: Circular vs Freehand

| Aspect | Circular ROI | Freehand ROI |
|--------|-------------|--------------|
| Drawing | Click-drag defines ellipse | Click-drag traces path |
| Shape | Always elliptical | Arbitrary polygon |
| Rotation | Supported | N/A (inherent in shape) |
| Best for | Regular structures | Irregular structures |
| Precision | Good for round cells | Excellent for any shape |
| Signal extraction | Identical method | Identical method |

Both modes use the same `get_ellipse_mask()` method for signal extraction!

## Troubleshooting

**Q: My freehand ROI is rejected**
- A: Need at least 3 points. Draw a larger path.

**Q: Mask seems incorrect**
- A: Ensure image coordinates match the displayed image size
- Check that `set_image_size()` was called correctly

**Q: Signal extraction returns None**
- A: Verify that an ROI is drawn and finalized
- Check that the mask overlaps with valid image data

**Q: Time series extraction is slow**
- A: For large stacks, consider using the helper functions which are optimized
- Process in chunks if memory is limited

## API Reference

### CircleRoiTool Methods

**`set_drawing_mode(mode: str)`**
- Set mode to 'circular' or 'freehand'

**`get_drawing_mode() -> str`**
- Returns current mode

**`get_ellipse_mask() -> tuple or None`**
- Returns (X0, Y0, X1, Y1, mask) where mask is boolean array
- Works for both circular and freehand modes

**`get_freehand_points_image_coords() -> list or None`**
- Returns list of (x, y) tuples for polygon vertices
- Only available in freehand mode

### Helper Functions

See `phasor_handler/utils/roi_signal_extraction.py` for complete documentation.

## Future Enhancements

Potential additions:
- ✓ Signal extraction (implemented)
- ✓ Polygon area calculation (implemented)
- ⚬ Polygon perimeter calculation
- ⚬ Centroid calculation
- ⚬ Convex hull
- ⚬ Polygon simplification (reduce number of vertices)
- ⚬ Save/load polygon coordinates
- ⚬ Export masks as images

## References

- Ray casting algorithm: https://en.wikipedia.org/wiki/Point_in_polygon
- Shoelace formula: https://en.wikipedia.org/wiki/Shoelace_formula
- Matplotlib Path: https://matplotlib.org/stable/api/path_api.html
