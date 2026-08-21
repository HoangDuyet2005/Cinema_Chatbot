import re
import unicodedata
from typing import Any, Optional


LEGAL_REFERENCE_RE = re.compile(
    r"(?i)(?:nd|nghi\s*dinh|quyet\s*dinh|qd|thong\s*tu|tt|luat)?[-\s]*\d+/\d{4}/[a-z0-9\-]+"
)


def normalize_text(value: str) -> str:
    text = (
        value or ""
    ).translate(
        str.maketrans(
            {
                "\u0111": "d",
                "\u0110": "D",
                "\u00f0": "d",
                "\u00d0": "D",
            }
        )
    )
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = (
        text.replace("đ", "d")
        .replace("Đ", "D")
        .replace("Ä‘", "d")
        .replace("Ä", "D")
        .replace("Ã„â€˜", "d")
        .replace("Ã„Â", "D")
        .lower()
    )
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_legal_reference_text(value: str) -> str:
    text = (
        value or ""
    ).translate(
        str.maketrans(
            {
                "\u0111": "d",
                "\u0110": "D",
                "\u00f0": "d",
                "\u00d0": "D",
            }
        )
    )
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = (
        text.replace("đ", "d")
        .replace("Đ", "D")
        .replace("Ä‘", "d")
        .replace("Ä", "D")
        .replace("Ã„â€˜", "d")
        .replace("Ã„Â", "D")
        .replace("Ãƒâ€žÃ¢â‚¬Ëœ", "d")
        .replace("Ãƒâ€žÃ‚Â", "D")
        .lower()
    )
    text = re.sub(r"[^a-z0-9/\-\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def meaningful_tokens(value: str) -> set[str]:
    stop_words = {
        "va",
        "hoac",
        "cua",
        "cho",
        "cac",
        "nhung",
        "mot",
        "trong",
        "tren",
        "duoi",
        "ngay",
        "thang",
        "nam",
        "tai",
        "ve",
        "la",
        "co",
        "khong",
        "duoc",
        "noi",
        "dung",
        "thong",
        "tin",
        "lich",
        "lam",
        "viec",
        "hop",
        "cuoc",
        "hoi",
        "nghi",
        "giao",
        "ban",
        "ubnd",
        "hdnd",
        "phuong",
        "xa",
    }
    return {
        token
        for token in normalize_text(value).split()
        if len(token) >= 3 and token not in stop_words
    }


def is_no_context_answer(answer: str) -> bool:
    normalized = (answer or "").lower()
    phrases = [
        "chưa có dữ liệu",
        "chua co du lieu",
        "chưa có thông tin",
        "chua co thong tin",
        "thông tin chưa có",
        "thong tin chua co",
        "chưa tìm thấy",
        "chua tim thay",
        "không có thông tin",
        "khong co thong tin",
        "không có dữ liệu",
        "khong co du lieu",
        "không tìm thấy",
        "khong tim thay",
        "không rõ nghĩa",
        "khong ro nghia",
        "hệ thống chưa có",
        "he thong chua co",
    ]
    return any(phrase in normalized for phrase in phrases)


def is_explicit_legal_reference(query: str) -> bool:
    normalized = normalize_legal_reference_text(query)
    return bool(LEGAL_REFERENCE_RE.search(normalized))


def is_specific_fact_check_query(query: str) -> bool:
    normalized = normalize_text(query)
    tokens = meaningful_tokens(query)
    fact_check_markers = [
        "dung khong",
        "co phai",
        "phai khong",
        "chinh xac khong",
        "that khong",
    ]
    return len(tokens) >= 8 or any(marker in normalized for marker in fact_check_markers)


STANDALONE_SUBJECT_RE = re.compile(
    r"^(.+?)\s+(la ai|la gi|la nhu the nao|o dau|lam gi|co gi|noi ve gi)$"
)

PRONOUN_SUBJECTS = {
    "no",
    "nay",
    "kia",
    "cai nay",
    "cai do",
    "viec nay",
    "viec do",
    "tin nay",
    "tin do",
    "bai nay",
    "bai do",
    "thu tuc nay",
    "thu tuc do",
    "su kien nay",
    "su kien do",
    "cuoc hop nay",
    "cuoc hop do",
}


def subject_from_standalone_question(query: str) -> Optional[str]:
    normalized = normalize_text(query)
    match = STANDALONE_SUBJECT_RE.match(normalized)
    if not match:
        return None

    subject = match.group(1).strip()
    if not subject:
        return None

    if subject in PRONOUN_SUBJECTS:
        return None

    return subject if len(meaningful_tokens(subject)) >= 2 else None


def has_standalone_subject_question(query: str) -> bool:
    return subject_from_standalone_question(query) is not None


def has_explicit_reference_anchor(query: str) -> bool:
    normalized = normalize_text(query)
    if re.search(r"\b\d{1,2}\s+\d{1,2}\b|\b\d{1,2}\s*/\s*\d{1,2}\b|\b\d{4}\b", query):
        return True
    if re.search(r"\b\d{1,2}\s+\d{1,2}\b|\b\d{4}\b", normalized):
        return True
    if is_explicit_legal_reference(query):
        return True
    if has_standalone_subject_question(query):
        return True
    if len(meaningful_tokens(query)) >= 5:
        return True
    return False


def is_follow_up_query(query: str) -> bool:
    normalized = normalize_text(query)
    if not normalized:
        return False

    tokens = normalized.split()
    is_short = len(tokens) <= 12
    if len(meaningful_tokens(query)) >= 8:
        return False

    has_named_subject = any(
        term in normalized
        for term in [
            "so dan toc",
            "so ",
            "ban ",
            "phong ",
            "trung tam",
            "tinh doan",
            "ubnd",
            "hdnd",
            "hoi dong",
            "mat tran",
            "cong an",
        ]
    )
    has_news_event_topic = any(
        term in normalized
        for term in [
            "to chuc le",
            "to chuc hoi nghi",
            "to chuc chuong trinh",
            "le vu lan",
            "vu lan",
            "bao hieu",
            "khai mac",
            "hoi nghi",
            "chuong trinh",
            "su kien",
        ]
    )
    if has_named_subject and (has_news_event_topic or len(meaningful_tokens(query)) >= 5):
        return False

    has_business_topic = any(term in normalized for term in [
        "thu tuc",
        "dang ky",
        "ho kinh doanh",
        "khai sinh",
        "ket hon",
        "can cuoc",
        "cccd",
        "luat",
        "dat dai",
        "van ban",
        "nghi dinh",
        "quyet dinh",
        "thong tu",
        "du an",
        "quy hoach",
        "quy dinh",
        "phu cap",
        "chuc danh",
        "to dan pho",
        "thon",
        "so dan toc",
        "ton giao",
        "vu lan",
        "bao hieu",
        "to chuc le",
    ])
    if has_business_topic:
        return False

    follow_up_phrases = [
        "can gi",
        "can nhung gi",
        "can giay to",
        "mang gi",
        "mang theo gi",
        "mang theo giay to",
        "nop gi",
        "nop o dau",
        "lam o dau",
        "o dau",
        "bao lau",
        "mat bao lau",
        "le phi",
        "le phi bao nhieu",
        "le phi la bao nhieu",
        "muc le phi",
        "muc phi",
        "phi bao nhieu",
        "phi la bao nhieu",
        "chi phi",
        "chi phi bao nhieu",
        "chi phi la bao nhieu",
        "co mat phi",
        "co can",
        "co duoc",
        "duoc khong",
        "khong duoc",
        "ai duoc",
        "ai khong duoc",
        "tham du",
        "duoc tham du",
        "khong duoc tham du",
        "duoc tham gia",
        "khong duoc tham gia",
        "dan co duoc",
        "nguoi dan co duoc",
        "nguoi dan khong duoc",
        "ho so gom",
        "giay to gom",
        "chi tiet hon",
        "noi ro hon",
        "them ve",
        "tiep theo",
    ]
    pronoun_terms = [
        "no",
        "nay",
        "kia",
        "viec do",
        "thu tuc do",
        "cuoc hop do",
        "hoi nghi do",
        "su kien do",
        "tin do",
        "bai do",
    ]
    question_markers = [
        "ai",
        "gi",
        "nao",
        "dau",
        "bao lau",
        "khong",
        "chua",
        "a",
        "ha",
        "nhi",
    ]
    has_follow_up_phrase = any(phrase in normalized for phrase in follow_up_phrases)
    has_pronoun_reference = any(re.search(rf"\b{term}\b", normalized) for term in pronoun_terms)
    has_question_marker = any(re.search(rf"\b{term}\b", normalized) for term in question_markers)

    if not is_short:
        return False

    if has_standalone_subject_question(query):
        return False

    if has_explicit_reference_anchor(query) and not has_pronoun_reference:
        return False

    if has_follow_up_phrase or has_pronoun_reference:
        return True

    return has_question_marker and len(meaningful_tokens(query)) <= 2


def _message_value(message: Any, field: str) -> Any:
    if isinstance(message, dict):
        return message.get(field)
    return getattr(message, field, None)


def last_context_user_message(query: str, history: Optional[list[Any]]) -> Optional[str]:
    if not history:
        return None

    normalized_query = normalize_text(query)
    for message in reversed(history):
        role = _message_value(message, "role")
        content = _message_value(message, "content")
        if role != "user" or not content or not str(content).strip():
            continue
        if normalize_text(str(content)) == normalized_query:
            continue
        return str(content).strip()

    return None


def build_contextual_query(query: str, history: Optional[list[Any]]) -> str:
    if not history or not is_follow_up_query(query):
        return query

    last_user_message = last_context_user_message(query, history)
    if not last_user_message:
        return query

    return last_user_message + ". " + query


def doc_title_focus_score(query: str, doc) -> float:
    query_tokens = meaningful_tokens(query)
    title_tokens = meaningful_tokens(str(doc.get("source_title") or ""))
    if not query_tokens or not title_tokens:
        return 0.0

    overlap = query_tokens & title_tokens
    return len(overlap) / max(1, min(len(query_tokens), len(title_tokens)))


def date_anchor_tokens(value: str) -> set[str]:
    normalized = normalize_text(value)
    return set(re.findall(r"\b\d{1,2}\s+\d{1,2}\b|\b\d{4}\b", normalized))


def doc_matches_date_anchor(query: str, doc) -> bool:
    query_dates = date_anchor_tokens(query)
    if not query_dates:
        return False
    doc_text = " ".join(
        [
            str(doc.get("source_title") or ""),
            str(doc.get("content_chunk") or ""),
            str(doc.get("chunk_metadata") or ""),
        ]
    )
    doc_dates = date_anchor_tokens(doc_text)
    return bool(query_dates & doc_dates)


def query_prefers_news(query: str) -> bool:
    normalized = normalize_text(query)
    if any(
        term in normalized
        for term in [
            "tin gi",
            "bai gi",
            "to chuc le",
            "to chuc hoi nghi",
            "to chuc chuong trinh",
            "le vu lan",
            "vu lan",
            "bao hieu",
            "khai mac",
            "su kien",
        ]
    ):
        return True

    return has_explicit_reference_anchor(query) and any(
        term in normalized
        for term in [
            "hop",
            "thao luan",
            "dien ra",
            "to chuc",
            "cai gi",
            "noi dung",
            "hom nay",
        ]
    )


def focus_docs_for_specific_query(query: str, docs):
    if not docs or len(docs) <= 1:
        return docs

    if query_prefers_news(query):
        news_docs = [
            doc
            for doc in docs
            if str(doc.get("source_type") or "").upper() == "NEWS"
        ]
        if news_docs:
            date_matched_docs = [doc for doc in news_docs if doc_matches_date_anchor(query, doc)]
            if date_matched_docs:
                focused_source_id = date_matched_docs[0].get("source_id")
                return [
                    doc
                    for doc in news_docs
                    if doc.get("source_id") == focused_source_id
                ][:3]
            docs = news_docs

    scored = [(doc_title_focus_score(query, doc), doc) for doc in docs]
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score = scored[0][0]

    if best_score >= 0.65:
        threshold = max(0.6, best_score * 0.8)
        focused = [doc for score, doc in scored if score >= threshold]
        return focused[:3] or [scored[0][1]]

    if best_score >= 0.45 and len(meaningful_tokens(query)) >= 6:
        return [scored[0][1]]

    return docs
