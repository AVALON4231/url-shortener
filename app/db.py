import os
import string
import secrets
import sqlite3

DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_DEFAULT = "sqlite:///urls.db"

if DATABASE_URL:
    DB_TYPE = "postgres"
    import psycopg2
else:
    DB_TYPE = "sqlite"


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
        except Exception:
            pass
    conn.commit()
    cur.close()
    conn.close()


def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))