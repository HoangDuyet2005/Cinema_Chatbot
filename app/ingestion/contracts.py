from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IngestionDocument:
    """Normalized document shape accepted by the RAG ingestion boundary."""

    source_type: str
    source_id: str | int
    title: str
    content: str
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_sync_payload(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "source_title": self.title,
            "source_url": self.source_url,
            "content": self.content,
            "metadata": self.metadata,
        }
