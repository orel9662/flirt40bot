import os
import sqlite3
from flask import Flask, request, session, redirect, url_for, jsonify
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("WEB_SECRET_KEY", "flirt40-secret-2024")

DB_PATH = os.environ.get("DB_PATH", "dating_bot.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_WEB_PASSWORD", "admin123")

REGIONS = {
    "north": "צפון 🌿",
    "center": "מרכז 🏙",
    "south": "דרום 🌵"
}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda cursor, row: {
        col[0]: row[idx] for idx, col in enumerate(cursor.description)
    } if cursor.description else row
    return conn


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/")
        error = "סיסמה שגויה"
    return f"""<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flirt40 - כניסה</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0d0d0d; color: #fff; font-family: 'Segoe UI', sans-serif;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
  .box {{ background: #1a1a1a; border: 1px solid #333; border-radius: 16px;
          padding: 48px; width: 360px; text-align: center; }}
  h1 {{ font-size: 2rem; margin-bottom: 8px; }}
  .sub {{ color: #888; margin-bottom: 32px; font-size: 0.9rem; }}
  input {{ width: 100%; padding: 14px; background: #111; border: 1px solid #333;
           border-radius: 10px; color: #fff; font-size: 1rem; margin-bottom: 16px;
           outline: none; text-align: center; }}
  input:focus {{ border-color: #e91e8c; }}
  button {{ width: 100%; padding: 14px; background: #e91e8c; border: none;
            border-radius: 10px; color: #fff; font-size: 1rem; font-weight: bold;
            cursor: pointer; transition: opacity 0.2s; }}
  button:hover {{ opacity: 0.85; }}
  .error {{ color: #ff4444; font-size: 0.85rem; margin-top: 12px; }}
</style>
</head>
<body>
<div class="box">
  <h1>💋 Flirt40</h1>
  <p class="sub">פאנל ניהול</p>
  <form method="POST">
    <input type="password" name="password" placeholder="סיסמה" autofocus>
    <button type="submit">כניסה</button>
  </form>
  {f'<p class="error">{error}</p>' if error else ''}
</div>
</body>
</html>"""


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
@login_required
def index():
    conn = get_conn()
    stats = {
        "total": conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"],
        "pending": conn.execute("SELECT COUNT(*) as c FROM users WHERE status='pending'").fetchone()["c"],
        "approved": conn.execute("SELECT COUNT(*) as c FROM users WHERE status='approved'").fetchone()["c"],
        "blocked": conn.execute("SELECT COUNT(*) as c FROM users WHERE is_blocked=1").fetchone()["c"],
        "reports": conn.execute("SELECT COUNT(*) as c FROM reports WHERE status='pending'").fetchone()["c"],
        "matches": conn.execute("SELECT COUNT(*) as c FROM matches").fetchone()["c"],
    }
    conn.close()
    return f"""<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flirt40 Admin</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0d0d0d; color: #fff; font-family: 'Segoe UI', sans-serif; }}
  nav {{ background: #1a1a1a; border-bottom: 1px solid #2a2a2a; padding: 16px 32px;
         display: flex; align-items: center; justify-content: space-between; }}
  nav h1 {{ font-size: 1.4rem; color: #e91e8c; }}
  nav a {{ color: #aaa; text-decoration: none; margin-right: 24px; font-size: 0.9rem; }}
  nav a:hover {{ color: #fff; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 32px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 40px; }}
  .stat {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; padding: 24px; text-align: center; }}
  .stat-num {{ font-size: 2.5rem; font-weight: bold; color: #e91e8c; }}
  .stat-label {{ color: #888; font-size: 0.85rem; margin-top: 4px; }}
  .btn {{ display: inline-block; padding: 10px 20px; background: #e91e8c; color: #fff;
          border-radius: 8px; text-decoration: none; font-size: 0.9rem; font-weight: bold; margin: 4px; }}
  .btn-outline {{ background: transparent; border: 1px solid #e91e8c; color: #e91e8c; }}
  .btn-danger {{ background: #c0392b; }}
  .btn-warn {{ background: #e67e22; }}
  .section-title {{ font-size: 1.2rem; font-weight: bold; margin-bottom: 20px; color: #e91e8c; }}
  .quick-links {{ display: flex; flex-wrap: wrap; gap: 12px; }}
</style>
</head>
<body>
<nav>
  <h1>💋 Flirt40 Admin</h1>
  <div>
    <a href="/">🏠 ראשי</a>
    <a href="/users">👥 משתמשים</a>
    <a href="/reports">🚨 דיווחים</a>
    <a href="/logout">יציאה</a>
  </div>
</nav>
<div class="container">
  <div class="stats">
    <div class="stat"><div class="stat-num">{stats['total']}</div><div class="stat-label">סה"כ משתמשים</div></div>
    <div class="stat"><div class="stat-num" style="color:#f39c12">{stats['pending']}</div><div class="stat-label">ממתינים לאישור</div></div>
    <div class="stat"><div class="stat-num" style="color:#2ecc71">{stats['approved']}</div><div class="stat-label">מאושרים</div></div>
    <div class="stat"><div class="stat-num" style="color:#e74c3c">{stats['blocked']}</div><div class="stat-label">חסומים</div></div>
    <div class="stat"><div class="stat-num" style="color:#e91e8c">{stats['reports']}</div><div class="stat-label">דיווחים פתוחים</div></div>
    <div class="stat"><div class="stat-num" style="color:#9b59b6">{stats['matches']}</div><div class="stat-label">התאמות</div></div>
  </div>
  <p class="section-title">קישורים מהירים</p>
  <div class="quick-links">
    <a href="/users?status=pending" class="btn">⏳ ממתינים ({stats['pending']})</a>
    <a href="/users?status=approved" class="btn btn-outline">✅ מאושרים</a>
    <a href="/reports" class="btn btn-warn">🚨 דיווחים ({stats['reports']})</a>
    <a href="/users" class="btn btn-outline">👥 כל המשתמשים</a>
  </div>
</div>
</body>
</html>"""


@app.route("/users")
@login_required
def users():
    conn = get_conn()
    status_filter = request.args.get("status", "")
    search = request.args.get("search", "")
    page = int(request.args.get("page", 1))
    per_page = 12

    where = "WHERE 1=1"
    params = []
    if status_filter:
        where += " AND status = ?"
        params.append(status_filter)
    if search:
        try:
            uid = int(search)
            where += " AND user_id = ?"
            params.append(uid)
        except ValueError:
            where += " AND LOWER(name) LIKE LOWER(?)"
            params.append(f"%{search}%")

    total = conn.execute(f"SELECT COUNT(*) as c FROM users {where}", params).fetchone()["c"]
    offset = (page - 1) * per_page
    users_list = conn.execute(
        f"SELECT * FROM users {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()

    # Build user cards HTML
    cards_html = ""
    for u in users_list:
        photos = conn.execute(
            "SELECT file_id FROM user_photos WHERE user_id = ? ORDER BY position LIMIT 1",
            (u["user_id"],)
        ).fetchone()
        report_count = conn.execute(
            "SELECT COUNT(*) as c FROM reports WHERE reported_id = ?", (u["user_id"],)
        ).fetchone()["c"]

        status_badge = {
            "approved": '<span style="color:#2ecc71">✅ מאושר</span>',
            "pending": '<span style="color:#f39c12">⏳ ממתין</span>',
            "rejected": '<span style="color:#e74c3c">❌ נדחה</span>',
            "deleted": '<span style="color:#888">🗑 נמחק</span>',
        }.get(u["status"], u["status"])

        flags = []
        if u.get("is_blocked"): flags.append('<span style="color:#e74c3c">🚫 חסום</span>')
        if u.get("is_suspended"): flags.append('<span style="color:#f39c12">⏸ מושעה</span>')
        if u.get("is_premium"): flags.append('<span style="color:#f1c40f">⭐ פרמיום</span>')

        gender_emoji = "👩" if u["gender"] == "female" else "👨"
        region_name = REGIONS.get(u.get("region", ""), "")
        username_display = f"@{u['username']}" if u.get("username") else "אין"

        photo_html = ""
        if photos:
            # Use Telegram file_id via our proxy endpoint
            photo_html = f'<div class="card-photo" style="background:#111;height:200px;display:flex;align-items:center;justify-content:center;font-size:4rem">{gender_emoji}</div>'
        else:
            photo_html = f'<div class="card-photo" style="background:#111;height:200px;display:flex;align-items:center;justify-content:center;font-size:4rem">{gender_emoji}</div>'

        cards_html += f"""
        <div class="card">
          {photo_html}
          <div class="card-body">
            <div class="card-name">{gender_emoji} {u['name']}, {u['age']}</div>
            <div class="card-meta">📍 {region_name} {u.get('city','')}</div>
            <div class="card-meta">📱 {username_display}</div>
            <div class="card-meta">🆔 <code>{u['user_id']}</code></div>
            <div class="card-meta">{status_badge} {' '.join(flags)}</div>
            <div class="card-bio">{(u.get('bio') or '')[:80]}{'...' if len(u.get('bio') or '') > 80 else ''}</div>
            {"f'<div class=\"card-meta\" style=\"color:#e74c3c\">🚨 {report_count} דיווחים</div>'" if report_count > 0 else ''}
            <div class="card-actions">
              <a href="/user/{u['user_id']}" class="btn-sm">👁 פרטים</a>
              {'<a href="/action/approve/' + str(u['user_id']) + '" class="btn-sm btn-green">✅ אשר</a>' if u['status'] == 'pending' else ''}
              {'<a href="/action/unblock/' + str(u['user_id']) + '" class="btn-sm btn-green">🔓 שחרר</a>' if u.get('is_blocked') else '<a href="/action/block/' + str(u['user_id']) + '" class="btn-sm btn-red">🚫 חסום</a>'}
              {'<a href="/action/unsuspend/' + str(u['user_id']) + '" class="btn-sm btn-orange">▶️ שחרר</a>' if u.get('is_suspended') else '<a href="/action/suspend/' + str(u['user_id']) + '" class="btn-sm btn-orange">⏸ השעה</a>'}
            </div>
          </div>
        </div>"""

    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)
    pagination = ""
    for p in range(1, total_pages + 1):
        active = "background:#e91e8c;" if p == page else ""
        pagination += f'<a href="?page={p}&status={status_filter}&search={search}" style="display:inline-block;padding:8px 14px;margin:2px;background:#1a1a1a;{active}color:#fff;border-radius:6px;text-decoration:none">{p}</a>'

    return f"""<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>משתמשים - Flirt40</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0d0d0d; color: #fff; font-family: 'Segoe UI', sans-serif; }}
  nav {{ background: #1a1a1a; border-bottom: 1px solid #2a2a2a; padding: 16px 32px;
         display: flex; align-items: center; justify-content: space-between; }}
  nav h1 {{ font-size: 1.4rem; color: #e91e8c; }}
  nav a {{ color: #aaa; text-decoration: none; margin-right: 24px; font-size: 0.9rem; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 32px; }}
  .filters {{ display: flex; gap: 12px; margin-bottom: 28px; flex-wrap: wrap; align-items: center; }}
  .filters input {{ padding: 10px 16px; background: #1a1a1a; border: 1px solid #333;
                    border-radius: 8px; color: #fff; font-size: 0.9rem; width: 250px; }}
  .filters input:focus {{ outline: none; border-color: #e91e8c; }}
  .filter-btn {{ padding: 10px 18px; background: #1a1a1a; border: 1px solid #333;
                 border-radius: 8px; color: #aaa; text-decoration: none; font-size: 0.85rem; }}
  .filter-btn.active {{ background: #e91e8c; color: #fff; border-color: #e91e8c; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 20px; }}
  .card {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; overflow: hidden; }}
  .card-body {{ padding: 16px; }}
  .card-name {{ font-size: 1.1rem; font-weight: bold; margin-bottom: 8px; }}
  .card-meta {{ font-size: 0.8rem; color: #aaa; margin-bottom: 4px; }}
  .card-bio {{ font-size: 0.85rem; color: #ccc; margin: 10px 0; line-height: 1.4; }}
  .card-actions {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }}
  .btn-sm {{ padding: 6px 12px; border-radius: 6px; font-size: 0.78rem; text-decoration: none;
             background: #2a2a2a; color: #fff; }}
  .btn-green {{ background: #1a5c2e; color: #2ecc71; }}
  .btn-red {{ background: #5c1a1a; color: #e74c3c; }}
  .btn-orange {{ background: #5c3a1a; color: #e67e22; }}
  code {{ background: #111; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; }}
  .total {{ color: #888; font-size: 0.9rem; margin-bottom: 16px; }}
  .pagination {{ margin-top: 32px; text-align: center; }}
</style>
</head>
<body>
<nav>
  <h1>💋 Flirt40 Admin</h1>
  <div><a href="/">🏠 ראשי</a><a href="/users">👥 משתמשים</a><a href="/reports">🚨 דיווחים</a><a href="/logout">יציאה</a></div>
</nav>
<div class="container">
  <form method="GET" class="filters">
    <input type="text" name="search" placeholder="🔍 חפש לפי שם או ID..." value="{search}">
    <a href="/users" class="filter-btn {'active' if not status_filter else ''}">הכל</a>
    <a href="/users?status=pending" class="filter-btn {'active' if status_filter == 'pending' else ''}">⏳ ממתינים</a>
    <a href="/users?status=approved" class="filter-btn {'active' if status_filter == 'approved' else ''}">✅ מאושרים</a>
    <a href="/users?status=rejected" class="filter-btn {'active' if status_filter == 'rejected' else ''}">❌ נדחו</a>
    <button type="submit" style="padding:10px 18px;background:#e91e8c;border:none;border-radius:8px;color:#fff;cursor:pointer">חפש</button>
  </form>
  <p class="total">נמצאו {total} משתמשים</p>
  <div class="grid">{cards_html}</div>
  <div class="pagination">{pagination}</div>
</div>
</body>
</html>"""


@app.route("/user/<int:user_id>")
@login_required
def user_detail(user_id):
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return "משתמש לא נמצא", 404

    photos = conn.execute(
        "SELECT file_id FROM user_photos WHERE user_id = ? ORDER BY position",
        (user_id,)
    ).fetchall()
    reports = conn.execute(
        "SELECT r.*, u.name as reporter_name FROM reports r "
        "LEFT JOIN users u ON r.reporter_id = u.user_id "
        "WHERE r.reported_id = ? ORDER BY r.created_at DESC",
        (user_id,)
    ).fetchall()

    conn.close()

    status_color = {"approved": "#2ecc71", "pending": "#f39c12",
                    "rejected": "#e74c3c", "deleted": "#888"}.get(user["status"], "#fff")
    gender_emoji = "👩" if user["gender"] == "female" else "👨"
    region_name = REGIONS.get(user.get("region", ""), "")
    username_display = f"@{user['username']}" if user.get("username") else "אין"

    photos_html = ""
    for i, p in enumerate(photos):
        photos_html += f'<div style="background:#111;width:120px;height:120px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:3rem">{gender_emoji}</div>'

    reports_html = ""
    for r in reports:
        reports_html += f"""
        <div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:16px;margin-bottom:12px">
          <div style="color:#aaa;font-size:0.8rem">מדווח: {r.get('reporter_name','?')} | {str(r.get('created_at',''))[:10]}</div>
          <div style="margin-top:8px">{r.get('reason','')}</div>
          <div style="margin-top:4px;color:{'#2ecc71' if r['status']=='closed' else '#f39c12'}">{r['status']}</div>
        </div>"""

    id_card_html = ""
    if user.get("id_card_file_id"):
        id_card_html = f'<div style="margin-top:16px;padding:12px;background:#1a1a1a;border:1px solid #333;border-radius:8px">🪪 תעודת זהות: <code>{user["id_card_file_id"][:30]}...</code><br><small style="color:#888">העתק את ה-file_id ושלח לבוט לצפייה</small></div>'

    return f"""<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<title>{user['name']} - Flirt40</title>
<style>
  * {{ margin:0;padding:0;box-sizing:border-box; }}
  body {{ background:#0d0d0d;color:#fff;font-family:'Segoe UI',sans-serif; }}
  nav {{ background:#1a1a1a;border-bottom:1px solid #2a2a2a;padding:16px 32px;
         display:flex;align-items:center;justify-content:space-between; }}
  nav h1 {{ font-size:1.4rem;color:#e91e8c; }}
  nav a {{ color:#aaa;text-decoration:none;margin-right:24px;font-size:0.9rem; }}
  .container {{ max-width:900px;margin:0 auto;padding:32px; }}
  .profile-header {{ display:flex;gap:32px;margin-bottom:32px;flex-wrap:wrap; }}
  .profile-info {{ flex:1;min-width:280px; }}
  .name {{ font-size:1.8rem;font-weight:bold;margin-bottom:8px; }}
  .meta {{ color:#aaa;margin-bottom:6px;font-size:0.9rem; }}
  .bio {{ background:#1a1a1a;border-radius:8px;padding:16px;margin:16px 0;line-height:1.6; }}
  .actions {{ display:flex;flex-wrap:wrap;gap:10px;margin-top:20px; }}
  .btn {{ padding:10px 20px;border-radius:8px;text-decoration:none;font-size:0.9rem;font-weight:bold; }}
  .btn-green {{ background:#1a5c2e;color:#2ecc71; }}
  .btn-red {{ background:#5c1a1a;color:#e74c3c; }}
  .btn-orange {{ background:#5c3a1a;color:#e67e22; }}
  .btn-gray {{ background:#2a2a2a;color:#fff; }}
  code {{ background:#111;padding:2px 8px;border-radius:4px;font-size:0.85rem; }}
  h3 {{ margin-bottom:16px;color:#e91e8c; }}
</style>
</head>
<body>
<nav>
  <h1>💋 Flirt40 Admin</h1>
  <div><a href="/">🏠 ראשי</a><a href="/users">👥 משתמשים</a><a href="/logout">יציאה</a></div>
</nav>
<div class="container">
  <a href="/users" style="color:#888;text-decoration:none;font-size:0.9rem">← חזרה למשתמשים</a>
  <div class="profile-header" style="margin-top:24px">
    <div style="display:flex;gap:12px;flex-wrap:wrap">{photos_html if photos_html else f'<div style="background:#111;width:120px;height:120px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:4rem">{gender_emoji}</div>'}</div>
    <div class="profile-info">
      <div class="name">{gender_emoji} {user['name']}, {user['age']}</div>
      <div class="meta">📍 {region_name} - {user.get('city','')}</div>
      <div class="meta">📱 טלגרם: {username_display}</div>
      <div class="meta">🆔 ID: <code>{user_id}</code></div>
      <div class="meta">📅 נרשם: {str(user.get('created_at',''))[:10]}</div>
      <div class="meta">סטטוס: <span style="color:{status_color}">{user['status']}</span>
        {'| 🚫 חסום' if user.get('is_blocked') else ''}
        {'| ⏸ מושעה' if user.get('is_suspended') else ''}
        {'| ⭐ פרמיום' if user.get('is_premium') else ''}
      </div>
      {id_card_html}
      <div class="bio">{user.get('bio','')}</div>
      <div class="actions">
        {'<a href="/action/approve/' + str(user_id) + '" class="btn btn-green">✅ אשר</a>' if user['status'] == 'pending' else ''}
        {'<a href="/action/unblock/' + str(user_id) + '" class="btn btn-green">🔓 שחרר חסימה</a>' if user.get('is_blocked') else '<a href="/action/block/' + str(user_id) + '" class="btn btn-red">🚫 חסום</a>'}
        {'<a href="/action/unsuspend/' + str(user_id) + '" class="btn btn-orange">▶️ שחרר השעיה</a>' if user.get('is_suspended') else '<a href="/action/suspend/' + str(user_id) + '" class="btn btn-orange">⏸ השעה</a>'}
        <a href="/action/delete/{user_id}" class="btn btn-red" onclick="return confirm('למחוק את המשתמש?')">🗑 מחק</a>
        <a href="/users" class="btn btn-gray">← חזרה</a>
      </div>
    </div>
  </div>
  {'<div><h3>דיווחים (' + str(len(reports)) + ')</h3>' + reports_html + '</div>' if reports else '<p style="color:#555">אין דיווחים על משתמש זה.</p>'}
</div>
</body>
</html>"""


@app.route("/action/<action>/<int:user_id>")
@login_required
def do_action(action, user_id):
    conn = get_conn()
    if action == "approve":
        conn.execute("UPDATE users SET status='approved' WHERE user_id=?", (user_id,))
    elif action == "block":
        conn.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (user_id,))
    elif action == "unblock":
        conn.execute("UPDATE users SET is_blocked=0, is_suspended=0, status='approved' WHERE user_id=?", (user_id,))
    elif action == "suspend":
        conn.execute("UPDATE users SET is_suspended=1 WHERE user_id=?", (user_id,))
    elif action == "unsuspend":
        conn.execute("UPDATE users SET is_suspended=0 WHERE user_id=?", (user_id,))
    elif action == "delete":
        conn.execute("UPDATE users SET status='deleted' WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or "/users")


@app.route("/reports")
@login_required
def reports():
    conn = get_conn()
    reports_list = conn.execute("""
        SELECT r.*, u1.name as reporter_name, u2.name as reported_name
        FROM reports r
        LEFT JOIN users u1 ON r.reporter_id = u1.user_id
        LEFT JOIN users u2 ON r.reported_id = u2.user_id
        WHERE r.status = 'pending'
        ORDER BY r.created_at DESC
    """).fetchall()
    conn.close()

    rows_html = ""
    for r in reports_list:
        rows_html += f"""
        <tr>
          <td>{r.get('reporter_name','?')} <a href="/user/{r['reporter_id']}" style="color:#888;font-size:0.8rem">({r['reporter_id']})</a></td>
          <td><a href="/user/{r['reported_id']}" style="color:#e91e8c">{r.get('reported_name','?')}</a> ({r['reported_id']})</td>
          <td>{r.get('reason','')}</td>
          <td>{str(r.get('created_at',''))[:10]}</td>
          <td>
            <a href="/action/suspend/{r['reported_id']}" style="color:#e67e22;text-decoration:none;margin-left:8px">⏸ השעה</a>
            <a href="/action/block/{r['reported_id']}" style="color:#e74c3c;text-decoration:none;margin-left:8px">🚫 חסום</a>
            <a href="/report/close/{r['id']}" style="color:#2ecc71;text-decoration:none">✅ סגור</a>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<title>דיווחים - Flirt40</title>
<style>
  * {{ margin:0;padding:0;box-sizing:border-box; }}
  body {{ background:#0d0d0d;color:#fff;font-family:'Segoe UI',sans-serif; }}
  nav {{ background:#1a1a1a;border-bottom:1px solid #2a2a2a;padding:16px 32px;
         display:flex;align-items:center;justify-content:space-between; }}
  nav h1 {{ font-size:1.4rem;color:#e91e8c; }}
  nav a {{ color:#aaa;text-decoration:none;margin-right:24px; }}
  .container {{ max-width:1200px;margin:0 auto;padding:32px; }}
  table {{ width:100%;border-collapse:collapse; }}
  th {{ background:#1a1a1a;padding:12px 16px;text-align:right;color:#888;font-size:0.85rem; }}
  td {{ padding:14px 16px;border-bottom:1px solid #1a1a1a;font-size:0.9rem; }}
  tr:hover td {{ background:#111; }}
</style>
</head>
<body>
<nav>
  <h1>💋 Flirt40 Admin</h1>
  <div><a href="/">🏠 ראשי</a><a href="/users">👥 משתמשים</a><a href="/reports">🚨 דיווחים</a><a href="/logout">יציאה</a></div>
</nav>
<div class="container">
  <h2 style="margin-bottom:24px">🚨 דיווחים פתוחים ({len(reports_list)})</h2>
  {'<table><tr><th>מדווח</th><th>מדוּוח</th><th>סיבה</th><th>תאריך</th><th>פעולה</th></tr>' + rows_html + '</table>' if reports_list else '<p style="color:#555">אין דיווחים פתוחים.</p>'}
</div>
</body>
</html>"""


@app.route("/report/close/<int:report_id>")
@login_required
def close_report(report_id):
    conn = get_conn()
    conn.execute("UPDATE reports SET status='closed' WHERE id=?", (report_id,))
    conn.commit()
    conn.close()
    return redirect("/reports")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
