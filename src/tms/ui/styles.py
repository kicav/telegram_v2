APP_STYLESHEET = r"""
QMainWindow, QWidget {
    background: #f5f6f8;
    color: #202124;
    font-size: 13px;
}
QListWidget#navigation {
    background: #ffffff;
    border: none;
    border-right: 1px solid #e2e5e9;
    padding: 10px 6px;
    font-size: 14px;
}
QListWidget#navigation::item {
    padding: 11px 12px;
    margin: 2px 0;
    border-radius: 7px;
}
QListWidget#navigation::item:selected {
    background: #e8f0fe;
    color: #174ea6;
    font-weight: 600;
}
QLabel#pageTitle {
    font-size: 22px;
    font-weight: 700;
    padding-bottom: 6px;
}
QLabel#sectionTitle {
    font-size: 15px;
    font-weight: 650;
}
QFrame#card, QGroupBox {
    background: #ffffff;
    border: 1px solid #e0e3e7;
    border-radius: 9px;
}
QGroupBox {
    margin-top: 10px;
    padding-top: 12px;
    font-weight: 600;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #cfd4da;
    border-radius: 6px;
    padding: 7px 12px;
    min-height: 20px;
}
QPushButton:hover { background: #f1f3f4; }
QPushButton#primaryButton {
    background: #1a73e8;
    border-color: #1a73e8;
    color: white;
    font-weight: 600;
}
QPushButton#dangerButton {
    background: #d93025;
    border-color: #d93025;
    color: white;
    font-weight: 600;
}
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #cfd4da;
    border-radius: 5px;
    padding: 6px;
    min-height: 20px;
}
QTableView {
    background: #ffffff;
    border: 1px solid #e0e3e7;
    gridline-color: #eceff1;
    selection-background-color: #e8f0fe;
    selection-color: #202124;
}
QHeaderView::section {
    background: #f8f9fa;
    border: none;
    border-bottom: 1px solid #e0e3e7;
    padding: 7px;
    font-weight: 600;
}
QProgressBar {
    border: 1px solid #d5d9dd;
    border-radius: 5px;
    background: #ffffff;
    text-align: center;
    min-height: 18px;
}
QProgressBar::chunk { background: #1a73e8; border-radius: 4px; }
QStatusBar { background: #ffffff; border-top: 1px solid #e0e3e7; }
QTabWidget::pane { border: 1px solid #e0e3e7; background: #ffffff; }
QTabBar::tab { padding: 8px 14px; background: #f1f3f4; }
QTabBar::tab:selected { background: #ffffff; font-weight: 600; }
"""
