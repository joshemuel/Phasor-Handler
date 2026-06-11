"""
SecondLevelWidget - Display all ROI traces in a scrollable card grid.

Shows every saved ROI trace from the First Level analysis as a dark "trace card"
in a wrapping, auto-fitting grid (no pagination). Each card renders its mini-trace
once to a QPixmap via the matplotlib Agg backend (not a live canvas), so hundreds
of ROIs scroll smoothly. Clicking a card opens a larger, zoomable detail view.

The trace math, formula handling, baseline cap, frame-range logic, and the
SecondLevelWorker contract are unchanged from the previous implementation.
"""

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
try:
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
except ImportError:  # older/newer matplotlib layouts
    from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QScrollArea, QFrame, QDialog,
    QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QProgressBar,
    QToolButton, QMenu
)
from PyQt6.QtCore import Qt, QThread, QLocale, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QColor

from phasor_handler.workers.secondlevel_worker import SecondLevelWorker
from phasor_handler.widgets.common import FlowLayout
from phasor_handler.theme import tokens
from phasor_handler.theme.mpl import render_trace_pixmap, plot_trace_on_ax

# Card geometry (logical px). Cards are fixed-width so FlowLayout wraps to as many
# columns as the viewport allows; the pixmap is rendered at device-pixel-ratio for
# crispness on HiDPI displays.
CARD_W = 300
CARD_H = 206
PLOT_W = 272
PLOT_H = 150

# Dict key standing in for "ROIs with no tag" in the tag-filter check state.
_UNTAGGED_KEY = "\x00untagged"


def _swatch_icon(color, size=12):
    """A small solid-color square icon for a tag, matching the First Level panel."""
    pm = QPixmap(size, size)
    pm.fill(QColor(int(color[0]), int(color[1]), int(color[2])))
    return QIcon(pm)


class _CheckableMenu(QMenu):
    """A QMenu that stays open when a checkable item is toggled, so several tags
    can be checked/unchecked without reopening the dropdown each time."""

    def mouseReleaseEvent(self, event):
        action = self.activeAction()
        if action is not None and action.isCheckable() and action.isEnabled():
            action.trigger()  # toggle + emit triggered, but keep the menu open
            return
        super().mouseReleaseEvent(event)


def _formula_ylabel(formula_idx):
    """Y-axis label for a given formula index (matches First Level conventions)."""
    if formula_idx in (0, 1):
        return "ΔF/F₀"
    if formula_idx == 2:
        return "Green (a.u.)"
    if formula_idx == 3:
        return "Red (a.u.)"
    return "Signal"


class _TraceCard(QFrame):
    """A single ROI trace card: title chip + mini-trace pixmap, click to expand."""

    clicked = pyqtSignal()

    def __init__(self, roi_name, pixmap, parent=None):
        super().__init__(parent)
        self.setObjectName("traceCard")
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame#traceCard {{
                background-color: {tokens.ELEVATED};
                border: 1px solid {tokens.HAIRLINE};
                border-radius: {tokens.RADIUS_PANEL}px;
            }}
            QFrame#traceCard:hover {{
                border: 1px solid {tokens.ACCENT};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        title = QLabel(roi_name)
        title.setStyleSheet(
            f"color: {tokens.ACCENT}; font-weight: 600; font-size: 12px; "
            f"background: transparent; border: none;")
        title.setMaximumHeight(20)
        layout.addWidget(title)

        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setStyleSheet("background: transparent; border: none;")
        if pixmap is not None and not pixmap.isNull():
            self._image.setPixmap(pixmap)
        layout.addWidget(self._image, 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _TraceDetailDialog(QDialog):
    """A larger, zoomable view of one ROI trace (live matplotlib canvas)."""

    def __init__(self, roi_name, trace, *, frame_start, frame_end, ymin, ymax,
                 stim_frames, ylabel, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Trace - {roi_name}")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(820, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Figure created directly (not via pyplot) so it GCs with the dialog.
        fig = Figure(figsize=(8, 4.6), dpi=100)
        fig.patch.set_facecolor(tokens.BASE)
        self._canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.set_facecolor(tokens.SURFACE)
        plot_trace_on_ax(
            ax, trace, frame_start=frame_start, frame_end=frame_end,
            ymin=ymin, ymax=ymax, stim_frames=stim_frames,
            title=roi_name, ylabel=ylabel, variant="card",
            title_size=14, label_size=12, tick_size=10, linewidth=1.6,
        )
        fig.tight_layout(pad=0.8)

        toolbar = NavigationToolbar(self._canvas, self)
        layout.addWidget(toolbar)
        layout.addWidget(self._canvas, 1)


class SecondLevelWidget(QWidget):
    """Second Level Analysis tab - all ROI traces in a scrollable card grid."""

    def __init__(self, main_window):
        super().__init__()
        self.window = main_window

        # Store reference in main window (used by app.py on tab change).
        self.window.second_level_widget = self

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Card widgets currently displayed.
        self.cards = []

        # Guard against recursive parameter-change refreshes.
        self._updating = False

        # Worker thread management.
        self.worker = None
        self.worker_thread = None
        self._render_params = {}

        # Tag-filter state: which tags (+ untagged) to show. Keyed by tag name and
        # _UNTAGGED_KEY; default-shown (True) when absent. _signature tracks the
        # tag set last built into the menu so we only rebuild on structural change.
        self._tag_checked = {}
        self._tag_filter_signature = None
        self._tag_actions = {}
        self._all_action = None
        self._untagged_action = None

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # --- Control bar ---
        control_group = QGroupBox("Display Controls")
        control_layout = QHBoxLayout()
        control_layout.setSpacing(12)

        # Y-axis limits
        ylim_group = QGroupBox("Y-Axis Limits")
        ylim_layout = QHBoxLayout()
        ylim_layout.addWidget(QLabel("Min:"))
        self.ylim_min_edit = QDoubleSpinBox()
        self.ylim_min_edit.setRange(-999999.99, 999999.99)
        self.ylim_min_edit.setDecimals(3)
        self.ylim_min_edit.setSingleStep(0.1)
        self.ylim_min_edit.setValue(-0.1)
        self.ylim_min_edit.setMaximumWidth(100)
        self.ylim_min_edit.valueChanged.connect(self._on_parameter_changed)
        ylim_layout.addWidget(self.ylim_min_edit)
        ylim_layout.addWidget(QLabel("Max:"))
        self.ylim_max_edit = QDoubleSpinBox()
        self.ylim_max_edit.setRange(-999999.99, 999999.99)
        self.ylim_max_edit.setDecimals(3)
        self.ylim_max_edit.setSingleStep(0.1)
        self.ylim_max_edit.setValue(0.5)
        self.ylim_max_edit.setMaximumWidth(100)
        self.ylim_max_edit.valueChanged.connect(self._on_parameter_changed)
        ylim_layout.addWidget(self.ylim_max_edit)
        ylim_group.setLayout(ylim_layout)

        # Frame range
        frame_group = QGroupBox("Frame Range")
        frame_layout = QHBoxLayout()
        frame_layout.addWidget(QLabel("Start:"))
        self.frame_start_edit = QSpinBox()
        self.frame_start_edit.setRange(0, 999999)
        self.frame_start_edit.setValue(0)
        self.frame_start_edit.setMaximumWidth(100)
        self.frame_start_edit.valueChanged.connect(self._on_parameter_changed)
        frame_layout.addWidget(self.frame_start_edit)
        frame_layout.addWidget(QLabel("End:"))
        self.frame_end_edit = QSpinBox()
        self.frame_end_edit.setRange(0, 999999)
        self.frame_end_edit.setValue(999999)
        self.frame_end_edit.setSpecialValueText("All")
        self.frame_end_edit.setMaximumWidth(100)
        self.frame_end_edit.valueChanged.connect(self._on_parameter_changed)
        frame_layout.addWidget(self.frame_end_edit)
        frame_group.setLayout(frame_layout)

        # Formula
        formula_group = QGroupBox("Formula")
        formula_layout = QHBoxLayout()
        self.formula_dropdown = QComboBox()
        self.formula_dropdown.addItem("Fg - Fog / Fr")
        self.formula_dropdown.addItem("Fg - Fog / Fog")
        self.formula_dropdown.addItem("Fg only")
        self.formula_dropdown.addItem("Fr only")
        self.formula_dropdown.setCurrentIndex(1)
        self.formula_dropdown.currentIndexChanged.connect(self._on_formula_changed)
        formula_layout.addWidget(self.formula_dropdown)
        formula_group.setLayout(formula_layout)

        # Baseline
        baseline_group = QGroupBox("Baseline")
        baseline_layout = QHBoxLayout()
        baseline_layout.addWidget(QLabel("Baseline (s):"))
        self.baseline_spinbox = QDoubleSpinBox()
        c_locale = QLocale(QLocale.Language.C)
        c_locale.setNumberOptions(QLocale.NumberOption.RejectGroupSeparator)
        self.baseline_spinbox.setLocale(c_locale)
        self.baseline_spinbox.setRange(0.1, 9999.0)
        self.baseline_spinbox.setValue(5.0)
        self.baseline_spinbox.setSingleStep(0.5)
        self.baseline_spinbox.setDecimals(1)
        self.baseline_spinbox.setSuffix(" s")
        self.baseline_spinbox.setMaximumWidth(100)
        self.baseline_spinbox.valueChanged.connect(self._on_parameter_changed)
        baseline_layout.addWidget(self.baseline_spinbox)
        baseline_group.setLayout(baseline_layout)

        # Stimulation toggle
        self.show_stim_checkbox = QCheckBox("Show Stimulation")
        self.show_stim_checkbox.setChecked(False)
        self.show_stim_checkbox.stateChanged.connect(self._on_parameter_changed)

        # Reset button (themed; no more ad-hoc colored buttons)
        self.reset_button = QPushButton("Reset Limits")
        self.reset_button.clicked.connect(self._reset_limits)

        # Tag filter: a "Tags:" label beside a dropdown checklist of tags
        # (+ Untagged) deciding which ROI cards to show. The button text summarizes
        # the selection ("All" by default). Disabled when no tags exist.
        self.tag_filter_label = QLabel("Tags:")
        self.tag_filter_button = QToolButton()
        self.tag_filter_button.setText("All")
        self.tag_filter_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.tag_filter_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup)
        self.tag_filter_button.setToolTip("Choose which tags to show")
        self.tag_menu = _CheckableMenu(self.tag_filter_button)
        self.tag_menu.setToolTipsVisible(True)
        self.tag_filter_button.setMenu(self.tag_menu)
        self._rebuild_tag_filter()

        # Hidden refresh button kept for backward compatibility (auto-update is on).
        self.refresh_button = QPushButton("Refresh Plots")
        self.refresh_button.clicked.connect(self.refresh_plots)
        self.refresh_button.setVisible(False)

        # Count readout (replaces the page label).
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {tokens.MUTED};")

        control_layout.addWidget(ylim_group)
        control_layout.addWidget(frame_group)
        control_layout.addWidget(formula_group)
        control_layout.addWidget(baseline_group)
        control_layout.addWidget(self.show_stim_checkbox)
        control_layout.addWidget(self.reset_button)
        control_layout.addWidget(self.tag_filter_label)
        control_layout.addWidget(self.tag_filter_button)
        control_layout.addStretch()
        control_layout.addWidget(self.count_label)
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)

        # --- Progress bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Computing traces  %v / %m")
        main_layout.addWidget(self.progress_bar)

        # --- Message label (empty / error states) ---
        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setVisible(False)
        main_layout.addWidget(self.message_label, 1)

        # --- Scrollable card grid ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_content = QWidget()
        self.flow_layout = FlowLayout(margin=4, spacing=14)
        self.scroll_content.setLayout(self.flow_layout)
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

        self.setLayout(main_layout)

        self.refresh_plots()

    # -------------------------------------------------------------- helpers
    def _on_parameter_changed(self):
        if not self._updating:
            self.refresh_plots()

    # ----------------------------------------------------------- tag filter
    def _rebuild_tag_filter(self):
        """Rebuild the tag dropdown from the current tags + whether any untagged
        ROI exists, preserving check states for surviving tags. Returns True if
        the menu structure actually changed (so callers can re-render)."""
        tags = getattr(self.window, '_roi_tags', None) or []
        all_rois = getattr(self.window, '_saved_rois', None) or []
        has_untagged = any(not roi.get('tag') for roi in all_rois)
        # Include colors so a recolor in First Level refreshes the swatch too.
        signature = (tuple((t.get('name'), tuple(t.get('color', ()))) for t in tags),
                     has_untagged)
        if signature == self._tag_filter_signature:
            return False
        self._tag_filter_signature = signature

        self.tag_menu.clear()
        self._tag_actions = {}

        self._all_action = self.tag_menu.addAction("(All)")
        self._all_action.setCheckable(True)
        self._all_action.triggered.connect(self._on_select_all_tags)
        self.tag_menu.addSeparator()

        for tag in tags:
            name = tag.get('name')
            act = self.tag_menu.addAction(
                _swatch_icon(tag.get('color', (200, 200, 200))), str(name))
            act.setCheckable(True)
            act.setChecked(self._tag_checked.get(name, True))
            act.triggered.connect(self._on_tag_filter_changed)
            self._tag_actions[name] = act

        if has_untagged:
            self.tag_menu.addSeparator()
            self._untagged_action = self.tag_menu.addAction("Untagged")
            self._untagged_action.setCheckable(True)
            self._untagged_action.setChecked(
                self._tag_checked.get(_UNTAGGED_KEY, True))
            self._untagged_action.triggered.connect(self._on_tag_filter_changed)
        else:
            self._untagged_action = None

        self._sync_checked_from_actions()
        self._refresh_all_action_state()
        self.tag_filter_button.setEnabled(bool(tags))
        return True

    def _sync_checked_from_actions(self):
        """Read the menu's check states back into self._tag_checked, preserving a
        prior Untagged preference while no untagged ROIs exist."""
        state = {}
        for name, act in self._tag_actions.items():
            state[name] = act.isChecked()
        if self._untagged_action is not None:
            state[_UNTAGGED_KEY] = self._untagged_action.isChecked()
        elif _UNTAGGED_KEY in self._tag_checked:
            state[_UNTAGGED_KEY] = self._tag_checked[_UNTAGGED_KEY]
        self._tag_checked = state

    def _refresh_all_action_state(self):
        """Tick "(All)" only when every tag (+ Untagged) is checked, and update
        the dropdown button's summary text."""
        if self._all_action is not None:
            acts = list(self._tag_actions.values())
            if self._untagged_action is not None:
                acts.append(self._untagged_action)
            all_checked = bool(acts) and all(a.isChecked() for a in acts)
            self._all_action.blockSignals(True)
            self._all_action.setChecked(all_checked)
            self._all_action.blockSignals(False)
        self._update_tag_button_text()

    def _update_tag_button_text(self):
        """Summarize the current filter on the dropdown button: "All" when every
        tag is shown, "None" when nothing is, else "<n> selected"."""
        acts = list(self._tag_actions.values())
        if self._untagged_action is not None:
            acts.append(self._untagged_action)
        total = len(acts)
        checked = sum(1 for a in acts if a.isChecked())
        if total == 0 or checked == total:
            self.tag_filter_button.setText("All")
        elif checked == 0:
            self.tag_filter_button.setText("None")
        else:
            self.tag_filter_button.setText(f"{checked} selected")

    def _on_tag_filter_changed(self, _checked=False):
        self._sync_checked_from_actions()
        self._refresh_all_action_state()
        if not self._updating:
            self.refresh_plots()

    def _on_select_all_tags(self, checked):
        for act in self._tag_actions.values():
            act.setChecked(checked)
        if self._untagged_action is not None:
            self._untagged_action.setChecked(checked)
        self._sync_checked_from_actions()
        self._refresh_all_action_state()
        if not self._updating:
            self.refresh_plots()

    def _apply_tag_filter(self, saved_rois):
        """Subset of saved_rois whose tag is checked (untagged ROIs gated by the
        Untagged item). With no tags defined, returns everything unchanged."""
        tags = getattr(self.window, '_roi_tags', None) or []
        if not tags:
            return list(saved_rois)
        include_untagged = self._tag_checked.get(_UNTAGGED_KEY, True)
        out = []
        for roi in saved_rois:
            tag = roi.get('tag')
            if not tag:
                if include_untagged:
                    out.append(roi)
            elif self._tag_checked.get(tag, True):
                out.append(roi)
        return out

    def _get_frame_range(self):
        start = self.frame_start_edit.value()
        end = self.frame_end_edit.value()
        if end >= 999999:
            end = None
        return start, end

    def _get_ylim(self):
        ymin = self.ylim_min_edit.value()
        ymax = self.ylim_max_edit.value()
        if ymin <= -999999:
            ymin = None
        if ymax >= 999999:
            ymax = None
        return ymin, ymax

    def _on_formula_changed(self):
        if self._updating:
            return
        self._updating = True
        formula_idx = self.formula_dropdown.currentIndex()
        if formula_idx in (0, 1):  # normalized dF/F0
            self.ylim_min_edit.setValue(-0.1)
            self.ylim_max_edit.setValue(0.5)
        else:  # raw signals
            self.ylim_min_edit.setValue(0)
            self.ylim_max_edit.setValue(1000)
        self._updating = False
        self.refresh_plots()

    def _reset_limits(self):
        self._updating = True
        self.ylim_min_edit.setValue(-0.1)
        self.ylim_max_edit.setValue(0.5)
        self.frame_start_edit.setValue(0)
        current_tif = getattr(self.window, '_current_tif', None)
        if current_tif is not None:
            nframes = current_tif.shape[0] if current_tif.ndim == 3 else 1
            self.frame_end_edit.setMaximum(nframes)
            self.frame_end_edit.setValue(nframes)
        else:
            self.frame_end_edit.setValue(999999)
        self.baseline_spinbox.setValue(5.0)
        self.formula_dropdown.setCurrentIndex(1)
        self._updating = False
        self.refresh_plots()

    def _update_baseline_max(self, nframes):
        """Cap baseline spinbox maximum to total recording duration in seconds."""
        exp_data = getattr(self.window, '_exp_data', None)
        if exp_data is None:
            return

        total_s = None
        time_stamps = None
        for attr_name in ['time_stamps', 'timeStamps', 'timestamps', 'ElapsedTimes']:
            if isinstance(exp_data, dict):
                if attr_name in exp_data:
                    time_stamps = exp_data[attr_name]
                    break
            else:
                if hasattr(exp_data, attr_name):
                    time_stamps = getattr(exp_data, attr_name)
                    break

        if time_stamps is not None and hasattr(time_stamps, '__len__') and len(time_stamps) > 0:
            try:
                if isinstance(time_stamps[0], str):
                    from datetime import datetime
                    first_dt = datetime.strptime(time_stamps[0], '%Y-%m-%d %H:%M:%S.%f')
                    last_idx = min(nframes, len(time_stamps)) - 1
                    last_dt = datetime.strptime(time_stamps[last_idx], '%Y-%m-%d %H:%M:%S.%f')
                    total_s = (last_dt - first_dt).total_seconds()
                else:
                    ts_arr = np.asarray(time_stamps[:min(nframes, len(time_stamps))], dtype=float)
                    max_t = float(ts_arr[-1]) if len(ts_arr) > 0 else 0
                    total_s = max_t / 1000.0 if max_t > 10000 else max_t
            except Exception:
                pass

        if total_s is None:
            frame_rate = None
            if isinstance(exp_data, dict):
                frame_rate = exp_data.get('frame_rate', None)
            else:
                frame_rate = getattr(exp_data, 'frame_rate', None)
            if frame_rate is not None and frame_rate != 'NA':
                try:
                    fr = float(frame_rate)
                    if fr > 0:
                        total_s = nframes / fr
                except (ValueError, TypeError):
                    pass

        if total_s is not None and total_s > 0:
            self.baseline_spinbox.setMaximum(round(total_s, 1))
        else:
            self.baseline_spinbox.setMaximum(9999.0)

    def _get_stimulation_frames(self):
        """Get stimulation frame indices from experiment metadata."""
        try:
            exp_data = getattr(self.window, '_exp_data', None)
            if exp_data is None:
                return []
            if isinstance(exp_data, dict):
                stim_frames = exp_data.get('stimulation_timeframes', [])
            elif hasattr(exp_data, 'stimulation_timeframes'):
                stim_frames = getattr(exp_data, 'stimulation_timeframes', [])
            else:
                try:
                    stim_frames = exp_data['stimulation_timeframes']
                except (KeyError, TypeError):
                    stim_frames = []
            if stim_frames and len(stim_frames) > 0:
                return list(stim_frames)
        except Exception:
            pass
        return []

    # ----------------------------------------------------------- card grid
    def _clear_cards(self):
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item is not None and item.widget():
                item.widget().deleteLater()
        self.cards = []

    def _show_message(self, text, danger=False):
        """Show a centered empty/error message and hide the card grid."""
        self._clear_cards()
        color = tokens.DANGER if danger else tokens.MUTED
        self.message_label.setStyleSheet(
            f"color: {color}; font-size: 15px; padding: 40px;")
        self.message_label.setText(text)
        self.message_label.setVisible(True)
        self.scroll_area.setVisible(False)
        self.count_label.setText("")

    def _show_grid(self):
        self.message_label.setVisible(False)
        self.scroll_area.setVisible(True)

    # ------------------------------------------------------------- refresh
    def refresh_plots(self):
        """Recompute traces (full ROI set) and rebuild the card grid."""
        self._stop_worker()
        self._clear_cards()

        all_rois = getattr(self.window, '_saved_rois', [])
        if not all_rois:
            self._show_message(
                "No ROIs defined.\n\nDraw and save ROIs in the First Level tab.")
            return

        # Keep the tag dropdown in sync, then drop ROIs whose tag is unchecked.
        self._rebuild_tag_filter()
        saved_rois = self._apply_tag_filter(all_rois)

        current_tif = getattr(self.window, '_current_tif', None)
        current_tif_chan2 = getattr(self.window, '_current_tif_chan2', None)
        if current_tif is None:
            self._show_message(
                "No image data loaded.\n\nSelect an experiment in the First Level tab.")
            return

        if not saved_rois:
            self._show_message(
                "No ROIs match the selected tags.\n\nAdjust the Tags filter above.")
            return

        # Default frame range to the actual recording length on first load.
        nframes = current_tif.shape[0] if current_tif.ndim == 3 else 1
        if self.frame_end_edit.value() == 999999 and not self._updating:
            self._updating = True
            self.frame_end_edit.setMaximum(nframes)
            self.frame_end_edit.setValue(nframes)
            self.frame_start_edit.setMaximum(nframes - 1)
            self._updating = False

        self._update_baseline_max(nframes)

        frame_start, frame_end = self._get_frame_range()
        ymin, ymax = self._get_ylim()

        total_rois = len(saved_rois)
        self._show_grid()
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total_rois)
        self.progress_bar.setValue(0)

        self._render_params = {
            'frame_start': frame_start,
            'frame_end': frame_end,
            'ymin': ymin,
            'ymax': ymax,
        }

        # --- Worker (unchanged contract; full ROI set, no pagination) ---
        exp_data = getattr(self.window, '_exp_data', None)
        time_stamps = None
        frame_rate = None
        if exp_data is not None:
            if isinstance(exp_data, dict):
                time_stamps = exp_data.get('time_stamps')
                frame_rate = exp_data.get('frame_rate')
            else:
                time_stamps = getattr(exp_data, 'time_stamps', None)
                frame_rate = getattr(exp_data, 'frame_rate', None)

        self.worker_thread = QThread()
        self.worker = SecondLevelWorker(
            saved_rois=saved_rois,
            tif=current_tif,
            tif_chan2=current_tif_chan2,
            formula_idx=self.formula_dropdown.currentIndex(),
            baseline_seconds=self.baseline_spinbox.value(),
            frame_start=frame_start,
            frame_end=frame_end,
            page_rois_slice=(0, total_rois),
            time_stamps=time_stamps,
            frame_rate=frame_rate,
        )
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.error.connect(self._on_worker_error)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self._cleanup_worker)
        self.worker_thread.start()

    def _stop_worker(self):
        try:
            if self.worker_thread is not None and self.worker_thread.isRunning():
                for sig in ('started',):
                    try:
                        getattr(self.worker_thread, sig).disconnect()
                    except Exception:
                        pass
                for sig in ('finished', 'progress', 'error'):
                    try:
                        getattr(self.worker, sig).disconnect()
                    except Exception:
                        pass
                self.worker_thread.quit()
                self.worker_thread.wait(1000)
        except RuntimeError:
            pass
        finally:
            self.worker = None
            self.worker_thread = None

    def _cleanup_worker(self):
        if self.worker is not None:
            self.worker.deleteLater()
        if self.worker_thread is not None:
            self.worker_thread.deleteLater()
        self.worker = None
        self.worker_thread = None

    def _on_worker_progress(self, current, total):
        self.progress_bar.setValue(current)

    def _on_worker_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self._show_message(f"Error computing traces:\n\n{error_msg}", danger=True)

    def _on_worker_finished(self, trace_data_list):
        self.progress_bar.setVisible(False)
        params = self._render_params
        frame_start = params['frame_start']
        frame_end = params['frame_end']
        ymin = params['ymin']
        ymax = params['ymax']
        ylabel = _formula_ylabel(self.formula_dropdown.currentIndex())
        stim_frames = self._get_stimulation_frames() if self.show_stim_checkbox.isChecked() else None
        dpr = self.devicePixelRatioF()

        self._show_grid()
        for trace_data in trace_data_list:
            roi_data = trace_data['roi_data']
            roi_idx = trace_data['roi_idx']
            trace = trace_data['trace']
            roi_name = roi_data.get('name', f'ROI {roi_idx + 1}')

            pixmap = render_trace_pixmap(
                trace, width_px=PLOT_W, height_px=PLOT_H, device_pixel_ratio=dpr,
                frame_start=frame_start, frame_end=frame_end,
                ymin=ymin, ymax=ymax, stim_frames=stim_frames, ylabel=ylabel,
            )
            card = _TraceCard(roi_name, pixmap)
            # Bind current values for the detail view via default args.
            card.clicked.connect(
                lambda _=False, rn=roi_name, tr=trace, fs=frame_start, fe=frame_end,
                yn=ymin, yx=ymax, sf=stim_frames, yl=ylabel:
                self._open_detail(rn, tr, fs, fe, yn, yx, sf, yl))
            self.flow_layout.addWidget(card)
            self.cards.append(card)

        self.count_label.setText(f"{len(trace_data_list)} ROIs")

    def _open_detail(self, roi_name, trace, frame_start, frame_end, ymin, ymax,
                     stim_frames, ylabel):
        dialog = _TraceDetailDialog(
            roi_name, trace, frame_start=frame_start, frame_end=frame_end,
            ymin=ymin, ymax=ymax, stim_frames=stim_frames, ylabel=ylabel,
            parent=self)
        dialog.show()

    # --------------------------------------------------------------- events
    def showEvent(self, event):
        super().showEvent(event)
        current_tif = getattr(self.window, '_current_tif', None)
        if current_tif is not None:
            nframes = current_tif.shape[0] if current_tif.ndim == 3 else 1
            self._updating = True
            self.frame_end_edit.setMaximum(nframes)
            self.frame_start_edit.setMaximum(nframes - 1)
            if self.frame_end_edit.value() >= 999999 or self.frame_end_edit.value() > nframes:
                self.frame_end_edit.setValue(nframes)
            self._updating = False

        # Tags may have changed in First Level while this tab was hidden; rebuild
        # the dropdown and re-render if its structure changed (or nothing is shown).
        tag_filter_changed = self._rebuild_tag_filter()
        if tag_filter_changed or not self.cards:
            self.refresh_plots()
