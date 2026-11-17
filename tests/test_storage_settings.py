import json

import pytest

from reed_reader.models import Book, Chapter
from reed_reader.settings import Preferences, Settings
from reed_reader.storage import Library


def test_import_dedup_progress_bookmarks_and_remove(tmp_path):
    path = tmp_path / "library.sqlite3"
    library = Library(path)
    book = Book("测试", "作者", [Chapter("第一章", "正文😀 needle"), Chapter("第二章", "另一章")])
    library.add("aa", book)
    library.add("aa", book)
    library.favorite("aa", True)
    library.progress("aa", 1, 2)
    library.bookmark("aa", 1, 2, "位置")
    library.bookmark("aa", 1, 2, "位置")
    assert len(library.entries()) == 1
    assert len(library.bookmarks("aa")) == 1
    hit = library.search("aa", "NEEDLE")[0]
    assert hit.offset == 4
    library.close()
    reopened = Library(path)
    entry = reopened.entry("aa")
    assert (entry.chapter, entry.offset, entry.favorite) == (1, 2, True)
    reopened.remove("aa")
    assert not reopened.entries()
    assert not reopened.bookmarks("aa")
    assert not reopened.chapters("aa")
    reopened.close()


def test_invalid_progress_is_rejected_and_offset_clamped(tmp_path):
    library = Library(tmp_path / "lib.db")
    library.add("a", Book("书", chapters=[Chapter("一", "正文")]))
    library.progress("a", 0, 100)
    assert library.entry("a").offset == 2
    with pytest.raises(ValueError):
        library.progress("a", 2, 0)
    library.close()


def test_remote_identity_and_cache(tmp_path):
    library = Library(tmp_path / "lib.db")
    book = Book("网络书", chapters=[Chapter("一", None)], format="WEB")
    first = library.add_remote(book, "http://one", "https://book")
    second = library.add_remote(book, "http://two", "https://book")
    assert first != second
    library.cache(first, 0, "缓存")
    assert library.chapter(first, 0).text == "缓存"
    assert library.chapter(second, 0).text is None
    library.close()


def test_settings_roundtrip_and_share_excludes_private_state(tmp_path):
    settings = Settings(tmp_path / "settings.json")
    settings.preferences.font_size = 27
    settings.local = {"endpoint": "http://phone:1234", "main_geometry": "opaque"}
    settings.save()
    loaded = Settings(settings.path)
    assert loaded.preferences.font_size == 27
    assert "endpoint" not in loaded.export()
    assert "geometry" not in loaded.export()
    loaded.import_code(settings.export())
    assert loaded.local["endpoint"] == "http://phone:1234"
    assert not settings.path.with_suffix(".tmp").exists()


@pytest.mark.parametrize("data", [{"font_size": True}, {"font_size": 90}, {"line_spacing": float('nan')},
                                   {"background": "red"}, {"wheel_pages": 1}, {"unknown": 1},
                                   {"next_key": "Alt+Z"}])
def test_invalid_settings(data):
    with pytest.raises(ValueError):
        Preferences.parse(data)


def test_malformed_settings_are_preserved(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("not json")
    settings = Settings(path)
    assert settings.warning
    assert path.read_text() == "not json"
    with pytest.raises(ValueError):
        settings.import_code(json.dumps({"reed_reader": 1, "preferences": {"font_size": 999}}))
    assert settings.preferences.font_size == Preferences().font_size


def test_refresh_remote_preserves_state_and_rejects_reordering(tmp_path):
    library = Library(tmp_path / "lib.db")
    book_id = library.add_remote(Book("连载", chapters=[Chapter("一", "正文")]), "http://phone", "book")
    library.progress(book_id, 0, 1)
    library.bookmark(book_id, 0, 1, "书签")
    assert library.refresh_remote(book_id, Book("连载", chapters=[Chapter("一", None), Chapter("二", None)])) == 1
    assert library.chapter(book_id, 0).text == "正文"
    assert library.entry(book_id).offset == 1
    assert len(library.bookmarks(book_id)) == 1
    with pytest.raises(ValueError, match="顺序"):
        library.refresh_remote(book_id, Book("连载", chapters=[Chapter("不同", None)]))
    assert library.entry(book_id).count == 2
    library.close()
