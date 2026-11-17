"""Legado Web API client. No bundled book sources or implicit progress writes."""

import json
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .models import Book, Chapter

MAX_RESPONSE = 8 * 1024 * 1024


class NetworkFailure(ValueError):
    pass


def endpoint_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise NetworkFailure("请输入完整 HTTP(S) 地址，例如 http://192.168.1.20:1234。")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise NetworkFailure("服务地址不能包含账号、密码、查询参数或片段。")
    try:
        _port = parts.port  # Access validates the port, including non-numeric values.
    except ValueError as exc:
        raise NetworkFailure("端口格式错误。") from exc
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


@dataclass(frozen=True)
class RemoteBook:
    url: str
    title: str
    author: str
    chapter: int
    position_utf16: int


def integer(value, field: str) -> int:
    if type(value) is not int or value < 0:
        raise NetworkFailure(f"服务返回的 {field} 不是非负整数。")
    return value


def remote_book(row) -> RemoteBook:
    if not isinstance(row, dict) or not isinstance(row.get("bookUrl"), str) or not row["bookUrl"]:
        raise NetworkFailure("书架条目缺少 bookUrl。")
    if not isinstance(row.get("name"), str) or not isinstance(row.get("author", ""), str):
        raise NetworkFailure("书架条目的书名或作者格式错误。")
    return RemoteBook(row["bookUrl"], row["name"], row.get("author", ""),
                      integer(row.get("durChapterIndex", 0), "durChapterIndex"),
                      integer(row.get("durChapterPos", 0), "durChapterPos"))


def from_utf16(text: str, offset: int) -> int:
    return len(text.encode("utf-16-le")[:max(0, offset) * 2].decode("utf-16-le", errors="ignore"))


def to_utf16(text: str, offset: int) -> int:
    return len(text[:offset].encode("utf-16-le")) // 2


class Legado:
    def __init__(self, endpoint: str, timeout: float = 12):
        self.endpoint = endpoint_url(endpoint)
        self.timeout = timeout

    def request(self, route: str, query=None, payload=None):
        url = self.endpoint + "/" + route
        if query:
            url += "?" + urlencode(query)
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=body, headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise NetworkFailure("响应超过 8 MiB，已停止读取。")
            result = json.loads(raw)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise NetworkFailure(f"无法连接阅读服务：{exc}") from exc
        except (ValueError, UnicodeError) as exc:
            raise NetworkFailure("服务未返回有效 JSON；请检查地址和 Web 服务是否开启。") from exc
        if not isinstance(result, dict) or result.get("isSuccess") is not True:
            message = result.get("errorMsg", "响应缺少 isSuccess=true") if isinstance(result, dict) else "响应不是对象"
            raise NetworkFailure(str(message))
        return result.get("data")

    def bookshelf(self) -> list[RemoteBook]:
        rows = self.request("getBookshelf")
        if not isinstance(rows, list):
            raise NetworkFailure("书架响应不是数组。")
        return [remote_book(row) for row in rows]

    def book(self, remote: RemoteBook) -> Book:
        rows = self.request("getChapterList", {"url": remote.url})
        if not isinstance(rows, list) or not rows:
            raise NetworkFailure("网络书籍没有目录。")
        chapters = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("title"), str):
                raise NetworkFailure("章节目录格式错误。")
            chapters.append(Chapter(row["title"], None))
        return Book(remote.title, remote.author, chapters, "WEB")

    def content(self, url: str, index: int) -> str:
        content = self.request("getBookContent", {"url": url, "index": index})
        if not isinstance(content, str) or not content.strip():
            raise NetworkFailure("服务返回了空白或无效的章节正文。")
        return content

    def push(self, remote: RemoteBook, chapter: int, offset: int, text: str, title: str):
        return self.request("saveBookProgress", payload={
            "name": remote.title, "author": remote.author,
            "durChapterIndex": chapter, "durChapterPos": to_utf16(text, offset),
            "durChapterTime": int(time.time() * 1000), "durChapterTitle": title,
        })
