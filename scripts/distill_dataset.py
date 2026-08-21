import os
import sys
import ollama
import psycopg2

# Add parent directory to path to import database module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db_connection

def generate_qa_pairs(text: str) -> str:
    """
    Uses Qwen2.5 to read a long text and generate 3 Q&A pairs (Distillation).
    """
    prompt = f"""Đọc kỹ văn bản thủ tục hành chính sau và "chưng cất" nó thành 3 cặp Câu hỏi (Q) và Trả lời (A) súc tích nhất, nắm bắt nội dung cốt lõi:
    
Văn bản:
{text}

Yêu cầu định dạng:
Q1: [Câu hỏi 1]
A1: [Câu trả lời 1]
Q2: ...
"""
    try:
        response = ollama.generate(
            model='qwen2.5',
            prompt=prompt,
            options={"temperature": 0.2}
        )
        return response.get('response', '')
    except Exception as e:
        return f"Error generating Q&A: {e}"

def run_distillation():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Lấy 3 thủ tục hành chính đầu tiên để làm ví dụ
    cur.execute('SELECT "title", "description", "process_steps" FROM "AdministrativeProcedure" LIMIT 3')
    procedures = cur.fetchall()
    
    for i, proc in enumerate(procedures):
        title = proc['title']
        content = str(proc['description'] or '') + " " + str(proc['process_steps'] or '')
        
        print(f"--- Đang chưng cất thủ tục {i+1}: {title} ---")
        # Giới hạn nội dung đọc để tránh tràn context khi dùng model nhỏ
        short_content = content[:1500] if content else ""
        
        if short_content:
            qa_output = generate_qa_pairs(short_content)
            print(qa_output)
            print("-" * 50)
            
    cur.close()
    conn.close()

if __name__ == "__main__":
    print("Bắt đầu Dataset Distillation (Offline)...")
    run_distillation()
    print("Hoàn tất.")
