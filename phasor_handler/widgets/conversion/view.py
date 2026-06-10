from PyQt6.QtWidgets import (
	QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit, QGroupBox, QListWidget,
	QComboBox, QAbstractItemView
)


class ConversionWidget(QWidget):
	"""Encapsulated Conversion tab widget.

	The widget accepts the main window instance so it can call its helper
	methods (e.g., add_dirs_dialog, run_conversion_script) and expose a
	compatible API (sets attributes like conv_list_widget, conv_log, mode_combo
	on the main window for backward compatibility).
	"""

	def __init__(self, main_window):
		super().__init__()
		self.window = main_window

		layout = QVBoxLayout()

		# --- Directory List Management ---
		dir_group = QGroupBox("Select Directories for Batch Conversion")
		dir_layout = QVBoxLayout()

		# maintain selected_dirs on the main window for compatibility
		if not hasattr(self.window, 'selected_dirs'):
			self.window.selected_dirs = []

		self.conv_list_widget = QListWidget()
		self.conv_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
		# expose to main window like the previous implementation
		self.window.conv_list_widget = self.conv_list_widget

		dir_button_layout = QHBoxLayout()
		add_dir_btn = QPushButton("Add Directories...")
		add_dir_btn.clicked.connect(lambda: self.window.add_dirs_dialog('conversion'))
		remove_dir_btn = QPushButton("Remove Selected")
		remove_dir_btn.clicked.connect(lambda: self.window.remove_selected_dirs('conversion'))

		dir_button_layout.addWidget(add_dir_btn)
		dir_button_layout.addWidget(remove_dir_btn)

		dir_layout.addWidget(self.conv_list_widget)
		dir_layout.addLayout(dir_button_layout)
		dir_group.setLayout(dir_layout)
		layout.addWidget(dir_group)

		# --- Options ---
		options_group = QGroupBox("Set Conversion Options")
		mode_layout = QHBoxLayout()
		mode_label = QLabel("Mode:")
		self.mode_combo = QComboBox()
		self.mode_combo.addItems(["Interleaved", "Block"])  # default
		# expose to main window
		self.window.mode_combo = self.mode_combo

		mode_layout.addWidget(mode_label)
		mode_layout.addWidget(self.mode_combo)
		options_group.setLayout(mode_layout)
		layout.addWidget(options_group)

		# --- Run and Log ---
		run_group = QGroupBox("Run and Monitor")
		run_layout = QVBoxLayout()

		run_btn = QPushButton("Run Conversion on All Directories")
		run_btn.setProperty("class", "primary")
		run_btn.clicked.connect(self.window.run_conversion_script)

		convert_register_btn = QPushButton("Convert + Register All Directories")
		convert_register_btn.setProperty("class", "primary")
		convert_register_btn.setToolTip(
			"Run conversion followed by registration in one step.\n"
			"Uses registration parameters from the Registration tab.")
		convert_register_btn.clicked.connect(self.window.run_convert_and_register)

		self.conv_log = QTextEdit()
		self.conv_log.setReadOnly(True)
		self.conv_log.setMinimumHeight(150)
		# expose to main window
		self.window.conv_log = self.conv_log

		run_layout.addWidget(self.conv_log)
		btn_row = QHBoxLayout()
		btn_row.addWidget(run_btn)
		btn_row.addWidget(convert_register_btn)
		run_layout.addLayout(btn_row)
		run_group.setLayout(run_layout)
		layout.addWidget(run_group, 1)

		self.setLayout(layout)
		
