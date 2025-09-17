import sys
import os
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFileDialog, QGroupBox, QListWidget,
    QComboBox, QMessageBox, QListView, QTreeView, QAbstractItemView,
    QTabWidget, QGridLayout, QLineEdit
)
from PyQt6.QtGui import QFileSystemModel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phasor Handler v1.0")
        # Set a reasonable minimum size and default size
        self.setMinimumSize(800, 600)
        self.resize(1200, 800)
        self.selected_dirs = []

        tabs = QTabWidget()
        tabs.addTab(self.create_conversion_tab(), "Conversion")
        tabs.addTab(self.create_registration_tab(), "Registration")
        tabs.addTab(self.create_analysis_tab(), "Analysis")

        self.setCentralWidget(tabs)


    def create_conversion_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        # --- Directory List Management ---
        dir_group = QGroupBox("Select Directories for Batch Conversion")
        dir_layout = QVBoxLayout()

        self.selected_dirs = []
        self.conv_list_widget = QListWidget()
        self.conv_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        dir_button_layout = QHBoxLayout()
        add_dir_btn = QPushButton("Add Directories...")
        add_dir_btn.clicked.connect(lambda: self.add_dirs_dialog('conversion'))
        remove_dir_btn = QPushButton("Remove Selected")
        remove_dir_btn.clicked.connect(lambda: self.remove_selected_dirs('conversion'))

        dir_button_layout.addWidget(add_dir_btn)
        dir_button_layout.addWidget(remove_dir_btn)

        dir_layout.addWidget(self.conv_list_widget)
        dir_layout.addLayout(dir_button_layout)
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)

        # --- Options ---
        options_group = QGroupBox("2. Set Conversion Options")
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Interleaved", "Block"]) # Interleaved first as it's the default
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_combo)
        options_group.setLayout(mode_layout)
        layout.addWidget(options_group)

        # --- Run and Log ---
        run_group = QGroupBox("3. Run and Monitor")
        run_layout = QVBoxLayout()
        
        run_btn = QPushButton("Run Conversion on All Directories")
        run_btn.setStyleSheet("font-weight: bold;")
        run_btn.clicked.connect(self.run_conversion_script)
        
        self.conv_log = QTextEdit()
        self.conv_log.setReadOnly(True)
        self.conv_log.setMinimumHeight(150)
        
        run_layout.addWidget(self.conv_log)
        run_layout.addWidget(run_btn)
        run_group.setLayout(run_layout)
        layout.addWidget(run_group, 1) # Give this group stretching priority

        widget.setLayout(layout)
        return widget


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
            for path_str in selected_paths:
                if path_str not in self.selected_dirs:
                    self.selected_dirs.append(path_str)
            self.refresh_dir_lists()
        dialog.deleteLater()

    def remove_selected_dirs(self, tab):
        widget = self.conv_list_widget if tab == 'conversion' else self.reg_list_widget
        selected_items = widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            row = widget.row(item)
            widget.takeItem(row)
            path_to_remove = item.text()
            if path_to_remove in self.selected_dirs:
                self.selected_dirs.remove(path_to_remove)
        self.refresh_dir_lists()

    def refresh_dir_lists(self):
        self.conv_list_widget.clear()
        self.reg_list_widget.clear()
        for d in self.selected_dirs:
            self.conv_list_widget.addItem(d)
            self.reg_list_widget.addItem(d)

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

    def create_registration_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        # --- Top HBox: Directories and Parameters ---
        top_hbox = QHBoxLayout()

        # Directories group
        dir_group = QGroupBox("Select Directories")
        dir_layout = QVBoxLayout()
        self.reg_list_widget = QListWidget()
        self.reg_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        reg_button_layout = QHBoxLayout()
        add_dir_btn = QPushButton("Add Directories...")
        add_dir_btn.clicked.connect(lambda: self.add_dirs_dialog('registration'))
        remove_dir_btn = QPushButton("Remove Selected")
        remove_dir_btn.clicked.connect(lambda: self.remove_selected_dirs('registration'))
        reg_button_layout.addWidget(add_dir_btn)
        reg_button_layout.addWidget(remove_dir_btn)
        dir_layout.addWidget(self.reg_list_widget)
        dir_layout.addLayout(reg_button_layout)
        dir_group.setLayout(dir_layout)


        # Parameters group
        param_group = QGroupBox("Suite2p Parameters")
        # Parameters group
        param_layout = QGridLayout()
        self.param_edits = []

        # Example parameter names and default values (replace with your actual list)
        self.param_names = ["n_channels", "functional_chan", "fs", "tau", "align_by_chan", "smooth_sigma", "smooth_sigma_time", "do_bidiphase",
                            "bidi_corrected", "batch_size", "nimg_init", "two_step_registration", "1Preg", "roidetect", "sparse_mode", "spatial_scale"]

        self.default_values = ["2", "1", "10", "0.7", "2", "1.15", "1", "1", "1", "500", "300", "1", "0", "0", "1", "0"]

        for i in range(16):
            row, col = divmod(i, 4)
            name = self.param_names[i] if i < len(self.param_names) else ""
            value = self.default_values[i] if i < len(self.default_values) else ""
            label = QLabel(name)
            edit = QLineEdit()
            edit.setText(value)
            self.param_edits.append(edit)
            param_layout.addWidget(label, row, col*2)
            param_layout.addWidget(edit, row, col*2+1)
        param_group.setLayout(param_layout)

        # Layout: directories and parameters side by side
        top_hbox.addWidget(dir_group)
        top_hbox.addWidget(param_group)
        layout.addLayout(top_hbox)

        # --- Run Registration Button ---
        run_btn = QPushButton("Run Registration on Selected Directories")
        run_btn.setStyleSheet("font-weight: bold;")
        run_btn.clicked.connect(self.run_registration_script)
        layout.addWidget(run_btn)


        # --- Log box ---
        run_group = QGroupBox("Log")
        run_layout = QVBoxLayout()
        self.reg_log = QTextEdit()
        self.reg_log.setReadOnly(True)
        self.reg_log.setMinimumHeight(150)
        run_layout.addWidget(self.reg_log)
        run_group.setLayout(run_layout)
        layout.addWidget(run_group, 1)
        widget.setLayout(layout)
        return widget

    def run_registration_script(self):
        # Get selected directories
        selected_dirs = [self.reg_list_widget.item(i).text() for i in range(self.reg_list_widget.count())]
        if not selected_dirs:
            QMessageBox.warning(self, "No Directories", "Please add at least one directory to the list before running registration.")
            return
        # Get parameter values
        params = {}
        for name, edit in zip(self.param_names, self.param_edits):
            value = edit.text().strip()
            if value:
                params[name] = value
        # Run registration for each directory
        self.reg_log.clear()
        for i, reg_dir in enumerate(selected_dirs):
            self.reg_log.append(f"[{i+1}/{len(selected_dirs)}] Registering: {reg_dir}")
            QApplication.processEvents()
            # Find the first .tif file in the directory
            tif_files = [f for f in os.listdir(reg_dir) if f.lower().endswith('.tif')]
            if not tif_files:
                self.reg_log.append(f"  No .tif file found in {reg_dir}\n")
                continue
            movie_path = os.path.join(reg_dir, tif_files[0])
            outdir = os.path.join(reg_dir, "suite2p_reg")
            # Build command
            cmd = [sys.executable, "scripts/register.py", "--movie", movie_path, "--outdir", outdir]
            for k, v in params.items():
                cmd.extend(["--param", f"{k}={v}"])
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=os.path.dirname(__file__))
                for line in proc.stdout:
                    self.reg_log.append(line.rstrip())
                    QApplication.processEvents()
                retcode = proc.wait()
                if retcode != 0:
                    self.reg_log.append(f"  FAILED: {reg_dir}\n")
                else:
                    self.reg_log.append(f"  Registration done: {reg_dir}\n")
            except Exception as e:
                self.reg_log.append(f"  FAILED: {reg_dir} (Error: {e})\n")
                continue
        self.reg_log.append("--- Batch Registration Finished ---")

    def create_analysis_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Analysis tools go here."))
        widget.setLayout(layout)
        return widget

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
