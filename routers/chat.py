import asyncio
import json
import os
import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from ollama import Client
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.chat.query_utils import (
    build_contextual_query,
    doc_title_focus_score,
    doc_matches_date_anchor,
    has_explicit_reference_anchor,
    has_standalone_subject_question,
    is_explicit_legal_reference,
    is_no_context_answer,
    is_specific_fact_check_query,
    normalize_text,
    query_prefers_news,
)
from app.chat.small_talk import build_small_talk_answer, stream_plain_answer
from app.chat.trace import ChatTrace
from app.generation.answer_builder import (
    NO_CONTEXT_ANSWER,
    build_context_text,
    build_extractive_answer,
    build_subject_answer,
)
from app.generation.react_agent import ReActAgent
from app.generation.source_selector import build_answer_sources, build_suggested_sources, source_to_action
from app.prompts.system_prompts import SYSTEM_PROMPT
from app.retrieval.retriever import retrieve_context
from cache_manager import get_cached_answer, set_cached_answer
from core.context_harness import check_guardrails
from core.tools import TOOL_DEFINITIONS


router = APIRouter()

OLLAMA_HOST = os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL") or os.getenv("EMBEDDING_MODEL", "bge-m3")
ollama_client = Client(host=OLLAMA_HOST)

react_agent = ReActAgent(hybrid_search_engine=None)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    query: str
    history: Optional[List[Message]] = []
    userId: Optional[str] = None
    userName: Optional[str] = None
    role: Optional[str] = "resident"
    organizationId: Optional[str] = None


def _message_payload(chunk: str, action=None, sources=None):
    payload = {"chunk": chunk, "action": action}
    if sources is not None:
        payload["sources"] = sources
    return {"event": "message", "data": json.dumps(payload, ensure_ascii=False)}


def _debug_payload(trace):
    return {"event": "debug", "data": json.dumps({"trace": trace}, ensure_ascii=False)}


async def _stream_words(answer: str, action=None, sources=None, delay: float = 0.0):
    words = answer.split(" ")
    for i, word in enumerate(words):
        is_last = i == len(words) - 1
        chunk = word + (" " if not is_last else "")
        yield _message_payload(
            chunk,
            action if is_last else None,
            sources if is_last else None,
        )
        if delay:
            await asyncio.sleep(delay)


def _history_dicts(req: ChatRequest, explicit_legal_reference: bool, is_follow_up: bool):
    if explicit_legal_reference or not is_follow_up:
        return []
    return [{"role": m.role, "content": m.content} for m in req.history]


def _resolve_search_query_legacy_unused(req: ChatRequest, enriched_query: str, explicit_legal_reference: bool, is_follow_up: bool):
    search_query = enriched_query
    if req.history and not explicit_legal_reference and not is_follow_up:
        last_user = [m.content for m in req.history if m.role == "user"]
        if last_user:
            query_lower = req.query.lower()
            has_ambiguous_pronoun = any(
                word in query_lower
                for word in [
                    " họ ",
                    "của họ",
                    " đó ",
                    " nó ",
                    " này ",
                    " kia ",
                    "chi tiết hơn",
                    "thêm về",
                    "tiếp theo",
                    "nói rõ hơn",
                ]
            )
            has_ambiguous_pronoun = (
                has_ambiguous_pronoun
                or query_lower.startswith("họ ")
                or query_lower.endswith(" họ")
                or query_lower.endswith(" họ?")
            )
            is_very_short = len(req.query.split()) <= 4
            if has_ambiguous_pronoun or is_very_short:
                search_query = last_user[-1] + ". " + req.query
    return search_query


def _resolve_search_query(
    req: ChatRequest,
    enriched_query: str,
    explicit_legal_reference: bool,
    is_follow_up: bool,
):
    from app.chat.query_utils import normalize_text

    search_query = enriched_query
    if req.history and not explicit_legal_reference and not is_follow_up:
        last_user = [m.content for m in req.history if m.role == "user"]
        if last_user:
            normalized_query = f" {normalize_text(req.query)} "
            dependent_terms = [
                " ho ",
                " cua ho ",
                " no ",
                " nay ",
                " kia ",
                " viec do ",
                " thu tuc do ",
                " cuoc hop do ",
                " hoi nghi do ",
                " su kien do ",
                " tin do ",
                " bai do ",
                " chi tiet hon ",
                " them ve ",
                " tiep theo ",
                " noi ro hon ",
            ]
            if any(term in normalized_query for term in dependent_terms):
                search_query = last_user[-1] + ". " + req.query
    return search_query


def _has_exact_title_match(query: str, docs) -> bool:
    normalized_query = normalize_text(query)
    for doc in docs or []:
        normalized_title = normalize_text(str(doc.get("source_title") or ""))
        if normalized_title and (
            normalized_title in normalized_query
            or normalized_query in normalized_title
        ):
            return True
    return False


def _has_strong_single_news_match(query: str, docs) -> bool:
    news_docs = [
        doc
        for doc in docs or []
        if str(doc.get("source_type") or "").upper() == "NEWS"
        and doc.get("source_id") not in (None, "")
    ]
    if not news_docs:
        return False

    source_ids = {str(doc.get("source_id")) for doc in news_docs}
    if len(source_ids) != 1:
        return False

    best_score = max(doc_title_focus_score(query, doc) for doc in news_docs)
    return best_score >= 0.55 or any(doc_matches_date_anchor(query, doc) for doc in news_docs)


@router.post("/query")
async def chat_with_rag(req: ChatRequest, request: Request):
    try:
        trace = ChatTrace(req.query)
        if check_guardrails(req.query):
            async def guardrail_gen():
                yield _message_payload(
                    "Xin lỗi, tôi không thể trả lời câu hỏi có nội dung không phù hợp.",
                    None,
                )
                yield {"event": "done", "data": "[DONE]"}

            return EventSourceResponse(guardrail_gen())

        small_talk_answer = build_small_talk_answer(req.query)
        if small_talk_answer:
            return EventSourceResponse(stream_plain_answer(small_talk_answer))

        explicit_legal_reference = is_explicit_legal_reference(req.query)
        enriched_query = (
            req.query
            if explicit_legal_reference
            else build_contextual_query(req.query, req.history)
        )
        trace.set("enriched_query", enriched_query)
        trace.set("explicit_legal_reference", explicit_legal_reference)
        is_follow_up = enriched_query != req.query
        trace.set("is_follow_up", is_follow_up)

        embed_resp = ollama_client.embeddings(model=EMBEDDING_MODEL, prompt=enriched_query)
        query_vector = embed_resp["embedding"]
        should_use_semantic_cache = (
            not is_follow_up
            and not has_explicit_reference_anchor(req.query)
            and not is_specific_fact_check_query(req.query)
            and not query_prefers_news(req.query)
        )
        trace.set("cache_status", "miss" if should_use_semantic_cache else "skip")
        cached = get_cached_answer(query_vector) if should_use_semantic_cache else None

        async def event_generator():
            if cached and not is_no_context_answer(cached["answer"]):
                trace.set("cache_status", "hit")
                trace.final_sources(cached.get("sources") or [])
                async for event in _stream_words(
                    cached["answer"],
                    cached.get("suggested_action"),
                    cached.get("sources") or [],
                    delay=0.01,
                ):
                    yield event
                yield _debug_payload(trace.finish())
                yield {"event": "done", "data": "[DONE]"}
                return

            search_query = _resolve_search_query(
                req,
                enriched_query,
                explicit_legal_reference,
                is_follow_up,
            )
            trace.set("search_query", search_query)

            search_embed = ollama_client.embeddings(model=EMBEDDING_MODEL, prompt=search_query)
            top_docs = retrieve_context(
                search_query,
                query_embedding=search_embed["embedding"],
                ollama_client=ollama_client,
                embedding_model=EMBEDDING_MODEL,
                top_k=8,
                candidate_k=20,
            )
            trace.top_sources(top_docs)

            if not top_docs:
                trace.final_sources([])
                async for event in _stream_words(NO_CONTEXT_ANSWER):
                    yield event
                yield _debug_payload(trace.finish())
                yield {"event": "done", "data": "[DONE]"}
                return

            context_text = build_context_text(top_docs)
            history_dicts = _history_dicts(req, explicit_legal_reference, is_follow_up)
            full_answer = ""

            if has_standalone_subject_question(req.query):
                full_answer = build_subject_answer(top_docs, req.query)
                if full_answer:
                    async for event in _stream_words(full_answer):
                        yield event
                    final_sources = build_suggested_sources(top_docs)
                    trace.final_sources(final_sources)
                    final_action = None if not final_sources else source_to_action(final_sources[0])
                    yield _debug_payload(trace.finish())
                    if final_action:
                        yield _message_payload("", final_action, final_sources)
                    yield {"event": "done", "data": "[DONE]"}
                    return

            can_use_news_summary = (
                not has_standalone_subject_question(req.query)
                and (
                    _has_exact_title_match(search_query, top_docs)
                    or _has_strong_single_news_match(search_query, top_docs)
                )
            )
            if can_use_news_summary:
                full_answer = build_extractive_answer(top_docs, req.query)
                async for event in _stream_words(full_answer):
                    yield event
                final_sources = build_suggested_sources(top_docs)
                trace.final_sources(final_sources)
                final_action = None if not final_sources else source_to_action(final_sources[0])
                yield _debug_payload(trace.finish())
                if final_action:
                    yield _message_payload("", final_action, final_sources)
                yield {"event": "done", "data": "[DONE]"}
                return

            try:
                async for text_chunk in react_agent.run(
                    query=req.query if explicit_legal_reference else search_query,
                    history=history_dicts,
                    tools=TOOL_DEFINITIONS,
                    ollama_client=ollama_client,
                    system_prompt=SYSTEM_PROMPT,
                    request=request,
                    initial_context=context_text if context_text else None,
                ):
                    if await request.is_disconnected():
                        break
                    text_chunk = re.sub(r"[\u4e00-\u9fff]+", "", text_chunk)
                    full_answer += text_chunk
                    yield _message_payload(text_chunk)
            except Exception as stream_err:
                print(f"ReAct streaming error: {stream_err}")

            if not full_answer.strip():
                full_answer = build_extractive_answer(top_docs, req.query)
                async for event in _stream_words(full_answer):
                    yield event
            elif is_no_context_answer(full_answer) and top_docs:
                full_answer = build_extractive_answer(top_docs, req.query)
                async for event in _stream_words(full_answer):
                    yield event

            final_sources = (
                []
                if is_no_context_answer(full_answer)
                else build_answer_sources(top_docs, full_answer, query=search_query)
            )
            if not final_sources and top_docs and not is_no_context_answer(full_answer):
                final_sources = build_suggested_sources(top_docs)
            trace.final_sources(final_sources)
            final_action = None if not final_sources else source_to_action(final_sources[0])
            yield _debug_payload(trace.finish())
            if final_action:
                yield _message_payload("", final_action, final_sources)

            if (
                should_use_semantic_cache
                and full_answer.strip()
                and not is_no_context_answer(full_answer)
            ):
                set_cached_answer(
                    str(uuid.uuid4()),
                    query_vector,
                    full_answer.strip(),
                    final_action,
                    final_sources,
                )

            yield {"event": "done", "data": "[DONE]"}

        return EventSourceResponse(event_generator())

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
