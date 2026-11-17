"""Original Reed identity and desktop styles."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

STYLE = """
QWidget { font-family: 'Noto Sans CJK SC', 'DejaVu Sans'; font-size: 13px; color: #263e36; }
QMainWindow, QDialog { background: #f7f8f4; }
QFrame#sidebar { background: #e9eee6; border: none; }
QLabel#brand { font-size: 29px; font-weight: 700; color: #264e40; }
QLabel#muted { color: #7a857d; font-size: 12px; }
QLabel#heading { font-size: 28px; font-weight: 650; }
QLabel#heroTitle { font-size: 22px; font-weight: 650; color: #f4f1df; }
QLabel#heroCopy { color: #c7d7c8; }
QFrame#hero { background: #315c49; border-radius: 16px; }
QPushButton { background: #edf1e9; border: 1px solid #dce3d9; border-radius: 7px; padding: 8px 14px; }
QPushButton:hover { background: #e0e8db; border-color: #a1b29b; }
QPushButton:pressed, QPushButton:checked { background: #d0dfca; color: #214b37; }
QPushButton:disabled { color: #9aa49b; background: #f0f2ed; }
QPushButton#primary { background: #315c49; color: #ffffff; border-color: #315c49; }
QPushButton#primary:hover { background: #426d59; }
QPushButton#nav { text-align: left; background: transparent; border: none; padding: 12px 16px; }
QPushButton#nav:checked { background: #d7e2d0; font-weight: 650; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QKeySequenceEdit, QTextEdit {
 background: #ffffff; border: 1px solid #d9e1d5; border-radius: 6px; padding: 7px;
 selection-background-color: #c9ddc1; selection-color: #233c2e;
}
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { border-radius: 8px; padding: 7px; }
QListWidget::item:selected { background: #dbe6d4; color: #253d30; }
QTabWidget::pane { border: 1px solid #d9e1d5; border-radius: 6px; }
QTabBar::tab { background: #e9eee5; padding: 10px 16px; }
QTabBar::tab:selected { background: #ffffff; }
QSlider::groove:horizontal { height: 4px; background: #d8e1d1; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #6a8962; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; margin: -4px 0; border-radius: 6px; background: #456e4a; }
QScrollBar:vertical { background: transparent; width: 9px; }
QScrollBar::handle:vertical { background: #c7d1c1; border-radius: 4px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QStatusBar { color: #70806f; background: #f0f3ec; }
QToolTip { color: #ffffff; background: #315c49; border: none; padding: 5px; }
"""


def app_icon() -> QIcon:
    pixmap = QPixmap(96, 96)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#315c49"))
    painter.drawRoundedRect(QRectF(2, 2, 92, 92), 22, 22)
    painter.setPen(QPen(QColor("#e3edcf"), 4))
    painter.drawLine(46, 76, 46, 27)
    painter.drawLine(53, 76, 67, 38)
    painter.drawArc(QRectF(20, 24, 27, 31), 0, 180 * 16)
    painter.drawLine(21, 39, 44, 59)
    painter.drawLine(46, 46, 63, 25)
    painter.end()
    return QIcon(pixmap)


def heading(text: str, name="heading"):
    from PySide6.QtWidgets import QLabel
    label = QLabel(text)
    label.setObjectName(name)
    return label
