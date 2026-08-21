from database import get_db_connection
from app.chat.query_utils import normalize_text

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    print("WARNING: rank_bm25 not installed. Run: pip install rank-bm25")


class HybridSearchEngine:
    def __init__(self):
        self.bm25_index = None
        self.corpus = []

    def build_bm25_index(self, corpus):
        self.corpus = corpus
        if not BM25_AVAILABLE or not corpus:
            return
        tokenized = [self._tokenize(doc["content_chunk"]) for doc in corpus]
        self.bm25_index = BM25Okapi(tokenized)
        print(f"BM25 index built with {len(corpus)} documents.")

    def _tokenize(self, text):
        return normalize_text(str(text or "")).split()

    def rebuild_index_from_db(self):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            rows = self._load_knowledge_rows(cur)
            if not rows:
                rows = self._load_legacy_rows(cur)
            cur.close()
            conn.close()
            self.build_bm25_index([dict(r) for r in rows])
        except Exception as e:
            print(f"WARNING: BM25 index rebuild skipped: {e}")

    def _load_knowledge_rows(self, cur):
        try:
            cur.execute(
                """
                SELECT
                    c.id,
                    'ai:' || c.id AS doc_key,
                    'ai_knowledge_chunks' AS data_source,
                    d.source_type,
                    d.source_id,
                    c.content AS content_chunk,
                    d.source_title,
                    d.source_url,
                    c.metadata::text AS chunk_metadata,
                    c.chunk_index
                FROM ai_knowledge_chunks c
                JOIN ai_knowledge_documents d ON d.id = c.document_id
                WHERE d.status = 'ACTIVE' AND d.is_public = TRUE
                ORDER BY d.source_type, d.source_id, c.chunk_index
                """
            )
            return cur.fetchall()
        except Exception as e:
            print(f"INFO: ai_knowledge tables are not ready, using legacy KnowledgeVector fallback: {e}")
            cur.connection.rollback()
            return []

    def _load_legacy_rows(self, cur):
        try:
            cur.execute(
                """
                SELECT id, source_type, source_id, content_chunk,
                       'legacy:' || id AS doc_key,
                       'KnowledgeVector' AS data_source,
                       source_title, NULL AS source_url, chunk_metadata, chunk_index
                FROM "KnowledgeVector"
                ORDER BY source_type, source_id, chunk_index
                """
            )
            return cur.fetchall()
        except Exception as e:
            print(f"INFO: legacy KnowledgeVector is not ready: {e}")
            cur.connection.rollback()
            return []

    def vector_search(self, query_embedding, top_k=20):
        if not query_embedding:
            return []
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            rows = self._vector_knowledge_rows(cur, query_embedding, top_k)
            if not rows:
                rows = self._vector_legacy_rows(cur, query_embedding, top_k)
            cur.close()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"Vector search error: {e}")
            return []

    def _vector_knowledge_rows(self, cur, query_embedding, top_k):
        try:
            cur.execute(
                """
                SELECT
                    c.id,
                    'ai:' || c.id AS doc_key,
                    'ai_knowledge_chunks' AS data_source,
                    d.source_type,
                    d.source_id,
                    c.content AS content_chunk,
                    d.source_title,
                    d.source_url,
                    c.metadata::text AS chunk_metadata,
                    c.chunk_index,
                    c.embedding <=> %s::vector AS distance,
                    1 - (c.embedding <=> %s::vector) AS vector_score
                FROM ai_knowledge_chunks c
                JOIN ai_knowledge_documents d ON d.id = c.document_id
                WHERE d.status = 'ACTIVE'
                  AND d.is_public = TRUE
                  AND c.embedding IS NOT NULL
                ORDER BY distance ASC
                LIMIT %s
                """,
                (str(query_embedding), str(query_embedding), top_k),
            )
            return cur.fetchall()
        except Exception:
            cur.connection.rollback()
            return []

    def _vector_legacy_rows(self, cur, query_embedding, top_k):
        try:
            cur.execute(
                """
                SELECT id,
                       'legacy:' || id AS doc_key,
                       'KnowledgeVector' AS data_source,
                       source_type,
                       source_id,
                       content_chunk,
                       source_title,
                       NULL AS source_url,
                       chunk_metadata,
                       chunk_index,
                       embedding <=> %s::vector AS distance,
                       1 - (embedding <=> %s::vector) AS vector_score
                FROM "KnowledgeVector"
                WHERE embedding IS NOT NULL
                ORDER BY distance ASC
                LIMIT %s
                """,
                (str(query_embedding), str(query_embedding), top_k),
            )
            return cur.fetchall()
        except Exception:
            cur.connection.rollback()
            return []

    def bm25_search(self, query, top_k=20):
        if not BM25_AVAILABLE or self.bm25_index is None or not self.corpus:
            return self.keyword_db_search(query, top_k=top_k)
        try:
            scores = self.bm25_index.get_scores(self._tokenize(query))
            indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            results = []
            for i, score in indexed[:top_k]:
                if score <= 0:
                    continue
                doc = dict(self.corpus[i])
                doc["bm25_score"] = float(score)
                results.append(doc)
            return results
        except Exception as e:
            print(f"BM25 search error: {e}")
            return self.keyword_db_search(query, top_k=top_k)

    def keyword_db_search(self, query, top_k=20):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            pattern = f"%{query}%"
            rows = self._keyword_knowledge_rows(cur, pattern, top_k)
            if not rows:
                rows = self._keyword_legacy_rows(cur, pattern, top_k)
            cur.close()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"Keyword DB search error: {e}")
            return []

    def normalized_keyword_db_search(self, query, top_k=20):
        query_tokens = {
            token
            for token in self._tokenize(query)
            if len(token) >= 3
            and token
            not in {
                "anh",
                "ban",
                "cac",
                "cho",
                "cua",
                "duoc",
                "khong",
                "noi",
                "thong",
                "tin",
                "tuc",
                "ve",
                "vao",
                "voi",
            }
        }
        if not query_tokens:
            return []

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            rows = self._load_knowledge_rows(cur)
            if not rows:
                rows = self._load_legacy_rows(cur)
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Normalized keyword DB search error: {e}")
            return []

        normalized_query = normalize_text(query)
        scored = []
        for row in rows:
            doc = dict(row)
            normalized_title = normalize_text(doc.get("source_title") or "")
            haystack = " ".join(
                [
                    str(doc.get("source_title") or ""),
                    str(doc.get("content_chunk") or ""),
                ]
            )
            doc_tokens = set(self._tokenize(haystack))
            overlap = query_tokens & doc_tokens
            if not overlap:
                continue
            title_tokens = set(normalized_title.split())
            title_overlap = query_tokens & title_tokens
            score = len(overlap) + (len(title_overlap) * 2)
            has_title_exact_match = bool(
                normalized_title
                and (
                    normalized_title in normalized_query
                    or normalized_query in normalized_title
                )
            )
            if has_title_exact_match:
                score += 100
            if title_tokens and query_tokens.issubset(title_tokens | doc_tokens):
                score += 3
            doc["normalized_keyword_score"] = float(score)
            doc["normalized_keyword_overlap"] = sorted(overlap)
            doc["title_exact_match"] = has_title_exact_match
            scored.append(doc)

        scored.sort(
            key=lambda doc: (
                doc.get("normalized_keyword_score", 0),
                1 if doc.get("title_exact_match") else 0,
                -int(doc.get("chunk_index") or 0),
            ),
            reverse=True,
        )
        return scored[:top_k]

    def _keyword_knowledge_rows(self, cur, pattern, top_k):
        try:
            cur.execute(
                """
                SELECT
                    c.id,
                    'ai:' || c.id AS doc_key,
                    'ai_knowledge_chunks' AS data_source,
                    d.source_type,
                    d.source_id,
                    c.content AS content_chunk,
                    d.source_title,
                    d.source_url,
                    c.metadata::text AS chunk_metadata,
                    c.chunk_index
                FROM ai_knowledge_chunks c
                JOIN ai_knowledge_documents d ON d.id = c.document_id
                WHERE d.status = 'ACTIVE'
                  AND d.is_public = TRUE
                  AND (c.search_text ILIKE %s OR d.source_title ILIKE %s)
                ORDER BY d.updated_at DESC, c.chunk_index ASC
                LIMIT %s
                """,
                (pattern, pattern, top_k),
            )
            return cur.fetchall()
        except Exception:
            cur.connection.rollback()
            return []

    def _keyword_legacy_rows(self, cur, pattern, top_k):
        try:
            cur.execute(
                """
                SELECT id, source_type, source_id, content_chunk,
                       'legacy:' || id AS doc_key,
                       'KnowledgeVector' AS data_source,
                       source_title, NULL AS source_url, chunk_metadata, chunk_index
                FROM "KnowledgeVector"
                WHERE content_chunk ILIKE %s OR source_title ILIKE %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (pattern, pattern, top_k),
            )
            return cur.fetchall()
        except Exception:
            cur.connection.rollback()
            return []

    def hybrid_merge(self, vector_results, bm25_results, top_k=20, k=60):
        rrf = {}
        docs = {}
        for rank, doc in enumerate(vector_results, 1):
            did = doc.get("doc_key") or f"{doc.get('source_type')}:{doc.get('source_id')}:{doc.get('chunk_index')}:{doc.get('id')}"
            rrf[did] = rrf.get(did, 0.0) + 1.0 / (k + rank)
            docs[did] = dict(doc)
        for rank, doc in enumerate(bm25_results, 1):
            did = doc.get("doc_key") or f"{doc.get('source_type')}:{doc.get('source_id')}:{doc.get('chunk_index')}:{doc.get('id')}"
            rrf[did] = rrf.get(did, 0.0) + 1.0 / (k + rank)
            docs[did] = {**docs.get(did, {}), **dict(doc)}
        merged = []
        for did in sorted(rrf, key=rrf.get, reverse=True)[:top_k]:
            doc = docs[did]
            doc["hybrid_score"] = rrf[did]
            merged.append(doc)
        return merged

    def search(self, query, query_embedding, top_k=20):
        vector_results = self.vector_search(query_embedding, top_k=top_k)
        bm25_results = self.bm25_search(query, top_k=top_k)
        normalized_results = self.normalized_keyword_db_search(query, top_k=top_k)
        lexical_results = self.hybrid_merge(
            bm25_results,
            normalized_results,
            top_k=top_k,
        )
        if not lexical_results:
            return vector_results[:top_k]
        return self.hybrid_merge(vector_results, lexical_results, top_k=top_k)


hybrid_search_engine = HybridSearchEngine()
