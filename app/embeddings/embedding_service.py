from dataclasses import dataclass
from typing import Optional

from app.retrieval.hybrid_search import hybrid_search_engine
from app.vectorstore.postgres_vector_store import (
    VectorChunkInput,
    postgres_vector_store,
)
from cache_manager import clear_semantic_cache

from .ollama_embedder import ollama_embedder


@dataclass(frozen=True)
class SyncChunkInput:
    source_type: str
    source_id: int
    content_chunk: str
    chunk_index: int = 0
    source_title: str = ""
    chunk_metadata: Optional[str] = None


class EmbeddingService:
    def __init__(self, embedder=ollama_embedder, vector_store=postgres_vector_store):
        self.embedder = embedder
        self.vector_store = vector_store

    @property
    def embedding_model(self):
        return self.embedder.model

    def sync_chunk(self, chunk: SyncChunkInput):
        embedding_text = f"{chunk.source_title}\n{chunk.content_chunk}".strip()
        embedding = self.embedder.embed(embedding_text)
        updated_chunks = self.vector_store.sync_chunk(
            VectorChunkInput(**chunk.__dict__),
            embedding,
            self.embedding_model,
        )
        self._after_vector_change()
        return {
            "status": "success",
            "message": f"Chunk {chunk.chunk_index} stored for {chunk.source_type}:{chunk.source_id}",
            "embedding_model": self.embedding_model,
            "ai_knowledge_chunks_updated": updated_chunks,
        }

    def delete_source(self, source_type: str, source_id: int):
        self.vector_store.delete_source(source_type, source_id)
        self._after_vector_change()
        return {
            "status": "success",
            "message": f"Deleted vector for {source_type} {source_id}",
        }

    def clear_vectors(self):
        self.vector_store.clear_vectors()
        self._after_vector_change(rebuild_index=False)
        return {"status": "success", "message": "All vectors cleared"}

    def rebuild_knowledge_embeddings(self, force: bool = False, limit: int = 500):
        rows = self.vector_store.list_knowledge_chunks_for_embedding(
            force=force,
            limit=limit,
        )
        updated = 0
        for row in rows:
            text = row.get("search_text") or row.get("content") or ""
            if not text.strip():
                continue
            embedding = self.embedder.embed(text)
            updated += self.vector_store.update_knowledge_chunk_embedding(
                row["id"],
                embedding,
                self.embedding_model,
            )

        self._after_vector_change()
        return {
            "status": "success",
            "embedding_model": self.embedding_model,
            "scanned": len(rows),
            "updated": updated,
            "has_more": len(rows) >= limit,
        }

    def _after_vector_change(self, rebuild_index: bool = True):
        clear_semantic_cache()
        if not rebuild_index:
            return
        try:
            hybrid_search_engine.rebuild_index_from_db()
        except Exception as idx_err:
            print(f"BM25 rebuild warning: {idx_err}")


embedding_service = EmbeddingService()
