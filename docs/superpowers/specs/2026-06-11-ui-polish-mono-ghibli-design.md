# UI Polish: Black & White Default + Ghibli Theme

Date: 2026-06-11
Status: Implemented

## Problem

The Ice Cyan redesign left six issues (user report):

1. Text rendered on rectangular backing boxes that overlap lines (ROI outlines
   on the image, group-box border lines).
2. The bottom of the First Level tab is cropped — the Seconds/Frames button is
   cut off.
3. The default theme should be black and white, not Ice Cyan.
4. First Level trace controls (Y-limits, Baseline, Seconds/Frames) are far too
   wide, stealing horizontal space from the trace plot.
5. The Brightness & Contrast box contents are misaligned/not centered.
6. A Ghibli theme (My Neighbour Totoro) is wanted, with character-design
   outlines where tasteful, and the chosen theme must persist across launches.

## Root causes

- **(1a)** `circle_roi.py` painted ROI/stim labels over
  `fillRect(QColor(0,0,0,180))` boxes — opaque rectangles crossing the
  ellipse/rect outlines.
- **(1b)** `QGroupBox::title` sat partially on the border line (14px top margin
  is smaller than the title height), so its background showed as a rectangle
  crossing the frame.
- **(2, 4)** The trace controls were a left-hand *column* whose minimum height
  (~200px) exceeded the 25% bottom panel, cropping the last control; the column
  was as wide as its widest row (~170-220px) and every button stretched to fill
  it.
- **(5)** BnC used stacked `QHBoxLayout`s with trailing stretches; the
  "Max (pth)" label did not sit over the max spinbox and rows hugged the left.
- **(3, 6)** Theme infrastructure (palettes, QSettings persistence, Preferences
  menu) already existed; only "ice" was hardwired as the default and no
  mono/ghibli palettes existed.

## Design

### Text integration (1)

- ROI/stim labels: replace backing boxes with **halo text** — white glyphs over
  a 1px 8-direction dark outline. Readable on any image content, outlines show
  through. Shared helper `CircleRoiTool._draw_halo_text`.
- Group boxes: title floats fully **above** the frame (`margin-top: 18px`,
  explicit transparent title background) so no rectangle can cross the border.

### Trace panel (2, 4)

`TraceplotWidget` controls move from a left column into **one compact
horizontal bar above the plot**: `Y: [min] [max] [Auto]  Baseline: [5.0 s]
[formula ▾] [Seconds]`, all 24px tall with fixed widths. The canvas gets the
full panel width and the panel minimum height drops to ~140px, so nothing is
cropped at any window size. All widget attribute names and signals are
unchanged (backward-compatible with `MainWindow` attribute exposure).

### BnC alignment (5)

Internals rebuilt as a 2-column `QGridLayout` with equal column stretch:
Channel 1/2, Min/Max labels, Min/Max spinboxes, Reset/Histogram — every row
aligned, contents filling the group box symmetrically.

### Themes (3, 6)

Two new palettes in `tokens.py` (total five):

- **mono** ("Black & White") — the new default everywhere a fallback existed
  (`ACTIVE_NAME`, `set_active_palette`, `_load_saved_theme`). Near-black ramp
  (#0A0A0A → #2C2C2C), white text/accent. Semantic markers (stim red, frame
  amber, success green) keep a muted hue because they encode data, not chrome.
- **ghibli** ("Ghibli (Totoro)") — the one light palette: cream paper base
  (#F6F1E1), warm panels, soot-charcoal text (#3A3833), Totoro forest-green
  accent (#4E7B52), clay/acorn semantic colors.

Character outlines (ghibli only, runtime-painted PNGs via `icons.py`, cached in
the temp dir like the existing arrow assets — no binary assets shipped):

- **Soot sprite (susuwatari) slider handles** — spiky fuzz ball with white
  eyes, via a QSS override appended by `qss._ghibli_rules()` only when the
  ghibli palette is active.
- **Totoro outline icon** on the Preferences corner button (egg body, leaf
  ears, whiskers, belly chevrons), applied by
  `MainWindow._apply_prefs_decoration()` and refreshed on theme switch through
  the existing `restyle_theme()` hook.

Persistence already existed via QSettings (`PhasorHandler/theme`); users who
previously picked a theme keep it, fresh installs get Black & White.

## Verification

- `py_compile` passes on all nine touched files.
- Standalone smoke tests: all five palettes share the exact token key set;
  default/fallback resolve to mono; QSS builds with balanced braces for every
  palette; ghibli decorations degrade to nothing when asset generation fails.
- GUI not run (Windows-only app; this session is WSL without PyQt6) — needs a
  manual launch check on Windows.
