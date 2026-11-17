"""Explicit network shelf and progress synchronization UI."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .legado import Legado
from .style import heading


class NetworkPanel(QWidget):
    imported = Signal(str)
    pull_requested = Signal(str, int, int)
    status = Signal(str)

    def __init__(self, library, settings, jobs, parent=None):
        super().__init__(parent)
        self.library, self.settings, self.jobs = library, settings, jobs
        self.client = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 20)
        layout.setSpacing(18)
        layout.addWidget(heading("网络书架"))
        description = QLabel("连接手机上的阅读 App，在电脑上继续阅读。\n在手机中开启 Web 服务，将显示的地址填入下方。")
        description.setObjectName("muted")
        layout.addWidget(description)
        row = QHBoxLayout()
        self.endpoint = QLineEdit(settings.local.get("endpoint", ""))
        self.endpoint.setPlaceholderText("http://192.168.1.20:1234")
        self.connect_button = QPushButton("连接 / 刷新")
        self.connect_button.setObjectName("primary")
        self.connect_button.clicked.connect(self.connect_service)
        row.addWidget(self.endpoint, 1)
        row.addWidget(self.connect_button)
        layout.addLayout(row)
        self.feedback = QLabel("尚未连接。已加入书架的网络书籍可离线阅读缓存章节。")
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        self.books = QListWidget()
        self.books.itemActivated.connect(lambda _: self.open_selected())
        layout.addWidget(self.books, 1)
        actions = QHBoxLayout()
        for label, action in [("加入书架并阅读", self.open_selected),
                              ("拉取手机进度", self.pull_selected), ("推送本机进度", self.push_selected)]:
            button = QPushButton(label)
            button.clicked.connect(action)
            actions.addWidget(button)
        layout.addLayout(actions)
        refresh = QPushButton("刷新所选书籍的章节目录")
        refresh.clicked.connect(self.refresh_chapters)
        layout.addWidget(refresh)
        note = QLabel("进度只在点击拉取 / 推送时同步；不会自动覆盖手机进度。\n在线内容由你配置的服务提供，苇读不内置书源。")
        note.setObjectName("muted")
        layout.addWidget(note)

    def fail(self, error):
        self.connect_button.setEnabled(True)
        self.feedback.setText(error)
        self.status.emit(error)

    def connect_service(self):
        try:
            client = Legado(self.endpoint.text())
        except ValueError as exc:
            self.fail(str(exc))
            return
        self.connect_button.setEnabled(False)
        self.feedback.setText("正在读取书架…")

        def done(books):
            self.client = client
            self.settings.local["endpoint"] = client.endpoint
            self.settings.save()
            self.books.clear()
            for book in books:
                item = QListWidgetItem(f"{book.title}  ·  {book.author or '未知作者'}\n手机进度：第 {book.chapter + 1} 章")
                item.setData(Qt.ItemDataRole.UserRole, book)
                self.books.addItem(item)
            self.connect_button.setEnabled(True)
            self.feedback.setText(f"已连接 · {len(books)} 本书。双击书籍即可开始阅读。")

        self.jobs.run(client.bookshelf, done, self.fail)

    def selected(self):
        item = self.books.currentItem()
        if not item or not self.client:
            self.feedback.setText("请先连接服务并选择一本书。")
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def existing(self, remote):
        return next((e for e in self.library.entries() if e.endpoint == self.client.endpoint and e.remote_url == remote.url), None)

    def open_selected(self):
        remote = self.selected()
        if remote is None:
            return
        if existing := self.existing(remote):
            self.imported.emit(existing.id)
            return
        client = self.client
        self.feedback.setText("正在读取章节目录…")

        def done(book):
            book_id = self.library.add_remote(book, client.endpoint, remote.url)
            self.feedback.setText("已加入本地书架；正文按需缓存。")
            self.imported.emit(book_id)
            self.pull_requested.emit(book_id, min(remote.chapter, len(book.chapters) - 1), remote.position_utf16)

        self.jobs.run(lambda: client.book(remote), done, self.fail)

    def pull_selected(self):
        remote = self.selected()
        if remote is None:
            return
        entry = self.existing(remote)
        if entry is None:
            self.feedback.setText("请先将这本书加入本地书架。")
            return
        client = self.client

        def done(books):
            current = next((b for b in books if b.url == remote.url), None)
            if current is None:
                self.fail("手机书架中已不存在这本书。")
                return
            if current.chapter >= entry.count:
                self.fail("手机章节超出本地目录；请先刷新章节目录，再拉取进度。")
                return
            self.imported.emit(entry.id)
            self.pull_requested.emit(entry.id, current.chapter, current.position_utf16)
            self.feedback.setText("已拉取手机进度。")

        self.jobs.run(client.bookshelf, done, self.fail)

    def refresh_chapters(self):
        remote = self.selected()
        if remote is None:
            return
        entry = self.existing(remote)
        if entry is None:
            self.feedback.setText("请先将这本书加入本地书架。")
            return
        client = self.client

        def done(book):
            try:
                added = self.library.refresh_remote(entry.id, book)
                self.feedback.setText(f"目录已更新，新增 {added} 章；本机进度、书签和缓存已保留。")
            except ValueError as exc:
                self.fail(str(exc))

        self.jobs.run(lambda: client.book(remote), done, self.fail)

    def push_selected(self):
        remote = self.selected()
        if remote is None:
            return
        entry = self.existing(remote)
        if entry is None:
            self.feedback.setText("请先将这本书加入本地书架。")
            return
        chapter = self.library.chapter(entry.id, entry.chapter)
        if chapter.text is None:
            self.feedback.setText("该章尚未缓存，请先阅读后再推送进度。")
            return
        client = self.client
        self.jobs.run(lambda: client.push(remote, entry.chapter, entry.offset, chapter.text, chapter.title),
                      lambda _: self.feedback.setText("本机进度已推送到手机。"), self.fail)
