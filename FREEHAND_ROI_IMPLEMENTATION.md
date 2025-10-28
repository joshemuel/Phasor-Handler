# Freehand ROI Implementation

## Overview
The `CircleRoiTool` class has been extended to support both circular (elliptical) and freehand drawing modes. Users can now draw freeform polygonal ROIs by tracking mouse movements.

## Changes Made

### 1. circle_roi.py Modifications

#### New Features Added:
- **Drawing Mode Support**: Added `_drawing_mode` attribute that can be 'circular' (default) or 'freehand'
- **Freehand Path Tracking**: Added `_freehand_points` list to store QPointF coordinates during freehand drawing
- **Mode Setter/Getter**: 
  - `set_drawing_mode(mode)`: Set the drawing mode ('circular' or 'freehand')
  - `get_drawing_mode()`: Get the current drawing mode

#### Modified Methods:
- **`__init__`**: Added initialization for drawing mode and freehand points
- **`clear()` and `clear_selection()`**: Now also clear freehand points
- **Mouse Event Handling**:
  - `MouseButtonPress`: Initializes freehand point list when starting to draw
  - `MouseMove`: Tracks mouse path and adds points to freehand list (with minimum distance threshold of 2 pixels)
  - `MouseButtonRelease`: Finalizes the freehand path (requires at least 3 points)
- **`_update_bbox_from_freehand_points()`**: New method to compute bounding box from freehand points
- **`_paint_overlay()`**: Updated to draw polygon paths for freehand ROIs with visual feedback
- **`get_ellipse_mask()`**: Extended to support freehand polygon masks using matplotlib.path
- **`_get_freehand_mask()`**: New method that generates boolean masks for freehand polygons
- **`_label_point_to_image_coords()`**: New helper to convert label coordinates to image coordinates
- **`get_freehand_points_image_coords()`**: New method to retrieve freehand points in image coordinates

#### Freehand Drawing Behavior:
1. User presses left mouse button to start drawing
2. As the mouse moves, points are collected (minimum 2-pixel spacing to reduce redundancy)
3. A live polygon preview is shown during drawing
4. On mouse release, the path is automatically closed (last point connects to first)
5. At least 3 points are required to create a valid freehand ROI
6. A bounding box is shown with dashed lines for reference

### 2. view.py Modifications

#### UI Components Added:
- **ROI Tool Selection Group**: New QGroupBox with two toggle buttons:
  - `circular_roi_button`: Toggle circular/elliptical ROI mode (default: checked)
  - `freehand_roi_button`: Toggle freehand ROI mode
- Both buttons are mutually exclusive (only one can be active at a time)

#### New Methods:
- **`_on_roi_tool_toggled(mode, checked)`**: Handles button toggling logic
  - Ensures mutual exclusivity between modes
  - Updates the ROI tool's drawing mode
  - Defaults back to circular if user tries to uncheck all modes
  - Prints status messages for user feedback

#### Button State Management:
- Buttons are enabled when an image is loaded
- Buttons are disabled when no experiment data is present
- The ROI tool group is added to the right column (midr_vbox) in the UI

### 3. Test Script
Created `test_freehand_roi.py` - a standalone test application to verify:
- Mode switching between circular and freehand
- Freehand path drawing and visualization
- ROI finalization and coordinate reporting
- Mask generation for both modes

## Data Structure

### Freehand ROI Storage:
- **During Drawing**: List of `QPointF` objects stored in `_freehand_points`
- **After Finalization**: 
  - Bounding box: `(x0, y0, x1, y1)` in image coordinates
  - Polygon points: N x 2 array of (x, y) coordinates in image coordinates
  - Mask: Boolean numpy array indicating pixels inside the polygon

### Coordinate Systems:
1. **Label Coordinates**: Widget/display coordinates where drawing occurs
2. **Image Coordinates**: Original image pixel coordinates (what gets saved/processed)
3. **Normalized Coordinates**: [0, 1] range used for coordinate transformation

## Usage

### Programmatic Usage:
```python
# Set drawing mode
roi_tool.set_drawing_mode('freehand')  # or 'circular'

# Check current mode
current_mode = roi_tool.get_drawing_mode()

# Get freehand points after drawing
if roi_tool.get_drawing_mode() == 'freehand':
    points = roi_tool.get_freehand_points_image_coords()
    # Returns list of (x, y) tuples in image coordinates

# Get mask (works for both modes)
mask_result = roi_tool.get_ellipse_mask()
if mask_result:
    x0, y0, x1, y1, mask = mask_result
    # mask is a boolean numpy array
```

### User Interaction:
1. Load an image/experiment in the Analysis tab
2. Select either "Circle ROI Tool" or "Freehand ROI Tool" button
3. Left-click and drag on the image to draw
4. Release to finalize the ROI
5. ROI coordinates and mask are available through the existing ROI management system

## Technical Details

### Freehand Path Smoothing:
- Points are only added if they're more than 2 pixels away from the last point (Manhattan distance)
- This reduces redundancy while maintaining path fidelity

### Polygon Closing:
- The polygon is automatically closed by connecting the last point to the first point
- The painter handles this automatically when drawing with `drawPolygon()`

### Mask Generation:
- Uses `matplotlib.path.Path.contains_points()` for accurate point-in-polygon testing
- Creates a grid of points within the bounding box
- Tests each point for inclusion in the polygon
- Returns a boolean mask matching the ROI shape

### Error Handling:
- Requires at least 3 points for a valid freehand ROI
- Invalid ROIs are discarded with a warning message
- Graceful fallback to circular mode if errors occur

## Backward Compatibility

All existing circular/elliptical ROI functionality remains unchanged:
- Default mode is still 'circular'
- All existing methods work as before
- The mask generation method automatically detects the mode
- Saved ROIs from both modes use the same storage format (xyxy bounding box)

## Future Enhancements

Potential improvements:
1. Path simplification algorithms (e.g., Douglas-Peucker) to reduce point count
2. Smooth curve interpolation for aesthetic improvement
3. Undo/redo functionality for freehand drawing
4. Export freehand points to various formats (JSON, CSV, etc.)
5. Import pre-defined polygon shapes
6. Support for editing freehand ROI vertices after creation
