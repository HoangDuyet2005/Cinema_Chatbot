from app.chat.small_talk import build_small_talk_answer
from app.chat.trace import ChatTrace
from app.chat.query_utils import (
    build_contextual_query,
    is_explicit_legal_reference,
    is_follow_up_query,
)
from app.chunking.chunker import chunk_text, clean_text
from app.chunking.chunk_policy import ChunkPolicy
from app.generation.source_selector import build_answer_sources, build_suggested_sources
from app.retrieval.relevance_filter import filter_relevant_documents


def test_small_talk_has_answer():
    assert build_small_talk_answer("xin chao")
    assert build_small_talk_answer("ban la ai")


def test_source_selector_keeps_answer_related_source():
    docs = [
        {
            "source_type": "WORK_SCHEDULE",
            "source_id": 1,
            "source_title": "Hop giao ban Thuong truc HDND - UBND",
        },
        {
            "source_type": "NEWS",
            "source_id": 7,
            "source_title": "Hoi nghi trien khai so",
        },
    ]
    answer = "Cuoc hop trong thang 6 la Hop giao ban Thuong truc HDND - UBND."

    sources = build_answer_sources(docs, answer)

    assert len(sources) == 1
    assert sources[0]["type"] == "WORK_SCHEDULE"
    assert sources[0]["id"] == 1


def test_source_selector_keeps_long_legal_source_by_content_overlap():
    docs = [
        {
            "source_type": "legal_document",
            "source_id": "80",
            "source_title": (
                "Quy định mức trần chi phí in, chụp, đánh máy giấy tờ, văn bản "
                "liên quan đến việc chứng thực trên địa bàn thành phố Đà Nẵng"
            ),
            "content_chunk": (
                "Số hiệu 118/2026/QĐ-UBND. Quy định mức trần chi phí chứng thực "
                "tại Đà Nẵng, gồm chi phí in, chụp, đánh máy giấy tờ, văn bản."
            ),
        }
    ]
    answer = (
        "Quy định này nói về mức trần chi phí chứng thực tại Đà Nẵng, "
        "bao gồm việc in, chụp và đánh máy giấy tờ."
    )

    sources = build_answer_sources(docs, answer)

    assert len(sources) == 1
    assert sources[0]["type"] == "LEGAL_DOCUMENT"
    assert sources[0]["id"] == "80"


def test_source_selector_keeps_legal_document_by_query_code():
    docs = [
        {
            "source_type": "LEGAL_DOCUMENT",
            "source_id": 292,
            "source_title": (
                "Nghị định số 292/2026/NĐ-CP Quy định chi tiết một số điều và "
                "biện pháp để tổ chức, hướng dẫn thi hành Luật Quản lý ngoại thương"
            ),
            "content_chunk": (
                "Số hiệu: 292/2026/NĐ-CP. Trích yếu: Quy định chi tiết một số điều "
                "và biện pháp để tổ chức, hướng dẫn thi hành Luật Quản lý ngoại thương."
            ),
        }
    ]
    query = (
        "Nghị định số 292/2026/NĐ-CP Quy định chi tiết một số điều và biện pháp "
        "để tổ chức, hướng dẫn thi hành Luật Quản lý ngoại thương"
    )
    answer = "# Nghị định số 292/2026/NĐ-CP\n\nVăn bản quy định chi tiết Luật Quản lý ngoại thương."

    assert is_explicit_legal_reference(query)
    sources = build_answer_sources(docs, answer, query=query)

    assert len(sources) == 1
    assert sources[0]["type"] == "LEGAL_DOCUMENT"
    assert sources[0]["id"] == 292


def test_source_selector_recovers_legal_library_source_from_url():
    docs = [
        {
            "source_type": "DOCUMENT",
            "source_id": 118,
            "source_title": "Quy định mức trần chi phí chứng thực tại Đà Nẵng",
            "source_url": "/legal-library/118",
            "content_chunk": "Quy định mức trần chi phí chứng thực tại Đà Nẵng.",
        }
    ]

    sources = build_suggested_sources(docs)

    assert sources[0]["type"] == "LEGAL_DOCUMENT"
    assert sources[0]["url"] == "/legal-library/118"


def test_relevance_filter_rejects_planning_doc_for_unrelated_person_query():
    docs = [
        {
            "source_type": "PLANNING",
            "source_id": 5,
            "source_title": (
                "Đăng tải thông tin xin ý kiến Điều chỉnh cục bộ Quy hoạch chi tiết "
                "xây dựng Khu đô thị mới Sen Hồ"
            ),
            "content_chunk": "Quy hoạch chi tiết tỷ lệ 1/500 tại phường Nếnh.",
        }
    ]

    filtered = filter_relevant_documents("thông tin chi tiết về Lê Quý Đôn", docs)

    assert filtered == []


def test_long_independent_legal_query_does_not_use_previous_context():
    history = [{"role": "user", "content": "tổ chức kỉ niệm vào ngày nào"}]
    query = (
        "Quy định mức phụ cấp, việc kiêm nhiệm chức danh người hoạt động không chuyên trách "
        "ở thôn, tổ dân phố trên địa bàn tỉnh Bắc Ninh"
    )

    assert not is_follow_up_query(query)
    assert build_contextual_query(query, history) == query


def test_source_selector_falls_back_to_retrieved_source():
    docs = [
        {
            "source_type": "legal_documents",
            "source_id": 12,
            "source_title": "Quy định mức phụ cấp người hoạt động không chuyên trách",
            "content_chunk": "Mức phụ cấp và việc kiêm nhiệm chức danh ở thôn, tổ dân phố.",
        }
    ]
    answer = "Hệ thống có thông tin về mức phụ cấp ở thôn, tổ dân phố."

    sources = build_answer_sources(docs, answer)
    suggested = build_suggested_sources(docs)

    assert sources
    assert suggested
    assert sources[0]["type"] == "LEGAL_DOCUMENT"


def test_trace_payload_contains_debug_fields():
    trace = ChatTrace("thu tuc dang ky ho kinh doanh")
    trace.set("enriched_query", "thu tuc dang ky ho kinh doanh can giay to gi")
    trace.set("cache_status", "miss")
    trace.top_sources(
        [
            {
                "source_type": "PROCEDURE",
                "source_id": 10,
                "source_title": "Dang ky ho kinh doanh",
                "score": 0.92,
                "chunk_index": 0,
            }
        ]
    )
    trace.final_sources([{"type": "PROCEDURE", "id": 10}])

    payload = trace.finish()

    assert payload["original_query"] == "thu tuc dang ky ho kinh doanh"
    assert payload["cache_status"] == "miss"
    assert payload["top_retrieved_sources"][0]["type"] == "PROCEDURE"
    assert payload["final_sources"][0]["id"] == 10
    assert payload["latency_ms"] >= 0


def test_short_legal_topic_is_not_forced_into_previous_context():
    history = [
        {"role": "user", "content": "An toàn trên mạng - Lá chắn thép trong kỷ nguyên số"}
    ]

    assert not is_follow_up_query("Luật Đất đai")
    assert build_contextual_query("Luật Đất đai", history) == "Luật Đất đai"
    assert not is_follow_up_query("Luật đất đai có gì mới")


def test_dependent_follow_up_still_uses_previous_context():
    history = [{"role": "user", "content": "Thủ tục đăng ký hộ kinh doanh"}]

    assert is_follow_up_query("cần giấy tờ gì")
    assert (
        build_contextual_query("cần giấy tờ gì", history)
        == "Thủ tục đăng ký hộ kinh doanh. cần giấy tờ gì"
    )


def test_chunking_cleans_html_and_splits_long_text():
    raw = "<h1>Tieu de</h1><p>" + " ".join(f"tu{i}" for i in range(80)) + "</p>"
    text = clean_text(raw)
    chunks = chunk_text(text, ChunkPolicy(max_words=30, overlap=5))

    assert "<h1>" not in text
    assert len(chunks) >= 3
    assert chunks[0].index == 0
    assert chunks[-1].index == len(chunks) - 1
