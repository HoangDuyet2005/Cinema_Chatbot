import os
from typing import Any, Optional

from ollama import Client

from app.chat.query_utils import build_contextual_query, focus_docs_for_specific_query
from .hybrid_search import hybrid_search_engine
from .relevance_filter import filter_relevant_documents
from .reranker import rerank_documents


def _embedding_client():
    ollama_host = os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST", "http://localhost:11434")
    return Client(host=ollama_host)


def _embedding_model():
    return os.getenv("OLLAMA_EMBEDDING_MODEL") or os.getenv("EMBEDDING_MODEL", "bge-m3")


def retrieve_context(
    query: str,
    history: Optional[list[Any]] = None,
    query_embedding: Optional[list[float]] = None,
    ollama_client: Optional[Client] = None,
    embedding_model: Optional[str] = None,
    top_k: int = 8,
    candidate_k: int = 20,
):
    search_query = build_contextual_query(query, history)
    client = ollama_client or _embedding_client()
    model = embedding_model or _embedding_model()

    embedding = query_embedding
    if embedding is None:
        embed_resp = client.embeddings(model=model, prompt=search_query)
        embedding = embed_resp["embedding"]

    candidates = hybrid_search_engine.search(
        query=search_query,
        query_embedding=embedding,
        top_k=candidate_k,
    )
    top_docs = rerank_documents(search_query, candidates, top_k=top_k)
    top_docs = filter_relevant_documents(search_query, top_docs)
    return focus_docs_for_specific_query(search_query, top_docs)
