import shutil
from pathlib import Path

import numpy as np

from phasor_handler.tools.lazy_stack import (
    LazyFrameStack,
    discover_channel_npy_files,
)
from phasor_handler.tools.misc import (
    load_or_create_experiment_metadata,
    resolve_pixel_size,
    resolve_timestamps,
)


BUG_FIXTURE = Path(
    "test_data/bug/StreamingPhasorCapture(1of3)-1776839887-508.imgdir"
)
LARGE_BUG_FIXTURE = Path("test_data/bug/large_data")


def test_resolve_timestamps_handles_raw_elapsed_times_yaml_shape():
    metadata = {"ElapsedTimes.yaml": {"theElapsedTimes": [4, 0, 95, 190, 285]}}

    assert resolve_timestamps(metadata, 4) == [0.0, 0.095, 0.19, 0.285]


def test_load_or_create_metadata_from_raw_i3_folder(tmp_path):
    raw_dir = tmp_path / "raw.imgdir"
    raw_dir.mkdir()
    for path in BUG_FIXTURE.glob("*.yaml"):
        shutil.copy2(path, raw_dir / path.name)

    metadata = load_or_create_experiment_metadata(str(raw_dir))

    assert metadata is not None
    assert metadata["n_frames"] == 9000
    assert len(metadata["time_stamps"]) == 9000
    assert resolve_timestamps(metadata, 4) == [0.0, 0.095, 0.19, 0.285]
    assert resolve_pixel_size(metadata) == 0.7154637
    assert (raw_dir / "experiment_summary.pkl").exists()
    assert (raw_dir / "experiment_summary.json").exists()


def test_lazy_frame_stack_indexes_across_split_npy_files(tmp_path):
    first = np.arange(2 * 2 * 3, dtype=np.uint16).reshape(2, 2, 3)
    second = np.arange(2 * 2 * 3, 5 * 2 * 3, dtype=np.uint16).reshape(3, 2, 3)
    np.save(tmp_path / "ImageData_Ch0_TP0000000.npy", first)
    np.save(tmp_path / "ImageData_Ch0_TP0003000.npy", second)

    paths = discover_channel_npy_files(str(tmp_path), "ImageData_Ch0")
    stack = LazyFrameStack(paths)

    assert stack.shape == (5, 2, 3)
    np.testing.assert_array_equal(stack[0], first[0])
    np.testing.assert_array_equal(stack[2], second[0])
    np.testing.assert_array_equal(
        stack[1:4],
        np.concatenate([first[1:], second[:2]], axis=0),
    )


def test_large_raw_recording_loads_as_lazy_stacks(monkeypatch, qt_app):
    from phasor_handler.widgets.analysis.components.image_view import (
        ImageViewWidget,
    )

    image_view = ImageViewWidget()
    monkeypatch.setattr(
        image_view,
        "_load_experiment_metadata",
        lambda exp_details, exp_json, directory_path: None,
    )

    data = image_view.load_experiment_data(
        str(LARGE_BUG_FIXTURE), use_registered=False
    )

    assert data["success"] is True
    assert data["error"] is None
    assert data["nframes"] == 9000
    assert isinstance(data["tif"], LazyFrameStack)
    assert isinstance(data["tif_chan2"], LazyFrameStack)
    assert data["tif"].shape == (9000, 356, 396)
    assert data["tif_chan2"].shape == (9000, 356, 396)


def test_streaming_roi_export_recovers_timestamps_for_loaded_frames(
    monkeypatch, tmp_path, qt_app
):
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    from phasor_handler.widgets.analysis.components.image_view import (
        ImageViewWidget,
    )
    from phasor_handler.widgets.analysis.components.roi_list import (
        RoiListWidget,
    )

    raw_metadata_dir = tmp_path / "raw_metadata.imgdir"
    raw_metadata_dir.mkdir()
    for path in BUG_FIXTURE.glob("*.yaml"):
        shutil.copy2(path, raw_metadata_dir / path.name)

    image_view = ImageViewWidget()
    monkeypatch.setattr(
        image_view,
        "_load_experiment_metadata",
        lambda exp_details, exp_json, directory_path: None,
    )
    data = image_view.load_experiment_data(
        str(BUG_FIXTURE), use_registered=False
    )

    output_path = tmp_path / "roi_traces.txt"
    monkeypatch.setattr(QFileDialog, "exec", lambda self: True)
    monkeypatch.setattr(
        QFileDialog, "selectedFiles", lambda self: [str(output_path)]
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    main_window = RoiExportMainWindowProbe(data, raw_metadata_dir)
    roi_list = RoiListWidget(main_window)
    roi_list._on_export_roi_clicked()

    lines = output_path.read_text().splitlines()
    first_rows = [line.split("\t")[:2] for line in lines[1:5]]

    assert main_window._exp_data["n_frames"] == 9000
    assert data["nframes"] == 526
    assert len(lines) == 527
    assert first_rows == [
        ["0", "0.000000"],
        ["1", "0.095000"],
        ["2", "0.190000"],
        ["3", "0.285000"],
    ]


class RoiExportMainWindowProbe:
    def __init__(self, data, metadata_dir):
        self._current_tif = data["tif"]
        self._current_tif_chan2 = data["tif_chan2"]
        self._saved_rois = [
            {
                "name": "ROI 1",
                "xyxy": (0, 0, 8, 8),
                "type": "circular",
                "rotation": 0.0,
            }
        ]
        self._exp_data = None
        self._metadata_dir = metadata_dir

    def _get_current_directory_path(self):
        return str(self._metadata_dir)
