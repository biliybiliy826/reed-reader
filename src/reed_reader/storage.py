"""SQLite boundary, owned by the GUI thread. Imports commit atomically."""

import hashlib
import re
import sqlite3
import time
from pathlib import Path

from .models import Book, Chapter, Entry, SearchHit


class Library:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL,
                format TEXT NOT NULL, favorite INTEGER NOT NULL DEFAULT 0,
                chapter INTEGER NOT NULL DEFAULT 0, offset INTEGER NOT NULL DEFAULT 0,
                updated REAL NOT NULL, endpoint TEXT NOT NULL DEFAULT '',
                remote_url TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS chapters (
                book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                idx INTEGER NOT NULL, title TEXT NOT NULL, text TEXT,
                PRIMARY KEY (book_id, idx)
            );
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY, book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                chapter INTEGER NOT NULL, offset INTEGER NOT NULL, label TEXT NOT NULL,
                UNIQUE(book_id, chapter, offset)
            );
        """)

    def add(self, book_id: str, book: Book, endpoint="", remote_url="") -> str:
        if not book.chapters:
            raise ValueError("书籍至少需要一章。")
        with self.db:
            exists = self.db.execute("SELECT 1 FROM books WHERE id=?", (book_id,)).fetchone()
            if not exists:
                self.db.execute(
                    "INSERT INTO books(id,title,author,format,updated,endpoint,remote_url) VALUES(?,?,?,?,?,?,?)",
                    (book_id, book.title, book.author, book.format, time.time(), endpoint, remote_url),
                )
                self.db.executemany("INSERT INTO chapters VALUES(?,?,?,?)", [
                    (book_id, i, c.title, c.text) for i, c in enumerate(book.chapters)
                ])
        return book_id

    def add_remote(self, book: Book, endpoint: str, url: str) -> str:
        book_id = hashlib.sha256(f"{endpoint}\n{url}".encode()).hexdigest()
        return self.add(book_id, book, endpoint, url)

    def entries(self) -> list[Entry]:
        rows = self.db.execute("""
            SELECT b.*, (SELECT count(*) FROM chapters c WHERE c.book_id=b.id) AS count
            FROM books b ORDER BY updated DESC
        """).fetchall()
        return [Entry(**dict(row)) for row in rows]

    def refresh_remote(self, book_id: str, book: Book) -> int:
        """Append new chapters without invalidating cached text, bookmarks or positions."""
        current = self.chapters(book_id)
        if not self.entry(book_id).endpoint:
            raise ValueError("只有网络书籍可以刷新目录。")
        if len(book.chapters) < len(current) or any(
            old.title != new.title for old, new in zip(current, book.chapters, strict=False)
        ):
            raise ValueError("远端章节顺序发生变化，已保留本机进度与缓存；请将新版作为新的书架条目导入。")
        added = book.chapters[len(current):]
        with self.db:
            self.db.executemany("INSERT INTO chapters VALUES(?,?,?,?)", [
                (book_id, len(current) + i, chapter.title, chapter.text) for i, chapter in enumerate(added)
            ])
            self.db.execute("UPDATE books SET title=?,author=? WHERE id=?", (book.title, book.author, book_id))
        return len(added)

    def entry(self, book_id: str) -> Entry:
        return next(e for e in self.entries() if e.id == book_id)

    def chapters(self, book_id: str) -> list[Chapter]:
        return [Chapter(r[0], r[1]) for r in self.db.execute(
            "SELECT title,text FROM chapters WHERE book_id=? ORDER BY idx", (book_id,)
        )]

    def chapter(self, book_id: str, index: int) -> Chapter:
        row = self.db.execute("SELECT title,text FROM chapters WHERE book_id=? AND idx=?", (book_id, index)).fetchone()
        if row is None:
            raise ValueError("章节不存在。")
        return Chapter(row[0], row[1])

    def cache(self, book_id: str, index: int, text: str):
        with self.db:
            self.db.execute("UPDATE chapters SET text=? WHERE book_id=? AND idx=?", (text, book_id, index))

    def progress(self, book_id: str, chapter: int, offset: int):
        content = self.chapter(book_id, chapter)
        offset = max(0, offset)
        if content.text is not None:
            offset = min(offset, len(content.text))
        with self.db:
            self.db.execute("UPDATE books SET chapter=?,offset=?,updated=? WHERE id=?",
                            (chapter, offset, time.time(), book_id))

    def favorite(self, book_id: str, value: bool):
        with self.db:
            self.db.execute("UPDATE books SET favorite=? WHERE id=?", (int(value), book_id))

    def remove(self, book_id: str):
        with self.db:
            self.db.execute("DELETE FROM books WHERE id=?", (book_id,))

    def bookmark(self, book_id: str, chapter: int, offset: int, label: str):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO bookmarks(book_id,chapter,offset,label) VALUES(?,?,?,?)",
                            (book_id, chapter, offset, label))

    def bookmarks(self, book_id: str):
        return self.db.execute("SELECT * FROM bookmarks WHERE book_id=? ORDER BY chapter,offset", (book_id,)).fetchall()

    def remove_bookmark(self, bookmark_id: int):
        with self.db:
            self.db.execute("DELETE FROM bookmarks WHERE id=?", (bookmark_id,))

    def search(self, book_id: str, query: str, limit=200) -> list[SearchHit]:
        if not query.strip():
            return []
        pattern = re.compile(re.escape(query), re.I)
        hits = []
        for i, chapter in enumerate(self.chapters(book_id)):
            for match in pattern.finditer(chapter.text or ""):
                p = match.start()
                excerpt = chapter.text[max(0, p - 24):p + len(query) + 48].replace("\n", " ")
                hits.append(SearchHit(i, p, chapter.title, excerpt))
                if len(hits) >= limit:
                    return hits
        return hits

    def close(self):
        self.db.close()
