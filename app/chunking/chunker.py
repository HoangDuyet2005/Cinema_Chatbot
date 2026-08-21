import html
import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from .chunk_policy import DEFAULT_CHUNK_POLICY, ChunkPolicy


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    word_count: int


@dataclass(frozen=True)
class SourceChunk:
    source_type: str
    source_id: int
    content_chunk: str
    chunk_index: int
    source_title: str
    chunk_metadata: str


def strip_html(value: str) -> str:
    if not value:
        return ""

    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", value, flags=re.I)
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(p|div|section|article|li|tr|h[1-6])>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text)


def clean_text(value: str) -> str:
    text = strip_html(value)
    text = text.replace("\ufeff", " ")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _words(value: str) -> list[str]:
    return [word for word in re.split(r"\s+", value.strip()) if word]


def _paragraphs(value: str) -> list[str]:
    return [
        paragraph.strip()
        for paragraph in re.split(r"\n{2,}", value)
        if paragraph.strip()
    ]


def _window_chunks(words: list[str], max_words: int, overlap: int) -> list[list[str]]:
    if not words:
        return []
    step = max(1, max_words - overlap)
    windows = []
    start = 0
    while start < len(words):
        window = words[start:start + max_words]
        if window:
            windows.append(window)
        if start + max_words >= len(words):
            break
        start += step
    return windows


def chunk_text(text: str, policy: Optional[ChunkPolicy] = None) -> list[TextChunk]:
    policy = (policy or DEFAULT_CHUNK_POLICY).normalized()
    cleaned = clean_text(text)
    if not cleaned:
        return []

    units = _paragraphs(cleaned) if policy.preserve_paragraphs else [cleaned]
    chunks: list[list[str]] = []
    current: list[str] = []

    for unit in units:
        unit_words = _words(unit)
        if not unit_words:
            continue

        if len(unit_words) > policy.max_words:
            if current:
                chunks.append(current)
                current = []
            chunks.extend(_window_chunks(unit_words, policy.max_words, policy.overlap))
            continue

        if current and len(current) + len(unit_words) > policy.max_words:
            chunks.append(current)
            current = current[-policy.overlap:] if policy.overlap else []

        if len(current) + len(unit_words) > policy.max_words:
            chunks.append(current)
            current = []

        current.extend(unit_words)

    if current:
        chunks.append(current)

    return [
        TextChunk(index=index, content=" ".join(words), word_count=len(words))
        for index, words in enumerate(chunks)
        if words
    ]


def build_chunks_for_source(
    source_type: str,
    source_id: int,
    title: str,
    raw_content: str,
    policy: Optional[ChunkPolicy] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> list[SourceChunk]:
    cleaned = clean_text(raw_content)
    text_chunks = chunk_text(cleaned, policy)

    if not text_chunks:
        text_chunks = [
            TextChunk(index=0, content=cleaned or raw_content or title, word_count=0)
        ]

    total_chunks = len(text_chunks)
    source_chunks = []
    for chunk in text_chunks:
        chunk_metadata = {
            "chunk_index": chunk.index,
            "total_chunks": total_chunks,
            "word_count": chunk.word_count,
            **(metadata or {}),
        }
        source_chunks.append(
            SourceChunk(
                source_type=source_type,
                source_id=source_id,
                content_chunk=chunk.content,
                chunk_index=chunk.index,
                source_title=title,
                chunk_metadata=json.dumps(chunk_metadata, ensure_ascii=False),
            )
        )

    return source_chunks
