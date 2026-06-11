# ROI Tagging — Design Spec

Date: 2026-06-11
Status: Approved

## Context

Users can draw ROIs of various shapes (circular, rectangular, freehand) in the First Level tab, but have no way to group them. This adds **tags**: named, colored groups of ROIs. A new "Tags" panel joins the right control column (under Z-Projections, Brightness & Contrast, ROI Drawing Tool). Tags drive on-screen highlighting, a tag-details popup with management actions, a "Save Tag Image" export (tag members at full opacity, everything else dimmed), and a new "View" option (Per-ROI vs Per-Tag coloring) in Save Current View — useful for downstream analysis where ROI numbering must stay stable but colors should communicate group identity.

### Decisions (confirmed with user)

- One tag per ROI max (matches "Move" semantics; Per-Tag coloring unambiguous).
- "Create Tag" captures the ROIs currently selected in the Saved ROIs list; an "Assign" button adds the current ROI selection to the selected tag (overwriting their previous tag).
- Tag colors auto-assigned from a distinct 10-color palette, editable via "Change Color".
- Tag popup actions: Remove, Move, Save Tag Image, Rename Tag, Change Color, Export Tag Traces.

## Data model

- Tag definitions: `window._roi_tags = [{'name': str, 'color': (r, g, b, a)}]`.
- Membership: a `'tag': <tag name>` key **on each ROI dict** in `window._saved_rois` — never index lists, so ROI removal/reorder can't produce stale references. Membership is derived by scanning `_saved_rois`.
- Lifecycle mirrors ROIs exactly: `_saved_rois` persists across directory switches (`_on_item_changed_with_roi_preservation`); cleared only by Clear All ROIs and replaced by Load ROIs. Tags live app-wide on the window object.
- `CircleRoiTool.set_saved_rois` stores a shallow copy sharing the same dicts, so mutating `roi['tag']` is visible to the painter immediately — only a repaint is needed.

## Components

### `tag_panel.py` (new)

- `TAG_PALETTE`: 10 distinguishable colors (alpha 220); `UNTAGGED_COLOR = (150, 150, 150, 200)`.
- **`TagPanelWidget(QWidget)`**: QGroupBox("Tags") with compact tag QListWidget (swatch icon + name + member count) and buttons Create Tag / Delete Tag / Assign. Single click highlights the tag's ROIs on the image (tag color, full alpha, thick pen); double click opens `TagDetailsDialog`. Emits `tagsChanged`.
- **`TagDetailsDialog(QDialog)`**: modal; member ROI list; actions Remove (untag), Move (reassign to another tag), Rename Tag, Change Color, Save Tag Image (PNG: members full opacity, all other ROIs/stim ROIs/labels dimmed), Export Tag Traces (trace export restricted to members).

### `circle_roi.py` (CircleRoiTool)

- New state: `_highlighted_tag` (name or None), `_roi_tags` (defs pushed from panel). New API: `set_roi_tags(tags)`, `set_highlighted_tag(name)`, `_tag_qcolor(name)`.
- `_paint_overlay`: tag-highlight branch (list selection wins over tag highlight).
- `render_rois_to_pixmap(..., color_mode='per-roi'|'per-tag', emphasize_tag=None, dim_alpha=70)`; `_render_one_roi(..., color_override=None, alpha_override=None)`; alpha threads through label halo text. Defaults preserve existing output.

### `view.py` (AnalysisWidget)

- Tag panel inserted below the ROI Drawing Tool group in the 250px-capped right column.
- Save Current View: a "View:" combo (Per-ROI colors / Per-Tag colors) embedded in the (non-native) save QFileDialog, shown only when tags exist; rendering happens after the dialog with the chosen mode. Per-Tag keeps ROI numbering, strokes ROIs in tag colors, untagged ROIs in neutral gray.
- `_render_native_export_pixmap(color_mode=..., emphasize_tag=...)` serves both Save Current View and Save Tag Image.

### `roi_list.py` (RoiListWidget)

- JSON schema gains top-level `"tags": [{"name", "color"}]`; per-ROI `"tag"` field rides the existing copy loop. Load replaces tags, sanitizes memberships (drops non-strings, auto-creates defs for unknown names), clears highlight, emits new `roisLoaded` signal.
- Trace export body extracted into `export_traces_for_rois(rois, default_filename)` so the tag dialog can export a member subset; column headers derive from ROI names so numbering stays real.

## Edge cases

- Stale indices impossible: membership on the dict, highlight by name resolved at paint time, modal dialog re-resolves after each action.
- Delete clears an active highlight; rename re-points it; refresh prunes highlights for vanished tags.
- Duplicate tag names rejected; empty tags legal (except trace export → info box).
- Old JSONs (no `tags` key) load unchanged; palette cycles mod 10 when exhausted.
