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
Sao chép `.env.example` thành `.env` rồi điền giá trị thật của bạn:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-flash-lite-latest
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=CHANGE_ME
DB_NAME=cinema2
FRONTEND_URL=http://localhost:3000
```
Không commit file `.env` (đã có trong `.gitignore`) và không ghi mật khẩu thật vào bất kỳ file nào trong repo.

### 3. Khởi chạy AI Service
```bash
python main.py
# hoặc
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Sau khi khởi chạy thành công:
- **API Docs (Swagger)**: `http://localhost:8000/docs`