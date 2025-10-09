from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit, 
    QGroupBox, QListWidget, QAbstractItemView, QLineEdit, QGridLayout, QCheckBox
)
from PyQt6.QtCore import Qt


class RegistrationWidget(QWidget):
    """Encapsulated Registration tab widget.

    The widget accepts the main window instance so it can call its helper
    methods (e.g., add_dirs_dialog, run_registration_script) and expose a
    compatible API (sets attributes like reg_list_widget, reg_log, combine_checkbox
    on the main window for backward compatibility).
    """

    def __init__(self, main_window):
        super().__init__()
        self.window = main_window

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
        add_dir_btn.clicked.connect(lambda: self.window.add_dirs_dialog('registration'))
        remove_dir_btn = QPushButton("Remove Selected")
        remove_dir_btn.clicked.connect(lambda: self.window.remove_selected_dirs('registration'))
        reg_button_layout.addWidget(add_dir_btn)
        reg_button_layout.addWidget(remove_dir_btn)
        dir_layout.addWidget(self.reg_list_widget)
        dir_layout.addLayout(reg_button_layout)
        dir_group.setLayout(dir_layout)

        # Parameters group
        param_group = QGroupBox("Suite2p Parameters")
        param_layout = QGridLayout()
        self.param_edits = []

        # Example parameter names and default values
        self.param_names = [
            "n_channels", "functional_chan", "fs", "tau", "align_by_chan", "smooth_sigma",
            "smooth_sigma_time", "do_bidiphase", "bidi_corrected", "batch_size", "nimg_init",
            "two_step_registration", "1Preg", "roidetect", "sparse_mode", "spatial_scale"
        ]

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

        top_hbox.addWidget(dir_group)
        top_hbox.addWidget(param_group)
        layout.addLayout(top_hbox)

        # --- Run Registration Button ---
        mid_hbox = QHBoxLayout()
        run_btn = QPushButton("Run Registration on Selected Directories")
        run_btn.setStyleSheet("font-weight: bold;")
        checkbox_label = QLabel("[KEEP ON] Concatenate Suite2p Registered Recordings Per Channel:")
        checkbox_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.combine_checkbox = QCheckBox()
        self.combine_checkbox.setCheckState(Qt.CheckState.Checked)

        run_btn.clicked.connect(self.window.run_registration_script)

        mid_hbox.addWidget(run_btn)
        mid_hbox.addWidget(checkbox_label)
        mid_hbox.addWidget(self.combine_checkbox)
        layout.addLayout(mid_hbox)

        # --- Log box ---
        run_group = QGroupBox("Log")
        run_layout = QVBoxLayout()
        self.reg_log = QTextEdit()
        self.reg_log.setReadOnly(True)
        self.reg_log.setMinimumHeight(150)
        run_layout.addWidget(self.reg_log)
        run_group.setLayout(run_layout)
        layout.addWidget(run_group, 1)

        # Expose key widgets on the main window for compatibility with
        # existing MainWindow methods that expect them as attributes.
        try:
            self.window.reg_list_widget = self.reg_list_widget
            self.window.reg_log = self.reg_log
            self.window.combine_checkbox = self.combine_checkbox
            self.window.param_names = self.param_names
            self.window.param_edits = self.param_edits
        except Exception:
            pass

        self.setLayout(layout)