from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.embeddings.embedding_service import SyncChunkInput, embedding_service


router = APIRouter()


class SyncRequest(BaseModel):
    source_type: str
    source_id: int
    content_chunk: str
    chunk_index: int = 0
    source_title: str = ""
    chunk_metadata: Optional[str] = None


@router.post("/sync")
def sync_vector(req: SyncRequest):
    try:
        return embedding_service.sync_chunk(SyncChunkInput(**req.dict()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sync/{source_type}/{source_id}")
def delete_vector(source_type: str, source_id: int):
    try:
        return embedding_service.delete_source(source_type, source_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
def clear_vectors():
    try:
        return embedding_service.clear_vectors()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild-knowledge")
def rebuild_knowledge_embeddings(force: bool = False, limit: int = 500):
    try:
        return embedding_service.rebuild_knowledge_embeddings(force=force, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
