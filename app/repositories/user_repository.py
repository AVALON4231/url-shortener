from passlib.context import CryptContext
from app.db import get_db, DB_TYPE

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

class UserRepository:
    def create_user(self, email: str, password: str) -> bool:
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

    def get_user_by_email(self, email: str):
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
            return {
                "id": row["id"],
                "email": row["email"],
                "hashed_password": row["hashed_password"],
                "created_at": row["created_at"]
            }

    def verify_password(self, plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)