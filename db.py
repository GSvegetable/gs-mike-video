import sqlite3

DB_PATH = 'videos.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            file_id TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_video(title, file_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO videos (title, file_id) VALUES (?, ?)", (title, file_id))
    conn.commit()
    conn.close()

def get_video_by_title(title):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM videos WHERE title = ?", (title,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_video_by_id(vid):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM videos WHERE id = ?", (vid,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None
