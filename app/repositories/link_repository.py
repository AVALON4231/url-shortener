from app.db import get_db, DB_TYPE, generate_short_code


class LinkRepository:
    def create_short_link(self, original_url: str, user_id: int) -> str:
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
            cur.execute(
                "INSERT INTO urls (short_code, original_url, user_id) VALUES (%s, %s, %s)",
                (short_code, original_url, user_id)
            )
        else:
            cur.execute(
                "INSERT INTO urls (short_code, original_url, user_id) VALUES (?, ?, ?)",
                (short_code, original_url, user_id)
            )
        conn.commit()
        cur.close()
        conn.close()
        return short_code

    def update_link_title(self, short_code: str, title: str):
        conn = get_db()
        cur = conn.cursor()
        if DB_TYPE == "postgres":
            cur.execute("UPDATE urls SET title = %s WHERE short_code = %s", (title, short_code))
        else:
            cur.execute("UPDATE urls SET title = ? WHERE short_code = ?", (title, short_code))
        conn.commit()
        cur.close()
        conn.close()

    def get_user_links(self, user_id: int):
        conn = get_db()
        cur = conn.cursor()
        if DB_TYPE == "postgres":
            cur.execute(
                """SELECT original_url, short_code, title, clicks, created_at
                   FROM urls WHERE user_id = %s ORDER BY created_at DESC LIMIT 20""",
                (user_id,)
            )
        else:
            cur.execute(
                """SELECT original_url, short_code, title, clicks, created_at
                   FROM urls WHERE user_id = ? ORDER BY created_at DESC LIMIT 20""",
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
                "title": row[2] or row[0],
                "clicks": row[3] or 0,
                "created_at": str(row[4]) if row[4] else None
            })
        return links

    def get_original_url(self, short_code: str):
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

    def increment_clicks(self, short_code: str):
        conn = get_db()
        cur = conn.cursor()
        if DB_TYPE == "postgres":
            cur.execute("UPDATE urls SET clicks = clicks + 1 WHERE short_code = %s", (short_code,))
        else:
            cur.execute("UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?", (short_code,))
        conn.commit()
        cur.close()
        conn.close()

    def delete_link(self, short_code: str, user_id: int) -> bool:
        conn = get_db()
        cur = conn.cursor()
        if DB_TYPE == "postgres":
            cur.execute("DELETE FROM urls WHERE short_code = %s AND user_id = %s",
                        (short_code, user_id))
        else:
            cur.execute("DELETE FROM urls WHERE short_code = ? AND user_id = ?",
                        (short_code, user_id))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        conn.close()
        return deleted
    def get_stats(self, short_code: str, user_id: int):
        conn = get_db()
        cur = conn.cursor()
        if DB_TYPE == "postgres":
            cur.execute(
                "SELECT original_url, short_code, clicks, created_at FROM urls WHERE short_code = %s AND user_id = %s",
                (short_code, user_id)
            )
        else:
            cur.execute(
                "SELECT original_url, short_code, clicks, created_at FROM urls WHERE short_code = ? AND user_id = ?",
                (short_code, user_id)
            )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {
                "original_url": row[0],
                "short_code": row[1],
                "clicks": row[2],
                "created_at": row[3]
            }
        return None    