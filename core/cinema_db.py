import os
import urllib.parse
import mysql.connector
import json
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    url = urllib.parse.urlparse(DATABASE_URL)
    db_config = {
        'host': url.hostname or 'localhost',
        'port': url.port or 3306,
        'user': url.username or 'root',
        'password': url.password or '***REMOVED_LEAKED_PASSWORD***',
        'database': url.path.lstrip('/') if url.path else 'cinema2',
        'charset': 'utf8mb4'
    }
else:
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', '***REMOVED_LEAKED_PASSWORD***'),
        'database': os.getenv('DB_NAME', 'cinema2'),
        'charset': 'utf8mb4'
    }

def get_connection():
    return mysql.connector.connect(**db_config)

def get_ten_chi_nhanh():
    """Lấy danh sách name từ bảng branch."""
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM branch")
        rows = cursor.fetchall()
        ten_chi_nhanh_list = [row[0] for row in rows]
        cursor.close()
        connection.close()
        return ten_chi_nhanh_list
    except mysql.connector.Error as ex:
        print("Lỗi khi kết nối đến MySQL Server:", ex)
        return []

def get_danh_sach_rap(user_message=""):
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        user_message = user_message.lower() if user_message else ""
        if "hà nội" in user_message or "ha noi" in user_message or "hn" in user_message:
            cursor.execute("SELECT name, address, phone_no FROM branch WHERE address LIKE '%Hà Nội%' OR address LIKE '%Ha Noi%'")
        elif "sài gòn" in user_message or "sai gon" in user_message or "hcm" in user_message or "tp hcm" in user_message or "thủ đức" in user_message or "thu duc" in user_message:
            cursor.execute("SELECT name, address, phone_no FROM branch WHERE address LIKE '%HCM%' OR address LIKE '%Hồ Chí Minh%' OR address LIKE '%Thủ Đức%'")
        else:
            cursor.execute("SELECT name, address, phone_no FROM branch")
            
        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        
        if not rows:
            return "Hệ thống World Cinema hiện có các cụm rạp tại Hà Nội và TP. Hồ Chí Minh."
            
        response = "Danh sách các chi nhánh rạp <b>World Cinema</b>:<br>"
        for idx, row in enumerate(rows):
            phone = f" (Hotline: {row[2]})" if row[2] else ""
            response += f"{idx + 1}. <b>{row[0]}</b> - Địa chỉ: {row[1]}{phone}<br>"
        return response
    except mysql.connector.Error as ex:
        print("Lỗi khi truy vấn danh sách rạp:", ex)
        return "Đã xảy ra lỗi khi lấy danh sách rạp World Cinema."

def get_thong_tin_phim_response(user_message=""):
    try:
        connection = get_connection()
        cursor = connection.cursor()
        user_message = user_message.lower()
        cursor.execute("SELECT name, director, actors, categories, duration, release_date, rated, is_showing, short_description FROM movie")
        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        
        for row in rows:
            movie_name = row[0]
            if movie_name.lower() in user_message:
                status_str = "Đang chiếu tại rạp" if row[7] == 1 else "Sắp chiếu"
                return (f"🎬 <b>Thông tin phim: {movie_name}</b> ({status_str})<br>"
                        f"- Đạo diễn: {row[1] or 'Đang cập nhật'}<br>"
                        f"- Diễn viên: {row[2] or 'Đang cập nhật'}<br>"
                        f"- Thể loại: {row[3] or 'Đang cập nhật'}<br>"
                        f"- Thời lượng: {row[4]} phút<br>"
                        f"- Ngày khởi chiếu: {row[5]}<br>"
                        f"- Độ tuổi: {row[6] or 'Mọi lứa tuổi'}<br>"
                        f"- Nội dung tóm tắt: {row[8] or ''}")
        return None
    except Exception as e:
        print("Lỗi khi tìm thông tin phim:", e)
        return None

def get_gio_ngay_chieu_theo_chi_nhanh(movie_name):
    try:
        connection = get_connection()
        cursor = connection.cursor()
        query = """
        SELECT b.name, lc.start_time, lc.start_date, lc.price
        FROM schedule lc
        JOIN movie p ON lc.movie_id = p.id
        JOIN room r ON lc.room_id = r.id
        JOIN branch b ON r.branch_id = b.id
        WHERE p.name LIKE %s AND lc.start_date >= CURDATE()
        ORDER BY b.name, lc.start_date, lc.start_time
        """
        cursor.execute(query, (f"%{movie_name}%",))
        rows = cursor.fetchall()
        result = {}
        for row in rows:
            branch_name = row[0]
            start_time = row[1]
            start_date = row[2]
            price = row[3] or 0
            
            if isinstance(start_time, timedelta):
                total_seconds = int(start_time.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                start_time_str = f"{hours:02d}:{minutes:02d}"
            else:
                start_time_str = str(start_time)
                
            start_date_str = start_date.strftime("%Y-%m-%d")
            time_str = f"{start_time_str} ({start_date_str}) - Giá vé: {price:,.0f}đ"
            if branch_name not in result:
                result[branch_name] = []
            result[branch_name].append(time_str)
            
        cursor.close()
        connection.close()
        return result
    except Exception as ex:
        print("Lỗi khi lấy lịch chiếu:", ex)
        return {}

def get_ten_phim():
    """Lấy danh sách phim đang chiếu tại World Cinema (is_showing = 1)"""
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT name, categories, duration FROM movie WHERE is_showing = 1 ORDER BY id DESC")
        rows = cursor.fetchall()
        res = [f"{row[0]} ({row[1]}, {row[2]} phút)" for row in rows]
        cursor.close()
        connection.close()
        return res
    except Exception as e:
        print("Lỗi:", e)
        return []

def get_phim_sap_chieu():
    """Lấy danh sách phim sắp chiếu tại World Cinema (is_showing = 0)"""
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT name, release_date, categories, director FROM movie WHERE is_showing = 0 ORDER BY release_date ASC")
        rows = cursor.fetchall()
        res = []
        for row in rows:
            res.append({
                "name": row[0],
                "release_date": str(row[1]),
                "categories": row[2] or "Chưa phân loại",
                "director": row[3] or "Đang cập nhật"
            })
        cursor.close()
        connection.close()
        return res
    except Exception as e:
        print("Lỗi:", e)
        return []

def LayMaSuatChieu(current_context, movie_name, ngay_chieu, gio_chieu, branch_name=None):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if "-" in ngay_chieu:
            ngay_chieu_sql = ngay_chieu
        else:
            try:
                ngay_chieu_sql = datetime.strptime(ngay_chieu, "%d/%m/%Y").strftime("%Y-%m-%d")
            except:
                ngay_chieu_sql = ngay_chieu

        if len(gio_chieu) == 5:
            gio_chieu = gio_chieu + ":00"

        if branch_name:
            query = """
            SELECT lc.id, b.id, p.id, lc.start_date, r.id, lc.start_time
            FROM schedule lc
            JOIN movie p ON lc.movie_id = p.id
            JOIN room r ON lc.room_id = r.id
            JOIN branch b ON r.branch_id = b.id
            WHERE (p.name = %s OR p.name LIKE %s) AND lc.start_date = %s AND lc.start_time = %s AND (b.name = %s OR b.name LIKE %s)
            """
            params = (movie_name, f"%{movie_name}%", ngay_chieu_sql, gio_chieu, branch_name, f"%{branch_name}%")
        else:
            query = """
            SELECT lc.id, b.id, p.id, lc.start_date, r.id, lc.start_time
            FROM schedule lc
            JOIN movie p ON lc.movie_id = p.id
            JOIN room r ON lc.room_id = r.id
            JOIN branch b ON r.branch_id = b.id
            WHERE (p.name = %s OR p.name LIKE %s) AND lc.start_date = %s AND lc.start_time = %s
            LIMIT 1
            """
            params = (movie_name, f"%{movie_name}%", ngay_chieu_sql, gio_chieu)

        cursor.execute(query, params)
        result = cursor.fetchall()
        if result:
            return result[0][0], result[0][1], result[0][2], result[0][3].strftime("%Y-%m-%d"), result[0][4], str(result[0][5])
        return None, None, None, None, None, None
    except Exception as e:
        print(f"Lỗi khi xử lý yêu cầu: {str(e)}")
        return None, None, None, None, None, None
    finally:
        cursor.close()
        connection.close()

def get_danh_sach_bap_nuoc():
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT name, description, price FROM food_item WHERE status = 1")
        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        if not rows:
            return "Hiện tại không có thông tin bắp nước."
        res = "Danh sách combo bắp nước tại rạp:\n"
        for row in rows:
            price = row[2] or 0
            res += f"- {row[0]}: {row[1]} - Giá: {price:,.0f}đ\n"
        return res
    except Exception as e:
        print("Lỗi khi lấy bắp nước:", e)
        return "Lỗi khi truy vấn bắp nước."

def get_danh_gia_phim(movie_name):
    try:
        connection = get_connection()
        cursor = connection.cursor()
        query = """
        SELECT AVG(mr.rating_score), COUNT(mr.id)
        FROM movie_rating mr
        JOIN movie p ON mr.movie_id = p.id
        WHERE p.name LIKE %s
        """
        cursor.execute(query, (f"%{movie_name}%",))
        row = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if row and row[1] > 0:
            avg_rating = float(row[0])
            count = row[1]
            return f"Phim {movie_name} được khán giả đánh giá trung bình {avg_rating:.1f}/5 sao (từ {count} lượt đánh giá)."
        return f"Hiện tại chưa có đánh giá nào cho phim {movie_name}."
    except Exception as e:
        print("Lỗi khi lấy đánh giá phim:", e)
        return "Không thể tra cứu đánh giá phim lúc này."

def get_remaining_seats(movie_name: str, branch_name: str, date: str, time: str) -> str:
    """Đếm số ghế trống cho một suất chiếu cụ thể."""
    maLichChieu, maRap, maPhim, ngayChieu, maPhong, gioChieu = LayMaSuatChieu(None, movie_name, date, time, branch_name)
    if not maLichChieu:
        return f"Không tìm thấy suất chiếu {time} ngày {date} cho phim {movie_name} tại {branch_name}."
    
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        # Đếm tổng số ghế của phòng chiếu
        cursor.execute("SELECT COUNT(id) FROM seat WHERE room_id = %s", (maPhong,))
        total_seats = cursor.fetchone()[0] or 0
        
        # Đếm số ghế đã được đặt cho suất chiếu này
        cursor.execute("SELECT COUNT(id) FROM ticket WHERE schedule_id = %s", (maLichChieu,))
        booked_seats = cursor.fetchone()[0] or 0
        
        cursor.close()
        connection.close()
        
        remaining = total_seats - booked_seats
        if remaining <= 0:
            return f"Suất chiếu {time} ngày {date} cho phim {movie_name} tại {branch_name} đã CHÁY VÉ (Hết ghế trống)."
        
        return f"Suất chiếu {time} ngày {date} cho phim {movie_name} tại {branch_name} hiện còn {remaining} ghế trống (Tổng: {total_seats}, Đã đặt: {booked_seats})."
    except Exception as e:
        print("Lỗi khi đếm ghế:", e)
        return "Lỗi khi kiểm tra số ghế trống."