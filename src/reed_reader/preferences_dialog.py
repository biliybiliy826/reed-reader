"""Validated settings editor and portable JSON sharing."""

from dataclasses import asdict

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .platform import key_spec, set_opacity, windows
from .settings import Preferences


class PreferencesDialog(QDialog):
    applied = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("阅读设置 · 苇读")
        self.resize(620, 640)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        self.controls = {}
        appearance = QWidget()
        form = QFormLayout(appearance)
        form.setSpacing(12)
        font = QFontComboBox()
        self.controls["font"] = font
        form.addRow("阅读字体", font)
        for name, label, low, high, suffix in [
            ("font_size", "字号", 10, 60, " pt"),
            ("text_opacity", "文字不透明度", 10, 100, "%"),
            ("background_opacity", "背景不透明度", 0, 100, "%"),
            ("window_opacity", "整个窗口不透明度", 15, 100, "%"),
        ]:
            spin = QSpinBox()
            spin.setRange(low, high)
            spin.setSuffix(suffix)
            self.controls[name] = spin
            form.addRow(label, spin)
        for name, label in [("foreground", "文字颜色"), ("background", "背景颜色")]:
            button = QPushButton()
            button.clicked.connect(lambda _, key=name: self.choose_color(key))
            self.controls[name] = button
            form.addRow(label, button)
        spacing = QDoubleSpinBox()
        spacing.setRange(1, 2.5)
        spacing.setSingleStep(0.05)
        self.controls["line_spacing"] = spacing
        form.addRow("行距倍率", spacing)
        theme_row = QHBoxLayout()
        for label, fg, bg in [("苇绿", "#33443d", "#f5f2e9"), ("夜读", "#c8cfc4", "#202a25"),
                              ("纸白", "#303833", "#ffffff")]:
            button = QPushButton(label)
            button.clicked.connect(lambda _, f=fg, b=bg: self.theme(f, b))
            theme_row.addWidget(button)
        form.addRow("快速配色", theme_row)
        tabs.addTab(appearance, "阅读外观")
        behavior = QWidget()
        form = QFormLayout(behavior)
        form.setSpacing(14)
        for name, label in [("wheel_pages", "鼠标滚轮翻页"), ("preserve_paragraphs", "保留段落换行"),
                            ("always_on_top", "阅读器始终置顶"), ("hide_on_leave", "鼠标离开小窗后隐藏")]:
            control = QCheckBox(label)
            self.controls[name] = control
            form.addRow(control)
        seconds = QSpinBox()
        seconds.setRange(1, 600)
        seconds.setSuffix(" 秒 / 页")
        self.controls["auto_seconds"] = seconds
        form.addRow("自动翻页间隔", seconds)
        position = QComboBox()
        for label, value in [("底部", "bottom"), ("顶部", "top"), ("隐藏", "hidden")]:
            position.addItem(label, value)
        self.controls["progress_position"] = position
        form.addRow("进度条位置", position)
        note = QLabel("隐藏窗口会暂停自动翻页，恢复窗口后继续。\n小窗上方标题区域可以拖动，右下角可以调整大小。")
        note.setWordWrap(True)
        form.addRow(note)
        tabs.addTab(behavior, "阅读行为")
        keyboard = QWidget()
        form = QFormLayout(keyboard)
        for name, label in [("previous_key", "上一页"), ("next_key", "下一页"),
                            ("toggle_key", "显示 / 隐藏阅读器"), ("panic_key", "立即隐藏所有窗口"),
                            ("panic_alt_key", "隐藏备用键（默认 F8）")]:
            control = QKeySequenceEdit()
            control.setMaximumSequenceLength(1)
            self.controls[name] = control
            form.addRow(label, control)
        middle = QCheckBox("鼠标中键全局隐藏（X11）")
        self.controls["global_middle_hide"] = middle
        form.addRow(middle)
        help_text = QLabel("X11：保存后立即注册全局快捷键，冲突会在书架状态栏提示。\n\n"
                           "Wayland：请在桌面设置中添加自定义快捷键，命令为：\n"
                           "reed-reader --toggle\nreed-reader --next\nreed-reader --previous\nreed-reader --hide\n\n"
                           "中键在苇读窗口内始终隐藏；X11 可在其他应用内触发，不拦截其原有中键操作。\n"
                           "F8 / Ctrl+Alt+H 只隐藏，Alt+V 恢复阅读。\n"
                           "窗口内快捷键：Ctrl+M 小窗、F11 沉浸、Ctrl+F 搜索、Ctrl+B 书签、Esc 隐藏。")
        help_text.setWordWrap(True)
        form.addRow(help_text)
        tabs.addTab(keyboard, "快捷键")
        share = QWidget()
        share_layout = QVBoxLayout(share)
        share_layout.addWidget(QLabel("分享外观和快捷键，不包含书籍、进度或网络服务地址。"))
        self.code = QTextEdit()
        self.code.setPlaceholderText("在这里粘贴苇读配置 JSON，或点击生成配置。")
        share_layout.addWidget(self.code)
        buttons = QHBoxLayout()
        for label, action in [("生成配置", self.export_code), ("复制", self.copy_code), ("载入配置", self.import_code)]:
            button = QPushButton(label)
            button.clicked.connect(action)
            buttons.addWidget(button)
        share_layout.addLayout(buttons)
        tabs.addTab(share, "配置分享")
        tools = QWidget()
        tools_layout = QVBoxLayout(tools)
        help_text = QLabel("X11 窗口透明工具\n\n选择一个窗口并调整透明度。需要桌面合成器支持。\n100% 会移除该窗口的透明度属性。")
        help_text.setWordWrap(True)
        tools_layout.addWidget(help_text)
        self.window_list = QComboBox()
        tools_layout.addWidget(self.window_list)
        refresh = QPushButton("刷新窗口列表")
        refresh.clicked.connect(self.refresh_windows)
        tools_layout.addWidget(refresh)
        self.opacity = QSpinBox()
        self.opacity.setRange(15, 100)
        self.opacity.setValue(100)
        self.opacity.setSuffix("%")
        tools_layout.addWidget(self.opacity)
        apply = QPushButton("设置选中窗口透明度")
        apply.clicked.connect(self.apply_opacity)
        tools_layout.addWidget(apply)
        tools_layout.addStretch()
        tabs.addTab(tools, "窗口工具")
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.save)
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        self.populate(settings.preferences)

    def populate(self, preferences):
        for name, value in asdict(preferences).items():
            control = self.controls[name]
            if isinstance(control, QFontComboBox):
                control.setCurrentFont(QFont(value))
            elif isinstance(control, QCheckBox):
                control.setChecked(value)
            elif isinstance(control, QComboBox):
                control.setCurrentIndex(control.findData(value))
            elif isinstance(control, QKeySequenceEdit):
                control.setKeySequence(QKeySequence(value))
            elif isinstance(control, QPushButton):
                control.setText(value)
            else:
                control.setValue(value)

    def values(self):
        data = {}
        for name, control in self.controls.items():
            if isinstance(control, QFontComboBox):
                data[name] = control.currentFont().family()
            elif isinstance(control, QCheckBox):
                data[name] = control.isChecked()
            elif isinstance(control, QComboBox):
                data[name] = control.currentData()
            elif isinstance(control, QKeySequenceEdit):
                data[name] = control.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
                key_spec(data[name])
            elif isinstance(control, QPushButton):
                data[name] = control.text()
            else:
                data[name] = control.value()
        return Preferences.parse(data)

    def choose_color(self, name):
        control = self.controls[name]
        color = QColorDialog.getColor(QColor(control.text()), self)
        if color.isValid():
            control.setText(color.name())

    def theme(self, foreground, background):
        self.controls["foreground"].setText(foreground)
        self.controls["background"].setText(background)

    def save(self):
        try:
            preferences = self.values()
            previous = self.settings.preferences
            self.settings.preferences = preferences
            try:
                self.settings.save()
            except OSError:
                self.settings.preferences = previous
                raise
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "设置未保存", str(exc))
            return
        self.applied.emit()
        self.accept()

    def export_code(self):
        import json
        try:
            self.code.setPlainText(json.dumps({"reed_reader": 1, "preferences": asdict(self.values())}, ensure_ascii=False, indent=2))
        except ValueError as exc:
            QMessageBox.warning(self, "配置无效", str(exc))

    def copy_code(self):
        QApplication.clipboard().setText(self.code.toPlainText())

    def import_code(self):
        previous = self.settings.preferences
        try:
            self.settings.import_code(self.code.toPlainText())
            self.populate(self.settings.preferences)
        except ValueError as exc:
            QMessageBox.warning(self, "配置无效", str(exc))
        finally:
            self.settings.preferences = previous

    def refresh_windows(self):
        try:
            entries = windows()
            self.window_list.clear()
            for window_id, title in entries:
                self.window_list.addItem(title, window_id)
        except Exception as exc:
            QMessageBox.warning(self, "窗口工具不可用", str(exc))

    def apply_opacity(self):
        window_id = self.window_list.currentData()
        if window_id is None:
            return
        try:
            set_opacity(window_id, self.opacity.value())
        except Exception as exc:
            QMessageBox.warning(self, "设置失败", str(exc))
