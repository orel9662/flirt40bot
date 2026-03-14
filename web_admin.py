import os
import sqlite3
from flask import Flask, request, session, redirect, jsonify
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("WEB_SECRET_KEY", "flirt40secret2024")
DB_PATH = os.environ.get("DB_PATH", "dating_bot.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_WEB_PASSWORD", "admin123")

REGIONS = {"north": "צפון 🌿", "center": "מרכז 🏙", "south": "דרום 🌵"}

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda c, r: {col[0]: r[i] for i, col in enumerate(c.description)} if c.description else r
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
    return f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8">
<title>Flirt40 Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;700;900&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#080810;color:#fff;font-family:'Heebo',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden}}
body::before{{content:'';position:fixed;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(ellipse at 60% 40%,rgba(233,30,140,0.15) 0%,transparent 60%),radial-gradient(ellipse at 30% 70%,rgba(100,0,200,0.1) 0%,transparent 50%);pointer-events:none}}
.box{{background:rgba(255,255,255,0.03);backdrop-filter:blur(20px);border:1px solid rgba(233,30,140,0.2);border-radius:24px;padding:56px 48px;width:400px;text-align:center;position:relative}}
.logo{{font-size:3rem;margin-bottom:4px}}
h1{{font-size:2rem;font-weight:900;letter-spacing:-1px;margin-bottom:4px}}
.sub{{color:rgba(255,255,255,0.4);font-size:.9rem;margin-bottom:40px;font-weight:300}}
input{{width:100%;padding:16px 20px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:12px;color:#fff;font-size:1rem;margin-bottom:16px;outline:none;font-family:inherit;text-align:center;transition:border-color .2s}}
input:focus{{border-color:#e91e8c}}
button{{width:100%;padding:16px;background:linear-gradient(135deg,#e91e8c,#9c27b0);border:none;border-radius:12px;color:#fff;font-size:1rem;font-weight:700;cursor:pointer;font-family:inherit;letter-spacing:.5px;transition:opacity .2s}}
button:hover{{opacity:.85}}
.err{{color:#ff6b8a;font-size:.85rem;margin-top:12px}}
</style></head>
<body><div class="box">
<div class="logo">💋</div>
<h1>Flirt40</h1>
<p class="sub">פאנל ניהול</p>
<form method="POST">
<input type="password" name="password" placeholder="• • • • • • • •" autofocus>
<button>כניסה</button></form>
{f'<p class="err">❌ {error}</p>' if error else ''}
</div></body></html>"""

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

def get_stats():
    conn = get_conn()
    try:
        s = {}
        s["total"] = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        s["pending"] = conn.execute("SELECT COUNT(*) as c FROM users WHERE status='pending'").fetchone()["c"]
        s["approved"] = conn.execute("SELECT COUNT(*) as c FROM users WHERE status='approved'").fetchone()["c"]
        s["blocked"] = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_blocked=1").fetchone()["c"]
        s["matches"] = conn.execute("SELECT COUNT(*) as c FROM matches").fetchone()["c"]
        try:
            s["reports"] = conn.execute("SELECT COUNT(*) as c FROM reports WHERE status='pending'").fetchone()["c"]
        except:
            s["reports"] = 0
        try:
            s["messages"] = conn.execute("SELECT COUNT(*) as c FROM user_messages WHERE is_read=0").fetchone()["c"]
        except:
            s["messages"] = 0
        conn.close()
        return s
    except Exception as e:
        conn.close()
        return {"total":0,"pending":0,"approved":0,"blocked":0,"matches":0,"reports":0,"messages":0}

NAV = """<nav>
  <div class="nav-inner">
    <a href="/" class="nav-logo">💋 Flirt40</a>
    <div class="nav-links">
      <a href="/" class="{home}">🏠 ראשי</a>
      <a href="/users" class="{users}">👥 משתמשים</a>
      <a href="/pending" class="{pending}">⏳ ממתינים</a>
      <a href="/reports" class="{reports}">🚨 דיווחים</a>
      <a href="/messages" class="{messages}">💬 הודעות</a>
      <a href="/logout" class="nav-logout">יציאה</a>
    </div>
  </div>
</nav>"""

BASE_STYLE = """<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;600;700;900&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#080810;color:#fff;font-family:'Heebo',sans-serif;min-height:100vh}}
body::before{{content:'';position:fixed;top:0;left:0;width:100%;height:300px;background:radial-gradient(ellipse at 50% 0%,rgba(233,30,140,0.12) 0%,transparent 70%);pointer-events:none;z-index:0}}
nav{{background:rgba(255,255,255,0.02);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.06);position:sticky;top:0;z-index:100}}
.nav-inner{{max-width:1400px;margin:0 auto;padding:0 32px;display:flex;align-items:center;justify-content:space-between;height:64px}}
.nav-logo{{font-size:1.3rem;font-weight:900;text-decoration:none;color:#fff;letter-spacing:-0.5px}}
.nav-links{{display:flex;gap:4px;align-items:center}}
.nav-links a{{color:rgba(255,255,255,0.5);text-decoration:none;padding:8px 14px;border-radius:8px;font-size:.85rem;font-weight:500;transition:all .2s}}
.nav-links a:hover,.nav-links a.active{{background:rgba(233,30,140,0.15);color:#fff}}
.nav-logout{{color:rgba(255,100,100,0.6)!important}}
.container{{max-width:1400px;margin:0 auto;padding:40px 32px;position:relative;z-index:1}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin-bottom:48px}}
.stat{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:16px;padding:24px;text-align:center;transition:border-color .2s}}
.stat:hover{{border-color:rgba(233,30,140,0.3)}}
.stat-num{{font-size:2.8rem;font-weight:900;line-height:1}}
.stat-label{{color:rgba(255,255,255,0.4);font-size:.8rem;margin-top:6px;font-weight:300}}
.pink{{color:#e91e8c}}.green{{color:#4caf50}}.orange{{color:#ff9800}}.red{{color:#f44336}}.purple{{color:#9c27b0}}.blue{{color:#2196f3}}
.section-title{{font-size:1.4rem;font-weight:700;margin-bottom:24px;letter-spacing:-.5px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}}
.card{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:16px;overflow:hidden;transition:all .2s}}
.card:hover{{border-color:rgba(233,30,140,0.3);transform:translateY(-2px)}}
.card-avatar{{height:180px;background:linear-gradient(135deg,rgba(233,30,140,0.2),rgba(100,0,200,0.2));display:flex;align-items:center;justify-content:center;font-size:5rem}}
.card-body{{padding:20px}}
.card-name{{font-size:1.1rem;font-weight:700;margin-bottom:6px}}
.card-meta{{color:rgba(255,255,255,0.4);font-size:.8rem;margin-bottom:4px}}
.card-bio{{color:rgba(255,255,255,0.6);font-size:.85rem;margin-top:10px;line-height:1.5}}
.badge{{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:600;margin:2px}}
.badge-green{{background:rgba(76,175,80,0.15);color:#4caf50;border:1px solid rgba(76,175,80,0.3)}}
.badge-orange{{background:rgba(255,152,0,0.15);color:#ff9800;border:1px solid rgba(255,152,0,0.3)}}
.badge-red{{background:rgba(244,67,54,0.15);color:#f44336;border:1px solid rgba(244,67,54,0.3)}}
.badge-pink{{background:rgba(233,30,140,0.15);color:#e91e8c;border:1px solid rgba(233,30,140,0.3)}}
.badge-gray{{background:rgba(255,255,255,0.07);color:rgba(255,255,255,0.4);border:1px solid rgba(255,255,255,0.1)}}
code{{background:rgba(255,255,255,0.07);padding:2px 8px;border-radius:6px;font-size:.78rem;font-family:monospace}}
.filters{{display:flex;gap:10px;margin-bottom:28px;flex-wrap:wrap;align-items:center}}
.filters input{{padding:10px 16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:10px;color:#fff;font-family:inherit;font-size:.9rem;outline:none;width:250px;transition:border-color .2s}}
.filters input:focus{{border-color:#e91e8c}}
.fa{{padding:9px 18px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:10px;color:rgba(255,255,255,0.5);text-decoration:none;font-size:.82rem;transition:all .2s}}
.fa:hover,.fa.active{{background:rgba(233,30,140,0.15);border-color:rgba(233,30,140,0.3);color:#fff}}
.fa-btn{{padding:9px 18px;background:linear-gradient(135deg,#e91e8c,#9c27b0);border:none;border-radius:10px;color:#fff;cursor:pointer;font-family:inherit;font-size:.82rem}}
.total{{color:rgba(255,255,255,0.3);font-size:.85rem;margin-bottom:20px}}
.pag{{margin-top:32px;display:flex;gap:6px;justify-content:center}}
.pag a{{display:inline-block;padding:8px 14px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:8px;color:rgba(255,255,255,0.5);text-decoration:none;font-size:.85rem;transition:all .2s}}
.pag a:hover{{background:rgba(233,30,140,0.15);color:#fff}}
.pag a.cur{{background:rgba(233,30,140,0.2);border-color:#e91e8c;color:#fff}}
table{{width:100%;border-collapse:collapse}}
th{{padding:12px 16px;text-align:right;color:rgba(255,255,255,0.3);font-size:.8rem;font-weight:500;border-bottom:1px solid rgba(255,255,255,0.06)}}
td{{padding:14px 16px;border-bottom:1px solid rgba(255,255,255,0.04);font-size:.88rem;vertical-align:middle}}
tr:hover td{{background:rgba(255,255,255,0.02)}}
.msg-card{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:20px;margin-bottom:14px}}
.msg-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}
.msg-name{{font-weight:700}}
.msg-time{{color:rgba(255,255,255,0.3);font-size:.8rem}}
.msg-text{{color:rgba(255,255,255,0.7);line-height:1.6}}
</style>"""

@app.route("/")
@login_required
def index():
    s = get_stats()
    nav = NAV.format(home="active",users="",pending="",reports="",messages="")
    return f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>Flirt40 Admin</title>{BASE_STYLE}</head>
<body>{nav}<div class="container">
<div class="stats">
<div class="stat"><div class="stat-num pink">{s['total']}</div><div class="stat-label">סה"כ משתמשים</div></div>
<div class="stat"><div class="stat-num orange">{s['pending']}</div><div class="stat-label">ממתינים לאישור</div></div>
<div class="stat"><div class="stat-num green">{s['approved']}</div><div class="stat-label">מאושרים</div></div>
<div class="stat"><div class="stat-num red">{s['blocked']}</div><div class="stat-label">חסומים</div></div>
<div class="stat"><div class="stat-num purple">{s['matches']}</div><div class="stat-label">התאמות</div></div>
<div class="stat"><div class="stat-num blue">{s['reports']}</div><div class="stat-label">דיווחים פתוחים</div></div>
<div class="stat"><div class="stat-num pink">{s['messages']}</div><div class="stat-label">הודעות חדשות</div></div>
</div>
<p class="section-title">קישורים מהירים</p>
<div style="display:flex;gap:12px;flex-wrap:wrap">
<a href="/pending" class="fa active">⏳ ממתינים לאישור ({s['pending']})</a>
<a href="/users" class="fa">👥 כל המשתמשים</a>
<a href="/reports" class="fa">🚨 דיווחים ({s['reports']})</a>
<a href="/messages" class="fa">💬 הודעות ({s['messages']})</a>
</div>
</div></body></html>"""

@app.route("/users")
@login_required
def users():
    conn = get_conn()
    status_filter = request.args.get("status","")
    search = request.args.get("search","")
    page = int(request.args.get("page",1))
    per_page = 12
    where, params = "WHERE 1=1", []
    if status_filter:
        where += " AND status=?"; params.append(status_filter)
    if search:
        try:
            uid = int(search); where += " AND user_id=?"; params.append(uid)
        except:
            where += " AND LOWER(name) LIKE LOWER(?)"; params.append(f"%{search}%")
    total = conn.execute(f"SELECT COUNT(*) as c FROM users {where}", params).fetchone()["c"]
    users_list = conn.execute(f"SELECT * FROM users {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params+[per_page,(page-1)*per_page]).fetchall()
    conn.close()

    cards = ""
    for u in users_list:
        ge = "👩" if u["gender"]=="female" else "👨"
        reg = REGIONS.get(u.get("region",""),"")
        un = f"@{u['username']}" if u.get("username") else "אין"
        st_badge = {"approved":'<span class="badge badge-green">✅ מאושר</span>',
                    "pending":'<span class="badge badge-orange">⏳ ממתין</span>',
                    "rejected":'<span class="badge badge-red">❌ נדחה</span>'}.get(u["status"],'')
        flags = ""
        if u.get("is_blocked"): flags += '<span class="badge badge-red">🚫 חסום</span>'
        if u.get("is_suspended"): flags += '<span class="badge badge-orange">⏸ מושעה</span>'
        if u.get("is_premium"): flags += '<span class="badge badge-pink">⭐ פרמיום</span>'
        bio = (u.get("bio") or "")[:80]
        cards += f"""<div class="card">
<div class="card-avatar">{ge}</div>
<div class="card-body">
<div class="card-name">{ge} {u['name']}, {u['age']}</div>
<div class="card-meta">📍 {reg} {u.get('city','')}</div>
<div class="card-meta">📱 {un} | 🆔 <code>{u['user_id']}</code></div>
<div style="margin-top:8px">{st_badge}{flags}</div>
<div class="card-bio">{bio}{'...' if len(u.get('bio') or '') > 80 else ''}</div>
</div></div>"""

    total_pages = max(1,(total+per_page-1)//per_page)
    pag = "".join([f'<a href="?page={p}&status={status_filter}&search={search}" class="{"cur" if p==page else ""}">{p}</a>' for p in range(1,min(total_pages+1,11))])
    nav = NAV.format(home="",users="active",pending="",reports="",messages="")
    return f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>משתמשים</title>{BASE_STYLE}</head>
<body>{nav}<div class="container">
<form method="GET" class="filters">
<input type="text" name="search" placeholder="🔍 חפש לפי שם או מזהה..." value="{search}">
<a href="/users" class="fa {'active' if not status_filter else ''}">הכל ({total if not status_filter else ''})</a>
<a href="/users?status=approved" class="fa {'active' if status_filter=='approved' else ''}">✅ מאושרים</a>
<a href="/users?status=pending" class="fa {'active' if status_filter=='pending' else ''}">⏳ ממתינים</a>
<a href="/users?status=rejected" class="fa {'active' if status_filter=='rejected' else ''}">❌ נדחו</a>
<button type="submit" class="fa-btn">חפש</button>
</form>
<p class="total">נמצאו {total} משתמשים</p>
<div class="grid">{cards if cards else '<p style="color:rgba(255,255,255,0.3)">אין משתמשים</p>'}</div>
<div class="pag">{pag}</div>
</div></body></html>"""

@app.route("/pending")
@login_required
def pending():
    conn = get_conn()
    users_list = conn.execute("SELECT * FROM users WHERE status='pending' ORDER BY created_at DESC").fetchall()
    conn.close()
    cards = ""
    for u in users_list:
        ge = "👩" if u["gender"]=="female" else "👨"
        reg = REGIONS.get(u.get("region",""),"")
        un = f"@{u['username']}" if u.get("username") else "אין"
        cards += f"""<div class="card">
<div class="card-avatar">{ge}</div>
<div class="card-body">
<div class="card-name">{ge} {u['name']}, {u['age']}</div>
<div class="card-meta">📍 {reg} {u.get('city','')}</div>
<div class="card-meta">📱 {un} | 🆔 <code>{u['user_id']}</code></div>
<span class="badge badge-orange">⏳ ממתין לאישור</span>
<div class="card-bio">{(u.get('bio') or '')[:80]}</div>
<div style="margin-top:12px;color:rgba(255,255,255,0.3);font-size:.78rem">לאישור/דחייה - השתמש בפאנל הטלגרם</div>
</div></div>"""
    nav = NAV.format(home="",users="",pending="active",reports="",messages="")
    return f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>ממתינים</title>{BASE_STYLE}</head>
<body>{nav}<div class="container">
<p class="section-title">⏳ ממתינים לאישור ({len(users_list)})</p>
<div class="grid">{cards if cards else '<p style="color:rgba(255,255,255,0.3)">אין ממתינים</p>'}</div>
</div></body></html>"""

@app.route("/reports")
@login_required
def reports():
    conn = get_conn()
    try:
        reps = conn.execute("""
            SELECT r.*,u1.name as rname,u2.name as dname,u2.age as dage
            FROM reports r
            LEFT JOIN users u1 ON r.reporter_id=u1.user_id
            LEFT JOIN users u2 ON r.reported_id=u2.user_id
            WHERE r.status='pending' ORDER BY r.created_at DESC
        """).fetchall()
    except:
        reps = []
    conn.close()
    rows = ""
    for r in reps:
        rows += f"""<tr>
<td>{r.get('rname','?')}</td>
<td>{r.get('dname','?')}, {r.get('dage','?')} | <code>{r['reported_id']}</code></td>
<td>{r.get('reason','')}</td>
<td style="color:rgba(255,255,255,0.3)">{str(r.get('created_at',''))[:10]}</td>
<td><span class="badge badge-orange">פתוח</span></td>
</tr>"""
    nav = NAV.format(home="",users="",pending="",reports="active",messages="")
    return f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>דיווחים</title>{BASE_STYLE}</head>
<body>{nav}<div class="container">
<p class="section-title">🚨 דיווחים פתוחים ({len(reps)})</p>
{'<table><tr><th>מדווח</th><th>מדוּוח</th><th>סיבה</th><th>תאריך</th><th>סטטוס</th></tr>'+rows+'</table>' if reps else '<p style="color:rgba(255,255,255,0.3)">אין דיווחים פתוחים</p>'}
<p style="color:rgba(255,255,255,0.3);font-size:.82rem;margin-top:24px">לטיפול בדיווחים - השתמש בפאנל הטלגרם</p>
</div></body></html>"""

@app.route("/messages")
@login_required
def messages():
    conn = get_conn()
    try:
        msgs = conn.execute("""
            SELECT m.*,u.name,u.age,u.gender FROM user_messages m
            LEFT JOIN users u ON m.from_user_id=u.user_id
            WHERE m.admin_closed=0 ORDER BY m.created_at DESC LIMIT 50
        """).fetchall()
    except:
        msgs = []
    conn.close()
    cards = ""
    for m in msgs:
        ge = "👩" if m.get("gender")=="female" else "👨"
        name = m.get("name") or m["from_user_id"]
        unread = not m.get("is_read")
        cards += f"""<div class="msg-card" style="{'border-color:rgba(233,30,140,0.3)' if unread else ''}">
<div class="msg-header">
<div class="msg-name">{ge} {name} <code>{m['from_user_id']}</code> {'<span class="badge badge-pink">חדש</span>' if unread else ''}</div>
<div class="msg-time">{str(m.get('created_at',''))[:16]}</div>
</div>
<div class="msg-text">{m.get('message_text','')}</div>
</div>"""
    nav = NAV.format(home="",users="",pending="",reports="",messages="active")
    return f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>הודעות</title>{BASE_STYLE}</head>
<body>{nav}<div class="container">
<p class="section-title">💬 הודעות מהמשתמשים ({len(msgs)})</p>
{cards if cards else '<p style="color:rgba(255,255,255,0.3)">אין הודעות</p>'}
<p style="color:rgba(255,255,255,0.3);font-size:.82rem;margin-top:24px">למענה - השתמש בפאנל הטלגרם</p>
</div></body></html>"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
