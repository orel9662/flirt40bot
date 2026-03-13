import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "dating_bot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            gender TEXT,
            name TEXT,
            age INTEGER,
            city TEXT,
            bio TEXT,
            photo_file_id TEXT,
            id_card_file_id TEXT,
            status TEXT DEFAULT 'pending',
            is_blocked INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            to_user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(from_user_id, to_user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER,
            user2_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS seen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            viewer_id INTEGER,
            viewed_id INTEGER,
            UNIQUE(viewer_id, viewed_id)
        )
    """)

    conn.commit()
    conn.close()


def add_user(user_id, username, gender, name, age, city, bio, photo_file_id, id_card_file_id):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO users
        (user_id, username, gender, name, age, city, bio, photo_file_id, id_card_file_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
    """, (user_id, username, gender, name, age, city, bio, photo_file_id, id_card_file_id))
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def get_pending_users():
    conn = get_conn()
    users = conn.execute("SELECT * FROM users WHERE status = 'pending'").fetchall()
    conn.close()
    return users


def approve_user(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET status = 'approved' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def reject_user(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET status = 'rejected' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def block_user(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def unblock_user(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET is_blocked = 0, status = 'approved' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def delete_id_card(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET id_card_file_id = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_next_profile(viewer_id, viewer_gender):
    """Get next unseen profile for viewer. Women see men, men see women."""
    target_gender = "male" if viewer_gender == "female" else "female"
    conn = get_conn()
    profile = conn.execute("""
        SELECT * FROM users
        WHERE gender = ?
        AND status = 'approved'
        AND is_blocked = 0
        AND user_id != ?
        AND user_id NOT IN (
            SELECT viewed_id FROM seen WHERE viewer_id = ?
        )
        ORDER BY RANDOM()
        LIMIT 1
    """, (target_gender, viewer_id, viewer_id)).fetchone()
    conn.close()
    return profile


def mark_seen(viewer_id, viewed_id):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO seen (viewer_id, viewed_id) VALUES (?, ?)",
                 (viewer_id, viewed_id))
    conn.commit()
    conn.close()


def add_like(from_user_id, to_user_id):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO likes (from_user_id, to_user_id) VALUES (?, ?)",
                 (from_user_id, to_user_id))
    conn.commit()
    conn.close()


def check_mutual_like(user1_id, user2_id):
    conn = get_conn()
    result = conn.execute("""
        SELECT COUNT(*) as cnt FROM likes
        WHERE from_user_id = ? AND to_user_id = ?
    """, (user2_id, user1_id)).fetchone()
    conn.close()
    return result["cnt"] > 0


def save_match(user1_id, user2_id):
    conn = get_conn()
    conn.execute("INSERT INTO matches (user1_id, user2_id) VALUES (?, ?)",
                 (user1_id, user2_id))
    conn.commit()
    conn.close()


def add_appeal(user_id, message):
    conn = get_conn()
    conn.execute("INSERT INTO appeals (user_id, message) VALUES (?, ?)",
                 (user_id, message))
    conn.commit()
    conn.close()


def get_pending_appeals():
    conn = get_conn()
    appeals = conn.execute("""
        SELECT a.*, u.name, u.age FROM appeals a
        JOIN users u ON a.user_id = u.user_id
        WHERE a.status = 'pending'
    """).fetchall()
    conn.close()
    return appeals


def resolve_appeal(appeal_id, status):
    conn = get_conn()
    conn.execute("UPDATE appeals SET status = ? WHERE id = ?", (status, appeal_id))
    conn.commit()
    conn.close()


def get_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) as c FROM users WHERE status='pending'").fetchone()["c"]
    approved = conn.execute("SELECT COUNT(*) as c FROM users WHERE status='approved'").fetchone()["c"]
    blocked = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_blocked=1").fetchone()["c"]
    matches = conn.execute("SELECT COUNT(*) as c FROM matches").fetchone()["c"]
    conn.close()
    return {"total": total, "pending": pending, "approved": approved, "blocked": blocked, "matches": matches}
