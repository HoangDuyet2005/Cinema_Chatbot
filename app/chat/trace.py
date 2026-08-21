import time
from typing import Any


class ChatTrace:
    def __init__(self, query: str) -> None:
        self.started_at = time.perf_counter()
        self.payload: dict[str, Any] = {
            "original_query": query,
            "enriched_query": query,
            "search_query": query,
            "cache_status": "skip",
            "top_retrieved_sources": [],
            "final_sources": [],
            "latency_ms": 0,
        }

    def set(self, key: str, value: Any) -> None:
        self.payload[key] = value

    def top_sources(self, docs: list[dict[str, Any]] | None, limit: int = 8) -> None:
        self.payload["top_retrieved_sources"] = [
            {
                "type": doc.get("source_type"),
                "id": doc.get("source_id"),
                "title": doc.get("source_title"),
                "score": _score(doc),
                "chunkIndex": doc.get("chunk_index"),
            }
            for doc in (docs or [])[:limit]
        ]

    def final_sources(self, sources: list[dict[str, Any]] | None) -> None:
        self.payload["final_sources"] = sources or []

    def finish(self) -> dict[str, Any]:
        self.payload["latency_ms"] = round((time.perf_counter() - self.started_at) * 1000)
        return self.payload


def _score(doc: dict[str, Any]) -> float | None:
    for key in ("rerank_score", "hybrid_score", "score", "similarity"):
        value = doc.get(key)
        if isinstance(value, (int, float)):
            return round(float(value), 4)
    return None
