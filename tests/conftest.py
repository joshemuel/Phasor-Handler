import os

import pytest


@pytest.fixture(scope="session")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pyqt_widgets = pytest.importorskip("PyQt6.QtWidgets")
    app = pyqt_widgets.QApplication.instance()
    return app or pyqt_widgets.QApplication([])
