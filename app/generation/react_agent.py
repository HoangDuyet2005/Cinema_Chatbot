import json
import os
import re

from ollama import AsyncClient

from .answer_builder import polish_mobile_markdown


OLLAMA_HOST = os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST", "http://localhost:11434")
LLM_MODEL = os.getenv("OLLAMA_MODEL") or os.getenv("LLM_MODEL", "qwen3.5:9b")
ollama_async_client = AsyncClient(host=OLLAMA_HOST)


def safe_print(text):
    try:
        print(text)
    except Exception:
        pass


class ReActAgent:
    MAX_ITERATIONS = 3

    def __init__(self, hybrid_search_engine=None):
        self.hybrid_search = hybrid_search_engine

    async def run(self, query, history, tools, ollama_client, system_prompt, request=None, initial_context=None):
        from core.tools import execute_tool

        messages = [{"role": "system", "content": system_prompt}]

        if initial_context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "THÔNG TIN THAM KHẢO TỪ HỆ THỐNG:\n"
                        + initial_context
                        + "\n\nHãy dựa vào THÔNG TIN THAM KHẢO trên để trả lời người dùng. "
                        "Chỉ sử dụng thông tin liên quan trực tiếp. Nếu thiếu dữ liệu, nói rõ hệ thống chưa có dữ liệu phù hợp."
                    ),
                }
            )

        for msg in history:
            if isinstance(msg, dict):
                messages.append(msg)
            else:
                messages.append({"role": msg.role, "content": msg.content})

        user_query = query + "\n\n[LƯU Ý: BẮT BUỘC trả lời bằng tiếng Việt.]"
        messages.append({"role": "user", "content": user_query})

        for iteration in range(self.MAX_ITERATIONS):
            safe_print(f"[ReAct] Iteration {iteration + 1}/{self.MAX_ITERATIONS}")
            try:
                response = await ollama_async_client.chat(
                    model=LLM_MODEL,
                    messages=messages,
                    tools=tools,
                    options={"temperature": 0.1},
                    stream=False,
                )
                msg = response["message"]
                tool_calls = msg.get("tool_calls") or []

                if not tool_calls:
                    final_content = msg.get("content", "")
                    final_content = re.sub(r"[\u4e00-\u9fff]+", "", final_content)
                    final_content = polish_mobile_markdown(final_content)
                    words = final_content.split(" ")
                    for i, word in enumerate(words):
                        yield word + (" " if i < len(words) - 1 else "")
                    return

                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.get("content", ""),
                        "tool_calls": tool_calls,
                    }
                )
                for tc in tool_calls:
                    tool_name = tc["function"]["name"]
                    try:
                        arguments = tc["function"]["arguments"]
                        if isinstance(arguments, str):
                            arguments = json.loads(arguments)
                    except Exception:
                        arguments = {}
                    safe_print(f"[ReAct] Calling tool: {tool_name}({arguments})")
                    tool_result = await execute_tool(tool_name, arguments)
                    safe_print(f"[ReAct] Result: {str(tool_result)[:100]}")
                    messages.append({"role": "tool", "content": tool_result})

            except Exception as e:
                safe_print(f"[ReAct] Error at iteration {iteration + 1}: {e}")
                yield "Xin lỗi, tôi gặp sự cố khi xử lý yêu cầu của bạn."
                return

        safe_print("[ReAct] Reached MAX_ITERATIONS, forcing final answer...")
        try:
            final_resp = await ollama_async_client.chat(
                model=LLM_MODEL,
                messages=messages,
                options={"temperature": 0.1},
                stream=True,
            )
            async for chunk in final_resp:
                if request and await request.is_disconnected():
                    break
                text = chunk["message"]["content"]
                text = re.sub(r"[\u4e00-\u9fff]+", "", text)
                yield text
        except Exception as e:
            safe_print(f"[ReAct] Final chat error: {e}")
            yield "Xin lỗi, tôi không thể hoàn thành câu trả lời."
