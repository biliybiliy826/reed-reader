"""Independent reader window; owns current chapter and page transitions."""

from PySide6.QtCore import QByteArray, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .canvas import ReadingCanvas
from .legado import Legado, from_utf16
from .reader_dialogs import NavigationDialog


class DragBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.origin = None
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if not handle or not handle.startSystemMove():
                self.origin = event.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, event):
        if self.origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self.origin)

    def mouseReleaseEvent(self, event):
        self.origin = None


class Reader(QWidget):
    changed = Signal()
    settings_requested = Signal()
    shelf_requested = Signal()
    message = Signal(str)

    def __init__(self, library, settings, jobs):
        super().__init__()
        self.library, self.settings, self.jobs = library, settings, jobs
        self.book_id = None
        self.chapter_index = 0
        self.offset = 0
        self.text = ""
        self.mini = False
        self.loading = False
        self.generation = 0
        self.inflight = set()
        self.pending = None
        self.setWindowTitle("苇读 · 阅读器")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(800, 650)
        self.setMinimumSize(340, 180)
        self.layout_root = QVBoxLayout(self)
        self.layout_root.setContentsMargins(10, 8, 10, 8)
        self.layout_root.setSpacing(2)
        self.header = DragBar()
        header = QHBoxLayout(self.header)
        header.setContentsMargins(10, 0, 4, 0)
        self.title = QLabel("苇读")
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.title.setMinimumWidth(20)
        header.addWidget(self.title, 1)
        for label, callback in [("书架", self.shelf_requested.emit), ("小窗", self.toggle_mini), ("隐藏", self.hide)]:
            button = QPushButton(label)
            button.setFixedHeight(28)
            button.clicked.connect(callback)
            header.addWidget(button)
        self.layout_root.addWidget(self.header)
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 10000)
        self.progress.setToolTip("拖动跳转全书进度")
        self.progress.sliderReleased.connect(self.seek)
        self.canvas = ReadingCanvas()
        self.canvas.turn_requested.connect(self.turn)
        self.canvas.page_changed.connect(lambda _: self.update_progress())
        self.layout_root.addWidget(self.canvas, 1)
        self.layout_root.addWidget(self.progress)
        self.footer = QWidget()
        footer = QHBoxLayout(self.footer)
        footer.setContentsMargins(4, 0, 0, 0)
        self.previous_button = QPushButton("‹")
        self.previous_button.setToolTip("上一页")
        self.previous_button.clicked.connect(lambda: self.turn(-1))
        self.next_button = QPushButton("›")
        self.next_button.setToolTip("下一页")
        self.next_button.clicked.connect(lambda: self.turn(1))
        self.status = QLabel("")
        self.status.setMinimumWidth(20)
        footer.addWidget(self.previous_button)
        footer.addWidget(self.status, 1)
        footer.addWidget(self.next_button)
        footer.addWidget(QSizeGrip(self))
        self.layout_root.addWidget(self.footer)
        self.toolbar = QWidget()
        toolbar = QHBoxLayout(self.toolbar)
        toolbar.setContentsMargins(6, 2, 6, 2)
        self.auto_button = QPushButton("自动翻页")
        self.auto_button.setCheckable(True)
        self.auto_button.toggled.connect(self.set_auto)
        for label, callback in [("目录 / 搜索", self.navigate), ("加书签", self.add_bookmark),
                                ("沉浸", self.toggle_fullscreen), ("外观", self.settings_requested.emit)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        toolbar.addWidget(self.auto_button)
        self.layout_root.addWidget(self.toolbar)
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.turn(1))
        self.shortcuts = []
        for sequence, action in [("Right", lambda: self.turn(1)), ("Left", lambda: self.turn(-1)),
                                 ("PgDown", lambda: self.turn(1)), ("PgUp", lambda: self.turn(-1)),
                                 ("Space", lambda: self.turn(1)), ("Escape", self.escape),
                                 ("Ctrl+M", self.toggle_mini), ("F11", self.toggle_fullscreen),
                                 ("Ctrl+F", self.navigate), ("Ctrl+B", self.add_bookmark)]:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(action)
            self.shortcuts.append(shortcut)
        self.apply_settings()
        self.restore_geometry()

    def open_book(self, book_id: str):
        self.book_id = book_id
        entry = self.library.entry(book_id)
        self.setWindowTitle(f"{entry.title} · 苇读")
        self.load_chapter(entry.chapter, entry.offset)
        self.show()
        self.raise_()
        self.activateWindow()

    def load_chapter(self, index: int, offset: int = 0, utf16=False):
        if not self.book_id:
            return
        entry = self.library.entry(self.book_id)
        index = max(0, min(index, entry.count - 1))
        chapter = self.library.chapter(self.book_id, index)
        self.generation += 1
        self.chapter_index, self.offset = index, max(0, offset)
        self.title.setText(chapter.title[:45])
        if chapter.text is None:
            self.loading = True
            self.text = ""
            self.canvas.set_content("正在读取章节…", 0, self.settings.preferences)
            self.pending = (self.book_id, index, offset, utf16)
            self.fetch(entry, index)
        else:
            self.pending = None
            self.loading = False
            self.text = chapter.text
            self.offset = min(from_utf16(self.text, offset) if utf16 else offset, len(self.text))
            if self.text and self.offset == len(self.text):
                self.canvas.set_content(self.text, self.offset, self.settings.preferences)
                self.offset = self.canvas.previous_offset()
            self.render()
            self.fetch(entry, index + 1, prefetch=True)

    def fetch(self, entry, index, prefetch=False):
        if not entry.endpoint or index >= entry.count:
            return
        if self.library.chapter(entry.id, index).text is not None:
            return
        key = (entry.id, index)
        if key in self.inflight:
            return
        self.inflight.add(key)

        def done(text):
            self.inflight.discard(key)
            if not any(e.id == entry.id for e in self.library.entries()):
                return
            self.library.cache(entry.id, index, text)
            if self.pending and self.pending[:2] == key:
                _, _, offset, utf16 = self.pending
                self.load_chapter(index, offset, utf16)

        def failed(error):
            self.inflight.discard(key)
            if self.pending and self.pending[:2] == key:
                self.loading = True
                self.auto_button.setChecked(False)
                self.canvas.set_content("章节读取失败。\n\n" + error + "\n\n按下一页重试，或打开目录选择已缓存章节。", 0, self.settings.preferences)
                self.status.setText("连接失败 · 可重试")
            self.message.emit(("下一章预加载失败：" if prefetch else "章节读取失败：") + error)

        self.jobs.run(lambda: Legado(entry.endpoint).content(entry.remote_url, index), done, failed)

    def render(self):
        self.canvas.set_content(self.text, self.offset, self.settings.preferences)
        self.library.progress(self.book_id, self.chapter_index, self.offset)
        self.changed.emit()
        self.update_progress()

    def update_progress(self):
        if not self.book_id:
            return
        entry = self.library.entry(self.book_id)
        fraction = self.offset / max(1, len(self.text))
        percent = 100 * (self.chapter_index + fraction) / entry.count
        if not self.loading and self.text and self.chapter_index == entry.count - 1 and self.canvas.page.end == len(self.text):
            percent = 100
        if not self.progress.isSliderDown():
            self.progress.setValue(round(percent * 100))
        self.status.setText(f"{self.chapter_index + 1} / {entry.count} 章 · {percent:.1f}%")
        self.status.setToolTip("按章节等权估算的全书进度")

    def turn(self, direction: int):
        if not self.book_id:
            return
        if self.loading:
            if self.pending:
                self.load_chapter(self.chapter_index, self.pending[2], self.pending[3])
            return
        entry = self.library.entry(self.book_id)
        if direction > 0:
            if self.canvas.page.end < len(self.text):
                self.offset = self.canvas.page.end
                self.render()
            elif self.chapter_index + 1 < entry.count:
                self.load_chapter(self.chapter_index + 1)
            else:
                self.auto_button.setChecked(False)
                self.library.progress(self.book_id, self.chapter_index, self.offset)
                self.update_progress()
                self.status.setText("已读完 · 100%")
                self.changed.emit()
        elif self.offset > 0:
            self.offset = self.canvas.previous_offset()
            self.render()
        elif self.chapter_index > 0:
            previous = self.library.chapter(self.book_id, self.chapter_index - 1)
            self.load_chapter(self.chapter_index - 1, max(0, len(previous.text or "") - 1))
            if not self.loading:
                self.offset = self.canvas.previous_offset()
                self.render()

    def seek(self):
        if not self.book_id:
            return
        count = self.library.entry(self.book_id).count
        position = self.progress.value() / 10000 * count
        index = min(count - 1, int(position))
        chapter = self.library.chapter(self.book_id, index)
        offset = int((position - index) * len(chapter.text or ""))
        self.load_chapter(index, offset)

    def navigate(self):
        if self.book_id:
            NavigationDialog(self.library, self.book_id, self.load_chapter, self).exec()

    def add_bookmark(self):
        if self.book_id and not self.loading:
            title = self.library.chapter(self.book_id, self.chapter_index).title
            excerpt = self.text[self.offset:self.offset + 30].replace("\n", " ")
            self.library.bookmark(self.book_id, self.chapter_index, self.offset, f"{title} · {excerpt}")
            self.status.setText("书签已保存")

    def set_auto(self, checked):
        self.auto_button.setText("暂停翻页" if checked else "自动翻页")
        if checked and self.isVisible():
            self.timer.start(self.settings.preferences.auto_seconds * 1000)
        else:
            self.timer.stop()

    def apply_settings(self):
        prefs = self.settings.preferences
        self.setWindowOpacity(prefs.window_opacity / 100)
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, prefs.always_on_top)
        if visible:
            self.show()
        self.layout_root.removeWidget(self.progress)
        self.layout_root.insertWidget(1 if prefs.progress_position == "top" else 3, self.progress)
        self.progress.setVisible(prefs.progress_position != "hidden")
        self.setStyleSheet(f"QLabel {{color: {prefs.foreground}; background: transparent;}} "
                           "QPushButton {padding: 3px 8px; min-width: 15px; font-size: 12px;} "
                           "QSlider {max-height: 12px;}")
        self.canvas.set_content(self.text, self.offset, prefs)
        if self.auto_button.isChecked():
            self.set_auto(True)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        color = QColor(self.settings.preferences.background)
        color.setAlphaF(self.settings.preferences.background_opacity / 100)
        painter.fillRect(self.rect(), color)

    def save_geometry(self):
        if not self.isFullScreen():
            self.settings.local["mini_geometry" if self.mini else "reader_geometry"] = bytes(self.saveGeometry().toBase64()).decode()

    def restore_geometry(self):
        value = self.settings.local.get("mini_geometry" if self.mini else "reader_geometry")
        if isinstance(value, str):
            self.restoreGeometry(QByteArray.fromBase64(value.encode()))
        elif self.mini:
            self.resize(640, 220)
        else:
            self.resize(800, 650)

    def toggle_mini(self):
        if self.isFullScreen():
            self.showNormal()
        self.save_geometry()
        self.hide()  # Preserve the old mode's geometry before changing window flags.
        self.mini = not self.mini
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, self.mini)
        self.toolbar.setVisible(not self.mini)
        self.canvas.margin = 12 if self.mini else 24
        self.restore_geometry()
        self.show()
        self.canvas.reflow()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            if self.mini:
                self.toggle_mini()
            self.save_geometry()
            self.showFullScreen()

    def escape(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.hide()

    def hideEvent(self, event):
        self.timer.stop()
        self.save_geometry()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self.auto_button.isChecked():
            self.set_auto(True)

    def leaveEvent(self, event):
        if self.mini and self.settings.preferences.hide_on_leave and self.isActiveWindow():
            QTimer.singleShot(150, self._hide_if_outside)
        super().leaveEvent(event)

    def _hide_if_outside(self):
        from PySide6.QtGui import QCursor
        if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            self.hide()

    def closeEvent(self, event):
        self.hide()
        event.ignore()
