import os
import urllib.parse
import mysql.connector
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    url = urllib.parse.urlparse(DATABASE_URL)
    DATABASE_HOST = url.hostname or "localhost"
    DATABASE_PORT = url.port or 3306
    DATABASE_USER = url.username or "root"
    DATABASE_PASSWORD = url.password or "***REMOVED_LEAKED_PASSWORD***"
    DATABASE_NAME = url.path.lstrip("/") if url.path else "cinema2"
else:
    DATABASE_HOST = os.getenv("DB_HOST", "localhost")
    DATABASE_PORT = int(os.getenv("DB_PORT", "3306"))
    DATABASE_USER = os.getenv("DB_USER", "root")
    DATABASE_PASSWORD = os.getenv("DB_PASSWORD", "***REMOVED_LEAKED_PASSWORD***")
    DATABASE_NAME = os.getenv("DB_NAME", "cinema2")

def get_db_connection():
    return mysql.connector.connect(
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_NAME,
        charset="utf8mb4"
    )