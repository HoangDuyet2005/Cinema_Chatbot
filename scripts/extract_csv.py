import requests
from bs4 import BeautifulSoup
import ollama
import csv
import json

urls = [
    "https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26052",
    "https://xaydungchinhsach.chinhphu.vn/thu-tuc-dang-ky-dat-dai-tai-san-gan-lien-voi-dat-cap-so-do-lan-dau-voi-ho-gia-dinh-ca-nhan-cong-dong-dan-cu-nguoi-goc-viet-nam-dinh-cu-o-nuoc-ngoai-119250829141421258.htm",
    "https://vietnamnet.vn/huong-dan-thu-tuc-lam-giay-khai-sinh-2478874.html"
]

def get_text_from_url(url):
    try:
        # Tắt check SSL vì một số trang chính phủ bị lỗi SSL
        res = requests.get(url, verify=False, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        text = soup.get_text(separator='\n')
        # collapse whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Limit text length to avoid context overflow
        return text[:4000]
    except Exception as e:
        print(f"Error reading {url}: {e}")
        return ""

prompt_template = """Trích xuất thông tin thủ tục hành chính từ văn bản dưới đây.
Định dạng JSON với các trường:
{
  "code": "Mã thủ tục (tự tạo mã ngắn gọn, VD: TTHC-001 nếu không có)",
  "title": "Tên thủ tục (ngắn gọn, chính xác)",
  "description": "Mô tả ngắn gọn",
  "fee": "Lệ phí (VD: Miễn phí, 50.000đ)",
  "duration": "Thời gian giải quyết (VD: 1 ngày, 5 ngày làm việc)",
  "process_steps": "Các bước thực hiện (tóm tắt các bước, đánh số 1, 2, 3)"
}

Văn bản:
"""

results = []

for idx, url in enumerate(urls):
    print(f"Processing URL {idx+1}: {url}")
    text = get_text_from_url(url)
    if not text:
        continue
        
    try:
        response = ollama.chat(
            model='qwen2.5',
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts administrative procedures into strict JSON format."},
                {"role": "user", "content": prompt_template + text}
            ],
            options={"temperature": 0.1},
            format="json"
        )
        data = json.loads(response['message']['content'])
        results.append(data)
        print("Success!")
    except Exception as e:
        print(f"Ollama error: {e}")

# Write to CSV
csv_file = "d:/Nam3-Ky2/VissSoft/mini-app/Template_ThuTuc.csv"
headers = ['Mã thủ tục', 'Tên thủ tục', 'Mô tả', 'Lệ phí', 'Thời gian', 'Các bước']

try:
    with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in results:
            writer.writerow([
                r.get('code', f'TTHC-NEW-{len(results)}'),
                r.get('title', ''),
                r.get('description', ''),
                r.get('fee', 'Miễn phí'),
                r.get('duration', ''),
                r.get('process_steps', '')
            ])
    print(f"Saved to {csv_file}")
except Exception as e:
    print(f"Error writing CSV: {e}")
