import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id SERIAL PRIMARY KEY,
            title TEXT UNIQUE NOT NULL,
            file_id TEXT NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def add_video(title, file_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO videos (title, file_id) VALUES (%s, %s)
        ON CONFLICT (title) DO UPDATE SET file_id = excluded.file_id
    """, (title, file_id))
    conn.commit()
    cur.close()
    conn.close()

def get_video_by_title(title):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT file_id FROM videos WHERE title = %s", (title,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

def get_video_by_id(vid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT file_id, title FROM videos WHERE id = %s", (vid,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def get_all_videos():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title FROM videos ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def delete_video_by_id(vid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM videos WHERE id = %s", (vid,))
    conn.commit()
    cur.close()
    conn.close()
