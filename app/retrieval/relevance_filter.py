import re
from app.chat.query_utils import normalize_text


STOPWORDS = {
    "anh", "ban", "bi", "bo", "cac", "can", "cau", "cho", "co", "cua",
    "chi", "chi tiet", "duoc", "du", "duong", "du lieu", "gi", "giay", "he", "ho", "hoi",
    "khong", "lam", "la", "lieu", "muon", "nay", "nhu", "noi", "ra",
    "sao", "thong", "thong tin", "tiet", "tim", "tin", "toi", "trong", "tu", "tuc",
    "thu", "ve", "va", "xin",
}

SYNONYMS = {
    "cccd": {"cccd", "can", "cuoc", "cong", "dan"},
    "cmnd": {"cmnd", "chung", "minh", "nhan", "dan"},
}

ACRONYM_PHRASES = {
    "cccd": {"cccd", "can cuoc", "can cuoc cong dan"},
    "cmnd": {"cmnd", "chung minh nhan dan"},
}

SOURCE_INTENT_TERMS = {
    "PROCEDURE": {
        "thu tuc", "ho so", "giay to", "dang ky", "cap doi", "cap moi",
        "le phi", "phi", "thoi gian xu ly", "nop o dau",
    },
    "NEWS": {"tin tuc", "bai viet", "su kien moi", "tin moi"},
    "DOCUMENT": {"van ban", "cong van", "quyet dinh", "nghi dinh", "thong tu", "luat"},
    "LEGAL_DOCUMENT": {"van ban", "phap luat", "quyet dinh", "nghi dinh", "thong tu", "luat"},
    "WORK_SCHEDULE": {"lich hop", "cuoc hop", "hoi nghi", "lich cong tac", "giao ban"},
    "EVENT": {"su kien", "lich su kien"},
    "PLANNING": {"quy hoach", "ban do", "du an quy hoach"},
}


def tokenize_relevance(text):
    tokens = re.findall(r"[a-z0-9]+", normalize_text(text))
    expanded = set()
    for token in tokens:
        if len(token) < 3 or token in STOPWORDS:
            continue
        expanded.add(token)
        expanded.update(SYNONYMS.get(token, set()))
    return expanded


def _contains_phrase(text, phrases):
    normalized = normalize_text(text)
    return any(phrase in normalized for phrase in phrases)


def _query_source_intents(query):
    return {
        source_type
        for source_type, phrases in SOURCE_INTENT_TERMS.items()
        if _contains_phrase(query, phrases)
    }


def _required_subject_tokens(query):
    normalized = normalize_text(query)
    patterns = [
        r"\b(?:thong tin(?: chi tiet)?|noi dung|gioi thieu|tim hieu)\s+ve\s+(.+)$",
        r"\bve\s+(.+)$",
    ]
    subject = ""
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            subject = match.group(1)
            break

    if not subject:
        return set()

    subject = re.sub(r"\b(?:la gi|nhu the nao|co gi|chi tiet|thong tin)\b.*$", "", subject).strip()
    tokens = tokenize_relevance(subject)
    return {
        token
        for token in tokens
        if token not in {"quy", "le"} and len(token) >= 3
    }


def is_procedure_lookup(query):
    return "PROCEDURE" in _query_source_intents(query)


def required_acronym_phrases(query):
    normalized = normalize_text(query)
    required = set()
    for token, phrases in ACRONYM_PHRASES.items():
        if re.search(rf"\b{re.escape(token)}\b", normalized):
            required.update(phrases)
    if "can cuoc" in normalized or "can cuoc cong dan" in normalized:
        required.update(ACRONYM_PHRASES["cccd"])
    if "chung minh nhan dan" in normalized:
        required.update(ACRONYM_PHRASES["cmnd"])
    return required


def _doc_text(doc):
    return " ".join(
        [
            str(doc.get("source_title") or ""),
            str(doc.get("content_chunk") or ""),
            str(doc.get("source_type") or ""),
        ]
    )


def _passes_source_intent(query_intents, doc):
    if not query_intents:
        return True
    source_type = str(doc.get("source_type") or "").upper()
    return source_type in query_intents or (
        source_type == "DOCUMENT" and "LEGAL_DOCUMENT" in query_intents
    ) or (
        source_type == "LEGAL_DOCUMENT" and "DOCUMENT" in query_intents
    )


def _min_overlap_for_query(query_tokens, query_intents):
    if len(query_tokens) <= 1:
        return 1
    if query_intents:
        return 1
    return 2


def filter_relevant_documents(query, documents, min_overlap=None):
    query_tokens = tokenize_relevance(query)
    if not query_tokens:
        return documents

    normalized_query = normalize_text(query)
    query_intents = _query_source_intents(query)
    min_required_overlap = (
        min_overlap
        if min_overlap is not None
        else _min_overlap_for_query(query_tokens, query_intents)
    )
    title_required_for_procedure = is_procedure_lookup(query)
    acronym_phrases = required_acronym_phrases(query)
    subject_tokens = _required_subject_tokens(query)

    filtered = []
    for doc in documents or []:
        title = str(doc.get("source_title") or "")
        normalized_title = normalize_text(title)
        haystack = _doc_text(doc)
        normalized_haystack = normalize_text(haystack)
        title_tokens = tokenize_relevance(title)
        doc_tokens = tokenize_relevance(haystack)
        overlap = query_tokens & doc_tokens
        title_overlap = query_tokens & title_tokens
        has_acronym_match = any(
            phrase in normalized_haystack for phrase in acronym_phrases
        )
        has_title_acronym_match = any(
            phrase in normalize_text(title) for phrase in acronym_phrases
        )

        has_title_exact_match = bool(
            normalized_title
            and (
                normalized_title in normalized_query
                or normalized_query in normalized_title
            )
        )

        if has_title_exact_match:
            next_doc = dict(doc)
            next_doc["lexical_overlap"] = sorted(query_tokens & doc_tokens)
            next_doc["title_overlap"] = sorted(query_tokens & title_tokens)
            filtered.append(next_doc)
            continue

        if not _passes_source_intent(query_intents, doc):
            continue

        if subject_tokens and not subject_tokens.issubset(doc_tokens):
            continue

        if acronym_phrases and not has_acronym_match:
            continue

        if acronym_phrases and title_required_for_procedure and not title_overlap and not has_title_acronym_match:
            continue

        if (
            title_required_for_procedure
            and str(doc.get("source_type") or "").upper() == "PROCEDURE"
            and not title_overlap
            and not has_title_acronym_match
        ):
            continue

        if len(overlap) >= min_required_overlap or has_acronym_match:
            next_doc = dict(doc)
            next_doc["lexical_overlap"] = sorted(overlap)
            next_doc["title_overlap"] = sorted(title_overlap)
            filtered.append(next_doc)

    return filtered
