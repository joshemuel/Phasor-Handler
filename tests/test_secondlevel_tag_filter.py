"""Regression tests for the Second Level tag-filter dropdown.

Guards the fix for the "(None)" bug: opening the tag dropdown (an InstantPopup
QToolButton) delivers only the *release* of the opening click to the menu — the
press went to the button. The menu pops up under the cursor, so that stray
release used to land on and toggle the top "(All)" item, deselecting every tag
and leaving the grid empty. _CheckableMenu now ignores any release whose press
did not occur inside the menu.
"""

import pytest


def _mouse_event(kind):
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtCore import QPointF, Qt
    return QMouseEvent(kind, QPointF(5, 5), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)


def _make_menu():
    from phasor_handler.widgets.secondlevel.view import _CheckableMenu
    menu = _CheckableMenu()
    action = menu.addAction("(All)")
    action.setCheckable(True)
    action.setChecked(True)
    fired = []
    action.triggered.connect(fired.append)
    menu.setActiveAction(action)
    return menu, action, fired


def test_fallthrough_release_does_not_toggle(qt_app):
    """A release with no preceding in-menu press (the popup-opening click) must
    not toggle the highlighted item."""
    pytest.importorskip("tifffile")  # needed to import the widget module
    from PyQt6.QtCore import QEvent

    menu, action, fired = _make_menu()
    menu.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease))

    assert action.isChecked() is True, "(All) must stay checked on a stray release"
    assert fired == [], "no trigger should fire for a press-less release"


def test_real_click_still_toggles(qt_app):
    """A genuine in-menu click (press then release) toggles the item as before."""
    pytest.importorskip("tifffile")
    from PyQt6.QtCore import QEvent

    menu, action, fired = _make_menu()
    menu.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress))
    menu.setActiveAction(action)
    menu.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease))

    assert action.isChecked() is False, "a real click must toggle the item"
    assert fired == [False], "a real click must emit triggered once"
