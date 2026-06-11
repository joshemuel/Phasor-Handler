"""
CollapsibleColumn - wrap a column of controls with a small toggle chevron.

Gives a fixed side column a compact, top-anchored chevron button («/») that hides
or shows its content, so the user can reclaim the space (e.g. to widen the image
viewer) and reopen it later. Only the *content* collapses; the chevron stays
visible so there is always something to click.

The chevron carries the objectName "collapseChevron" and is styled centrally in
theme/qss.py (flat, no background, half opacity, accent on hover) - the same
pattern as the preferences gear - so it follows the active theme automatically
whenever the application stylesheet is rebuilt.

`side='left'` puts the chevron on the content's right edge (use for a left-hand
column, like the First Level view-controls); `side='right'` puts it on the left
edge (use for a right-hand column, like the Z-projection / BnC / ROI-tool stack).
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QToolButton
from PyQt6.QtCore import Qt


class CollapsibleColumn(QWidget):
    """A content widget plus a small chevron button that hides/shows it."""

    def __init__(self, content_widget, side='left', parent=None):
        super().__init__(parent)
        if side not in ('left', 'right'):
            side = 'left'
        self._side = side
        self._content = content_widget
        self._collapsed = False

        self._toggle = QToolButton()
        self._toggle.setObjectName("collapseChevron")
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setFixedSize(16, 26)
        self._toggle.setToolTip("Collapse / expand this panel")
        self._toggle.clicked.connect(self.toggle)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        if side == 'left':
            layout.addWidget(self._content)
            layout.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignTop)
        else:
            layout.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignTop)
            layout.addWidget(self._content)

        self._update_arrow()

    def is_collapsed(self):
        return self._collapsed

    def toggle(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed):
        self._collapsed = bool(collapsed)
        self._content.setVisible(not self._collapsed)
        self._update_arrow()

    def _update_arrow(self):
        if self._side == 'left':
            glyph = "»" if self._collapsed else "«"  # » expand / « collapse
        else:
            glyph = "«" if self._collapsed else "»"  # « expand / » collapse
        self._toggle.setText(glyph)
