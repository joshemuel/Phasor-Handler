"""
Dark theme stylesheet for Phasor Handler application.
Provides consistent dark appearance across all devices and platforms.
"""


def get_dark_stylesheet():
    """Return the dark theme stylesheet for the application."""
    return """
    QMainWindow {
        background-color: #2b2b2b;
        color: #ffffff;
    }
    
    QWidget {
        background-color: #2b2b2b;
        color: #ffffff;
        selection-background-color: #3daee9;
    }
    
    QTabWidget::pane {
        border: 1px solid #555555;
        background-color: #2b2b2b;
    }
    
    QTabBar::tab {
        background-color: #3c3c3c;
        color: #ffffff;
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    
    QTabBar::tab:selected {
        background-color: #2b2b2b;
        border-bottom: 2px solid #3daee9;
    }
    
    QTabBar::tab:hover {
        background-color: #404040;
    }
    
    QPushButton {
        background-color: #3c3c3c;
        color: #ffffff;
        border: 1px solid #555555;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: normal;
        min-height: 16px;
        text-align: center;
    }
    
    /* Specific styling for small buttons to prevent text cropping */
    QPushButton[text*="Reset"], QPushButton[text*="Auto"], QPushButton[text*="Frames"] {
        padding: 2px 6px;
        min-width: 50px;
        min-height: 20px;
    }
    
    QPushButton:hover {
        background-color: #404040;
        border-color: #3daee9;
    }
    
    QPushButton:pressed {
        background-color: #2a2a2a;
    }
    
    QPushButton:checked {
        background-color: #4caf50;
        border-color: #66bb6a;
        color: #ffffff;
    }
    
    QPushButton:checked:hover {
        background-color: #66bb6a;
        border-color: #81c784;
    }
    
    QPushButton:checked:pressed {
        background-color: #388e3c;
        border-color: #4caf50;
    }
    
    QPushButton:disabled {
        background-color: #2a2a2a;
        color: #666666;
        border-color: #444444;
    }
    
    QGroupBox {
        font-weight: bold;
        border: 2px solid #555555;
        border-radius: 6px;
        margin-top: 1ex;
        padding-top: 8px;
        background-color: #2b2b2b;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
        color: #ffffff;
    }
    
    QListWidget {
        background-color: #3c3c3c;
        border: 1px solid #555555;
        border-radius: 4px;
        alternate-background-color: #404040;
    }
    
    QListWidget::item {
        padding: 4px;
        border-bottom: 1px solid #555555;
    }
    
    QListWidget::item:selected {
        background-color: #3daee9;
        color: #ffffff;
    }
    
    QListWidget::item:hover {
        background-color: #404040;
    }
    
    QTextEdit {
        background-color: #3c3c3c;
        color: #ffffff;
        border: 1px solid #555555;
        border-radius: 4px;
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    }
    
    QComboBox {
        background-color: #3c3c3c;
        color: #ffffff;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 4px 8px;
        min-width: 6em;
    }
    
    QComboBox:hover {
        border-color: #3daee9;
    }
    
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left-width: 1px;
        border-left-color: #555555;
        border-left-style: solid;
        border-top-right-radius: 3px;
        border-bottom-right-radius: 3px;
        background-color: #404040;
    }
    
    /* Use embedded SVG data-URIs for arrows so they render reliably across platforms */
    QComboBox::down-arrow {
    /* chevron-down placeholder (will be replaced at runtime) */
    image: url("/*BASE_CHEVRON_DOWN*/");
        width: 14px;
        height: 14px;
    }
    
    QComboBox QAbstractItemView {
        background-color: #3c3c3c;
        color: #ffffff;
        selection-background-color: #3daee9;
        border: 1px solid #555555;
    }
    
    QLabel {
        color: #ffffff;
        background-color: transparent;
    }
    
    QCheckBox {
        color: #ffffff;
        background-color: transparent;
    }
    
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border: 1px solid #555555;
        border-radius: 2px;
        background-color: #3c3c3c;
    }
    
    QCheckBox::indicator:checked {
        background-color: #3daee9;
        border-color: #3daee9;
    }
    
    QCheckBox::indicator:hover {
        border-color: #3daee9;
    }
    
    QSlider::groove:horizontal {
        border: 1px solid #555555;
        height: 6px;
        background-color: #3c3c3c;
        border-radius: 3px;
    }
    
    QSlider::handle:horizontal {
        background-color: #3daee9;
        border: 1px solid #3daee9;
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 8px;
    }
    
    QSlider::handle:horizontal:hover {
        background-color: #4fc3f7;
        border-color: #4fc3f7;
    }
    
    QDoubleSpinBox {
        background-color: #3c3c3c;
        color: #ffffff;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 2px 4px;
    }
    
    QDoubleSpinBox:hover {
        border-color: #3daee9;
    }
    
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
        background-color: #404040;
        border: 1px solid #555555;
        width: 18px;
        height: 12px;
    }
    
    QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
        background-color: #4a4a4a;
        border-color: #3daee9;
    }
    
    QDoubleSpinBox::up-arrow {
    /* chevron-up placeholder (will be replaced at runtime) */
    image: url("/*BASE_CHEVRON_UP*/");
        width: 12px;
        height: 12px;
    }

    QDoubleSpinBox::down-arrow {
    /* chevron-down placeholder (will be replaced at runtime) */
    image: url("/*BASE_CHEVRON_DOWN*/");
        width: 12px;
        height: 12px;
    }
    
    QSpinBox {
        background-color: #3c3c3c;
        color: #ffffff;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 2px 4px;
    }
    
    QSpinBox:hover {
        border-color: #3daee9;
    }
    
    QSpinBox::up-button, QSpinBox::down-button {
        background-color: #404040;
        border: 1px solid #555555;
        width: 18px;
        height: 12px;
    }
    
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {
        background-color: #4a4a4a;
        border-color: #3daee9;
    }
    
    QSpinBox::up-arrow {
    /* chevron-up placeholder (will be replaced at runtime) */
    image: url("/*BASE_CHEVRON_UP*/");
        width: 12px;
        height: 12px;
    }

    QSpinBox::down-arrow {
    /* chevron-down placeholder (will be replaced at runtime) */
    image: url("/*BASE_CHEVRON_DOWN*/");
        width: 12px;
        height: 12px;
    }
    
    QScrollBar:vertical {
        background-color: #2b2b2b;
        width: 12px;
        border-radius: 6px;
    }
    
    QScrollBar::handle:vertical {
        background-color: #555555;
        border-radius: 6px;
        min-height: 20px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #666666;
    }
    
    QScrollBar:horizontal {
        background-color: #2b2b2b;
        height: 12px;
        border-radius: 6px;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #555555;
        border-radius: 6px;
        min-width: 20px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background-color: #666666;
    }
    
    QScrollBar::add-line, QScrollBar::sub-line {
        background: none;
        border: none;
    }
    
    QMessageBox {
        background-color: #2b2b2b;
        color: #ffffff;
    }
    
    QFileDialog {
        background-color: #2b2b2b;
        color: #ffffff;
    }

    /* Grey out the Brightness and Contrast group when a Z-projection is active */
    QGroupBox#bnc_group[ zprojActive="true" ] {
        background-color: #262626;
        color: #999999;
        border: 1px solid #444444;
    }

    QGroupBox#bnc_group[ zprojActive="true" ] QLabel,
    QGroupBox#bnc_group[ zprojActive="true" ] QPushButton,
    QGroupBox#bnc_group[ zprojActive="true" ] QDoubleSpinBox {
        color: #7f7f7f;
    }
    """


def apply_dark_theme(app):
    """Apply the dark theme to the given QApplication instance."""
    # Some platforms/encodings can mangle utf8-embedded SVGs in QSS strings.
    # Instead, use local SVG files and insert file:// URIs into the stylesheet at runtime.
    import os
    stylesheet = get_dark_stylesheet()
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    icon_dir = os.path.join(base, 'img', 'icons')
    down_icon = os.path.join(icon_dir, 'chevron-down.svg')
    up_icon = os.path.join(icon_dir, 'chevron-up.svg')
    # Normalize for file URI
    def to_file_uri(path):
        p = os.path.abspath(path).replace('\\', '/')
        return 'file:///' + p

    stylesheet = stylesheet.replace('/*BASE_CHEVRON_DOWN*/', to_file_uri(down_icon))
    stylesheet = stylesheet.replace('/*BASE_CHEVRON_UP*/', to_file_uri(up_icon))
    app.setStyleSheet(stylesheet)