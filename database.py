import os
import string
import random
from passlib.context import CryptContext

DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_DEFAULT = "sqlite:///urls.db"

if DATABASE_URL:
    DB_TYPE = "postgres"
    import psycopg2
else:
    DB_TYPE = "sqlite"
    import sqlite3

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")


def get_db():
    if DB_TYPE == "postgres":
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect(SQLITE_DEFAULT.split("///")[1])
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    if DB_TYPE == "postgres":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id SERIAL PRIMARY KEY,
                short_code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users(id),
                clicks INTEGER DEFAULT 0,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Добавляем поле title, если таблица уже существовала без него
        cur.execute("ALTER TABLE urls ADD COLUMN IF NOT EXISTS title TEXT")
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users(id),
                clicks INTEGER DEFAULT 0,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            cur.execute("ALTER TABLE urls ADD COLUMN title TEXT")
        except:
            pass  # поле уже существует

    conn.commit()
    cur.close()
    conn.close()


def get_user_links(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    if DB_TYPE == "postgres":
        cur.execute(
            "SELECT original_url, short_code, title FROM urls WHERE user_id = %s ORDER BY created_at DESC LIMIT 20",
            (user_id,)
        )
    else:
        cur.execute(
            "SELECT original_url, short_code, title FROM urls WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (user_id,)
        )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    links = []
    for row in rows:
        links.append({
            "original_url": row[0],
            "short_code": row[1],
            "title": row[2] or row[0]  # если нет заголовка, покажем URL
        })
    return links


def update_link_title(short_code: str, title: str):
    conn = get_db()
    cur = conn.cursor()
    if DB_TYPE == "postgres":
        cur.execute("UPDATE urls SET title = %s WHERE short_code = %s", (title, short_code))
    else:
        cur.execute("UPDATE urls SET title = ? WHERE short_code = ?", (title, short_code))
    conn.commit()
    cur.close()
    conn.close()


def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))


def create_user(email: str, password: str):
    conn = get_db()
    cur = conn.cursor()
    hashed = pwd_context.hash(password)
    try:
        if DB_TYPE == "postgres":
            cur.execute("INSERT INTO users (email, hashed_password) VALUES (%s, %s)", (email, hashed))
        else:
            cur.execute("INSERT INTO users (email, hashed_password) VALUES (?, ?)", (email, hashed))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def get_user_by_email(email: str):
    conn = get_db()
    cur = conn.cursor()
    if DB_TYPE == "postgres":
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    else:
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    if DB_TYPE == "postgres":
        return {"id": row[0], "email": row[1], "hashed_password": row[2], "created_at": row[3]}
    else:
        return {"id": row["id"], "email": row["email"], "hashed_password": row["hashed_password"], "created_at": row["created_at"]}


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def create_short_link(original_url: str, user_id: int):
    conn = get_db()
    cur = conn.cursor()
    short_code = generate_short_code()
    while True:
        if DB_TYPE == "postgres":
            cur.execute("SELECT id FROM urls WHERE short_code = %s", (short_code,))
        else:
            cur.execute("SELECT id FROM urls WHERE short_code = ?", (short_code,))
        if cur.fetchone() is None:
            break
        short_code = generate_short_code()
    if DB_TYPE == "postgres":
        cur.execute("INSERT INTO urls (short_code, original_url, user_id) VALUES (%s, %s, %s)",
                    (short_code, original_url, user_id))
    else:
        cur.execute("INSERT INTO urls (short_code, original_url, user_id) VALUES (?, ?, ?)",
                    (short_code, original_url, user_id))
    conn.commit()
    cur.close()
    conn.close()
    return short_code


def get_original_url(short_code: str):
    conn = get_db()
    cur = conn.cursor()
    if DB_TYPE == "postgres":
        cur.execute("SELECT original_url FROM urls WHERE short_code = %s", (short_code,))
    else:
        cur.execute("SELECT original_url FROM urls WHERE short_code = ?", (short_code,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def increment_clicks(short_code: str):
    conn = get_db()
    cur = conn.cursor()
    if DB_TYPE == "postgres":
        cur.execute("UPDATE urls SET clicks = clicks + 1 WHERE short_code = %s", (short_code,))
    else:
        cur.execute("UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?", (short_code,))
    conn.commit()
    cur.close()
    conn.close()


def get_stats(short_code: str, user_id: int):
    conn = get_db()
    cur = conn.cursor()
    if DB_TYPE == "postgres":
        cur.execute("SELECT original_url, short_code, clicks, created_at FROM urls WHERE short_code = %s AND user_id = %s",
                    (short_code, user_id))
    else:
        cur.execute("SELECT original_url, short_code, clicks, created_at FROM urls WHERE short_code = ? AND user_id = ?",
                    (short_code, user_id))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {"original_url": row[0], "short_code": row[1], "clicks": row[2], "created_at": row[3]}
    return None