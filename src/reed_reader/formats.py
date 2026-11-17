"""Bounded, text-only book import. No source HTML is rendered in a browser."""

import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote
from zipfile import BadZipFile, ZipFile

from charset_normalizer import from_bytes
from defusedxml import ElementTree as ET

from .models import Book, Chapter

MAX_FILE = 64 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
CHAPTER_CHARS = 40_000
HEADING = re.compile(
    r"^\s*(?:第[〇零一二三四五六七八九十百千万两\d]+[章节卷回部篇].{0,60}"
    r"|chapter\s+\w+.{0,60}|(?:序章|序言|楔子|尾声|后记|终章))\s*$", re.I
)


class ImportFailure(ValueError):
    pass


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "head"}:
            self.ignored += 1
        elif not self.ignored and tag in {"p", "div", "br", "h1", "h2", "h3", "li", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "head"}:
            self.ignored = max(0, self.ignored - 1)
        elif not self.ignored and tag in {"p", "div", "h1", "h2", "h3", "li", "section"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def html_text(html: str) -> str:
    parser = PlainHTML()
    parser.feed(html)
    return normalize("".join(parser.parts))


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    return re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text).strip("\ufeff\n ")


def decode_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return data.decode("utf-32")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        detected = from_bytes(data, cp_isolation=["gb18030", "big5", "cp1252"]).best()
        if detected is None:
            raise ImportFailure("无法识别文本编码，请另存为 UTF-8 后导入。") from None
        return str(detected)


def split_long(title: str, text: str) -> list[Chapter]:
    result = []
    while len(text) > CHAPTER_CHARS:
        end = text.rfind("\n", CHAPTER_CHARS // 2, CHAPTER_CHARS)
        end = end + 1 if end >= 0 else CHAPTER_CHARS
        result.append(Chapter(title if not result else f"{title} · {len(result) + 1}", text[:end]))
        text = text[end:]
    if text:
        result.append(Chapter(title if not result else f"{title} · {len(result) + 1}", text))
    return result


def parse_txt(data: bytes, title: str) -> Book:
    text = normalize(decode_text(data))
    if not text:
        raise ImportFailure("这本书没有可阅读的文字。")
    chapters = []
    current_title, lines = "正文", []
    for line in text.splitlines(keepends=True):
        if HEADING.fullmatch(line.rstrip("\n")):
            if "".join(lines).strip():
                chapters.extend(split_long(current_title, "".join(lines)))
            current_title, lines = line.strip(), [line]
        else:
            lines.append(line)
    chapters.extend(split_long(current_title, "".join(lines)))
    return Book(title, chapters=chapters, format="TXT")


def epub_path(base: str, href: str) -> str:
    path = posixpath.normpath(posixpath.join(base, unquote(href.split("#")[0])))
    if path.startswith(("../", "/")) or ":" in path:
        raise ImportFailure("EPUB 包含非法的资源路径。")
    return path


def parse_epub(path: Path) -> Book:
    try:
        with ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > 10000 or sum(i.file_size for i in members) > MAX_EXPANDED:
                raise ImportFailure("EPUB 解压后过大（上限 128 MiB / 10000 个文件）。")
            if "META-INF/encryption.xml" in archive.namelist():
                encryption = ET.fromstring(archive.read("META-INF/encryption.xml"))
                for method in encryption.iter():
                    if method.tag.endswith("EncryptionMethod") and method.get("Algorithm") not in {
                        "http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC"
                    }:
                        raise ImportFailure("不支持受 DRM 加密的 EPUB。")
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = container.find(".//{*}rootfile")
            if rootfile is None or not rootfile.get("full-path"):
                raise ImportFailure("EPUB 缺少包描述文件。")
            opf_path = epub_path("", rootfile.get("full-path"))
            package = ET.fromstring(archive.read(opf_path))
            title_el = package.find(".//{*}metadata/{*}title")
            author_el = package.find(".//{*}metadata/{*}creator")
            title = title_el.text if title_el is not None and title_el.text else path.stem
            author = author_el.text if author_el is not None and author_el.text else ""
            manifest = {item.get("id"): item for item in package.findall(".//{*}manifest/{*}item")}
            chapters = []
            for ref in package.findall(".//{*}spine/{*}itemref"):
                if ref.get("linear") == "no":
                    continue
                item = manifest.get(ref.get("idref"))
                if item is None:
                    raise ImportFailure("EPUB 阅读顺序引用了不存在的资源。")
                if item.get("media-type") not in {"application/xhtml+xml", "text/html"}:
                    continue
                resource = epub_path(posixpath.dirname(opf_path), item.get("href", ""))
                text = html_text(decode_text(archive.read(resource)))
                if text:
                    heading = next((line.strip() for line in text.splitlines() if line.strip()), "正文")
                    chapters.extend(split_long(heading[:90], text))
            if not chapters:
                raise ImportFailure("EPUB 中没有可阅读的正文。")
            return Book(title, author, chapters, "EPUB")
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise ImportFailure(f"EPUB 文件损坏：{exc}") from exc


def parse_mobi(path: Path) -> Book:
    with tempfile.TemporaryDirectory(prefix="reed-mobi-") as directory:
        root = Path(directory)
        result = root / "result.json"
        try:
            process = subprocess.run(
                [sys.executable, "-m", "reed_reader.mobi_worker", str(path.resolve()), str(result)],
                env={**os.environ, "TMPDIR": directory}, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, timeout=45, check=False,
            )
            if process.returncode != 0 or not result.exists():
                detail = process.stderr.decode(errors="replace")[-1500:]
                raise ImportFailure("MOBI 解析失败（仅支持无 DRM 文件）：" + detail)
            extracted = Path(json.loads(result.read_text())["output"]).resolve()
            if not extracted.is_relative_to(root) or extracted.stat().st_size > MAX_EXPANDED:
                raise ImportFailure("MOBI 提取路径非法或正文超过 128 MiB。")
            if extracted.suffix.lower() == ".epub":
                book = parse_epub(extracted)
                return Book(book.title, book.author, book.chapters, "MOBI")
            if extracted.suffix.lower() not in {".html", ".htm"}:
                raise ImportFailure("该 MOBI 不含可读取的 HTML/EPUB 正文。")
            text = html_text(decode_text(extracted.read_bytes()))
            book = parse_txt(text.encode("utf-8"), path.stem)
            return Book(book.title, book.author, book.chapters, "MOBI")
        except subprocess.TimeoutExpired as exc:
            raise ImportFailure("MOBI 解析超过 45 秒，已停止。") from exc


def import_file(path: Path) -> tuple[str, Book]:
    if not path.is_file() or path.stat().st_size > MAX_FILE:
        raise ImportFailure("请选择不超过 64 MiB 的本地书籍。")
    suffix = path.suffix.lower()
    if suffix not in {".txt", ".epub", ".mobi", ".azw", ".azw3"}:
        raise ImportFailure(f"不支持 {suffix} 格式，请使用 TXT / EPUB / MOBI。")
    data = path.read_bytes()
    book = parse_txt(data, path.stem) if suffix == ".txt" else (
        parse_epub(path) if suffix == ".epub" else parse_mobi(path)
    )
    return hashlib.sha256(data).hexdigest(), book
