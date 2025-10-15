import sys
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QFileDialog, QMessageBox, 
    QListView, QTreeView, QAbstractItemView, QTabWidget
)
from PyQt6.QtGui import QFileSystemModel, QIcon
from PyQt6.QtCore import Qt
from PyQt6.QtCore import QThread

from widgets import ConversionWidget, RegistrationWidget, AnalysisWidget
from tools import misc
from workers import RegistrationWorker
from models.dir_manager import DirManager
from themes import apply_dark_theme
import qdarktheme

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phasor Handler v2.0")
        self.setWindowIcon(QIcon('img/logo.ico'))
        # self.setMinimumSize(1400, 1000)
        # central directory manager (shared with widgets)
        self.dir_manager = DirManager()
        # expose legacy attribute for compatibility
        self.selected_dirs = self.dir_manager.list()
        # keep the local list synced when dir_manager changes
        self.dir_manager.directoriesChanged.connect(lambda lst: setattr(self, 'selected_dirs', list(lst)))

        # Create tab widget and add sub-widgets
        self.tabs = QTabWidget()
        self.tabs.addTab(ConversionWidget(self), "Conversion")
        self.tabs.addTab(RegistrationWidget(self), "Registration")
        # AnalysisWidget exposes compatible attributes on the main window
        self.tabs.addTab(AnalysisWidget(self), "Analysis")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.setCentralWidget(self.tabs)

    def _init_roi_state(self):
        """Initialize ROI and CNB (contrast/brightness) state on the window instance."""
        self._roi_center = None
        self._roi_radius = None
        self._roi_overlay_pixmap = None

        # CNB (contrast & brightness) state
        self._current_qimage = None
        self._current_image_np = None
        self._cnb_window = None
        
        # ImageJ-like: min/max intensity (applied before contrast)
        self._cnb_min = None
        self._cnb_max = None

        # contrast multiplier around midpoint (1.0 = no change)
        self._cnb_contrast = 1.0

        # Master switch to disable/enable CNB functionality (default: disabled)
        self._cnb_active = False


    def add_dirs_dialog(self, tab):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Select One or More Directories')
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        for view in dialog.findChildren((QListView, QTreeView)):
            if isinstance(view.model(), QFileSystemModel):
                view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        if dialog.exec():
            selected_paths = dialog.selectedFiles()
            # delegate to the manager
            self.dir_manager.add(selected_paths)
            # refresh views (manager emits signal which can call refresh_dir_lists)
            self.refresh_dir_lists()
        dialog.deleteLater()

    def remove_selected_dirs(self, tab):
        widget = self.conv_list_widget if tab == 'conversion' else self.reg_list_widget if tab == "registration" else self.analysis_list_widget
        selected_items = widget.selectedItems()
        if not selected_items:
            return
        to_remove = []
        for item in selected_items:
            # Get the full path from UserRole, fallback to text for compatibility
            full_path = item.data(Qt.ItemDataRole.UserRole)
            if full_path is None:
                full_path = item.text()
            to_remove.append(full_path)
        # update model; UI will refresh on signal
        self.dir_manager.remove(to_remove)
        self.refresh_dir_lists()

    def refresh_dir_lists(self):
        # Clear only if the widgets exist and are valid
        if hasattr(self, 'conv_list_widget'):
            self.conv_list_widget.clear()
        if hasattr(self, 'reg_list_widget'):
            try:
                self.reg_list_widget.clear()
            except RuntimeError:
                # Widget was deleted; recreate the Registration tab if needed
                pass
        if hasattr(self, 'analysis_list_widget'):
            self.analysis_list_widget.clear()

        from PyQt6.QtWidgets import QListWidgetItem
        for full_path, display_name in self.dir_manager.get_display_names():
            if hasattr(self, 'conv_list_widget'):
                item = QListWidgetItem(display_name)
                item.setToolTip(full_path)
                item.setData(Qt.ItemDataRole.UserRole, full_path)
                self.conv_list_widget.addItem(item)
            if hasattr(self, 'reg_list_widget'):
                try:
                    item = QListWidgetItem(display_name)
                    item.setToolTip(full_path)
                    item.setData(Qt.ItemDataRole.UserRole, full_path)
                    self.reg_list_widget.addItem(item)
                except RuntimeError:
                    pass
            if hasattr(self, 'analysis_list_widget'):
                item = QListWidgetItem(display_name)
                item.setToolTip(full_path)
                item.setData(Qt.ItemDataRole.UserRole, full_path)
                self.analysis_list_widget.addItem(item)

    def on_tab_changed(self, idx):
        # When switching to analysis tab, refresh its directory list
        tab_text = self.tabs.tabText(idx)
        if tab_text == "Analysis":
            if hasattr(self, 'analysis_list_widget'):
                self.analysis_list_widget.clear()
                from PyQt6.QtWidgets import QListWidgetItem
                for full_path, display_name in self.dir_manager.get_display_names():
                    item = QListWidgetItem(display_name)
                    item.setToolTip(full_path)
                    item.setData(Qt.ItemDataRole.UserRole, full_path)
                    self.analysis_list_widget.addItem(item)

    def run_conversion_script(self):
        if not self.selected_dirs:
            QMessageBox.warning(self, "No Directories", "Please add at least one directory to the list before running.")
            return

        mode = self.mode_combo.currentText().lower()
        self.conv_log.clear()
        self.conv_log.append(f"--- Starting Batch Conversion in '{mode}' mode ---\n")
        for i, conv_dir in enumerate(self.selected_dirs):
            self.conv_log.append(f"Processing ({i+1}/{len(self.selected_dirs)}): {conv_dir}")
            # 1. Run convert.py
            cmd = [sys.executable, "scripts/convert.py", str(conv_dir), "--mode", mode]
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                for line in proc.stdout:
                    self.conv_log.append(line.rstrip())
                    QApplication.processEvents()
                retcode = proc.wait()
                if retcode != 0:
                    self.conv_log.append(f"FAILED to convert: {conv_dir}\n")
                else:
                    self.conv_log.append("--- Conversion done ---\n")
            except Exception as e:
                self.conv_log.append(f"FAILED to convert: {conv_dir} (Error: {e})\n")
                continue

            # 2. Run meta_reader.py
            meta_cmd = [sys.executable, "scripts/meta_reader.py", "-f", str(conv_dir)]
            self.conv_log.append(f"\n[meta_reader] Reading metadata for: {conv_dir}")
            try:
                meta_proc = subprocess.Popen(meta_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                for line in meta_proc.stdout:
                    self.conv_log.append(line.rstrip())
                    QApplication.processEvents()
                meta_retcode = meta_proc.wait()
                if meta_retcode != 0:
                    self.conv_log.append(f"FAILED to read metadata: {conv_dir}\n")
                else:
                    self.conv_log.append("--- Metadata read done ---\n")
            except Exception as e:
                self.conv_log.append(f"FAILED to read metadata: {conv_dir} (Error: {e})\n")
                continue
        self.conv_log.append("--- Batch Conversion Finished ---")

    def run_registration_script(self):
        # Gather inputs and start a background worker so the GUI doesn't block
        selected_dirs = []
        for i in range(self.reg_list_widget.count()):
            item = self.reg_list_widget.item(i)
            if item is not None:
                # Get full path from UserRole, fallback to text for compatibility
                full_path = item.data(Qt.ItemDataRole.UserRole)
                if full_path is None:
                    full_path = item.text()
                selected_dirs.append(full_path)
        if not selected_dirs:
            QMessageBox.warning(self, "No Directories", "Please add at least one directory to the list before running registration.")
            return

        params = {}
        for name, edit in zip(self.param_names, self.param_edits):
            value = edit.text().strip()
            if value:
                params[name] = value

        # Disable UI controls while running
        # Find the run button by text (safe because we created it nearby)
        run_btn = None
        for w in self.findChildren(QPushButton):
            if w.text().startswith("Run Registration"):
                run_btn = w
                break
        if run_btn:
            run_btn.setEnabled(False)

        self.reg_log.clear()

        # Create thread and worker
        self._reg_thread = QThread()
        self._reg_worker = RegistrationWorker(selected_dirs, params, self.combine_checkbox.isChecked())
        self._reg_worker.moveToThread(self._reg_thread)
        # Connect signals
        self._reg_thread.started.connect(self._reg_worker.run)
        self._reg_worker.log.connect(lambda s: (self.reg_log.append(s), QApplication.processEvents()))
        def _on_finished():
            if run_btn:
                run_btn.setEnabled(True)
            self._reg_thread.quit()
            self._reg_thread.wait()
            self._reg_worker.deleteLater()
            del self._reg_worker
            del self._reg_thread

        self._reg_worker.finished.connect(_on_finished)
        self._reg_worker.error.connect(lambda e: self.reg_log.append(f"ERROR: {e}"))
        self._reg_thread.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    qdarktheme.setup_theme()
    
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())