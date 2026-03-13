import sqlite3
import os
from datetime import datetime, date, timedelta

DB_PATH = os.environ.get("DB_PATH", "dating_bot.db")
FIRST_USERS_BONUS = 20
FIRST_USERS_COUNT = 20
FREE_DAILY_LIKES = 10
PREMIUM_PRICE_STARS = 1000


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
            is_premium INTEGER DEFAULT 0,
            premium_until TIMESTAMP,
            bonus_likes INTEGER DEFAULT 0,
            likes_used_today INTEGER DEFAULT 0,
            likes_reset_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            to_user_id INTEGER,
            message TEXT,
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS active_chats (
            user_id INTEGER PRIMARY KEY,
            partner_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_consents (
            user_id INTEGER,
            partner_id INTEGER,
            PRIMARY KEY (user_id, partner_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS share_consents (
            user_id INTEGER,
            partner_id INTEGER,
            PRIMARY KEY (user_id, partner_id)
        )
    """)
    conn.commit()
    conn.close()


def add_user(user_id, username, gender, name, age, city, bio, photo_file_id, id_card_file_id):
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    bonus = FIRST_USERS_BONUS if count < FIRST_USERS_COUNT else 0
    conn.execute("""
        INSERT OR REPLACE INTO users
        (user_id, username, gender, name, age, city, bio, photo_file_id, id_card_file_id, status, bonus_likes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (user_id, username, gender, name, age, city, bio, photo_file_id, id_card_file_id, bonus))
    conn.commit()
    conn.close()
    return bonus


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


def set_premium(user_id, days=30):
    conn = get_conn()
    until = datetime.now() + timedelta(days=days)
    conn.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?",
                 (until.isoformat(), user_id))
    conn.commit()
    conn.close()
    return until


def revoke_premium(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET is_premium = 0, premium_until = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def add_bonus_likes(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE users SET bonus_likes = bonus_likes + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def add_bonus_likes_all(amount):
    conn = get_conn()
    conn.execute("UPDATE users SET bonus_likes = bonus_likes + ? WHERE status = 'approved' AND is_blocked = 0", (amount,))
    affected = conn.execute("SELECT COUNT(*) as c FROM users WHERE status = 'approved' AND is_blocked = 0").fetchone()["c"]
    conn.commit()
    conn.close()
    return affected


def check_and_use_like(user_id):
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return False, 0

    today = date.today().isoformat()

    # Check premium expiry
    if user["is_premium"] and user["premium_until"]:
        if datetime.fromisoformat(user["premium_until"]) < datetime.now():
            conn.execute("UPDATE users SET is_premium = 0 WHERE user_id = ?", (user_id,))
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    if user["is_premium"]:
        conn.close()
        return True, -1

    # Reset daily likes
    if user["likes_reset_date"] != today:
        conn.execute("UPDATE users SET likes_used_today = 0, likes_reset_date = ? WHERE user_id = ?",
                     (today, user_id))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    # Use bonus likes first
    if user["bonus_likes"] > 0:
        conn.execute("UPDATE users SET bonus_likes = bonus_likes - 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        remaining = user["bonus_likes"] - 1
        conn.close()
        return True, remaining

    # Use daily likes
    if user["likes_used_today"] < FREE_DAILY_LIKES:
        conn.execute("UPDATE users SET likes_used_today = likes_used_today + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        remaining = FREE_DAILY_LIKES - user["likes_used_today"] - 1
        conn.close()
        return True, remaining

    conn.close()
    return False, 0


def get_likes_status(user_id):
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return None
    today = date.today().isoformat()
    if user["is_premium"]:
        conn.close()
        return {"type": "premium", "remaining": -1}
    if user["likes_reset_date"] != today:
        daily_remaining = FREE_DAILY_LIKES
    else:
        daily_remaining = FREE_DAILY_LIKES - user["likes_used_today"]
    conn.close()
    return {"type": "free", "daily_remaining": max(0, daily_remaining), "bonus_likes": user["bonus_likes"]}


def get_next_profile(viewer_id, viewer_gender):
    target_gender = "male" if viewer_gender == "female" else "female"
    conn = get_conn()
    profile = conn.execute("""
        SELECT * FROM users
        WHERE gender = ? AND status = 'approved' AND is_blocked = 0 AND user_id != ?
        AND user_id NOT IN (SELECT viewed_id FROM seen WHERE viewer_id = ?)
        ORDER BY is_premium DESC, RANDOM()
        LIMIT 1
    """, (target_gender, viewer_id, viewer_id)).fetchone()
    conn.close()
    return profile


def mark_seen(viewer_id, viewed_id):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO seen (viewer_id, viewed_id) VALUES (?, ?)", (viewer_id, viewed_id))
    conn.commit()
    conn.close()


def add_like(from_user_id, to_user_id, message=None):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO likes (from_user_id, to_user_id, message) VALUES (?, ?, ?)",
                 (from_user_id, to_user_id, message))
    conn.commit()
    conn.close()


def get_like_message(from_user_id, to_user_id):
    conn = get_conn()
    result = conn.execute("SELECT message FROM likes WHERE from_user_id = ? AND to_user_id = ?",
                          (from_user_id, to_user_id)).fetchone()
    conn.close()
    return result["message"] if result else None


def check_mutual_like(user1_id, user2_id):
    conn = get_conn()
    result = conn.execute("SELECT COUNT(*) as cnt FROM likes WHERE from_user_id = ? AND to_user_id = ?",
                          (user2_id, user1_id)).fetchone()
    conn.close()
    return result["cnt"] > 0


def save_match(user1_id, user2_id):
    conn = get_conn()
    conn.execute("INSERT INTO matches (user1_id, user2_id) VALUES (?, ?)", (user1_id, user2_id))
    conn.commit()
    conn.close()


def add_appeal(user_id, message):
    conn = get_conn()
    conn.execute("INSERT INTO appeals (user_id, message) VALUES (?, ?)", (user_id, message))
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


def get_all_approved_users():
    conn = get_conn()
    users = conn.execute("SELECT * FROM users WHERE status = 'approved' AND is_blocked = 0").fetchall()
    conn.close()
    return users


def get_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) as c FROM users WHERE status='pending'").fetchone()["c"]
    approved = conn.execute("SELECT COUNT(*) as c FROM users WHERE status='approved'").fetchone()["c"]
    blocked = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_blocked=1").fetchone()["c"]
    matches = conn.execute("SELECT COUNT(*) as c FROM matches").fetchone()["c"]
    premium = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_premium=1").fetchone()["c"]
    conn.close()
    return {"total": total, "pending": pending, "approved": approved,
            "blocked": blocked, "matches": matches, "premium": premium}
