import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
from dotenv import load_dotenv

load_dotenv(override=True)

from core.cinema_db import LayMaSuatChieu
from main import generate_booking_link

print(generate_booking_link('Avengers: Endgame', 'CGV Vincom Landmark 81', '19/08/2026', '18:00:00'))
