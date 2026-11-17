from pathlib import Path

import pytest

from reed_reader.formats import CHAPTER_CHARS, ImportFailure, import_file, parse_epub, parse_txt

from .book_fixtures import epub, mobi


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-32", "gb18030"])
def test_txt_chapters_and_chinese_encoding(encoding):
    text = "序言\n开头文字。\n第一章 清晨\n窗边的光照在桌面上。\n第二章 夜晚\n灯亮了。"
    book = parse_txt(text.encode(encoding), "光")
    assert [c.title for c in book.chapters] == ["序言", "第一章 清晨", "第二章 夜晚"]
    assert "".join(c.text for c in book.chapters) == text


def test_long_text_is_split_without_loss():
    text = "甲乙😀" * (CHAPTER_CHARS // 2)
    book = parse_txt(text.encode(), "长篇")
    assert len(book.chapters) > 1
    assert "".join(c.text for c in book.chapters) == text
    assert all(len(c.text) <= CHAPTER_CHARS for c in book.chapters)


def test_epub_spine_order_and_text_only(tmp_path):
    book = parse_epub(epub(tmp_path / "sample.epub"))
    assert book.title == "测试之书"
    assert book.author == "苇读"
    assert [c.title for c in book.chapters] == ["第二章", "第一章"]
    assert "正文甲😀" in book.chapters[1].text
    assert "alert" not in book.chapters[1].text
    assert "禁止展示" not in book.chapters[1].text


def test_epub_rejects_traversal(tmp_path):
    with pytest.raises(ImportFailure, match="资源路径"):
        parse_epub(epub(tmp_path / "bad.epub", bad_href=True))


def test_invalid_and_empty_files(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_bytes(b"")
    with pytest.raises(ImportFailure):
        import_file(path)
    path = tmp_path / "broken.epub"
    path.write_bytes(b"not a zip")
    with pytest.raises(ImportFailure, match="损坏"):
        import_file(path)


def test_real_mobi_decoder(tmp_path):
    _, book = import_file(mobi(tmp_path / "fixture.mobi"))
    assert book.format == "MOBI"
    assert "原创的 MOBI 测试文本" in "".join(c.text for c in book.chapters)


def test_mobi_failure_cleans_temporary_directory(tmp_path, monkeypatch):
    import reed_reader.formats as formats
    original = formats.tempfile.TemporaryDirectory
    directories = []

    def track(**kwargs):
        context = original(dir=tmp_path, **kwargs)
        directories.append(Path(context.name))
        return context

    monkeypatch.setattr(formats.tempfile, "TemporaryDirectory", track)
    path = tmp_path / "broken.mobi"
    path.write_bytes(b"broken")
    with pytest.raises(ImportFailure):
        import_file(path)
    assert directories and all(not p.exists() for p in directories)
