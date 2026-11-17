"""Hover-only native controls for the transparent WeRead reading strip."""

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QHBoxLayout, QMenu, QPushButton, QSizeGrip, QToolTip

from .reader import DragBar


class FishControls:
    def __init__(self, window):
        self.window = window
        self.bar = DragBar(window)
        self.bar.setObjectName("fishControls")
        self.bar.setStyleSheet("#fishControls {background: rgba(234,240,230,235); border-radius:6px;} "
                              "QPushButton {padding:2px 7px; font-size:11px;}")
        row = QHBoxLayout(self.bar)
        row.setContentsMargins(6, 2, 3, 2)
        for label, action in [("⠿", self.drag_hint), ("展开", window.toggle_mini),
                              ("设置", self.menu), ("隐藏", window.hide)]:
            button = QPushButton(label)
            button.clicked.connect(action)
            row.addWidget(button)
        self.bar.adjustSize()
        self.grip = QSizeGrip(window)
        self.drag_strip = DragBar(window)
        self.drag_strip.setToolTip("拖动此处移动小窗；Ctrl+M 返回完整窗口")
        self.hide()

    def drag_hint(self):
        self.notice("拖动窗口顶部细边移动；右下角调整大小。")

    def notice(self, message):
        QToolTip.showText(self.window.mapToGlobal(QPoint(8, self.window.height())), message, self.window)

    def position(self):
        self.bar.move(max(0, self.window.width() - self.bar.width() - 6), 6)
        self.grip.setGeometry(self.window.width() - 14, self.window.height() - 14, 14, 14)
        self.drag_strip.setGeometry(0, 0, self.window.width(), 6)
        for widget in (self.drag_strip, self.bar, self.grip):
            widget.raise_()

    def show(self):
        if self.window.mini:
            self.bar.show()
            self.grip.show()
            self.position()

    def hide(self):
        self.bar.hide()
        self.grip.hide()
        self.drag_strip.setVisible(self.window.mini)

    def hide_if_outside(self):
        if not self.window.rect().contains(self.window.mapFromGlobal(QCursor.pos())):
            self.hide()

    def menu(self):
        window = self.window
        menu = QMenu(window)
        menu.addAction("返回完整微信读书  Ctrl+M", window.toggle_mini)
        menu.addAction("隐藏阅读条  Alt+V", window.hide)
        menu.addSeparator()
        for label, light in [("深色文字 · 适合浅色桌面", False), ("浅色文字 · 适合深色桌面", True)]:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(window.settings.local.get("weread_fish_light", False) == light)
            action.triggered.connect(lambda checked=False, value=light: window.set_fish_option("weread_fish_light", value))
        backdrop = menu.addMenu("背景不透明度（文字保持清晰）")
        for percent in (0, 8, 20, 40, 80):
            backdrop.addAction(f"{percent}%", lambda p=percent: window.set_fish_option("weread_fish_background", p))
        ink = menu.addMenu("文字不透明度")
        for percent in (50, 70, 85, 100):
            ink.addAction(f"{percent}%", lambda p=percent: window.set_fish_option("weread_fish_ink", p))
        menu.addAction("放大文字", lambda: window.change_zoom(0.1))
        menu.addAction("缩小文字", lambda: window.change_zoom(-0.1))
        menu.exec(QCursor.pos())
        QTimer.singleShot(100, self.hide_if_outside)
