"""
matplotlib styling for the Ice Cyan theme.

Provides three things:
  - apply_mpl_theme(): global rcParams matching the token palette.
  - style_axes(ax, variant=...): shared spine/tick/color treatment used by the
    First Level trace plot, the BnC histogram, and the Second Level cards.
  - plot_trace_on_ax(...) + render_trace_pixmap(...): the trace drawing used by
    Second Level. render_trace_pixmap renders off the Agg backend to a QPixmap
    (no live FigureCanvas), so hundreds of ROI cards stay cheap.

style_axes intentionally touches ONLY spines/ticks/colors/fonts. It never plots
data, sets limits, clears axes, or calls draw()/tight_layout() - those stay at the
call site so existing behavior (vlines, ylim auto-populate, channel switching) is
preserved.
"""

import numpy as np

from . import tokens
from . import fonts as _fonts


def _mono_available(family):
    """True if matplotlib can resolve `family` without falling back."""
    try:
        from matplotlib import font_manager
        font_manager.findfont(family, fallback_to_default=False)
        return True
    except Exception:  # noqa: BLE001
        return False


def apply_mpl_theme():
    """Set global matplotlib rcParams to the token palette. Exception-safe."""
    try:
        import matplotlib as mpl
    except Exception:  # noqa: BLE001
        return

    rc = {
        "figure.facecolor": tokens.BASE,
        "axes.facecolor": tokens.SURFACE,
        "axes.edgecolor": tokens.HAIRLINE,
        "axes.labelcolor": tokens.MUTED,
        "axes.titlecolor": tokens.TEXT,
        "text.color": tokens.TEXT,
        "xtick.color": tokens.MUTED,
        "ytick.color": tokens.MUTED,
        "grid.color": tokens.HAIRLINE,
        "savefig.facecolor": tokens.BASE,
    }
    # Tick label color rcParams exist on matplotlib >= 3.4; guard for safety.
    for key in ("xtick.labelcolor", "ytick.labelcolor"):
        if key in mpl.rcParams:
            rc[key] = tokens.MUTED

    # Only pin the font family if matplotlib can actually resolve it; otherwise
    # leave the default so we never emit findfont warnings or break rendering.
    mono = getattr(_fonts, "MONO_FAMILY", None)
    if mono and _mono_available(mono):
        rc["font.family"] = mono

    try:
        mpl.rcParams.update(rc)
    except Exception:  # noqa: BLE001
        pass


def style_axes(ax, *, variant="card", transparent=False):
    """Apply the shared spine/tick treatment.

    variant:
      "trace"     - First Level trace plot: all four spines, hairline colored.
      "histogram" - BnC histogram: spines and ticks fully hidden.
      "card"      - Second Level card / detail: left + bottom spines only.
    transparent: when True, set the axes face to 'none' (caller manages the
      figure patch alpha). Used by the trace plot so the themed pane shows through.
    """
    if transparent:
        ax.set_facecolor("none")

    ax.grid(False)

    if variant == "histogram":
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])
        return

    if variant == "trace":
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color(tokens.HAIRLINE)
            spine.set_linewidth(1.0)
    else:  # "card"
        for name in ("left", "bottom"):
            ax.spines[name].set_visible(True)
            ax.spines[name].set_color(tokens.HAIRLINE)
            ax.spines[name].set_linewidth(0.8)
        for name in ("top", "right"):
            ax.spines[name].set_visible(False)

    ax.tick_params(colors=tokens.MUTED)


def plot_trace_on_ax(ax, trace, *, frame_start, frame_end, ymin, ymax,
                     stim_frames=None, title=None, ylabel=None,
                     variant="card", transparent=False,
                     title_size=10, label_size=9, tick_size=8, linewidth=1.4):
    """Draw a single ROI trace onto `ax` with token colors.

    Shared by the Second Level pixmap cards and the zoomable detail modal so both
    look identical. Returns the (frame_start, frame_end) actually used.
    """
    if trace is not None and len(trace) > 0:
        if frame_end is None or frame_end > len(trace):
            frame_end = len(trace)
        frame_start = max(0, frame_start or 0)
        frame_end = max(frame_start + 1, min(frame_end, len(trace)))

        x = np.arange(frame_start, frame_end)
        y = trace[frame_start:frame_end]
        ax.plot(x, y, linewidth=linewidth, color=tokens.ACCENT, alpha=0.95)

        if stim_frames:
            for sf in stim_frames:
                if frame_start <= sf < frame_end:
                    ax.axvline(x=sf, color=tokens.DANGER, linestyle="--",
                               alpha=0.8, linewidth=1.3)

        if ymin is not None and ymax is not None and ymax > ymin:
            ax.set_ylim(ymin, ymax)

        ax.set_xlabel("Frame", fontsize=label_size, color=tokens.MUTED)
        if ylabel:
            ax.set_ylabel(ylabel, fontsize=label_size, color=tokens.MUTED)
        ax.tick_params(labelsize=tick_size, colors=tokens.MUTED)
        style_axes(ax, variant=variant, transparent=transparent)
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                transform=ax.transAxes, fontsize=label_size, color=tokens.MUTED)
        ax.set_xticks([])
        ax.set_yticks([])
        style_axes(ax, variant=variant, transparent=transparent)

    if title:
        ax.set_title(title, fontsize=title_size, fontweight="bold",
                     color=tokens.TEXT, pad=4)
    return frame_start, frame_end


def render_trace_pixmap(trace, *, width_px, height_px, device_pixel_ratio=1.0,
                        **plot_kwargs):
    """Render a mini ROI trace to a QPixmap via the Agg backend (no Qt canvas).

    HiDPI-crisp (renders at dpi*dpr, tags the pixmap with the ratio) and leak-free
    (the Figure is created off-pyplot and dropped immediately after copying pixels
    out). Returns a QPixmap; on any failure returns an empty QPixmap so the caller
    can still place a card.
    """
    from PyQt6.QtGui import QImage, QPixmap
    try:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        dpr = max(1.0, float(device_pixel_ratio))
        dpi = 100.0
        fig = Figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi * dpr)
        fig.patch.set_facecolor(tokens.SURFACE)
        canvas = FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        ax.set_facecolor(tokens.SURFACE)

        plot_trace_on_ax(ax, trace, variant="card", **plot_kwargs)

        fig.tight_layout(pad=0.4)
        canvas.draw()

        w, h = canvas.get_width_height(physical=True)
        # buffer_rgba() returns a view into the renderer; tobytes() makes an owned
        # copy so the QImage does not outlive the figure's buffer (lifetime safe).
        buf = np.asarray(canvas.buffer_rgba()).reshape(h, w, 4)
        qimg = QImage(buf.tobytes(), w, h, 4 * w, QImage.Format.Format_RGBA8888)
        pix = QPixmap.fromImage(qimg)
        pix.setDevicePixelRatio(dpr)

        # Drop references so the figure + Agg buffer are GC'd (never registered
        # with pyplot, so do not call plt.close()).
        fig.clf()
        return pix
    except Exception as exc:  # noqa: BLE001
        print(f"[theme] render_trace_pixmap failed: {exc}")
        return QPixmap()
