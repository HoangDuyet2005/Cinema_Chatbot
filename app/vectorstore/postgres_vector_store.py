from dataclasses import dataclass
from typing import Optional

from database import get_db_connection


@dataclass(frozen=True)
class VectorChunkInput:
    source_type: str
    source_id: int
    content_chunk: str
    chunk_index: int = 0
    source_title: str = ""
    chunk_metadata: Optional[str] = None


class PostgresVectorStore:
    def sync_chunk(self, chunk: VectorChunkInput, embedding: list[float], embedding_model: str):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            updated_chunks = self._update_ai_knowledge_chunk(
                cur,
                chunk,
                embedding,
                embedding_model,
            )

            if chunk.chunk_index == 0:
                cur.execute(
                    'DELETE FROM "KnowledgeVector" WHERE source_type=%s AND source_id=%s',
                    (chunk.source_type, chunk.source_id),
                )

            cur.execute(
                """
                INSERT INTO "KnowledgeVector"
                    (source_type, source_id, content_chunk, chunk_index, source_title, chunk_metadata, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    chunk.source_type,
                    chunk.source_id,
                    chunk.content_chunk,
                    chunk.chunk_index,
                    chunk.source_title,
                    chunk.chunk_metadata,
                    embedding,
                ),
            )
            conn.commit()
            return updated_chunks
        finally:
            cur.close()
            conn.close()

    def delete_source(self, source_type: str, source_id: int):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            try:
                cur.execute(
                    """
                    UPDATE ai_knowledge_chunks c
                    SET embedding = NULL,
                        embedding_model = NULL,
                        embedded_at = NULL,
                        updated_at = NOW()
                    FROM ai_knowledge_documents d
                    WHERE d.id = c.document_id
                      AND d.source_type = %s
                      AND d.source_id = %s
                    """,
                    (source_type, source_id),
                )
            except Exception as e:
                print(f"AI knowledge chunk embedding delete skipped: {e}")
                cur.connection.rollback()

            cur.execute(
                'DELETE FROM "KnowledgeVector" WHERE source_type=%s AND source_id=%s',
                (source_type, source_id),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def clear_vectors(self):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            try:
                cur.execute(
                    """
                    UPDATE ai_knowledge_chunks
                    SET embedding = NULL,
                        embedding_model = NULL,
                        embedded_at = NULL,
                        updated_at = NOW()
                    """
                )
            except Exception as e:
                print(f"AI knowledge chunk embedding clear skipped: {e}")
                cur.connection.rollback()

            cur.execute('DELETE FROM "KnowledgeVector"')
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def list_knowledge_chunks_for_embedding(self, force: bool = False, limit: int = 500):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            where = "" if force else "WHERE c.embedding IS NULL"
            status_connector = "AND" if where else "WHERE"
            cur.execute(
                f"""
                SELECT
                    c.id,
                    c.content,
                    c.search_text
                FROM ai_knowledge_chunks c
                JOIN ai_knowledge_documents d ON d.id = c.document_id
                {where}
                  {status_connector} d.status = 'ACTIVE'
                ORDER BY c.id ASC
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    def update_knowledge_chunk_embedding(self, chunk_id: int, embedding: list[float], embedding_model: str):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE ai_knowledge_chunks
                SET embedding = %s::vector,
                    embedding_model = %s,
                    embedded_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (str(embedding), embedding_model, chunk_id),
            )
            updated = cur.rowcount
            conn.commit()
            return updated
        finally:
            cur.close()
            conn.close()

    def _update_ai_knowledge_chunk(self, cur, chunk: VectorChunkInput, embedding: list[float], embedding_model: str):
        try:
            cur.execute(
                """
                UPDATE ai_knowledge_chunks c
                SET embedding = %s::vector,
                    embedding_model = %s,
                    embedded_at = NOW(),
                    updated_at = NOW()
                FROM ai_knowledge_documents d
                WHERE d.id = c.document_id
                  AND d.source_type = %s
                  AND d.source_id = %s
                  AND c.chunk_index = %s
                """,
                (
                    str(embedding),
                    embedding_model,
                    chunk.source_type,
                    chunk.source_id,
                    chunk.chunk_index,
                ),
            )
            return cur.rowcount
        except Exception as e:
            print(f"AI knowledge chunk embedding update skipped: {e}")
            cur.connection.rollback()
            return 0


postgres_vector_store = PostgresVectorStore()
