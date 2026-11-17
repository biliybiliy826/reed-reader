from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from reed_reader.canvas import paginate
from reed_reader.jobs import Jobs
from reed_reader.models import Book, Chapter
from reed_reader.preferences_dialog import PreferencesDialog
from reed_reader.reader import Reader
from reed_reader.reader_dialogs import NavigationDialog
from reed_reader.settings import Settings
from reed_reader.storage import Library
from reed_reader.style import STYLE
from reed_reader.window import MainWindow


def make_reader(qtbot, tmp_path):
    library = Library(tmp_path / "library.db")
    settings = Settings(tmp_path / "settings.json")
    jobs = Jobs()
    reader = Reader(library, settings, jobs)
    qtbot.addWidget(reader)
    return library, settings, jobs, reader


def wait_jobs(qtbot, jobs):
    qtbot.waitUntil(lambda: not jobs.tasks, timeout=6000)


def test_pagination_preserves_every_character_and_emoji(qapp):
    text = ("中文😀 abc e\u0301 العربية\n\n" * 70) + "终点"
    for preserve in [True, False]:
        position = 0
        pieces = []
        while position < len(text):
            page = paginate(text, position, 180, 115, QFont("DejaVu Sans", 15), 1.4, preserve)
            assert position < page.end <= len(text)
            pieces.append(text[position:page.end])
            position = page.end
        assert "".join(pieces) == text
        assert len(pieces) > 10


def test_reader_turn_resize_resume_and_bookmarks(qtbot, tmp_path):
    library, settings, jobs, reader = make_reader(qtbot, tmp_path)
    text = "第一章\n\n" + "安静地翻开一页，看看窗外的风景。😀\n" * 100
    library.add("aa", Book("示例", chapters=[Chapter("第一章", text), Chapter("第二章", "结尾")]))
    reader.resize(500, 350)
    reader.open_book("aa")
    qtbot.wait(30)
    first_end = reader.canvas.page.end
    assert 0 < first_end < len(text)
    reader.turn(1)
    assert reader.offset == first_end
    reader.add_bookmark()
    assert library.bookmarks("aa")[0]["offset"] == first_end
    reader.turn(-1)
    assert reader.offset == 0
    reader.turn(1)
    reader.resize(600, 400)
    qtbot.wait(20)
    assert reader.offset == first_end
    assert library.entry("aa").offset == first_end
    reader.hide()
    reader.open_book("aa")
    assert reader.offset == first_end
    reader.hide()
    wait_jobs(qtbot, jobs)


def test_mini_mode_hiding_and_auto_timer(qtbot, tmp_path):
    library, settings, jobs, reader = make_reader(qtbot, tmp_path)
    library.add("aa", Book("示例", chapters=[Chapter("一", "文字" * 2000)]))
    reader.open_book("aa")
    reader.toggle_mini()
    qtbot.wait(30)
    assert reader.height() < 300
    assert reader.mini and not reader.toolbar.isVisible()
    assert reader.windowFlags() & Qt.WindowType.FramelessWindowHint
    reader.auto_button.setChecked(True)
    assert reader.timer.isActive()
    reader.hide()
    assert not reader.timer.isActive()
    reader.show()
    assert reader.timer.isActive()
    reader.toggle_mini()
    assert not reader.mini and reader.toolbar.isVisible()
    reader.hide()
    assert "mini_geometry" in settings.local


def test_final_page_remains_visible_after_reopen(qtbot, tmp_path):
    library, _, _, reader = make_reader(qtbot, tmp_path)
    library.add("aa", Book("短篇", chapters=[Chapter("一", "这里是结尾。")]))
    reader.open_book("aa")
    reader.turn(1)
    reader.open_book("aa")
    assert reader.canvas.offset == 0
    assert reader.progress.value() == 10000
    reader.hide()


def test_search_and_settings_apply(qtbot, tmp_path):
    library, settings, jobs, reader = make_reader(qtbot, tmp_path)
    library.add("aa", Book("测试", chapters=[Chapter("一", "前文 😀 找到这里 后文")]))
    reader.open_book("aa")
    dialog = NavigationDialog(library, "aa", reader.load_chapter, reader)
    qtbot.addWidget(dialog)
    dialog.query.setText("找到这里")
    dialog.search()
    assert dialog.results.count() == 1
    dialog.activate(dialog.results.item(0))
    assert reader.offset == 5
    preferences = PreferencesDialog(settings)
    qtbot.addWidget(preferences)
    preferences.controls["font_size"].setValue(24)
    preferences.controls["background_opacity"].setValue(30)
    preferences.applied.connect(reader.apply_settings)
    preferences.save()
    assert settings.preferences.font_size == 24
    assert reader.canvas.preferences.background_opacity == 30
    assert Settings(settings.path).preferences.font_size == 24
    reader.hide()


def test_library_import_and_favorite_filter(qtbot, tmp_path, qapp):
    qapp.setStyleSheet(STYLE)
    library, settings, jobs, reader = make_reader(qtbot, tmp_path)
    window = MainWindow(library, settings, jobs, reader)
    qtbot.addWidget(window)
    window.show()
    path = tmp_path / "新书.txt"
    path.write_text("第一章 风\n这是一段正文。\n第二章 雨\n又一段正文。")
    window.import_paths([path])
    wait_jobs(qtbot, jobs)
    assert len(library.entries()) == 1
    entry = library.entries()[0]
    window.set_favorite(entry)
    window.show_library(True)
    assert window.books.count() == 1
    window.search.setText("不存在")
    assert window.books.count() == 0
    window.search.setText("新书")
    assert window.books.count() == 1
    window.open_item(window.books.item(0))
    assert reader.isVisible()
    window.hide()
    assert reader.isVisible(), "reader must be independent of the shelf window"
    reader.hide()


def test_network_import_prefetch_explicit_sync_and_offline_cache(qtbot, tmp_path, service):
    endpoint, state = service
    library, settings, jobs, reader = make_reader(qtbot, tmp_path)
    window = MainWindow(library, settings, jobs, reader)
    qtbot.addWidget(window)
    panel = window.network
    panel.endpoint.setText(endpoint)
    panel.connect_service()
    wait_jobs(qtbot, jobs)
    assert panel.books.count() == 1
    panel.books.setCurrentRow(0)
    panel.open_selected()
    wait_jobs(qtbot, jobs)
    entry = library.entries()[0]
    assert reader.offset == 2, "Android UTF-16 position must become a Python character offset"
    assert library.chapter(entry.id, 1).text is not None, "next chapter is prefetched"
    assert not state["posts"], "reading must not implicitly overwrite phone progress"
    reader.turn(1)
    panel.push_selected()
    wait_jobs(qtbot, jobs)
    assert len(state["posts"]) == 1
    request_count = len(state["requests"])
    state["fail"] = True
    reader.load_chapter(1)
    assert not reader.loading
    assert len(state["requests"]) == request_count
    assert "网络正文" in reader.text
    reader.hide()


def test_seek_to_end_shows_last_page_instead_of_blank(qtbot, tmp_path):
    library, _, _, reader = make_reader(qtbot, tmp_path)
    text = "这是很长的一段故事。" * 150 + "最终一句。"
    library.add("aa", Book("示例", chapters=[Chapter("一", text)]))
    reader.open_book("aa")
    reader.progress.setValue(10000)
    reader.seek()
    assert reader.offset < len(text)
    assert reader.canvas.page.end == len(text)
    assert reader.progress.value() == 10000
    reader.hide()
