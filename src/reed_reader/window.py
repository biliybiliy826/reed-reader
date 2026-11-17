"""Bookshelf window and application-level navigation; reader is independent."""

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .demo import demo_book
from .formats import import_file
from .library_view import BookList
from .network_panel import NetworkPanel
from .preferences_dialog import PreferencesDialog
from .style import heading


class MainWindow(QMainWindow):
    preferences_changed = Signal()
    exit_requested = Signal()

    def __init__(self, library, settings, jobs, reader):
        super().__init__()
        self.library, self.settings, self.jobs, self.reader = library, settings, jobs, reader
        self.only_favorites = False
        self.tray_available = False
        self.setWindowTitle("苇读 · Reed Reader")
        self.resize(1160, 780)
        self.setMinimumSize(820, 580)
        self.setAcceptDrops(True)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20, 30, 20, 22)
        side.setSpacing(9)
        side.addWidget(heading("苇读", "brand"))
        side.addWidget(heading("R E E D   R E A D E R", "muted"))
        side.addSpacing(38)
        side.addWidget(heading("书 房", "muted"))
        self.nav_buttons = []
        for label, action in [("▤   我的书架", lambda: self.show_library(False)),
                              ("☆   我的收藏", lambda: self.show_library(True)),
                              ("↗   网络书架", self.show_network)]:
            button = QPushButton(label)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.clicked.connect(action)
            side.addWidget(button)
            self.nav_buttons.append(button)
        side.addStretch()
        side.addWidget(heading("让阅读，轻一点。", "muted"))
        for label, action in [("阅读设置", self.preferences), ("使用说明", self.help), ("退出苇读", self.exit_requested.emit)]:
            button = QPushButton(label)
            button.clicked.connect(action)
            side.addWidget(button)
        side.addSpacing(12)
        side.addWidget(heading("v0.1.0  ·  GPL-3.0\n离线优先 / Linux 原生", "muted"))
        layout.addWidget(sidebar)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        page = QWidget()
        body = QVBoxLayout(page)
        body.setContentsMargins(32, 28, 32, 20)
        body.setSpacing(20)
        header = QHBoxLayout()
        title_block = QVBoxLayout()
        self.page_title = heading("我的书架")
        title_block.addWidget(self.page_title)
        self.count_label = heading("把喜欢的故事，放在触手可及的地方。", "muted")
        title_block.addWidget(self.count_label)
        header.addLayout(title_block, 1)
        import_button = QPushButton("＋ 导入书籍")
        import_button.setObjectName("primary")
        import_button.clicked.connect(self.choose_files)
        header.addWidget(import_button)
        body.addLayout(header)
        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        copy = QVBoxLayout()
        copy.addWidget(heading("给自己，一页的时间。", "heroTitle"))
        self.continue_label = heading("导入一本书，或从原创示例开始。", "heroCopy")
        copy.addWidget(self.continue_label)
        hero_layout.addLayout(copy, 1)
        self.continue_button = QPushButton("开始阅读  →")
        self.continue_button.clicked.connect(self.continue_reading)
        hero_layout.addWidget(self.continue_button)
        body.addWidget(hero)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索书名或作者…")
        self.search.textChanged.connect(self.refresh)
        filters.addWidget(self.search, 1)
        self.layout_button = QPushButton("列表视图")
        self.layout_button.clicked.connect(self.toggle_layout)
        filters.addWidget(self.layout_button)
        body.addLayout(filters)
        self.books = BookList()
        self.books.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.books.customContextMenuRequested.connect(self.context_menu)
        self.books.itemActivated.connect(self.open_item)
        body.addWidget(self.books, 1)
        self.empty = QLabel("书架还是空的\n\n把 TXT / EPUB / MOBI 拖到这里，或点击右上方导入书籍。")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setObjectName("muted")
        body.addWidget(self.empty)
        bottom = QHBoxLayout()
        bottom.addWidget(heading("TXT · EPUB · MOBI     /     自动记住上次读到的地方", "muted"), 1)
        sample = QPushButton("打开示例")
        sample.clicked.connect(self.open_demo)
        bottom.addWidget(sample)
        body.addLayout(bottom)
        self.stack.addWidget(page)
        self.network = NetworkPanel(library, settings, jobs)
        self.network.imported.connect(self.open_book)
        self.network.pull_requested.connect(self.pull_progress)
        self.network.status.connect(self.notify)
        self.stack.addWidget(self.network)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(400)
        self.refresh_timer.timeout.connect(self.refresh)
        reader.changed.connect(lambda: self.refresh_timer.start())
        reader.settings_requested.connect(self.preferences)
        reader.shelf_requested.connect(self.show_shelf)
        reader.message.connect(self.notify)
        shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        shortcut.activated.connect(self.choose_files)
        self.show_library(False)
        self.books.set_grid(settings.local.get("grid", True))
        self.layout_button.setText("列表视图" if self.books.grid else "封面视图")
        geometry = settings.local.get("main_geometry")
        if isinstance(geometry, str):
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))

    def notify(self, message):
        self.statusBar().showMessage(message)

    def show_library(self, favorites=False):
        self.only_favorites = favorites
        self.stack.setCurrentIndex(0)
        self.page_title.setText("我的收藏" if favorites else "我的书架")
        self.select_nav(1 if favorites else 0)
        self.refresh()

    def select_nav(self, selected):
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == selected)

    def show_network(self):
        self.stack.setCurrentIndex(1)
        self.select_nav(2)

    def show_shelf(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def refresh(self):
        entries = self.library.entries()
        query = self.search.text().casefold()
        filtered = [e for e in entries if (not self.only_favorites or e.favorite)
                    and query in (e.title + " " + e.author).casefold()]
        self.books.populate(filtered)
        self.empty.setVisible(not filtered)
        self.books.setVisible(bool(filtered))
        self.count_label.setText(f"{len(filtered)} 本藏书  ·  每一页，都有新的风景。")
        if entries:
            self.continue_label.setText(f"上次读到  ·  {entries[0].title[:25]}  /  第 {entries[0].chapter + 1} 章")
            self.continue_button.setText("继续阅读  →")
        else:
            self.continue_label.setText("导入一本书，或从原创示例开始。")
            self.continue_button.setText("开始阅读  →")

    def toggle_layout(self):
        self.books.set_grid(not self.books.grid)
        self.layout_button.setText("列表视图" if self.books.grid else "封面视图")
        self.settings.local["grid"] = self.books.grid

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "导入书籍", str(Path.home()),
                                               "电子书 (*.txt *.epub *.mobi *.azw *.azw3)")
        if paths:
            self.import_paths([Path(p) for p in paths])

    def import_paths(self, paths):
        self.notify(f"正在导入 {len(paths)} 本书…")

        def work():
            books, errors = [], []
            for path in paths:
                try:
                    books.append(import_file(path))
                except Exception as exc:
                    errors.append(f"{path.name}：{exc}")
            return books, errors

        def done(result):
            books, errors = result
            existing = {e.id for e in self.library.entries()}
            for book_id, book in books:
                self.library.add(book_id, book)
            self.refresh()
            duplicates = sum(book_id in existing for book_id, _ in books)
            self.notify(f"导入完成：{len(books) - duplicates} 本新增，{duplicates} 本已在书架，{len(errors)} 本失败。")
            if errors:
                QMessageBox.warning(self, "部分文件未导入", "\n\n".join(errors))

        self.jobs.run(work, done, lambda error: self.notify("导入失败：" + error))

    def open_item(self, item):
        if item:
            self.open_book(item.data(Qt.ItemDataRole.UserRole).id)

    def open_book(self, book_id):
        self.reader.open_book(book_id)
        self.refresh()

    def continue_reading(self):
        entries = self.library.entries()
        if entries:
            self.open_book(entries[0].id)
        else:
            self.open_demo()

    def open_demo(self):
        self.library.add("de000000-reed-original-demo", demo_book())
        self.open_book("de000000-reed-original-demo")

    def pull_progress(self, book_id, chapter, offset):
        if self.reader.book_id != book_id:
            self.reader.open_book(book_id)
        self.reader.load_chapter(chapter, offset, utf16=True)

    def context_menu(self, point):
        item = self.books.itemAt(point)
        if not item:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction("开始阅读", lambda: self.open_book(entry.id))
        menu.addAction("取消收藏" if entry.favorite else "加入收藏", lambda: self.set_favorite(entry))
        menu.addSeparator()
        menu.addAction("移出书架…", lambda: self.remove(entry))
        menu.exec(self.books.mapToGlobal(point))

    def set_favorite(self, entry):
        self.library.favorite(entry.id, not entry.favorite)
        self.refresh()

    def remove(self, entry):
        response = QMessageBox.question(self, "移出书架", f"移除《{entry.title}》及其进度、书签和缓存？\n原始文件不会被删除。")
        if response == QMessageBox.StandardButton.Yes:
            if self.reader.book_id == entry.id:
                self.reader.hide()
                self.reader.book_id = None
                self.reader.pending = None
            self.library.remove(entry.id)
            self.refresh()

    def preferences(self):
        dialog = PreferencesDialog(self.settings, self.reader if self.reader.isVisible() else self)
        dialog.applied.connect(self.reader.apply_settings)
        dialog.applied.connect(self.preferences_changed.emit)
        dialog.exec()

    def help(self):
        QMessageBox.information(self, "使用苇读", "导入：Ctrl+O 或拖入 TXT / EPUB / MOBI。\n"
                                "阅读器：方向键 / 滚轮翻页，Ctrl+F 目录与搜索，Ctrl+B 加书签。\n"
                                "Ctrl+M 切换小窗，F11 沉浸阅读，Esc 隐藏。\n"
                                "默认全局键：Alt+Z 上页，Alt+C 下页，Alt+V 显隐，Ctrl+Alt+H 隐藏全部。\n\n"
                                "小窗拖动：拖拽顶部标题；缩放：右下角。\n"
                                "关闭书架时有托盘则继续运行，无托盘则退出。\n"
                                "网络：填写阅读 App 的 Web 服务地址；进度手动拉取 / 推送。\n\n"
                                "本软件为独立开源实现，与 Fish-book 无隶属关系。\n许可证：GPL-3.0-only。")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.import_paths(paths)
            event.acceptProposedAction()

    def closeEvent(self, event):
        self.settings.local["main_geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        if self.tray_available:
            self.hide()
            event.ignore()
        else:
            self.exit_requested.emit()
            event.accept()
