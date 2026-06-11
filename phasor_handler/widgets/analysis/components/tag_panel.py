"""
ROI Tag Panel Component

This component handles ROI tagging:
- Display of created tags (with color swatch and member count)
- Create/Delete/Assign tag functionality
- Single click highlights a tag's member ROIs on the image
- Double click opens a details dialog with per-tag actions
  (Remove, Move, Rename, Change Color, Save Tag Image, Export Tag Traces)

Tag definitions live on the main window as
``main_window._roi_tags = [{'name': str, 'color': (r, g, b, a)}]``.
Membership is a ``'tag'`` key on each ROI dict in ``_saved_rois`` so it can
never hold a stale index: removing an ROI removes its membership with it.
"""

import datetime
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QListWidget, QListWidgetItem,
    QPushButton, QGridLayout, QLabel, QSizePolicy, QInputDialog, QMessageBox,
    QColorDialog, QFileDialog, QDialog
)

from phasor_handler.theme import tokens
from phasor_handler.theme.dialogs import style_file_dialog

# Distinguishable 10-color palette (Trubetskoy) for auto-assigned tag colors;
# high-chroma values read well on the dark theme.
TAG_PALETTE = [
    (230, 25, 75, 220),    # red
    (60, 180, 75, 220),    # green
    (255, 225, 25, 220),   # yellow
    (0, 130, 200, 220),    # blue
    (245, 130, 48, 220),   # orange
    (145, 30, 180, 220),   # purple
    (70, 240, 240, 220),   # cyan
    (240, 50, 230, 220),   # magenta
    (210, 245, 60, 220),   # lime
    (250, 190, 212, 220),  # pink
]


def _safe_filename_part(name):
    """Reduce a tag name to filesystem-safe characters (same idiom as
    _save_current_view's directory-name cleaning)."""
    return "".join(c for c in name if c.isalnum() or c in ('-', '_')).rstrip() or "tag"


def _swatch_icon(color, size=12):
    pm = QPixmap(size, size)
    pm.fill(QColor(int(color[0]), int(color[1]), int(color[2])))
    return QIcon(pm)


class TagPanelWidget(QWidget):
    """Widget for managing ROI tags with create/delete/assign functionality."""

    # Emitted after any tag definition or membership mutation
    tagsChanged = pyqtSignal()

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()
        self.refresh()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        tag_group = QGroupBox("Tags")
        tag_vbox = QVBoxLayout()

        self.tag_list_widget = QListWidget()
        self.tag_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.tag_list_widget.setMaximumHeight(120)
        self.tag_list_widget.itemSelectionChanged.connect(self._on_tag_selection_changed)
        self.tag_list_widget.itemDoubleClicked.connect(self._on_tag_double_clicked)
        tag_vbox.addWidget(self.tag_list_widget)

        grid = QGridLayout()
        self.create_tag_btn = QPushButton("Create Tag")
        self.delete_tag_btn = QPushButton("Delete Tag")
        self.assign_btn = QPushButton("Assign")
        for btn in (self.create_tag_btn, self.delete_tag_btn, self.assign_btn):
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.assign_btn.setToolTip(
            "Assign the ROIs selected in the Saved ROIs list to the selected tag")
        grid.addWidget(self.create_tag_btn, 0, 0)
        grid.addWidget(self.delete_tag_btn, 0, 1)
        grid.addWidget(self.assign_btn, 1, 0, 1, 2)
        tag_vbox.addLayout(grid)

        tag_group.setLayout(tag_vbox)
        main_layout.addWidget(tag_group)
        self.setLayout(main_layout)

        self.create_tag_btn.clicked.connect(self._on_create_tag)
        self.delete_tag_btn.clicked.connect(self._on_delete_tag)
        self.assign_btn.clicked.connect(self._on_assign)

    # --- data helpers -----------------------------------------------------

    def _tags(self):
        if not hasattr(self.main_window, '_roi_tags') or self.main_window._roi_tags is None:
            self.main_window._roi_tags = []
        return self.main_window._roi_tags

    def _find_tag(self, name):
        for tag in self._tags():
            if tag.get('name') == name:
                return tag
        return None

    def members_of(self, tag_name):
        """Return [(index, roi_dict)] for ROIs carrying `tag_name`."""
        rois = getattr(self.main_window, '_saved_rois', None) or []
        return [(i, roi) for i, roi in enumerate(rois) if roi.get('tag') == tag_name]

    def next_palette_color(self):
        """First palette color no existing tag uses; cycle when all are taken."""
        used = {tuple(t.get('color', ())) for t in self._tags()}
        for color in TAG_PALETTE:
            if color not in used:
                return color
        return TAG_PALETTE[len(self._tags()) % len(TAG_PALETTE)]

    def unique_tag_name(self, base="Tag"):
        """First available "Tag N" name (same scheme as ROI naming)."""
        existing = {t.get('name') for t in self._tags()}
        next_num = 1
        while f"{base} {next_num}" in existing:
            next_num += 1
        return f"{base} {next_num}"

    def selected_tag_name(self):
        item = self.tag_list_widget.currentItem()
        if item is not None and item.isSelected():
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _selected_roi_rows(self):
        """Rows selected in the Saved ROIs list (rows map 1:1 to _saved_rois)."""
        list_widget = getattr(self.main_window, 'roi_list_widget', None)
        if list_widget is None:
            return []
        return sorted(list_widget.row(item) for item in list_widget.selectedItems())

    def _roi_tool(self):
        return getattr(self.main_window, 'roi_tool', None)

    def _repaint(self):
        tool = self._roi_tool()
        if tool is not None and getattr(tool, '_base_pixmap', None) is not None:
            tool._paint_overlay()

    def _emit_changed(self):
        self.refresh()
        self.tagsChanged.emit()

    # --- public API -------------------------------------------------------

    def refresh(self):
        """Rebuild the tag list from definitions, push them to the ROI tool,
        prune a highlight whose tag no longer exists, and repaint."""
        selected = self.selected_tag_name()
        names = []
        self.tag_list_widget.blockSignals(True)
        try:
            self.tag_list_widget.clear()
            for tag in self._tags():
                name = tag.get('name')
                names.append(name)
                count = len(self.members_of(name))
                item = QListWidgetItem(_swatch_icon(tag.get('color', (200, 200, 200))),
                                       f"{name}  ({count})")
                item.setData(Qt.ItemDataRole.UserRole, name)
                self.tag_list_widget.addItem(item)
                if name == selected:
                    item.setSelected(True)
                    self.tag_list_widget.setCurrentItem(item)
        finally:
            self.tag_list_widget.blockSignals(False)

        tool = self._roi_tool()
        if tool is not None:
            tool.set_roi_tags(self._tags())
            if (getattr(tool, '_highlighted_tag', None) is not None
                    and tool._highlighted_tag not in names):
                tool.set_highlighted_tag(None)
        self._repaint()

    # --- slots --------------------------------------------------------------

    def _on_create_tag(self):
        name, ok = QInputDialog.getText(self, "Create Tag", "Tag name:",
                                        text=self.unique_tag_name())
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if self._find_tag(name) is not None:
            QMessageBox.warning(self, "Duplicate Tag",
                                f"A tag named '{name}' already exists.")
            return

        self._tags().append({'name': name, 'color': self.next_palette_color()})
        for row in self._selected_roi_rows():
            self.main_window._saved_rois[row]['tag'] = name
        self._emit_changed()

        # Select the new tag (triggers the highlight via itemSelectionChanged)
        for i in range(self.tag_list_widget.count()):
            if self.tag_list_widget.item(i).data(Qt.ItemDataRole.UserRole) == name:
                self.tag_list_widget.setCurrentRow(i)
                break

    def _on_delete_tag(self):
        name = self.selected_tag_name()
        if name is None:
            return
        members = self.members_of(name)
        if members:
            answer = QMessageBox.question(
                self, "Delete Tag",
                f"Delete tag '{name}'? Its {len(members)} ROI(s) will be "
                "untagged, not deleted.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        for _idx, roi in members:
            roi.pop('tag', None)
        self.main_window._roi_tags = [t for t in self._tags() if t.get('name') != name]
        tool = self._roi_tool()
        if tool is not None and getattr(tool, '_highlighted_tag', None) == name:
            tool.set_highlighted_tag(None)
        self._emit_changed()

    def _on_assign(self):
        name = self.selected_tag_name()
        rows = self._selected_roi_rows()
        if name is None or not rows:
            QMessageBox.information(
                self, "Assign ROIs to Tag",
                "Select a tag in this list and one or more ROIs in the "
                "Saved ROIs list, then click Assign.")
            return
        for row in rows:
            self.main_window._saved_rois[row]['tag'] = name
        self._emit_changed()

    def _on_tag_selection_changed(self):
        tool = self._roi_tool()
        if tool is not None:
            tool.set_highlighted_tag(self.selected_tag_name())

    def _on_tag_double_clicked(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        dialog = TagDetailsDialog(self.main_window, self, name, parent=self)
        dialog.exec()
        self.refresh()


class TagDetailsDialog(QDialog):
    """Modal dialog listing a tag's member ROIs with per-tag actions.

    Modality blocks ROI list mutations while open, so the member indices
    cached in the item roles stay valid between refreshes.
    """

    def __init__(self, main_window, tag_panel, tag_name, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.tag_panel = tag_panel
        self._tag_name = tag_name

        self.setWindowTitle(f"Tag: {tag_name}")
        self.setModal(True)
        self.resize(360, 420)
        self._setup_ui()
        self._refresh_members()

    def _setup_ui(self):
        layout = QVBoxLayout()

        self.header_label = QLabel()
        self.header_label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: bold;
                padding: 8px;
                color: {tokens.TEXT};
                background-color: {tokens.ELEVATED};
                border: 1px solid {tokens.ACCENT_DIM};
                border-radius: {tokens.RADIUS_PANEL}px;
            }}
        """)
        layout.addWidget(self.header_label)

        self.member_list_widget = QListWidget()
        self.member_list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.member_list_widget)

        grid = QGridLayout()
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setToolTip("Remove the selected ROIs from this tag (keeps the ROIs)")
        self.move_btn = QPushButton("Move")
        self.move_btn.setToolTip("Move the selected ROIs to another tag")
        self.save_image_btn = QPushButton("Save Tag Image")
        self.save_image_btn.setToolTip(
            "Export a PNG highlighting this tag; all other ROIs are dimmed")
        self.rename_btn = QPushButton("Rename Tag")
        self.color_btn = QPushButton("Change Color")
        self.export_traces_btn = QPushButton("Export Tag Traces")
        self.export_traces_btn.setToolTip("Export traces for this tag's ROIs only")
        for btn in (self.remove_btn, self.move_btn, self.save_image_btn,
                    self.rename_btn, self.color_btn, self.export_traces_btn):
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grid.addWidget(self.remove_btn, 0, 0)
        grid.addWidget(self.move_btn, 0, 1)
        grid.addWidget(self.save_image_btn, 0, 2)
        grid.addWidget(self.rename_btn, 1, 0)
        grid.addWidget(self.color_btn, 1, 1)
        grid.addWidget(self.export_traces_btn, 1, 2)
        layout.addLayout(grid)

        button_bar = QHBoxLayout()
        button_bar.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_bar.addWidget(self.close_btn)
        layout.addLayout(button_bar)

        self.setLayout(layout)

        self.remove_btn.clicked.connect(self._on_remove_clicked)
        self.move_btn.clicked.connect(self._on_move_clicked)
        self.save_image_btn.clicked.connect(self._on_save_tag_image_clicked)
        self.rename_btn.clicked.connect(self._on_rename_clicked)
        self.color_btn.clicked.connect(self._on_change_color_clicked)
        self.export_traces_btn.clicked.connect(self._on_export_traces_clicked)

    def _refresh_members(self):
        """Rebuild the member list (indices in item roles are re-resolved here
        after every mutating action) and update the header."""
        self.member_list_widget.clear()
        members = self.tag_panel.members_of(self._tag_name)
        tag = self.tag_panel._find_tag(self._tag_name)
        color = tag.get('color', (200, 200, 200)) if tag else (200, 200, 200)
        for idx, roi in members:
            item = QListWidgetItem(_swatch_icon(roi.get('color', color)),
                                   roi.get('name', f"ROI {idx + 1}"))
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.member_list_widget.addItem(item)
        self.header_label.setText(f"{self._tag_name} — {len(members)} ROI(s)")
        swatch = QPixmap(14, 14)
        swatch.fill(QColor(int(color[0]), int(color[1]), int(color[2])))
        self.setWindowIcon(QIcon(swatch))
        self.setWindowTitle(f"Tag: {self._tag_name}")

    def _selected_member_indices(self):
        return [item.data(Qt.ItemDataRole.UserRole)
                for item in self.member_list_widget.selectedItems()]

    def _after_membership_change(self):
        self._refresh_members()
        self.tag_panel._emit_changed()

    # --- actions ----------------------------------------------------------

    def _on_remove_clicked(self):
        indices = self._selected_member_indices()
        if not indices:
            QMessageBox.information(self, "Remove from Tag",
                                    "Select one or more ROIs to remove from this tag.")
            return
        for idx in indices:
            self.main_window._saved_rois[idx].pop('tag', None)
        self._after_membership_change()

    def _on_move_clicked(self):
        indices = self._selected_member_indices()
        if not indices:
            QMessageBox.information(self, "Move to Tag",
                                    "Select one or more ROIs to move to another tag.")
            return
        other_names = [t.get('name') for t in self.tag_panel._tags()
                       if t.get('name') != self._tag_name]
        if not other_names:
            QMessageBox.information(self, "Move to Tag",
                                    "There are no other tags to move these ROIs to.")
            return
        target, ok = QInputDialog.getItem(self, "Move to Tag", "Target tag:",
                                          other_names, 0, False)
        if not ok or not target:
            return
        for idx in indices:
            self.main_window._saved_rois[idx]['tag'] = target
        self._after_membership_change()

    def _on_rename_clicked(self):
        name, ok = QInputDialog.getText(self, "Rename Tag", "New name:",
                                        text=self._tag_name)
        if not ok:
            return
        name = name.strip()
        if not name or name == self._tag_name:
            return
        if self.tag_panel._find_tag(name) is not None:
            QMessageBox.warning(self, "Duplicate Tag",
                                f"A tag named '{name}' already exists.")
            return
        tag = self.tag_panel._find_tag(self._tag_name)
        if tag is None:
            return
        members = self.tag_panel.members_of(self._tag_name)
        tag['name'] = name
        for _idx, roi in members:
            roi['tag'] = name
        tool = self.tag_panel._roi_tool()
        if tool is not None and getattr(tool, '_highlighted_tag', None) == self._tag_name:
            tool.set_highlighted_tag(name)
        self._tag_name = name
        self._after_membership_change()

    def _on_change_color_clicked(self):
        tag = self.tag_panel._find_tag(self._tag_name)
        if tag is None:
            return
        current = tag.get('color', (200, 200, 200, 220))
        initial = QColor(int(current[0]), int(current[1]), int(current[2]),
                         int(current[3]) if len(current) > 3 else 220)
        color = QColorDialog.getColor(
            initial, self, "Tag Color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel
            | QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if not color.isValid():
            return
        tag['color'] = (color.red(), color.green(), color.blue(), color.alpha())
        self._after_membership_change()

    def _on_save_tag_image_clicked(self):
        analysis_widget = getattr(self.main_window, 'analysis_widget', None)
        pixmap = None
        if analysis_widget is not None:
            pixmap = analysis_widget._render_native_export_pixmap(
                emphasize_tag=self._tag_name)
        if pixmap is None:
            QMessageBox.warning(self, "No Image",
                                "No image is currently displayed to save.")
            return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name = "image"
        default_dir = ""
        get_dir = getattr(self.main_window, '_get_current_directory_path', None)
        current_dir_path = get_dir() if get_dir else None
        if current_dir_path:
            default_dir = current_dir_path
            dir_name = _safe_filename_part(os.path.basename(current_dir_path))
        default_filename = (f"{dir_name}_tag_{_safe_filename_part(self._tag_name)}"
                            f"_{timestamp}.png")

        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Save Tag Image")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setNameFilter("PNG Files (*.png)")
        file_dialog.setDefaultSuffix("png")
        if default_dir:
            file_dialog.selectFile(os.path.join(default_dir, default_filename))
        else:
            file_dialog.selectFile(default_filename)
        style_file_dialog(file_dialog)
        if not file_dialog.exec():
            return
        file_path = file_dialog.selectedFiles()[0]
        if not file_path.lower().endswith('.png'):
            file_path += '.png'

        if pixmap.save(file_path, "PNG"):
            QMessageBox.information(self, "Image Saved",
                                    f"Tag image saved successfully to:\n{file_path}")
        else:
            QMessageBox.critical(self, "Save Failed",
                                 f"Failed to save tag image to:\n{file_path}")

    def _on_export_traces_clicked(self):
        members = self.tag_panel.members_of(self._tag_name)
        if not members:
            QMessageBox.information(self, "No ROIs",
                                    "This tag has no ROIs to export.")
            return
        roi_list_component = getattr(self.main_window, 'roi_list_component', None)
        if roi_list_component is None:
            return
        rois = [roi for _idx, roi in members]
        default_filename = f"roi_traces_{_safe_filename_part(self._tag_name)}.txt"
        roi_list_component.export_traces_for_rois(rois, default_filename=default_filename)
        self._refresh_members()
