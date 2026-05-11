import os
import string
import random
import psycopg2
from passlib.context import CryptContext

# Читаем DATABASE_URL из переменной окружения (Render передаст её автоматически)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set!")

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def get_db():
    """Подключение к PostgreSQL (каждый раз новое, для простоты)."""
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Создаём таблицы, если их нет."""
    conn = get_db()
    cur = conn.cursor()
    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Таблица ссылок
    cur.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id SERIAL PRIMARY KEY,
            short_code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id),
            clicks INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

# --- Пользователи ---
def create_user(email: str, password: str):
    conn = get_db()
    cur = conn.cursor()
    hashed = pwd_context.hash(password)
    try:
        cur.execute(
            "INSERT INTO users (email, hashed_password) VALUES (%s, %s)",
            (email, hashed)
        )
        conn.commit()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def get_user_by_email(email: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        # преобразуем кортеж в словарь для совместимости
        cols = ['id', 'email', 'hashed_password', 'created_at']
        return dict(zip(cols, row))
    return None

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# --- Ссылки ---
def create_short_link(original_url: str, user_id: int):
    conn = get_db()
    cur = conn.cursor()
    short_code = generate_short_code()
    # Проверка уникальности
    while True:
        cur.execute("SELECT id FROM urls WHERE short_code = %s", (short_code,))
        if cur.fetchone() is None:
            break
        short_code = generate_short_code()
    cur.execute(
        "INSERT INTO urls (short_code, original_url, user_id) VALUES (%s, %s, %s)",
        (short_code, original_url, user_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return short_code

def get_original_url(short_code: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT original_url FROM urls WHERE short_code = %s", (short_code,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

def increment_clicks(short_code: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE urls SET clicks = clicks + 1 WHERE short_code = %s", (short_code,))
    conn.commit()
    cur.close()
    conn.close()

def get_stats(short_code: str, user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT original_url, short_code, clicks, created_at FROM urls WHERE short_code = %s AND user_id = %s",
        (short_code, user_id)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        cols = ['original_url', 'short_code', 'clicks', 'created_at']
        return dict(zip(cols, row))
    return None