"""
Metadata Information Viewer Component

This module contains the MetadataViewer dialog that displays experiment metadata
in a formatted, user-friendly way.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QScrollArea, QWidget, QFrame, QGridLayout, QTabWidget, QSplitter,
    QGroupBox, QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QTextOption
import json
import datetime


class MetadataViewer(QDialog):
    """
    Dialog window that displays experiment metadata in a user-friendly format.
    
    Handles both dictionary and object-based metadata formats and provides
    multiple views (Overview, Raw JSON, Tree View) for comprehensive data inspection.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Experiment Metadata Viewer")
        self.setModal(False)  # Allow interaction with main window while open
        self.resize(400, 500)
        
        self.metadata = None
        self.directory_path = None
        
        self.setupUI()
        
    def setupUI(self):
        """Set up the user interface."""
        layout = QVBoxLayout()
        
        # Header with directory path
        self.header_label = QLabel("No experiment data loaded")
        self.header_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                background-color: #2a7d4e;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.header_label)
        
        # Create tab widget for different views
        self.tab_widget = QTabWidget()
        
        # Overview tab
        self.overview_tab = self.create_overview_tab()
        self.tab_widget.addTab(self.overview_tab, "Overview")
        
        # Detailed tree view tab
        self.tree_tab = self.create_tree_tab()
        self.tab_widget.addTab(self.tree_tab, "Tree View")
        
        # Raw JSON tab
        self.raw_tab = self.create_raw_tab()
        self.tab_widget.addTab(self.raw_tab, "Raw JSON")
        
        layout.addWidget(self.tab_widget)
        
        # Button bar
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_metadata)
        button_layout.addWidget(self.refresh_button)
        
        button_layout.addStretch()
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def create_overview_tab(self):
        """Create the overview tab with key experiment information."""
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        layout = QVBoxLayout()
        
        # Experiment Summary Group
        self.exp_summary_group = QGroupBox("Experiment Summary")
        self.exp_summary_layout = QGridLayout()
        self.exp_summary_group.setLayout(self.exp_summary_layout)
        layout.addWidget(self.exp_summary_group)
        
        # Timing Information Group
        self.timing_group = QGroupBox("Timing Information")
        self.timing_layout = QGridLayout()
        self.timing_group.setLayout(self.timing_layout)
        layout.addWidget(self.timing_group)
        
        # Stimulation Information Group
        self.stim_group = QGroupBox("Stimulation Information")
        self.stim_layout = QGridLayout()
        self.stim_group.setLayout(self.stim_layout)
        layout.addWidget(self.stim_group)
        
        # Image Information Group
        self.image_group = QGroupBox("Image Information")
        self.image_layout = QGridLayout()
        self.image_group.setLayout(self.image_layout)
        layout.addWidget(self.image_group)
        
        layout.addStretch()
        scroll_widget.setLayout(layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        
        return scroll_area
        
    def create_tree_tab(self):
        """Create the tree view tab for hierarchical data exploration."""
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Key", "Value", "Type"])
        
        # Set column widths
        header = self.tree_widget.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        return self.tree_widget
        
    def create_raw_tab(self):
        """Create the raw JSON tab for viewing unformatted data."""
        self.raw_text_edit = QTextEdit()
        self.raw_text_edit.setReadOnly(True)
        
        # Set monospace font for better readability
        font = QFont("Consolas", 10)
        if not font.exactMatch():
            font = QFont("Courier New", 10)
        self.raw_text_edit.setFont(font)
        
        return self.raw_text_edit
        
    def set_metadata(self, metadata, directory_path=None):
        """
        Set the metadata to display.
        
        Args:
            metadata: The experiment metadata (dict or object)
            directory_path: Path to the experiment directory
        """
        self.metadata = metadata
        self.directory_path = directory_path
        
        if directory_path:
            self.header_label.setText(f"Experiment Metadata: {directory_path}")
        else:
            self.header_label.setText("Experiment Metadata")
            
        self.update_display()
        
    def update_display(self):
        """Update all tabs with current metadata."""
        if self.metadata is None:
            self.clear_display()
            return
            
        self.update_overview_tab()
        self.update_tree_tab()
        self.update_raw_tab()
        
    def clear_display(self):
        """Clear all displayed content."""
        # Clear overview tab
        self.clear_group_layout(self.exp_summary_layout)
        self.clear_group_layout(self.timing_layout)
        self.clear_group_layout(self.stim_layout)
        self.clear_group_layout(self.image_layout)
        
        # Clear tree tab
        self.tree_widget.clear()
        
        # Clear raw tab
        self.raw_text_edit.clear()
        
        self.header_label.setText("No experiment data loaded")
        
    def clear_group_layout(self, layout):
        """Clear all widgets from a group layout."""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
    def update_overview_tab(self):
        """Update the overview tab with key information."""
        # Clear existing content
        self.clear_group_layout(self.exp_summary_layout)
        self.clear_group_layout(self.timing_layout)
        self.clear_group_layout(self.stim_layout)
        self.clear_group_layout(self.image_layout)
        
        if isinstance(self.metadata, dict):
            self.update_overview_from_dict()
        else:
            self.update_overview_from_object()
            
    def update_overview_from_dict(self):
        """Update overview from dictionary metadata."""
        # Experiment Summary
        row = 0
        for key in ['device_name', 'n_frames']:
            if key in self.metadata:
                value = self.metadata[key]
                if key == "device_name": key = "Device Name"
                elif key == "n_frames": key = "Number of Frames"

                self.add_info_row(self.exp_summary_layout, row, key.replace('_', ' '), 
                                str(value), self.format_value_with_unit(key, value))
                row += 1
        
        # Timing Information
        row = 0
        time_keys = ['time_stamps', 'elapsed_times', 'acquisition_start_time']
        for key in time_keys:
            if key in self.metadata:
                value = self.metadata[key]
                if isinstance(value, list) and len(value) > 0:
                    interval = (sum([value[i+1] - value[i] for i in range(len(value)-1)])/(len(value)-1))/1000
                    start_display = "0" if value[0] == 0 else f"{value[0]/1000:.3f}"
                    display_value = f"From {start_display} to {value[-1]/1000:.3f} seconds with an average interval of {interval:.3f} seconds"
                else:
                    display_value = str(value)
                self.add_info_row(self.timing_layout, row, key.replace('_', ' ').title(), 
                                display_value)
                row += 1
        
        # Stimulation Information
        row = 0
        stim_keys = ['stimulation_timeframes', 'stimulation_ms', 'duty_cycle', 'stimulated_roi_location', 'stimulated_rois']
        for key in stim_keys:
            if key in self.metadata:
                value = self.metadata[key]
                if isinstance(value, list):
                    if key == 'stimulation_timeframes':
                        display_value = ', '.join(map(str, value))
                        key = "Stimulation Timeframes"
                    elif key == 'stimulation_ms':
                        display_value = ', '.join(map(str, [int(v/1000) for v in value]))
                        key = "Stimulation Time (s)"
                    elif key == 'duty_cycle':
                        duty_cycle_counts = {val: value.count(val) for val in set(value)}
                        display_value = ' | '.join([f'{val}: {count}X' for val, count in duty_cycle_counts.items()])
                        key = "Duty Cycle"
                    elif key == 'stimulated_roi_location':
                        display_value = ', '.join(map(str, [len(x) for x in value]))
                        key = "Number of stimulated ROIs"
                    elif key == 'stimulated_rois':
                        if not value or all(not sublist for sublist in value):
                            display_value = "NA"
                        else:
                            display_value = ', '.join([', '.join(map(str, x)) for x in value])
                        key = "Stimulated ROIs"
                else:
                    display_value = str(value)
                self.add_info_row(self.stim_layout, row, key.replace('_', ' '), 
                                display_value)
                row += 1
        
        # Image Information
        row = 0
        image_keys = ['pixel_size', 'FOV_size']
        for key in image_keys:
            if key in self.metadata:
                value = self.metadata[key]
                if key == "pixel_size": key = "Pixel Size (µm)"
                elif key == "FOV_size": 
                    key = "FOV Size (µm)"
                    value = value[:-7]
                self.add_info_row(self.image_layout, row, key.replace('_', ' '), 
                                str(value))
                row += 1
                
    def update_overview_from_object(self):
        """Update overview from object metadata."""
        # Get all non-private attributes
        attrs = [attr for attr in dir(self.metadata) if not attr.startswith('_')]
        
        # Categorize attributes
        exp_attrs = []
        time_attrs = []
        stim_attrs = []
        image_attrs = []
        
        for attr in attrs:
            if any(keyword in attr.lower() for keyword in ['frame', 'duration', 'rate']):
                exp_attrs.append(attr)
            elif any(keyword in attr.lower() for keyword in ['time', 'elapsed']):
                time_attrs.append(attr)
            elif any(keyword in attr.lower() for keyword in ['stim', 'duty']):
                stim_attrs.append(attr)
            elif any(keyword in attr.lower() for keyword in ['image', 'width', 'height', 'channel', 'bit']):
                image_attrs.append(attr)
            else:
                exp_attrs.append(attr)  # Default to experiment summary
        
        # Populate each section
        self.populate_section_from_attrs(self.exp_summary_layout, exp_attrs)
        self.populate_section_from_attrs(self.timing_layout, time_attrs)
        self.populate_section_from_attrs(self.stim_layout, stim_attrs)
        self.populate_section_from_attrs(self.image_layout, image_attrs)
        
    def populate_section_from_attrs(self, layout, attrs):
        """Populate a section with attributes from the metadata object."""
        for row, attr in enumerate(attrs):
            try:
                value = getattr(self.metadata, attr)
                if isinstance(value, list) and len(value) > 0:
                    display_value = f"Array with {len(value)} entries"
                    if len(value) <= 10:
                        display_value += f": {value}"
                    else:
                        display_value += f" (first few: {value[:3]}...)"
                else:
                    display_value = str(value)
                self.add_info_row(layout, row, attr.replace('_', ' ').title(), display_value)
            except Exception as e:
                self.add_info_row(layout, row, attr.replace('_', ' ').title(), f"Error: {e}")
                
    def add_info_row(self, layout, row, label, value, tooltip=None):
        """Add an information row to a layout."""
        label_widget = QLabel(f"{label}:")
        label_widget.setStyleSheet("font-weight: bold;")
        
        value_widget = QLabel(str(value))
        value_widget.setWordWrap(True)
        value_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        if tooltip:
            value_widget.setToolTip(tooltip)
            
        layout.addWidget(label_widget, row, 0)
        layout.addWidget(value_widget, row, 1)
        
    def format_value_with_unit(self, key, value):
        """Format values with appropriate units for tooltips."""
        if 'ms' in key.lower():
            return f"{value} milliseconds"
        elif 'um' in key.lower():
            return f"{value} micrometers"
        elif 'rate' in key.lower():
            return f"{value} Hz"
        else:
            return str(value)
            
    def update_tree_tab(self):
        """Update the tree view tab."""
        self.tree_widget.clear()
        
        if self.metadata is None:
            return
            
        if isinstance(self.metadata, dict):
            self.add_dict_to_tree(self.metadata, self.tree_widget.invisibleRootItem())
        else:
            self.add_object_to_tree(self.metadata, self.tree_widget.invisibleRootItem())
            
        # Expand first level
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            if item.childCount() < 20:  # Don't auto-expand large sections
                item.setExpanded(True)
                
    def add_dict_to_tree(self, data, parent_item, max_depth=5, current_depth=0):
        """Recursively add dictionary data to tree widget."""
        if current_depth >= max_depth:
            return
            
        for key, value in data.items():
            self.add_value_to_tree(key, value, parent_item, current_depth)
            
    def add_object_to_tree(self, obj, parent_item, max_depth=5, current_depth=0):
        """Add object attributes to tree widget."""
        if current_depth >= max_depth:
            return
            
        attrs = [attr for attr in dir(obj) if not attr.startswith('_')]
        for attr in attrs:
            try:
                value = getattr(obj, attr)
                if not callable(value):  # Skip methods
                    self.add_value_to_tree(attr, value, parent_item, current_depth)
            except Exception:
                pass  # Skip attributes that can't be accessed
                
    def add_value_to_tree(self, key, value, parent_item, current_depth):
        """Add a key-value pair to the tree."""
        item = QTreeWidgetItem(parent_item)
        item.setText(0, str(key))
        
        value_type = type(value).__name__
        item.setText(2, value_type)
        
        if isinstance(value, (dict, list, tuple)) and len(value) > 0:
            if isinstance(value, dict):
                item.setText(1, f"Dictionary with {len(value)} items")
                if current_depth < 4:  # Prevent infinite recursion
                    self.add_dict_to_tree(value, item, current_depth=current_depth+1)
            elif isinstance(value, (list, tuple)):
                if len(value) <= 5:
                    item.setText(1, str(value))
                else:
                    item.setText(1, f"{value_type} with {len(value)} items: {value[:3]}...")
                    # Add first few items for lists
                    if current_depth < 3:
                        for i, list_val in enumerate(value[:10]):  # Limit to first 10 items
                            self.add_value_to_tree(f"[{i}]", list_val, item, current_depth+1)
        else:
            # Truncate very long strings
            str_value = str(value)
            if len(str_value) > 200:
                str_value = str_value[:200] + "..."
            item.setText(1, str_value)
            
    def update_raw_tab(self):
        """Update the raw JSON tab."""
        if self.metadata is None:
            self.raw_text_edit.clear()
            return
            
        try:
            if isinstance(self.metadata, dict):
                json_text = json.dumps(self.metadata, indent=2, default=str)
            else:
                # Convert object to dict for JSON serialization
                obj_dict = {}
                attrs = [attr for attr in dir(self.metadata) if not attr.startswith('_')]
                for attr in attrs:
                    try:
                        value = getattr(self.metadata, attr)
                        if not callable(value):
                            obj_dict[attr] = value
                    except Exception:
                        obj_dict[attr] = f"<Error accessing {attr}>"
                        
                json_text = json.dumps(obj_dict, indent=2, default=str)
                
            self.raw_text_edit.setPlainText(json_text)
        except Exception as e:
            self.raw_text_edit.setPlainText(f"Error displaying metadata: {e}")
            
    def refresh_metadata(self):
        """Refresh the metadata display."""
        self.update_display()
        
    def sizeHint(self):
        """Provide size hint for the dialog."""
        return QSize(900, 700)