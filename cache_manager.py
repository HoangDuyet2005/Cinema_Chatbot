import os
import json
import numpy as np
import redis
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.query import Query
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Connect to Redis
try:
    client = redis.Redis.from_url(REDIS_URL, decode_responses=False)
except Exception as e:
    print(f"Failed to connect to Redis: {e}")
    client = None

CACHE_VERSION = os.getenv("SEMANTIC_CACHE_VERSION", "v7")
CACHE_PREFIX = f"cache:{CACHE_VERSION}:"
INDEX_NAME = f"idx:semantic_cache:{CACHE_VERSION}"

def init_redis_index():
    global client
    if not client:
        return
    try:
        # Ping to check if Redis connection is active
        client.ping()
    except Exception as e:
        print(f"WARNING: Redis connection failed: {e}. Semantic Cache is DISABLED.")
        client = None
        return

    try:
        client.ft(INDEX_NAME).info()
    except Exception:
        # Create index if it doesn't exist
        print("Creating Redis Vector Index for Semantic Cache...")
        try:
            schema = (
                TextField("answer"),
                TextField("suggested_action"),
                TextField("sources"),
                VectorField("embedding", "FLAT", {"TYPE": "FLOAT32", "DIM": 1024, "DISTANCE_METRIC": "COSINE"})
            )
            client.ft(INDEX_NAME).create_index(
                schema, 
                definition=IndexDefinition(prefix=[CACHE_PREFIX], index_type=IndexType.HASH)
            )
        except Exception as e:
            print(f"WARNING: Failed to create Redis vector index: {e}. Semantic Cache is DISABLED.")
            client = None

def get_cached_answer(vector: list[float], threshold=0.05):
    """
    Search Redis for a similar query embedding.
    Returns dict with answer and suggested_action if found within threshold.
    """
    if not client:
        return None
    
    try:
        query = (
            Query("*=>[KNN 1 @embedding $vec AS score]")
            .sort_by("score")
            .return_fields("answer", "suggested_action", "sources", "score")
            .dialect(2)
        )
        vec_bytes = np.array(vector, dtype=np.float32).tobytes()
        res = client.ft(INDEX_NAME).search(query, query_params={"vec": vec_bytes})
        
        if res.docs and float(res.docs[0].score) < threshold:
            answer_text = res.docs[0].answer.decode('utf-8') if isinstance(res.docs[0].answer, bytes) else res.docs[0].answer
            action_text = res.docs[0].suggested_action.decode('utf-8') if isinstance(res.docs[0].suggested_action, bytes) else res.docs[0].suggested_action
            sources_text = getattr(res.docs[0], "sources", b"")
            sources_text = sources_text.decode('utf-8') if isinstance(sources_text, bytes) else sources_text
            
            print(f"Semantic Cache HIT! (Score: {res.docs[0].score})")
            return {
                "answer": answer_text,
                "suggested_action": json.loads(action_text) if action_text else None,
                "sources": json.loads(sources_text) if sources_text else [],
            }
    except Exception as e:
        print(f"Redis search error: {e}")
    
    return None

def set_cached_answer(query_id: str, vector: list[float], answer: str, suggested_action: dict = None, sources: list[dict] = None):
    """
    Save the newly generated answer into Redis Semantic Cache.
    """
    if not client:
        return
        
    try:
        vec_bytes = np.array(vector, dtype=np.float32).tobytes()
        
        # Redis hashes require all fields to be properly stringified/bytes
        mapping = {
            "answer": answer,
            "suggested_action": json.dumps(suggested_action) if suggested_action else "",
            "sources": json.dumps(sources or [], ensure_ascii=False),
            "embedding": vec_bytes
        }
        
        cache_key = f"{CACHE_PREFIX}{query_id}"
        client.hset(cache_key, mapping=mapping)
        client.expire(cache_key, 86400) # Cache expires in 24 hours
        print(f"Saved to Semantic Cache: {query_id}")
    except Exception as e:
        print(f"Redis save error: {e}")

def clear_semantic_cache():
    """
    Xóa toàn bộ semantic cache khi có dữ liệu mới được cập nhật
    để tránh trường hợp user hỏi lại câu cũ nhưng nhận được câu trả lời cũ (ví dụ: 'tôi không biết').
    """
    if not client:
        return
    try:
        keys = client.keys(f"{CACHE_PREFIX}*")
        if keys:
            client.delete(*keys)
            print(f"Cleared {len(keys)} entries from Semantic Cache")
    except Exception as e:
        print(f"Redis clear cache error: {e}")
