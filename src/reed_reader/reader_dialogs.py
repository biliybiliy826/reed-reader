"""Navigation tools shared by normal and mini readers."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class NavigationDialog(QDialog):
    def __init__(self, library, book_id: str, jump, parent=None):
        super().__init__(parent)
        self.setWindowTitle("目录、搜索与书签")
        self.resize(580, 560)
        self.library, self.book_id, self.jump = library, book_id, jump
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        chapter_page = QWidget()
        chapter_layout = QVBoxLayout(chapter_page)
        chapter_query = QLineEdit()
        chapter_query.setPlaceholderText("搜索章节标题…")
        chapter_layout.addWidget(chapter_query)
        self.chapter_list = QListWidget()
        for i, chapter in enumerate(library.chapters(book_id)):
            item = QListWidgetItem(f"{i + 1:03d}   {chapter.title}")
            item.setData(Qt.ItemDataRole.UserRole, (i, 0))
            self.chapter_list.addItem(item)
        chapter_layout.addWidget(self.chapter_list)
        chapter_query.textChanged.connect(self.filter_chapters)
        self.chapter_list.itemActivated.connect(self.activate)
        tabs.addTab(chapter_page, "章节目录")
        search_page = QWidget()
        search_layout = QVBoxLayout(search_page)
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("输入正文关键词，按回车搜索")
        button = QPushButton("搜索")
        row.addWidget(self.query)
        row.addWidget(button)
        search_layout.addLayout(row)
        self.results = QListWidget()
        search_layout.addWidget(self.results)
        search_layout.addWidget(QLabel("最多显示 200 条；网络书籍只搜索已缓存正文。双击结果跳转。"))
        self.query.returnPressed.connect(self.search)
        button.clicked.connect(self.search)
        self.results.itemActivated.connect(self.activate)
        tabs.addTab(search_page, "全文搜索")
        marks_page = QWidget()
        marks_layout = QVBoxLayout(marks_page)
        self.marks = QListWidget()
        marks_layout.addWidget(self.marks)
        remove = QPushButton("删除选中书签")
        remove.clicked.connect(self.remove_mark)
        marks_layout.addWidget(remove)
        self.marks.itemActivated.connect(self.activate)
        tabs.addTab(marks_page, "我的书签")
        self.load_marks()

    def filter_chapters(self, text):
        for i in range(self.chapter_list.count()):
            item = self.chapter_list.item(i)
            item.setHidden(text.casefold() not in item.text().casefold())

    def search(self):
        self.results.clear()
        for hit in self.library.search(self.book_id, self.query.text()):
            item = QListWidgetItem(f"{hit.title}\n{hit.excerpt}")
            item.setData(Qt.ItemDataRole.UserRole, (hit.chapter, hit.offset))
            self.results.addItem(item)
        if not self.results.count():
            item = QListWidgetItem("没有匹配结果")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(item)

    def activate(self, item):
        position = item.data(Qt.ItemDataRole.UserRole)
        if position is not None:
            self.jump(*position)
            self.accept()

    def load_marks(self):
        self.marks.clear()
        for mark in self.library.bookmarks(self.book_id):
            item = QListWidgetItem(mark["label"])
            item.setData(Qt.ItemDataRole.UserRole, (mark["chapter"], mark["offset"]))
            item.setData(Qt.ItemDataRole.UserRole + 1, mark["id"])
            self.marks.addItem(item)

    def remove_mark(self):
        if item := self.marks.currentItem():
            self.library.remove_bookmark(item.data(Qt.ItemDataRole.UserRole + 1))
            self.load_marks()
