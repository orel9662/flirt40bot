import sqlite3
import os
from datetime import datetime, date, timedelta

# ב-Railway מומלץ להגדיר Volume בנתיב /data ולכוון את ה-DB לשם
DB_PATH = os.environ.get("DB_PATH", "dating_bot.db")
FIRST_USERS_BONUS = 20
FIRST_USERS_COUNT = 20
FREE_DAILY_LIKES = 10
PREMIUM_PRICE_STARS = 1000

REGIONS = {
    "north": "צפון 🌿",
    "center": "מרכז 🏙",
    "south": "דרום 🌵"
}

RULES_TEXT = (
    "📋 *כללי Flirt40*\n\n"
    "🇮🇱\n"
    "✅ שמור/י על שיח מכבד ונעים\n"
    "✅ תמונות אמיתיות ועדכניות בלבד\n"
    "❌ אסור להטריד, לאיים או לפגוע\n"
    "❌ אסור לשלוח תוכן פוגעני או בלתי הולם\n"
    "❌ אסור להתחזות לאדם אחר\n"
    "⚠️ הפרת הכללים תגרור השעיה או חסימה.\n\n"
    "🇬🇧\n"
    "✅ Be respectful and kind\n"
    "✅ Real and recent photos only\n"
    "❌ No harassment, threats or harm\n"
    "❌ No offensive or inappropriate content\n"
    "❌ No impersonation\n"
    "⚠️ Violations may result in suspension or ban."
)

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10) # הוספת timeout למניעת נעילות
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # יצירת כל הטבלאות במרוכז
    tables = [
        """CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, gender TEXT, name TEXT, age INTEGER,
            region TEXT, city TEXT, bio TEXT, status TEXT DEFAULT 'pending',
            is_blocked INTEGER DEFAULT 0, is_suspended INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0, premium_until TIMESTAMP,
            bonus_likes INTEGER DEFAULT 0, likes_used_today INTEGER DEFAULT 0,
            likes_reset_date TEXT, filter_region TEXT, id_card_file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS deleted_users (
            user_id INTEGER PRIMARY KEY, username TEXT, gender TEXT, name TEXT, age INTEGER,
            region TEXT, city TEXT, had_reports INTEGER DEFAULT 0, 
            had_blocks INTEGER DEFAULT 0, deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS user_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, file_id TEXT, position INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER, reported_id INTEGER,
            reason TEXT, evidence_file_id TEXT, status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS bug_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, description TEXT,
            status TEXT DEFAULT 'open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, from_user_id INTEGER, to_user_id INTEGER,
            message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(from_user_id, to_user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user1_id INTEGER, user2_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT,
            status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS seen (
            id INTEGER PRIMARY KEY AUTOINCREMENT, viewer_id INTEGER, viewed_id INTEGER,
            UNIQUE(viewer_id, viewed_id)
        )""",
        """CREATE TABLE IF NOT EXISTS active_chats (
            user_id INTEGER PRIMARY KEY, partner_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS chat_consents (
            user_id INTEGER, partner_id INTEGER, PRIMARY KEY (user_id, partner_id)
        )""",
        """CREATE TABLE IF NOT EXISTS share_consents (
            user_id INTEGER, partner_id INTEGER, PRIMARY KEY (user_id, partner_id)
        )""",
        """CREATE TABLE IF NOT EXISTS premium_interest (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    ]
    
    for table in tables:
        c.execute(table)
        
    conn.commit()
    conn.close()

# --- פונקציות עזר וניהול משתמשים ---

def add_user(user_id, username, gender, name, age, region, city, bio, id_card_file_id, photos):
    conn = get_conn()
    try:
        deleted = conn.execute("SELECT * FROM deleted_users WHERE user_id = ?", (user_id,)).fetchone()
        count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        bonus = FIRST_USERS_BONUS if count < FIRST_USERS_COUNT else 0
        
        conn.execute("""
            INSERT OR REPLACE INTO users
            (user_id, username, gender, name, age, region, city, bio, id_card_file_id, status, bonus_likes, filter_region)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (user_id, username, gender, name, age, region, city, bio, id_card_file_id, bonus, region))
        
        conn.execute("DELETE FROM user_photos WHERE user_id = ?", (user_id,))
        for i, file_id in enumerate(photos):
            conn.execute("INSERT INTO user_photos (user_id, file_id, position) VALUES (?, ?, ?)",
                         (user_id, file_id, i))
        conn.commit()
        return bonus, deleted
    finally:
        conn.close()

def get_user(user_id):
    conn = get_conn()
    try:
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    finally:
        conn.close()

def get_user_photos(user_id):
    conn = get_conn()
    try:
        photos = conn.execute("SELECT file_id FROM user_photos WHERE user_id = ? ORDER BY position", (user_id,)).fetchall()
        return [p["file_id"] for p in photos]
    finally:
        conn.close()

def check_and_use_like(user_id):
    conn = get_conn()
    try:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user: return False, 0
        
        today = date.today().isoformat()
        
        # בדיקת פרימיום
        if user["is_premium"] and user["premium_until"]:
            if datetime.fromisoformat(user["premium_until"]) < datetime.now():
                conn.execute("UPDATE users SET is_premium = 0 WHERE user_id = ?", (user_id,))
                conn.commit()
                return True, -1 # הפך ללא פרימיום אבל הלייק הנוכחי מאושר
            return True, -1

        # איפוס לייקים יומי
        if user["likes_reset_date"] != today:
            conn.execute("UPDATE users SET likes_used_today = 0, likes_reset_date = ? WHERE user_id = ?", (today, user_id))
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

        if user["bonus_likes"] > 0:
            conn.execute("UPDATE users SET bonus_likes = bonus_likes - 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            return True, user["bonus_likes"] - 1

        if user["likes_used_today"] < FREE_DAILY_LIKES:
            conn.execute("UPDATE users SET likes_used_today = likes_used_today + 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            return True, FREE_DAILY_LIKES - user["likes_used_today"] - 1

        return False, 0
    finally:
        conn.close()

def get_stats():
    conn = get_conn()
    try:
        stats = {}
        queries = {
            "total": "SELECT COUNT(*) FROM users",
            "pending": "SELECT COUNT(*) FROM users WHERE status='pending'",
            "approved": "SELECT COUNT
