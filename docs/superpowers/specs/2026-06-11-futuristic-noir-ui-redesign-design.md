# Phasor Handler UI Redesign - Futuristic Noir

**Date:** 2026-06-11
**Mode:** Redesign (overhaul of the visual layer; information architecture preserved)
**Aesthetic:** Futuristic, noir, sleek - "Ice Cyan" palette

---

## 1. Goal & Scope

Substantially modernize the look of the Phasor Handler PyQt6 desktop app without
touching the data pipeline. Replace the ad-hoc styling (deprecated `dark_theme.py`,
`qdarktheme.setup_theme()`, ~15 scattered inline `setStyleSheet`/hardcoded-color
sites) with a single bespoke design-system module driven by design tokens.

The **Second Level tab** receives the most work: a full rebuild of its *view* into a
scrollable, auto-fitting grid of dark trace cards.

### In scope
- New `phasor_handler/theme/` package: tokens, QSS, fonts, matplotlib styling.
- Remove `qdarktheme` as the theming mechanism; remove inline style hacks.
- Restyle all four tabs through tokens.
- Rebuild the Second Level view (scrollable card grid, no pagination).
- Unify matplotlib styling across TraceplotWidget, BnCWidget, Second Level.

### Out of scope (must NOT change)
- `DirManager` shared-state model and `directoriesChanged` signals.
- Worker threads (`SecondLevelWorker`, conversion/registration workers) and their
  signal wiring.
- ROI drawing/extraction logic (`CircleRoiTool`), trace math, formulas, baseline
  computation, frame-range logic, file I/O, metadata parsing.
- Tab order, tab names, the 4-tab pipeline, `MainWindow` structure.
- Public attribute coupling (e.g. `self.window.<widget> = ...` backward-compat refs).

---

## 2. Design Tokens (Ice Cyan)

Single source of truth in `theme/tokens.py`. All values below are final.

| Token | Hex | Use |
|---|---|---|
| `BASE` | `#0B0E14` | window / deepest background |
| `SURFACE` | `#131A26` | panels, group boxes |
| `ELEVATED` | `#1B2535` | inputs, lists, log fields, cards |
| `HAIRLINE` | `#243349` | borders, dividers |
| `TEXT` | `#E7EEF7` | primary text |
| `MUTED` | `#6B7C95` | secondary text, ticks, placeholders |
| `ACCENT` | `#38E1FF` | primary action, selection, focus, trace line |
| `ACCENT_DIM` | `#1E6E84` | accent border at rest, hover scrims |
| `DANGER` | `#FF4D6D` | stimulation markers, errors, destructive |
| `SUCCESS` | `#3FE0A3` | success/run confirmation |
| `WARN` | `#FFB23E` | warnings |

**Radius scale:** panels/cards `10px`, controls (buttons/inputs) `6px`, pill toggles
full. **Spacing scale:** `4, 8, 12, 16, 24`. **Borders:** `1px` hairline by default
(replacing the current heavy `2px` group-box borders).

**Consistency locks (from taste-skill):** one accent (`ACCENT`) used identically
everywhere; one radius system; one theme (dark) for the whole app, no section flips
to a light surface. No em-dash characters anywhere in code comments or UI strings.

---

## 3. Architecture: `phasor_handler/theme/`

```
phasor_handler/theme/
  __init__.py        # exports apply_theme(app), tokens, mpl helpers
  tokens.py          # color/spacing/radius constants (the table above)
  fonts.py           # load_fonts() -> registers bundled TTFs, returns family names
  qss.py             # build_qss() -> full app stylesheet string built from tokens
  mpl.py             # apply_mpl_theme() rcParams + style_axes(ax) helper
  fonts/             # bundled OFL TTFs (Space Grotesk, JetBrains Mono)
```

`apply_theme(app)` (called once in `app.py`):
1. `load_fonts()` - register Space Grotesk + JetBrains Mono via `QFontDatabase`.
   If a file is missing/unregisterable, fall back to Segoe UI (display) / Consolas
   (mono) and continue without error.
2. `app.setStyleSheet(build_qss())`.
3. `apply_mpl_theme()` - set matplotlib rcParams globally.

`app.py` change: replace the `qdarktheme.setup_theme()` try/except block with
`from phasor_handler.theme import apply_theme; apply_theme(app)`. The deprecated
`themes/dark_theme.py` is left in place (already marked deprecated) but no longer
called; `qdarktheme` import is removed from `app.py`.

### Typography
- **Display** (Space Grotesk): tab labels, group-box titles, headings, button labels.
- **Mono** (JetBrains Mono): numeric inputs (spin boxes), log/text edits, plot tick
  labels and axis labels, page/status readouts, ΔF/F₀ and unit labels.
- Bundled as OFL TTFs under `theme/fonts/`. `fonts.py` registers each and exposes the
  resolved family names so QSS and matplotlib reference the same names.

### Matplotlib (`theme/mpl.py`)
`apply_mpl_theme()` sets rcParams: `figure.facecolor` and `axes.facecolor` to
`BASE`/`SURFACE` (or transparent where the widget already paints the bg), text/tick/
label colors to `TEXT`/`MUTED`, `font.family` to JetBrains Mono, default line color
to `ACCENT`. `style_axes(ax)` applies the shared spine treatment (left+bottom hairline
spines visible, top+right hidden, muted ticks, no grid) so TraceplotWidget, the BnC
histogram, and Second Level cards are visually identical.

---

## 4. Per-Tab Changes

### Conversion & Registration
- No layout/logic change. Remove inline `font-weight:bold` hacks (QSS handles weight).
- Primary action buttons (`Run Conversion`, `Convert + Register`, `Run Registration`)
  get a `primary` QSS class (object name or dynamic property) = accent fill, base text.
- Log `QTextEdit` uses the elevated surface + JetBrains Mono (already monospace; now
  themed and consistent).

### First Level (Analysis)
- Restyle only; no structural change to the image viewer, ROI tools, or layout.
- `ImageViewWidget` scale-bar font -> mono; overlay colors unchanged (functional).
- `BnCWidget` histogram: route its `#31363b`/`#232629` facecolors through `style_axes`
  / tokens so it matches the new palette.
- `TraceplotWidget`: replace inline canvas border (`#888`) and ad-hoc spine/line colors
  with the shared `style_axes()` + tokens (cyan trace, red stim, muted ticks). Remove
  the 8pt inline font overrides; sizing comes from rcParams/QSS.
- `MetadataViewer`: header `#2E4A67` -> `ELEVATED` + accent hairline; raw-JSON view
  stays mono (now JetBrains Mono).

### Second Level (centerpiece) - see Section 5.

---

## 5. Second Level Rebuild

Rebuild only the **view** (`widgets/secondlevel/view.py`). The `SecondLevelWorker`
contract (inputs, `finished(trace_data_list)`, `progress`, `error` signals) is
unchanged; trace math, formula handling, baseline cap, frame-range logic, stimulation
frame lookup are all preserved.

### Control bar
- Token-styled. The green/blue/orange inline buttons are removed. `Reset Limits`
  becomes a normal token button; the hidden `Refresh Plots` button stays hidden.
- Controls grouped on a single elevated bar: Formula, Baseline, Y-limits, Frame range,
  Show Stimulation. Same widgets, same signals (`_on_parameter_changed`,
  `_on_formula_changed`), just restyled and tidied.
- **Pagination removed.** `prev_page_button`, `next_page_button`, `page_label`,
  `current_page`, `plots_per_page` and the page-slicing path are retired. The worker
  is invoked for the full ROI set (no `page_rois_slice`, or slice = full range).

### Card grid
- A `QScrollArea` (vertical scroll, accent-styled scrollbar) wraps a flow container.
- **Flow layout**: a custom `FlowLayout` (standard Qt flow-layout pattern) that wraps
  fixed-width cards to as many columns as the width allows and reflows on resize.
  Auto-fitting; no hardcoded 5-column constant.
- **Trace card** (`_TraceCard` widget): elevated surface, `10px` radius, hairline
  border; a title chip (ROI name, display font) top-left; the mini trace below.
  - The mini trace is rendered **once to a `QPixmap`** via the matplotlib Agg backend
    (render figure to buffer -> `QImage` -> `QPixmap` on a `QLabel`), NOT a live
    `FigureCanvas`. This keeps hundreds of cards light enough to scroll smoothly.
    Re-render on parameter change (new worker result) and on card resize (debounced).
  - Cyan trace, red dashed stim lines (when enabled), muted ticks, mono labels ~9-10pt
    (legible, up from 5-7pt), shared `style_axes()` treatment.
  - Hover: border lifts to `ACCENT`/`ACCENT_DIM`. Click: opens the detail view.
- **Detail view**: clicking a card opens a larger interactive trace (a real
  `FigureCanvas`) for that ROI in a modal dialog (see Section 9). This is the one
  place a live, zoomable canvas is justified.

### States (token-styled, no white boxes)
- **Empty (no ROIs / no image)**: centered muted message on `BASE`, accent icon/rule.
- **Loading**: the existing `QProgressBar` restyled (accent chunk, mono `%v/%m` text);
  optionally skeleton card placeholders matching final card shape.
- **Error**: inline `DANGER`-colored message panel on `BASE` (replaces the white
  `#d32f2f`-on-white label).

---

## 6. Components & Boundaries

| Unit | Responsibility | Depends on |
|---|---|---|
| `theme/tokens.py` | constant values | nothing |
| `theme/fonts.py` | register TTFs, resolve family names | `QFontDatabase`, `fonts/` |
| `theme/qss.py` | build app stylesheet from tokens | tokens, fonts |
| `theme/mpl.py` | matplotlib rcParams + `style_axes()` | tokens, fonts |
| `theme/__init__.py` | `apply_theme(app)` orchestration | all of theme/ |
| `secondlevel/FlowLayout` | reflow cards to fit width | Qt layout API |
| `secondlevel/_TraceCard` | render one ROI mini-trace to pixmap + hover/click | mpl Agg, tokens |
| `secondlevel/view.py` | controls + scroll area + card lifecycle + states | worker, theme, FlowLayout, _TraceCard |

Each unit is independently understandable: tokens hold values, qss/mpl consume them,
the view orchestrates. Changing a color = edit `tokens.py` only.

---

## 7. Risks & Mitigations

- **Dropping qdarktheme leaves a widget unstyled.** Mitigation: QSS covers every
  widget class the audit found; verify live and grep for any remaining default-look
  widget; add rules as needed.
- **Font TTFs unavailable at build/run time.** Mitigation: `fonts.py` degrades to
  system fonts silently; the look survives on color/layout alone.
- **Many cards hurt performance.** Mitigation: pixmap rendering instead of live
  canvases; only the detail view is a live canvas.
- **Pixmap mini-plots look soft on HiDPI.** Mitigation: render at device pixel ratio
  and set the pixmap DPR so they stay crisp.
- **Regressing the data pipeline.** Mitigation: no edits to workers/trace math; view
  consumes the same worker output shape.

---

## 8. Verification

Run on Windows Anaconda `suite2p` env from WSL via the `!` prefix (user runs):
```
! <conda> run -n suite2p phasor-handler-debug
```
Checklist when live:
1. App launches, dark Ice-Cyan theme applied app-wide, custom fonts visible.
2. All four tabs render with no white/unstyled patches and no leftover colored buttons.
3. Second Level: cards fill the width, reflow on resize, scroll smoothly with many ROIs,
   labels are legible, hover + click-to-detail work, empty/loading/error states themed.
4. First Level trace plot + BnC histogram match the new matplotlib style.
5. No functional regression: conversion, registration, ROI draw/export, trace compute
   all still work.

---

## 9. Open Implementation Choices (resolved defaults)

- Display font: **Space Grotesk** (sleeker than Chakra Petch for this UI).
- Detail view: **modal dialog** with a live `FigureCanvas` (simpler than expand-in-place;
  revisit if it feels heavy).
- Primary-button styling hook: **dynamic property** `class="primary"` selected in QSS
  (avoids per-widget inline styles).
