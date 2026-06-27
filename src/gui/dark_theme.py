"""Dark theme for the dyrobot GUI — Catppuccin Mocha-inspired palette."""

from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

# ── Color Palette ──────────────────────────────────────────────
BASE      = "#1e1e2e"   # window background
SURFACE   = "#313244"   # card / group-box background
OVERLAY   = "#45475a"   # hover / selection overlay
TEXT      = "#cdd6f4"   # primary text
SUBTEXT   = "#a6adc8"   # secondary text
BORDER    = "#585b70"   # border color
ACCENT    = "#89b4fa"   # blue accent
GREEN     = "#a6e3a1"   # success / running
YELLOW    = "#f9e2af"   # warning / starting
RED       = "#f38ba8"   # error / stopped
DISABLED  = "#6c7086"   # disabled text


def get_dark_palette() -> QPalette:
    """Build and return a dark QPalette for the entire application."""
    p = QPalette()

    p.setColor(QPalette.ColorRole.Window,          QColor(BASE))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT))
    p.setColor(QPalette.ColorRole.Base,            QColor("#181825"))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(SURFACE))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(SURFACE))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(TEXT))
    p.setColor(QPalette.ColorRole.Text,            QColor(TEXT))
    p.setColor(QPalette.ColorRole.Button,          QColor(SURFACE))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT))
    p.setColor(QPalette.ColorRole.BrightText,      QColor(TEXT))
    p.setColor(QPalette.ColorRole.Link,            QColor(ACCENT))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(BASE))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(SUBTEXT))

    # Disabled colors
    p.setColor(QPalette.ColorGroup.Disabled,
               QPalette.ColorRole.WindowText, QColor(DISABLED))
    p.setColor(QPalette.ColorGroup.Disabled,
               QPalette.ColorRole.Text,       QColor(DISABLED))
    p.setColor(QPalette.ColorGroup.Disabled,
               QPalette.ColorRole.ButtonText, QColor(DISABLED))

    return p


# ── Global Stylesheet ──────────────────────────────────────────
DARK_STYLESHEET = f"""
/* ── Global ── */
QMainWindow {{
    background-color: {BASE};
}}
QWidget {{
    font-family: "Microsoft YaHei", "Segoe UI", "Noto Sans SC", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}

/* ── Sidebar ── */
QPushButton[cssClass="nav-btn"] {{
    text-align: left;
    padding: 10px 16px;
    border: none;
    border-radius: 6px;
    margin: 2px 8px;
    font-size: 13px;
    color: {SUBTEXT};
    background: transparent;
}}
QPushButton[cssClass="nav-btn"]:hover {{
    background: {SURFACE};
    color: {TEXT};
}}
QPushButton[cssClass="nav-btn"]:checked {{
    background: {OVERLAY};
    color: {ACCENT};
    font-weight: bold;
}}

/* ── General Buttons ── */
QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 20px;
    color: {TEXT};
}}
QPushButton:hover {{
    background: {OVERLAY};
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background: {ACCENT};
    color: {BASE};
}}
QPushButton:disabled {{
    background: {BASE};
    color: {DISABLED};
    border-color: {BORDER};
}}

/* ── Primary action button ── */
QPushButton[cssClass="primary"] {{
    background: {ACCENT};
    color: {BASE};
    border: none;
    font-weight: bold;
}}
QPushButton[cssClass="primary"]:hover {{
    background: #74c7ec;
}}
QPushButton[cssClass="primary"]:pressed {{
    background: #b4befe;
}}

/* ── Danger button ── */
QPushButton[cssClass="danger"] {{
    background: {RED};
    color: {BASE};
    border: none;
    font-weight: bold;
}}
QPushButton[cssClass="danger"]:hover {{
    background: #eba0ac;
}}

/* ── Success button ── */
QPushButton[cssClass="success"] {{
    background: {GREEN};
    color: {BASE};
    border: none;
    font-weight: bold;
}}
QPushButton[cssClass="success"]:hover {{
    background: #94e2d5;
}}

/* ── Input Fields ── */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background: #181825;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: {BASE};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}

/* ── Combo Box ── */
QComboBox {{
    background: #181825;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT};
}}
QComboBox:hover {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    selection-background-color: {OVERLAY};
    color: {TEXT};
}}

/* ── Group Box ── */
QGroupBox {{
    font-weight: bold;
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {ACCENT};
}}

/* ── List / Tree / Table ── */
QListWidget, QTableWidget, QTreeWidget {{
    background: #181825;
    border: 1px solid {BORDER};
    border-radius: 6px;
    outline: none;
}}
QListWidget::item, QTableWidget::item, QTreeWidget::item {{
    padding: 6px 10px;
    border-bottom: 1px solid {SURFACE};
}}
QListWidget::item:selected, QTableWidget::item:selected,
QTreeWidget::item:selected {{
    background: {OVERLAY};
    color: {TEXT};
}}
QListWidget::item:hover, QTableWidget::item:hover,
QTreeWidget::item:hover {{
    background: {SURFACE};
}}

/* ── Scroll Bars ── */
QScrollBar:vertical {{
    background: {BASE};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {OVERLAY};
    min-height: 30px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: {BORDER};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {BASE};
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {OVERLAY};
    min-width: 30px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {BORDER};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Status Bar ── */
QStatusBar {{
    background: {SURFACE};
    border-top: 1px solid {BORDER};
    padding: 4px 12px;
    color: {SUBTEXT};
}}

/* ── Tab Widget ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background: {BASE};
}}
QTabBar::tab {{
    background: {SURFACE};
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    background: {BASE};
    border-bottom: 2px solid {ACCENT};
}}

/* ── Checkbox / Radio ── */
QCheckBox, QRadioButton {{
    spacing: 8px;
    color: {TEXT};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background: #181825;
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

/* ── Tooltips ── */
QToolTip {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
    border-radius: 4px;
}}

/* ── Labels ── */
QLabel[cssClass="title"] {{
    font-size: 22px;
    font-weight: bold;
    color: {TEXT};
}}
QLabel[cssClass="subtitle"] {{
    font-size: 14px;
    color: {SUBTEXT};
}}
QLabel[cssClass="heading"] {{
    font-size: 16px;
    font-weight: bold;
    color: {ACCENT};
}}
"""
