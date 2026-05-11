import sqlite3
import string
import random
from passlib.context import CryptContext

DATABASE_NAME = "urls.db"

# Настройка хеширования паролей
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def get_db():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    # Таблица пользователей
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Таблица ссылок с внешним ключом на пользователя
    conn.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            clicks INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    # Попытка добавить поле user_id в старую таблицу, если её структура без него (миграция)
    try:
        conn.execute("ALTER TABLE urls ADD COLUMN user_id INTEGER")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

# --- Функции для пользователей ---

def create_user(email: str, password: str):
    conn = get_db()
    hashed = pwd_context.hash(password)
    try:
        conn.execute(
            "INSERT INTO users (email, hashed_password) VALUES (?, ?)",
            (email, hashed)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # email уже существует
        return False
    finally:
        conn.close()

def get_user_by_email(email: str):
    conn = get_db()
    result = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return result

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# --- Функции для ссылок (привязаны к пользователю) ---

def create_short_link(original_url: str, user_id: int):
    conn = get_db()
    short_code = generate_short_code()
    while conn.execute("SELECT id FROM urls WHERE short_code = ?", (short_code,)).fetchone():
        short_code = generate_short_code()
    
    conn.execute(
        "INSERT INTO urls (short_code, original_url, user_id) VALUES (?, ?, ?)",
        (short_code, original_url, user_id)
    )
    conn.commit()
    return short_code

def get_original_url(short_code: str):
    conn = get_db()
    result = conn.execute(
        "SELECT original_url FROM urls WHERE short_code = ?",
        (short_code,)
    ).fetchone()
    conn.close()
    if result:
        return result["original_url"]
    return None

def increment_clicks(short_code: str):
    conn = get_db()
    conn.execute(
        "UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?",
        (short_code,)
    )
    conn.commit()
    conn.close()

def get_stats(short_code: str, user_id: int):
    """Возвращает статистику только если ссылка принадлежит данному пользователю."""
    conn = get_db()
    result = conn.execute(
        "SELECT original_url, short_code, clicks, created_at FROM urls WHERE short_code = ? AND user_id = ?",
        (short_code, user_id)
    ).fetchone()
    conn.close()
    if result:
        return dict(result)
    return None