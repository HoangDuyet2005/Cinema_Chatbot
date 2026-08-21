import re

from app.chat.query_utils import meaningful_tokens, normalize_text, subject_from_standalone_question


NO_CONTEXT_ANSWER = "Hiện hệ thống chưa có dữ liệu phù hợp về nội dung này."


def polish_mobile_markdown(text: str) -> str:
    """Make common model Markdown patterns easier to read in mobile chat bubbles."""
    if not text:
        return text

    lines = text.splitlines()
    polished = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        is_two_col_header = re.match(
            r"^\|\s*(nội dung|noi dung)\s*\|\s*(chi tiết|chi tiet)\s*\|$",
            stripped,
            re.I,
        )
        has_separator = i + 1 < len(lines) and re.match(
            r"^\|\s*:?-{3,}:?\s*\|\s*:?-{3,}:?\s*\|$",
            lines[i + 1].strip(),
        )
        if is_two_col_header and has_separator:
            i += 2
            while i < len(lines):
                row = lines[i].strip()
                if not row.startswith("|") or row.count("|") < 3:
                    break
                cells = [cell.strip() for cell in row.strip("|").split("|")]
                if len(cells) >= 2:
                    label = re.sub(r"^\*\*(.*?)\*\*$", r"\1", cells[0]).strip()
                    value = cells[1].strip()
                    if label and value:
                        polished.append(f"- **{label}:** {value}")
                i += 1
            continue

        polished.append(line)
        i += 1

    result = "\n".join(polished)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result


def plain_preview(value: str, max_length: int = 280) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(
        r"(?<=[a-zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ])(?=[A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ])",
        " ",
        text,
    )
    text = re.sub(r"Thực đơn\s*Truy cập nội dung\s*luôn?", " ", text, flags=re.I)
    text = re.sub(r"Nguồn:\s*$", " ", text, flags=re.I)
    text = re.sub(r"Nguồn:\s*https?://\S+", " ", text, flags=re.I)
    text = re.sub(r"https?://\S+", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0].strip() + "..."


def _clean_sentence_preview(value: str, max_sentences: int = 4) -> str:
    text = re.sub(r"^\s*\[[^\]]+\]\s*", " ", value or "")
    text = re.sub(r"^\s*Chuyen muc:\s*.*?\s+Noi dung:\s*", " ", text, flags=re.I | re.S)
    text = plain_preview(text, max_length=620)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    selected = [sentence.strip() for sentence in sentences if sentence.strip()]
    return " ".join(selected[:max_sentences]).strip()


def _sentences_from_text(value: str) -> list[str]:
    text = re.sub(r"^\s*\[[^\]]+\]\s*", " ", value or "")
    text = re.sub(r"^\s*Chuyen muc:\s*.*?\s+Noi dung:\s*", " ", text, flags=re.I | re.S)
    text = re.sub(r"Nguồn:\s*https?://\S+", " ", text, flags=re.I)
    text = re.sub(r"https?://\S+", " ", text, flags=re.I)
    text = plain_preview(text, max_length=5000)
    text = re.sub(r"(?<=[.!?])(?=\S)", " ", text)
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def _sentence_key(value: str) -> str:
    return normalize_text(value)[:180]


def _sentence_tokens(value: str) -> set[str]:
    return {token for token in normalize_text(value).split() if len(token) >= 3}


def _is_similar_sentence(value: str, selected_values: list[str]) -> bool:
    value_tokens = _sentence_tokens(value)
    if not value_tokens:
        return False
    for selected in selected_values:
        if (
            "du an luat" in normalize_text(value)
            and "du an luat" in normalize_text(selected)
            and normalize_text(value) != normalize_text(selected)
        ):
            continue
        selected_tokens = _sentence_tokens(selected)
        if not selected_tokens:
            continue
        overlap = len(value_tokens & selected_tokens)
        similarity = overlap / max(len(value_tokens), len(selected_tokens))
        if similarity >= 0.55:
            return True
    return False


def _news_sentence_score(sentence: str, normalized_keywords: list[str]) -> int:
    normalized_sentence = normalize_text(sentence)
    score = sum(3 for keyword in normalized_keywords if keyword in normalized_sentence)
    if re.search(r"\d", sentence):
        score += 4
    if any(term in normalized_sentence for term in ["303", "100 trieu", "150 nha"]):
        score += 6
    if any(term in normalized_sentence for term in ["trieu", "ho ngheo", "can ngheo", "toan tinh"]):
        score += 3
    if any(term in normalized_sentence for term in ["nam 2026", "muc ho tro", "nguon quy", "ngan sach"]):
        score += 3
    if any(term in normalized_sentence for term in ["muc tieu", "doi tuong", "tieu chi"]):
        score += 2
    if "du an luat" in normalized_sentence:
        score += 8
    if any(term in normalized_sentence for term in ["nguoi dan", "nhan dan", "dia phuong", "chuong trinh"]):
        score += 1
    if any(
        term in normalized_sentence
        for term in [
            "sinh nam",
            "xuc dong",
            "chia se",
            "me con toi",
            "gia dinh ba",
            "gia dinh anh",
            "tuoi gia",
            "hang xom",
            "vuong mac",
            "chua duoc thu huong",
            "tap trung trao tang",
            "doan dai bieu",
        ]
    ):
        score -= 6
    if "“" in sentence or "”" in sentence or '"' in sentence:
        score -= 3
    return score


def _pick_sentences(
    sentences: list[str],
    keywords: list[str],
    limit: int = 2,
    excluded: set[str] | None = None,
) -> list[str]:
    seen = set(excluded or set())
    normalized_keywords = [normalize_text(keyword) for keyword in keywords]
    candidates = []
    for order, sentence in enumerate(sentences):
        sentence_norm = normalize_text(sentence)
        sentence_key = _sentence_key(sentence)
        if sentence_key in seen:
            continue
        if any(keyword in sentence_norm for keyword in normalized_keywords):
            score = _news_sentence_score(sentence, normalized_keywords)
            if score > 0:
                candidates.append((score, -order, sentence_key, plain_preview(sentence, max_length=230)))
    candidates.sort(reverse=True)

    picked = []
    picked_for_similarity = []
    for _, _, sentence_key, sentence in candidates:
        if sentence_key in seen:
            continue
        if _is_similar_sentence(sentence, picked_for_similarity):
            continue
        picked.append(sentence)
        picked_for_similarity.append(sentence)
        seen.add(sentence_key)
        if len(picked) >= limit:
            break
    return picked


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items if item]


def _display_subject_from_query(query: str) -> str:
    match = re.match(
        r"^(.+?)\s+(là ai|la ai|là gì|la gi|là như thế nào|la nhu the nao|ở đâu|o dau|làm gì|lam gi|có gì|co gi|nói về gì|noi ve gi)\??$",
        (query or "").strip(),
        re.I,
    )
    if match:
        return match.group(1).strip()
    return (query or "").strip().rstrip("?")


def _subject_sentence_score(sentence: str, subject_tokens: set[str]) -> int:
    normalized_sentence = normalize_text(sentence)
    sentence_tokens = _sentence_tokens(sentence)
    overlap = len(subject_tokens & sentence_tokens)
    if overlap == 0:
        return 0

    score = overlap * 8
    if subject_tokens and overlap == len(subject_tokens):
        score += 10

    info_terms = [
        "la",
        "sinh",
        "mat",
        "nam sinh",
        "que",
        "lang",
        "huyen",
        "tinh",
        "danh nhan",
        "nha bac hoc",
        "nha van",
        "nha tho",
        "hoc gia",
        "su nghiep",
        "dong gop",
        "tac pham",
        "di san",
        "noi tieng",
        "tieu bieu",
        "giao duc",
        "lich su",
        "van hoa",
    ]
    if any(term in normalized_sentence for term in info_terms):
        score += 8

    if re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", sentence):
        score += 3

    event_terms = [
        "ky niem",
        "le ky niem",
        "to chuc",
        "chuong trinh",
        "hoat dong",
        "tuyen truyen",
        "cuoc thi",
        "hoi nghi",
    ]
    if any(term in normalized_sentence for term in event_terms):
        score -= 5

    if len(sentence) < 35:
        score -= 4

    return score


def build_subject_answer(docs, query: str) -> str:
    subject = subject_from_standalone_question(query)
    if not subject or not docs:
        return ""

    subject_tokens = meaningful_tokens(subject)
    sorted_docs = sorted(
        docs,
        key=lambda doc: (
            str(doc.get("source_type") or ""),
            str(doc.get("source_id") or ""),
            int(doc.get("chunk_index") or 0),
        ),
    )

    title = sorted_docs[0].get("source_title") or query.strip()
    sentences = []
    for doc in sorted_docs[:6]:
        sentences.extend(_sentences_from_text(str(doc.get("content_chunk") or "")))

    candidates = []
    for order, sentence in enumerate(sentences):
        score = _subject_sentence_score(sentence, subject_tokens)
        if score > 0:
            candidates.append((score, -order, sentence))
    candidates.sort(reverse=True)

    picked = []
    for _, _, sentence in candidates:
        preview = plain_preview(sentence, max_length=280)
        if not preview or _is_similar_sentence(preview, picked):
            continue
        picked.append(preview)
        if len(picked) >= 6:
            break

    if not picked:
        return ""

    heading = _display_subject_from_query(query) or title
    lines = [f"**{heading}**", "", "**Thông tin chính:**"]
    lines.extend(_bullet_lines(picked[:4]))

    if len(picked) > 4:
        lines.extend(["", "**Thông tin bổ sung:**", *_bullet_lines(picked[4:])])

    lines.extend(["", "Bạn có thể mở nguồn tham khảo để xem nội dung đầy đủ hơn."])
    return "\n".join(lines)


def _build_news_answer(title: str, content: str) -> str:
    sentences = _sentences_from_text(content)
    intro = plain_preview(sentences[0], max_length=420) if sentences else ""
    excluded = {_sentence_key(intro)} if intro else set()
    support_items = _pick_sentences(
        sentences,
        [
            "ho tro",
            "nguon von",
            "kinh phi",
            "ngay cong",
            "vat lieu",
            "doi tuong",
            "ho ngheo",
            "can ngheo",
            "303",
            "100 trieu",
            "du an luat",
            "thao luan",
            "phien buoi",
            "hoi truong",
        ],
        limit=4,
        excluded=excluded,
    )
    excluded.update(_sentence_key(item) for item in support_items)
    process_items = _pick_sentences(
        sentences,
        [
            "ra soat",
            "phan loai",
            "hoan thien thu tuc",
            "van dong",
            "giam sat",
            "day nhanh",
            "phoi hop",
        ],
        limit=2,
        excluded=excluded,
    )
    excluded.update(_sentence_key(item) for item in process_items)
    impact_items = _pick_sentences(
        sentences,
        ["y nghia", "mang lai", "giup", "gop phan", "hieu qua", "phat trien", "an tam"],
        limit=1,
        excluded=excluded,
    )

    lines = [f"**{title}**"]
    if intro:
        lines.extend(["", "**Thông tin chính:**", intro])

    if support_items:
        lines.extend(["", "**Điểm đáng chú ý:**", *_bullet_lines(support_items)])

    if process_items:
        lines.extend(["", "**Cách triển khai:**", *_bullet_lines(process_items)])

    if impact_items:
        lines.extend(["", "**Ý nghĩa:**", *_bullet_lines(impact_items)])

    lines.extend(["", "Bạn có thể mở tin để xem toàn bộ nội dung và hình ảnh kèm theo."])
    return "\n".join(lines)


def _query_asks_fee(query: str) -> bool:
    normalized = normalize_text(query)
    return any(
        term in normalized
        for term in [
            "le phi",
            "muc phi",
            "chi phi",
            "phi bao nhieu",
            "phi la bao nhieu",
            "co mat phi",
        ]
    )


def _build_procedure_fee_answer(title: str, content: str) -> str:
    text = plain_preview(content, max_length=1200)
    fee_match = re.search(
        r"(?:Le phi|Lệ phí|Phi|Phí)\s*:\s*(.+?)(?:\s+(?:Thoi gian|Thời gian|Quy trinh|Quy trình|Ho so|Hồ sơ)\s*:|$)",
        text,
        re.I,
    )
    if not fee_match:
        return ""

    fee = fee_match.group(1).strip()
    return "\n".join(
        [
            f"**{title}**",
            "",
            f"- **Lệ phí:** {fee}",
            "",
            "Bạn có thể mở thủ tục để xem thêm hồ sơ, thời gian xử lý và quy trình thực hiện.",
        ]
    )


def build_extractive_answer(docs, query: str) -> str:
    if not docs:
        return NO_CONTEXT_ANSWER

    sorted_docs = sorted(
        docs,
        key=lambda doc: (
            str(doc.get("source_type") or ""),
            str(doc.get("source_id") or ""),
            int(doc.get("chunk_index") or 0),
        ),
    )

    first_doc = sorted_docs[0]
    first_type = str(first_doc.get("source_type") or "").upper()
    if first_type == "NEWS":
        title = first_doc.get("source_title") or "Tin tức"
        same_source_docs = [
            doc
            for doc in sorted_docs
            if doc.get("source_type") == first_doc.get("source_type")
            and doc.get("source_id") == first_doc.get("source_id")
        ]
        content = " ".join(str(doc.get("content_chunk") or "") for doc in same_source_docs)
        return _build_news_answer(title, content)

    if first_type == "PROCEDURE" and _query_asks_fee(query):
        title = first_doc.get("source_title") or "Thủ tục"
        same_source_docs = [
            doc
            for doc in sorted_docs
            if doc.get("source_type") == first_doc.get("source_type")
            and doc.get("source_id") == first_doc.get("source_id")
        ]
        content = " ".join(str(doc.get("content_chunk") or "") for doc in same_source_docs)
        fee_answer = _build_procedure_fee_answer(title, content)
        if fee_answer:
            return fee_answer

    query_norm = normalize_text(query)
    is_news_query = "tin tuc" in query_norm or "bai viet" in query_norm
    heading = (
        "Các tin tức phù hợp trong hệ thống:"
        if is_news_query
        else "Tôi tìm thấy thông tin liên quan trong hệ thống:"
    )

    lines = [heading]
    seen = set()
    index = 1
    for doc in docs[:5]:
        source_type = doc.get("source_type")
        source_id = doc.get("source_id")
        key = f"{source_type}:{source_id}"
        if key in seen:
            continue
        seen.add(key)

        title = doc.get("source_title") or source_type or "Nguồn dữ liệu"
        preview = plain_preview(doc.get("content_chunk", ""), max_length=450)
        lines.append(f"{index}. **{title}**")
        if preview:
            lines.append(f"   - {preview}")
        index += 1

    return "\n".join(lines)


def build_context_text(docs, max_chunk_chars: int = 1500) -> str:
    parts = []
    for doc in docs or []:
        title = doc.get("source_title") or doc.get("source_type", "")
        source_type = doc.get("source_type") or ""
        chunk = str(doc.get("content_chunk") or "")[:max_chunk_chars]
        source_label = "[Nguồn: " + title + (" | Loại: " + source_type if source_type else "") + "]"
        parts.append((source_label + "\n" + chunk) if title else chunk)
    return "\n\n---\n\n".join(parts)
