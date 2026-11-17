"""Domain values. All reading offsets count Python Unicode code points."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Chapter:
    title: str
    text: str | None


@dataclass(frozen=True)
class Book:
    title: str
    author: str = ""
    chapters: list[Chapter] = field(default_factory=list)
    format: str = "TXT"


@dataclass(frozen=True)
class Entry:
    id: str
    title: str
    author: str
    format: str
    favorite: bool
    chapter: int
    offset: int
    count: int
    updated: float
    endpoint: str = ""
    remote_url: str = ""


@dataclass(frozen=True)
class SearchHit:
    chapter: int
    offset: int
    title: str
    excerpt: str
