"""Qt-shaped pagination with stable Unicode offsets and no skipped characters."""

from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QTextLayout, QTextOption
from PySide6.QtWidgets import QWidget

from .legado import from_utf16
from .settings import Preferences


@dataclass
class Page:
    end: int
    layouts: list[QTextLayout]


def paginate(text: str, start: int, width: float, height: float, font: QFont,
             spacing: float, preserve: bool) -> Page:
    start = max(0, min(start, len(text)))
    source = text if preserve else text.replace("\n", " ")
    offset, y = start, 0.0
    layouts = []
    line_height = QFontMetricsF(font).height() * spacing
    width, height = max(16, width), max(line_height, height)
    while offset < len(source) and y + line_height <= height + 0.01:
        end = source.find("\n", offset)
        end = len(source) if end < 0 else end
        paragraph = source[offset:end]
        if not paragraph:
            offset += 1
            y += line_height * 0.55
            continue
        layout = QTextLayout(paragraph, font)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        layout.beginLayout()
        consumed = 0
        while y + line_height <= height + 0.01:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(width)
            line.setPosition(QPointF(0, y))
            consumed = line.textStart() + line.textLength()
            y += line_height
        layout.endLayout()
        layouts.append(layout)
        count = from_utf16(paragraph, consumed)
        if count == 0:
            # Even a viewport smaller than one glyph must make forward progress.
            count = 1
        offset += count
        if offset == end and end < len(source):
            offset += 1
        elif offset < end:
            break
    return Page(offset, layouts)


class ReadingCanvas(QWidget):
    page_changed = Signal(int)
    turn_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 55)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.text = ""
        self.offset = 0
        self.preferences = Preferences()
        self.page = Page(0, [])
        self.margin = 24
        self.wheel_total = 0
        self.setAccessibleName("阅读正文")

    def reading_font(self):
        return QFont(self.preferences.font, self.preferences.font_size)

    def set_content(self, text: str, offset: int, preferences: Preferences):
        self.text = text
        self.offset = max(0, min(offset, len(text)))
        self.preferences = preferences
        self.reflow()

    def page_at(self, offset: int):
        return paginate(self.text, offset, self.width() - self.margin * 2,
                        self.height() - self.margin * 2, self.reading_font(),
                        self.preferences.line_spacing, self.preferences.preserve_paragraphs)

    def previous_offset(self):
        cursor = 0
        previous = 0
        while cursor < self.offset:
            previous = cursor
            end = self.page_at(cursor).end
            if end >= self.offset or end <= cursor:
                return previous
            cursor = end
        return previous

    def reflow(self):
        self.page = self.page_at(self.offset)
        self.page_changed.emit(self.page.end)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        color = QColor(self.preferences.foreground)
        color.setAlphaF(self.preferences.text_opacity / 100)
        painter.setPen(color)
        painter.setClipRect(self.rect())
        for layout in self.page.layouts:
            layout.draw(painter, QPointF(self.margin, self.margin))

    def wheelEvent(self, event):
        if self.preferences.wheel_pages:
            self.wheel_total += event.angleDelta().y()
            if abs(self.wheel_total) >= 120:
                self.turn_requested.emit(-1 if self.wheel_total > 0 else 1)
                self.wheel_total = 0
            event.accept()
        else:
            event.ignore()
