import json
import re

from app.chat.query_utils import normalize_text


def build_small_talk_answer(query: str):
    normalized = normalize_text(query)
    if not normalized:
        return None

    filler_words = {
        "a",
        "ah",
        "ak",
        "nha",
        "nhe",
        "nhi",
        "the",
        "vay",
        "voi",
        "di",
        "nao",
        "duoc",
        "khong",
        "ko",
        "k",
        "nua",
    }
    tokens = normalized.split()
    core_tokens = [token for token in tokens if token not in filler_words]
    compact = " ".join(core_tokens)

    def has_phrase(*phrases: str) -> bool:
        return any(re.search(rf"\b{re.escape(phrase)}\b", normalized) for phrase in phrases)

    is_short = len(tokens) <= 8
    is_greeting = is_short and (
        has_phrase("xin chao", "chao ban", "hello", "hey", "alo")
        or normalized in {"chao", "hi"}
        or compact in {"xin chao", "chao", "chao ban", "hello", "hi", "hey", "alo"}
    )
    is_thanks = is_short and (
        has_phrase("cam on", "thank you", "thanks")
        or compact in {"cam on", "thank", "thanks", "ok", "oke", "okie"}
    )
    is_goodbye = is_short and (
        has_phrase("tam biet", "hen gap lai", "goodbye")
        or compact in {"bye", "tam biet", "goodbye"}
    )
    asks_identity = (
        re.search(r"\bban\s+(la|ten)\s+(ai|gi)\b", normalized)
        or re.search(r"\b(bot|chatbot|tro ly)\s+(nay\s+)?(la|ten)\s+(ai|gi)\b", normalized)
        or compact in {"ban la ai", "ban ten gi", "chatbot la ai", "tro ly la ai"}
    )
    asks_capability = (
        re.search(r"\bban\s+(co the\s+)?(lam|giup|ho tro)\s+(duoc\s+)?(gi|nhung gi)\b", normalized)
        or re.search(r"\b(bot|chatbot|tro ly)\s+(nay\s+)?(lam|giup|ho tro)\s+(duoc\s+)?(gi|nhung gi)\b", normalized)
        or compact in {"ban co the lam gi", "ban giup gi", "ban ho tro gi", "tro ly nay lam gi", "chatbot nay lam gi"}
    )

    if is_greeting:
        return (
            "Xin chào! Tôi là Trợ lý AI Cộng Đồng Số. "
            "Bạn có thể hỏi tôi về thủ tục hành chính, văn bản, thông tin hướng dẫn, "
            "tin tức hoặc các tiện ích đang có trong hệ thống."
        )
    if is_thanks:
        return "Rất vui được hỗ trợ bạn. Khi cần tra cứu thông tin, bạn cứ nhắn cho tôi nhé."
    if is_goodbye:
        return "Tạm biệt bạn. Chúc bạn một ngày thuận lợi!"
    if asks_identity or asks_capability:
        return (
            "Tôi là Trợ lý AI Cộng Đồng Số, hỗ trợ tra cứu thông tin trong hệ thống như "
            "thủ tục hành chính, hướng dẫn, văn bản, tin tức và một số dịch vụ công trực tuyến."
        )

    return None


def stream_plain_answer(answer: str, action=None):
    async def generator():
        words = answer.split(" ")
        for i, word in enumerate(words):
            yield {
                "event": "message",
                "data": json.dumps({
                    "chunk": word + (" " if i < len(words) - 1 else ""),
                    "action": action if i == len(words) - 1 else None,
                }, ensure_ascii=False),
            }
        yield {"event": "done", "data": "[DONE]"}

    return generator()
