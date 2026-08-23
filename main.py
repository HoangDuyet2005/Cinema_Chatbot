import os
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv

from core.cinema_db import (
    get_ten_phim,
    get_phim_sap_chieu,
    get_gio_ngay_chieu_theo_chi_nhanh,
    LayMaSuatChieu,
    get_danh_sach_rap,
    get_thong_tin_phim_response,
    get_danh_sach_bap_nuoc,
    get_danh_gia_phim,
    get_remaining_seats
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
    """Tra cuu lich chieu va gia ve cua mot bo phim cu the tai cac cum rap World Cinema."""
    showtimes = get_gio_ngay_chieu_theo_chi_nhanh(movie_name)
    if not showtimes:
        return f"Hien tai chua co lich chieu moi cho phim {movie_name} hoac phim chua khoi chieu."
    result = f"Lich chieu va gia ve phim {movie_name} tai World Cinema:\n"
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

def get_food_items() -> str:
    """Trả về danh sách các combo bắp rang bơ và nước ngọt đang bán tại rạp. Dùng khi khách hỏi đồ ăn, thức uống, bắp rang bơ, popcorn, combo, ăn uống."""
    return get_danh_sach_bap_nuoc()

def search_movie_rating(movie_name: str) -> str:
    """Trả về đánh giá trung bình của một bộ phim. Dùng khi khách hỏi phim này có hay không, phim được mấy sao, review phim."""
    return get_danh_gia_phim(movie_name)

def check_remaining_seats(movie_name: str, branch_name: str, date: str, time: str) -> str:
    """Kiểm tra số ghế trống (còn bao nhiêu chỗ) của một suất chiếu cụ thể. Bắt buộc phải có tên phim, tên rạp, ngày chiếu và giờ chiếu."""
    return get_remaining_seats(movie_name, branch_name, date, time)

# Cau hinh model Gemini
model_name = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
model = genai.GenerativeModel(
    model_name=model_name,
    tools=[get_movies, get_upcoming_movies, get_movie_detail, search_showtimes, get_cinemas, generate_booking_link, get_food_items, search_movie_rating, check_remaining_seats],
    system_instruction=(
        "Bạn là trợ lý ảo AI hỗ trợ Hệ thống Rạp chiếu phim World Cinema. "
        "Tuyệt đối TỪ CHỐI trả lời bất kỳ câu hỏi nào không liên quan đến rạp chiếu phim, điện ảnh hoặc dịch vụ của World Cinema một cách lịch sự nhưng kiên quyết. "
        "CHỈ THỰC HIỆN TRẢ LỜI BẰNG TIẾNG VIỆT. "
        "Mọi thông tin về lịch chiếu, giá vé, phim, bắp nước BẮT BUỘC dùng công cụ (tools) để tra cứu dữ liệu thực tế, tuyệt đối KHÔNG tự bịa ra dữ liệu. "
        "Đối với các câu giao tiếp thông thường (chào hỏi, cảm ơn), hãy tự trả lời thân thiện mà không gọi công cụ. "
        "Nếu khách hỏi về một phim mà không chắc chắn, hãy dùng công cụ tìm kiếm phim trước. "
        "Định dạng câu trả lời bằng HTML để hiển thị trên web (sử dụng thẻ <br>, <b>, <i>, <ul>, <li>, <a href>). "
        "Các chi nhánh World Cinema gồm có: World Cinema Hà Đông, World Cinema Thủ Đức, World Cinema Ba Đình, World Cinema Phạm Hùng. "
        "Khi khách hỏi về phim sắp chiếu, gọi công cụ get_upcoming_movies. "
        "Khi khách hỏi về phim đang chiếu, gọi công cụ get_movies. "
        "Khi khách hỏi về lịch chiếu hoặc giá vé, gọi search_showtimes. "
        "Nếu khách đã chọn suất chiếu và rạp, luôn gọi công cụ generate_booking_link để lấy link đặt vé. "
        "Khi khách hỏi về số lượng ghế trống, số chỗ còn lại, hãy gọi công cụ check_remaining_seats để kiểm tra."
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
                print(f"Exception in call_gemini: {e}")
                return "Xin lỗi, hiện tại hệ thống AI đang gặp lỗi (Chi tiết: " + err_str + ")"
    return "Hệ thống AI đang quá tải, vui lòng thử lại sau."

@app.post("/handle_message")
def handle_message(req: MessageRequest):
    start_time = time.time()
    user_id = req.user_id
    user_message = req.message
    
    if user_id not in user_sessions:
        user_sessions[user_id] = model.start_chat(enable_automatic_function_calling=True)
    
    chat_session = user_sessions[user_id]
    
    response_text = call_gemini_with_retry(chat_session, user_message)
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