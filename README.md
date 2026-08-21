# Chatbot_Cinema (AI Service)

Dịch vụ AI Chatbot tư vấn phim, tra cứu suất chiếu, giá vé, rạp chiếu và hỗ trợ khách hàng đặt vé xem phim thông minh.

---

## 🛠️ Yêu cầu môi trường
- **Python**: 3.9+ (khuyên dùng Python 3.10 hoặc 3.11)
- **FastAPI / Uvicorn**
- **Cơ sở dữ liệu**: MySQL `cinema2`

---

## 🚀 Hướng dẫn cài đặt & Khởi chạy

### 1. Cài đặt các thư viện cần thiết
```bash
pip install -r requirements.txt
```

### 2. Cấu hình biến môi trường
Tạo file `.env` (tham khảo `.env.example`):
```env
GEMINI_API_KEY=your_gemini_api_key_here
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=***REMOVED_LEAKED_PASSWORD***
DB_NAME=cinema2
```

### 3. Khởi chạy AI Service
```bash
python main.py
# hoặc
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Sau khi khởi chạy thành công:
- **API Docs (Swagger)**: `http://localhost:8000/docs`