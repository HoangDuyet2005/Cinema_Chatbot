from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlparse

import httpx

from .contracts import IngestionDocument


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.links: list[str] = []
        self._skip_depth = 0
        self._in_title = False
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"p", "div", "li", "br", "h1", "h2", "h3"}:
            self._text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text or self._skip_depth:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
        self._text_parts.append(text)

    @property
    def readable_text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self._text_parts).splitlines()]
        return "\n".join(line for line in lines if line)


def crawl_page(url: str, source_type: str = "WEB_PAGE") -> IngestionDocument:
    response = httpx.get(url, timeout=20, follow_redirects=True)
    response.raise_for_status()

    parser = _ReadableHtmlParser()
    parser.feed(response.text)

    parsed_url = urlparse(str(response.url))
    title = parser.title or parsed_url.path.strip("/") or parsed_url.netloc
    source_id = str(response.url).rstrip("/")

    return IngestionDocument(
        source_type=source_type,
        source_id=source_id,
        title=title,
        content=parser.readable_text,
        source_url=str(response.url),
        metadata={"links": _same_site_links(str(response.url), parser.links)},
    )


def _same_site_links(base_url: str, links: Iterable[str]) -> list[str]:
    base_host = urlparse(base_url).netloc
    normalized: list[str] = []
    seen: set[str] = set()
    for link in links:
        absolute = urljoin(base_url, link).split("#", 1)[0].rstrip("/")
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != base_host:
            continue
        if absolute not in seen:
            seen.add(absolute)
            normalized.append(absolute)
    return normalized
