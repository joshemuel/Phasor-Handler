"""Shared styling for non-native QFileDialogs.

The themed (non-native) QFileDialog inherits its navigation glyphs from the Qt
style. Against the dark palettes (Ice Cyan especially) those glyphs are nearly
invisible - the forward arrow goes dark when enabled, and the parent-directory
button blends into the background. This module repaints the navigation tool
buttons with our own high-contrast arrow icons and gives them clear tooltips:

  - back arrow    -> previous (history back)
  - forward arrow -> enter / next (history forward)
  - up arrow      -> parent directory

Use style_file_dialog(dialog) on every QFileDialog so the look is consistent
across the "Add Directories" picker and the Save/Load ROI dialogs.
"""

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QFileDialog, QToolButton

from . import icons as theme_icons
from . import tokens

# objectName -> (nav asset key, tooltip)
_NAV_BUTTONS = {
    "backButton": ("back", "Back (previous)"),
    "forwardButton": ("forward", "Forward (next)"),
    "toParentButton": ("up", "Up (parent directory)"),
}


def style_file_dialog(dialog):
    """Force a QFileDialog non-native and give it high-contrast nav arrows.

    Safe to call on any QFileDialog; styling failures never block the dialog.
    """
    try:
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        assets = theme_icons.ensure_nav_assets(tokens.TEXT)
        if not assets:
            return
        for obj_name, (asset_key, tip) in _NAV_BUTTONS.items():
            btn = dialog.findChild(QToolButton, obj_name)
            if btn is not None and assets.get(asset_key):
                btn.setIcon(QIcon(assets[asset_key]))
                btn.setIconSize(QSize(18, 18))
                btn.setToolTip(tip)
    except Exception as exc:  # noqa: BLE001 - styling must never block the dialog
        print(f"[theme] style_file_dialog failed: {exc}")
