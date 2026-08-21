import os
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv

from core.cinema_db import (
    get_ten_phim,
    get_phim_sap_chieu,
    get_gio_ngay_chieu_theo_chi_nhanh,
    LayMaSuatChieu,
    get_danh_sach_rap,
    get_thong_tin_phim_response
)

load_dotenv(override=True)

app = FastAPI(title="World Cinema AI Chatbot Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("WARNING: GEMINI_API_KEY is not set in .env")

# Khai bao cac cong cu (tools) cho Gemini
def get_movies() -> str:
    """Lay danh sach cac phim hien dang chieu tai rap World Cinema."""
    movies = get_ten_phim()
    if not movies:
        return "Hien tai khong co phim nao dang chieu."
    return "Danh sach phim dang chieu tai World Cinema:\n" + "\n".join([f"- {m}" for m in movies])

def get_upcoming_movies() -> str:
    """Lay danh sach cac phim sap chieu (phim bom tan sap ra mat) tai World Cinema kem ngay khoi chieu."""
    movies = get_phim_sap_chieu()
    if not movies:
        return "Hien tai chua co thong tin phim sap chieu."
    res = "Danh sach phim sap chieu tai he thong World Cinema:\n"
    for m in movies:
        res += f"- {m['name']} (Khoi chieu: {m['release_date']}, The loai: {m['categories']}, Dao dien: {m['director']})\n"
    return res

def get_movie_detail(movie_name: str) -> str:
    """Lay thong tin chi tiet mot bo phim (dao dien, dien vien, the loai, thoi luong, ngay khoi chieu, mo ta)."""
    detail = get_thong_tin_phim_response(movie_name)
    if detail:
        return detail
    return f"Khong tim thay thong tin chi tiet cho phim {movie_name}."

def search_showtimes(movie_name: str) -> str:
    """Tra cuu lich chieu cua mot bo phim cu the tai cac cum rap World Cinema."""
    showtimes = get_gio_ngay_chieu_theo_chi_nhanh(movie_name)
    if not showtimes:
        return f"Hien tai chua co lich chieu moi cho phim {movie_name} hoac phim chua khoi chieu."
    result = f"Lich chieu phim {movie_name} tai World Cinema:\n"
    for branch, times in showtimes.items():
        result += f"- Chi nhanh {branch}:\n"
        for t in times:
            result += f"  + Suat chieu: {t}\n"
    return result

def get_cinemas() -> str:
    """Lay danh sach cac chi nhanh rap World Cinema (Ha Dong, Thu Duc, Ba Dinh, Pham Hung) va dia chi, hotline."""
    return get_danh_sach_rap()

def generate_booking_link(movie_name: str, branch_name: str, date: str, time: str) -> str:
    """Tao duong link de khach hang dat ve xem phim. Bat buoc phai co ten rap (branch_name)."""
    maLichChieu, maRap, maPhim, ngayChieu, maPhong, gioChieu = LayMaSuatChieu(None, movie_name, date, time, branch_name)
    if maLichChieu:
        return f"Day la link dat ghe cho phim <b>{movie_name}</b> suat <b>{time}</b> ngay <b>{date}</b> tai <b>{branch_name}</b>: <a href='http://localhost:3000/datvechitiet/{maLichChieu}/{maRap}/{maPhim}/{ngayChieu}/{maPhong}/{gioChieu}' target='_blank' style='color:#f26b38;font-weight:bold;'>Đặt vé tại đây</a>"
    return f"Xin loi, suat chieu luc {time} ngay {date} cho phim {movie_name} tai rap {branch_name} da het han hoac khong hop le."

# Cau hinh model Gemini
model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
model = genai.GenerativeModel(
    model_name=model_name,
    tools=[get_movies, get_upcoming_movies, get_movie_detail, search_showtimes, get_cinemas, generate_booking_link],
    system_instruction=(
        "Ban la tro ly ao AI ho tro He thong Rap chieu phim World Cinema. "
        "CHI THUC HIEN TRA LOI BANG TIENG VIET. "
        "Dinh dang cau tra loi bang HTML de hien thi tren web (su dung the <br>, <b>, <i>, <ul>, <li>, <a href>). "
        "Luon dung cac cong cu (tools) de lay thong tin chinh xac tu he thong World Cinema, khong tu bia ra thong tin phim va lich chieu. "
        "Cac chi nhanh World Cinema gom co: World Cinema Ha Dong, World Cinema Thu Duc, World Cinema Ba Dinh, World Cinema Pham Hung. "
        "Khi khach hoi ve phim sap chieu, goi cong cu get_upcoming_movies de liet ke cac phim sap ra mat kem ngay khoi chieu. "
        "Khi khach hoi ve phim dang chieu, goi cong cu get_movies. "
        "Khi khach hoi ve lich chieu, neu chua ro chi nhanh thi hoi khach muon xem o chi nhanh nao. "
        "Neu khach da chon suat chieu va rap, luon goi cong cu generate_booking_link de cung cap duong link dat ve cho khach hang."
    )
)

# Quan ly phien chat (session)
user_sessions = {}

class MessageRequest(BaseModel):
    message: str
    user_id: int = 0

def call_gemini_with_retry(chat_session, user_message, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = chat_session.send_message(user_message)
            return response.text
        except Exception as e:
            err_str = str(e)
            if ("429" in err_str or "quota" in err_str.lower() or "resourceexhausted" in err_str.lower()) and attempt < max_retries - 1:
                wait_secs = (attempt + 1) * 3
                print(f"Rate limit hit, retry in {wait_secs}s...")
                time.sleep(wait_secs)
            else:
                raise e

@app.post("/handle_message")
def handle_message(req: MessageRequest):
    start_time = time.time()
    user_id = req.user_id
    user_message = req.message
    
    if user_id not in user_sessions:
        user_sessions[user_id] = model.start_chat(enable_automatic_function_calling=True)
    
    chat_session = user_sessions[user_id]
    
    try:
        response_text = call_gemini_with_retry(chat_session, user_message)
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        try:
            user_sessions[user_id] = model.start_chat(enable_automatic_function_calling=True)
            response_text = call_gemini_with_retry(user_sessions[user_id], user_message)
        except Exception as e2:
            print(f"Retry failed: {e2}")
            response_text = "Xin lỗi, hiện tại hệ thống AI đang nhận nhiều yêu cầu. Bạn vui lòng đợi vài giây và nhắn lại giúp mình nhé!"
        
    processing_time = time.time() - start_time
    
    return {
        "response": response_text,
        "processing_time": processing_time
    }

@app.get("/")
def read_root():
    return {"status": "ok", "message": "World Cinema AI Chatbot Service is running"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 5001))
    uvicorn.run(app, host="0.0.0.0", port=port)