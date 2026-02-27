"""Shared data models for the web app."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Citation:
    """A source citation from a search result."""

    article_id: str
    title: str
    section_header: str
    chunk_index: int
    content: str = ""
    image_urls: list[str] = field(default_factory=list)
