"""A keyboard-accessible book grid with original typographic covers."""

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate

COLORS = [("#d5dec7", "#35543e"), ("#e4ceb0", "#765c40"), ("#cddcdb", "#38615e"),
          ("#dbcdd1", "#715360"), ("#dddcbf", "#60603c")]


class BookDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return super().paint(painter, option, index)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(9, 6, -9, -6)
        selected = option.state & QStyle.StateFlag.State_Selected
        painter.setPen(QPen(QColor("#a8bba0") if selected else QColor("#e2e7dc"), 1))
        painter.setBrush(QColor("#e8efdf") if selected else QColor("#ffffff"))
        painter.drawRoundedRect(rect, 10, 10)
        bg, fg = COLORS[int(entry.id[:4], 16) % len(COLORS)]
        grid = option.rect.height() > 100
        cover = QRect(rect.x() + 12, rect.y() + 12, rect.width() - 24, 162) if grid else QRect(rect.x() + 8, rect.y() + 8, 50, rect.height() - 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(cover, 5, 5)
        painter.setPen(QPen(QColor(fg), 1))
        painter.drawLine(cover.x() + 9, cover.y() + 7, cover.x() + 9, cover.bottom() - 7)
        painter.setFont(QFont("Noto Serif CJK SC", 17 if grid else 13, QFont.Weight.DemiBold))
        painter.drawText(cover.adjusted(20 if grid else 13, 18 if grid else 3, -12 if grid else -3, -32 if grid else -3),
                         Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, entry.title[:22] if grid else entry.title[:2])
        if grid:
            painter.setFont(QFont("DejaVu Sans", 8))
            painter.drawText(cover.adjusted(20, 0, -10, -12), Qt.AlignmentFlag.AlignBottom, "R E E D   /   " + entry.format)
            detail = QRect(rect.x() + 12, cover.bottom() + 12, rect.width() - 24, 65)
        else:
            detail = QRect(cover.right() + 16, rect.y() + 9, rect.width() - 88, rect.height() - 14)
        painter.setPen(QColor("#2e4437"))
        painter.setFont(QFont("Noto Sans CJK SC", 11, QFont.Weight.DemiBold))
        title = painter.fontMetrics().elidedText(entry.title, Qt.TextElideMode.ElideRight, detail.width() - 20)
        painter.drawText(detail, Qt.AlignmentFlag.AlignTop, title)
        if entry.favorite:
            painter.setPen(QColor("#9b7e3c"))
            painter.drawText(detail, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, "★")
        painter.setPen(QColor("#86917f"))
        painter.setFont(QFont("Noto Sans CJK SC", 9))
        subtitle = entry.author or ("网络书架" if entry.endpoint else "本地藏书")
        painter.drawText(detail.adjusted(0, 25, 0, 0), Qt.AlignmentFlag.AlignTop,
                         painter.fontMetrics().elidedText(subtitle, Qt.TextElideMode.ElideRight, detail.width()))
        if grid:
            painter.setFont(QFont("Noto Sans CJK SC", 8))
            painter.drawText(detail.adjusted(0, 49, 0, 0), Qt.AlignmentFlag.AlignTop,
                             f"第 {entry.chapter + 1} / {entry.count} 章   ·   {entry.format}")
        painter.restore()


class BookList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = True
        self.setItemDelegate(BookDelegate(self))
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSpacing(2)
        self.set_grid(True)
        self.setAccessibleName("我的书架")

    def set_grid(self, grid):
        self.grid = grid
        self.setViewMode(QListWidget.ViewMode.IconMode if grid else QListWidget.ViewMode.ListMode)
        self.setFlow(QListWidget.Flow.LeftToRight if grid else QListWidget.Flow.TopToBottom)
        self.setWrapping(grid)
        self.setGridSize(QSize(196, 272) if grid else QSize())
        for i in range(self.count()):
            self.item(i).setSizeHint(QSize(196, 272) if grid else QSize(300, 80))

    def populate(self, entries):
        selected = self.currentItem().data(Qt.ItemDataRole.UserRole).id if self.currentItem() else None
        self.clear()
        for entry in entries:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, f"{entry.title}，{entry.author}，{entry.format}")
            item.setSizeHint(QSize(196, 272) if self.grid else QSize(300, 80))
            item.setToolTip(f"{entry.title}\n{entry.author}\n双击阅读；右键收藏或移出书架")
            self.addItem(item)
            if entry.id == selected:
                self.setCurrentItem(item)
