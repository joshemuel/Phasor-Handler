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
    def __init__(self, parent=None, margin=0, spacing=12, center=False):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        # When True and the laid-out content is short enough to fit the given
        # rect, rows are centered horizontally and the block is centered
        # vertically. This is what makes a handful of trace cards sit zoomed and
        # centered instead of clinging to the top-left corner.
        self._center = center
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
        spacing = self._spacing

        # First pass: group items into rows (independent of positioning) so we can
        # measure each row's width/height and the whole block's height up front.
        rows = []  # each: {'items': [(item, hint)], 'width': int, 'height': int}
        cur_items = []
        cur_w = 0
        cur_h = 0
        for item in self._items:
            hint = item.sizeHint()
            if cur_items and cur_w + hint.width() > effective.width():
                rows.append({'items': cur_items, 'width': cur_w - spacing,
                             'height': cur_h})
                cur_items = []
                cur_w = 0
                cur_h = 0
            cur_items.append((item, hint))
            cur_w += hint.width() + spacing
            cur_h = max(cur_h, hint.height())
        if cur_items:
            rows.append({'items': cur_items, 'width': cur_w - spacing,
                         'height': cur_h})

        total_h = sum(r['height'] for r in rows)
        if rows:
            total_h += spacing * (len(rows) - 1)

        # Center the whole block only when there's spare room (content shorter than
        # the rect); when it exactly fills or overflows — the scrolling, many-card
        # case — keep the natural top-left flow.
        fits = self._center and total_h < effective.height()
        y = effective.y()
        if fits:
            y += (effective.height() - total_h) // 2

        for row in rows:
            x = effective.x()
            if fits and row['width'] < effective.width():
                x += (effective.width() - row['width']) // 2
            for item, hint in row['items']:
                if not test_only:
                    item.setGeometry(QRect(QPoint(x, y), hint))
                x += hint.width() + spacing
            y += row['height'] + spacing

        return total_h + margins.top() + margins.bottom()
