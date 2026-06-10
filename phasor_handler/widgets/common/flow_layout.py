"""
FlowLayout - a left-to-right wrapping layout.

Standard Qt "flow layout" pattern ported to PyQt6: lays items out horizontally and
wraps to a new row when the current row runs out of width, reflowing on resize.
Reports heightForWidth so it works correctly inside a QScrollArea with
setWidgetResizable(True). Used by the Second Level tab to auto-fit ROI trace cards
to as many columns as the window allows (replacing a hardcoded column count).
"""

from PyQt6.QtWidgets import QLayout
from PyQt6.QtCore import Qt, QRect, QSize, QPoint


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=12):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    # --- required QLayout overrides ---
    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(),
                      margins.top() + margins.bottom())
        return size

    # --- layout engine ---
    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(),
                                  -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0
        spacing = self._spacing

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > effective.right() and line_height > 0:
                # wrap to next row
                x = effective.x()
                y = y + line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + margins.bottom()
