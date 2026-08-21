import sys
sys.path.append('D:/CGV/ai-service')
from core.cinema_db import get_ten_phim, get_phim_sap_chieu, get_danh_sach_rap, get_gio_ngay_chieu_theo_chi_nhanh, LayMaSuatChieu

print('=== 1. PHIM DANG CHIEU TU DATABASE ===')
movies = get_ten_phim()
for m in movies:
    print('  -', m)

print('\n=== 2. PHIM SAP CHIEU TU DATABASE ===')
upcoming = get_phim_sap_chieu()
for u in upcoming:
    print(f"  - {u['name']} (Khoi chieu: {u['release_date']}, The loai: {u['categories']})")

print('\n=== 3. DANH SACH RAP WORLD CINEMA TU DATABASE ===')
cinemas = get_danh_sach_rap()
print(cinemas.replace('<br>', '\n').replace('<b>', '').replace('</b>', ''))

print('=== 4. LICH CHIEU THUC TE (Vi du: Phim Nghỉ Hè Sợ Nghỉ Hưu) ===')
st = get_gio_ngay_chieu_theo_chi_nhanh('Nghỉ Hè Sợ Nghỉ Hưu')
for branch, times in st.items():
    print(f'  Rap {branch}:', times)