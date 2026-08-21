import re

from app.chat.query_utils import (
    meaningful_tokens,
    normalize_legal_reference_text,
    normalize_text,
)


SUPPORTED_SOURCE_TYPES = {
    "PROCEDURE",
    "NEWS",
    "DOCUMENT",
    "LEGAL_DOCUMENT",
    "INFORMATION_GUIDE",
    "PLANNING",
    "EVENT",
    "INVESTMENT_PROJECT",
    "BIDDING",
    "WORK_SCHEDULE",
}


SOURCE_TYPE_ALIASES = {
    "LEGAL": "LEGAL_DOCUMENT",
    "LEGAL_DOCUMENTS": "LEGAL_DOCUMENT",
    "LEGAL_LIBRARY": "LEGAL_DOCUMENT",
    "DOC": "DOCUMENT",
    "DOCUMENTS": "DOCUMENT",
    "WORKSCHEDULE": "WORK_SCHEDULE",
    "WORK-SCHEDULE": "WORK_SCHEDULE",
}


def normalize_source_type(value):
    source_type = str(value or "").strip().upper()
    return SOURCE_TYPE_ALIASES.get(source_type, source_type)


def normalize_doc_source_type(doc):
    source_type = normalize_source_type(doc.get("source_type"))
    source_url = str(doc.get("source_url") or doc.get("url") or "")

    if source_type == "DOCUMENT" and "/legal-library/" in source_url:
        return "LEGAL_DOCUMENT"

    return source_type


def source_url_for(source_type: str, source_id, source_url=None):
    route_by_type = {
        "PROCEDURE": f"/procedures/{source_id}",
        "NEWS": f"/news/{source_id}",
        "DOCUMENT": f"/documents/{source_id}",
        "LEGAL_DOCUMENT": f"/legal-library/{source_id}",
        "INFORMATION_GUIDE": f"/information-guide/{source_id}",
        "PLANNING": f"/planning/{source_id}",
        "EVENT": f"/events/{source_id}",
        "INVESTMENT_PROJECT": f"/projects/{source_id}",
        "BIDDING": f"/biddings/{source_id}",
        "WORK_SCHEDULE": "/work-schedule",
    }
    if source_type in route_by_type:
        return route_by_type[source_type]
    return source_url or ""


def build_suggested_sources(docs, limit=5):
    sources = []
    seen = set()

    for doc in docs or []:
        source_type = normalize_doc_source_type(doc)
        source_id = doc.get("source_id")
        source_title = doc.get("source_title") or doc.get("title") or source_type or "Nguồn dữ liệu"
        if not source_type or source_id in (None, ""):
            continue

        key = f"{source_type}:{source_id}"
        if key in seen:
            continue

        seen.add(key)
        sources.append(
            {
                "type": source_type,
                "id": source_id,
                "title": source_title,
                "url": source_url_for(
                    source_type,
                    source_id,
                    doc.get("source_url"),
                ),
            }
        )
        if len(sources) >= limit:
            break

    return sources


def source_to_action(source):
    if not source:
        return None
    return {"type": source["type"], "id": source.get("id")}


def _legal_codes(value: str) -> set[str]:
    normalized = normalize_legal_reference_text(value)
    return set(re.findall(r"\b\d+/\d{4}/[a-z0-9-]+\b", normalized))


def _doc_identity_text(doc) -> str:
    return " ".join(
        [
            str(doc.get("source_title") or ""),
            str(doc.get("content_chunk") or ""),
            str(doc.get("chunk_metadata") or ""),
        ]
    )


def _matches_query_for_legal_doc(doc, query: str) -> bool:
    if not query:
        return False
    source_type = normalize_doc_source_type(doc)
    if source_type not in {"LEGAL_DOCUMENT", "DOCUMENT"}:
        return False

    query_codes = _legal_codes(query)
    doc_text = _doc_identity_text(doc)
    if query_codes and query_codes & _legal_codes(doc_text):
        return True

    query_tokens = meaningful_tokens(query)
    title_tokens = meaningful_tokens(str(doc.get("source_title") or ""))
    if not query_tokens or not title_tokens:
        return False

    title_overlap = query_tokens & title_tokens
    return len(title_overlap) >= max(4, min(10, len(title_tokens) // 2))


def build_answer_sources(docs, answer: str, limit=5, query: str = ""):
    if not docs or not answer:
        return []

    answer_norm = normalize_text(answer)
    answer_tokens = meaningful_tokens(answer)
    selected_docs = []
    seen = set()

    for doc in docs:
        source_type = normalize_doc_source_type(doc)
        source_id = doc.get("source_id")
        if not source_type or source_id in (None, ""):
            continue

        key = f"{source_type}:{source_id}"
        if key in seen:
            continue

        title = str(doc.get("source_title") or "")
        content = str(doc.get("content_chunk") or "")
        title_norm = normalize_text(title)
        title_tokens = meaningful_tokens(title)
        content_tokens = meaningful_tokens(content)
        title_overlap = len(title_tokens & answer_tokens)
        content_overlap = len(content_tokens & answer_tokens)

        title_matched = bool(title_norm and title_norm in answer_norm)
        enough_title_overlap = bool(
            title_tokens
            and len(title_tokens) >= 4
            and title_overlap == len(title_tokens)
        )
        enough_content_overlap = bool(
            content_tokens
            and content_overlap >= max(4, min(10, len(content_tokens) // 8))
        )

        query_matched_legal_doc = _matches_query_for_legal_doc(doc, query)

        if (
            title_matched
            or enough_title_overlap
            or enough_content_overlap
            or query_matched_legal_doc
        ):
            selected_docs.append({**doc, "source_type": source_type})
            seen.add(key)

        if len(selected_docs) >= limit:
            break

    if not selected_docs:
        selected_docs = [
            {**doc, "source_type": normalize_doc_source_type(doc)}
            for doc in docs
            if normalize_doc_source_type(doc)
            and doc.get("source_id") not in (None, "")
        ][:1]

    return build_suggested_sources(selected_docs, limit=limit)
