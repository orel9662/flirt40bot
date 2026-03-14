import logging
import os
import threading
from flask import Flask, request, session, redirect, jsonify
from functools import wraps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler,
    PreCheckoutQueryHandler, filters
)
from handlers.registration import (
    start, get_gender, get_name, get_age, get_region, get_city,
    get_bio, get_photos, get_id_card, send_main_menu,
    GENDER, NAME, AGE, REGION, CITY, BIO, PHOTOS, ID_CARD
)
from handlers.matching import (
    show_next_profile, handle_like_dislike, handle_chat_consent,
    handle_like_message_text, handle_region_filter
)
from handlers.admin import admin_panel, handle_admin_callback, handle_appeal_message
from handlers.chat import handle_chat_message, handle_chat_callbacks
from database.db import (
    init_db, get_user, get_likes_status, REGIONS,
    add_report, add_bug_report, delete_user_self, track_premium_interest,
    get_user_settings, update_user_setting
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

WAITING_REPORT_REASON = {}
WAITING_REPORT_EVIDENCE = {}
WAITING_BUG = set()
WAITING_EDIT_BIO = set()
WAITING_EDIT_PHOTOS = set()  # set of user_ids adding photos
WAITING_DELETE_PHOTO = {}  # user_id -> list of file_ids to choose from


async def handle_menu_callbacks(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    settings = get_user_settings(user_id)
    lang = settings.get("language", "he")

    if data == "menu_back":
        await send_main_menu(context, user_id)
        return

    if data == "menu_browse":
        await show_next_profile(update, context)
        return

    if data == "menu_premium":
        track_premium_interest(user_id)
        if lang == "he":
            text = (
                "⭐ *Flirt40 Premium*\n\n"
                "✅ לייקים ללא הגבלה\n"
                "✅ הפרופיל מופיע ראשון\n"
                "✅ שלח הודעה עם כל לייק\n"
                "✅ בחר אזור / טווח קילומטרים\n"
                "✅ ראה מי לייקד אותך\n\n"
                "⏰ תוקף: 30 יום | ~50₪/חודש"
            )
        else:
            text = (
                "⭐ *Flirt40 Premium*\n\n"
                "✅ Unlimited likes\n"
                "✅ Profile shown first\n"
                "✅ Send message with every like\n"
                "✅ Choose region / distance\n"
                "✅ See who liked you\n\n"
                "⏰ Valid: 30 days | ~$15/month"
            )
        keyboard = [
            [InlineKeyboardButton("💰 רכישה | Purchase", callback_data="menu_premium_buy")],
            [InlineKeyboardButton("🔙 חזרה | Back", callback_data="menu_back")]
        ]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "menu_premium_buy":
        track_premium_interest(user_id)
        msg = (
            "🚧 *הפיצ'ר בפיתוח!*\n\n"
            "אנחנו עובדים על מערכת התשלומים.\n"
            "נשלח לך הודעה כשיהיה מוכן! 💌"
            if lang == "he" else
            "🚧 *Feature in development!*\n\n"
            "We're working on the payment system.\n"
            "We'll message you when it's ready! 💌"
        )
        kb = [[InlineKeyboardButton("🔙 חזרה | Back", callback_data="menu_back")]]
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "menu_status":
        user = get_user(user_id)
        if not user:
            await query.message.reply_text("❌ לא נמצא חשבון")
            return
        likes = get_likes_status(user_id)
        if likes and likes["type"] == "premium":
            likes_text = "⭐ פרמיום - ללא הגבלה" if lang == "he" else "⭐ Premium - unlimited"
        elif likes:
            likes_text = f"❤️ {likes['daily_remaining']} לייקים היום + {likes['bonus_likes']} בונוס"
        else:
            likes_text = "?"
        region_name = REGIONS.get(user.get("region", ""), "")
        from database.db import get_user_photos as gup
        photos = gup(user_id)
        gender_emoji = "👩" if user["gender"] == "female" else "👨"
        premium_badge = "⭐ " if user.get("is_premium") else ""
        profile_text = (
            f"{gender_emoji} {premium_badge}*{user['name']}*, גיל {user['age']}\n"
            f"📍 {region_name} - {user.get('city', '')}\n\n"
            f"📝 {user.get('bio', '')}\n\n"
            f"🔢 {likes_text}"
        )
        kb = [[InlineKeyboardButton("🔙 חזרה | Back", callback_data="menu_back")]]
        if photos:
            from telegram import InputMediaPhoto
            if len(photos) == 1:
                await query.message.reply_photo(
                    photo=photos[0], caption=profile_text,
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
                )
            else:
                media = [InputMediaPhoto(media=f) for f in photos[:5]]
                media[0] = InputMediaPhoto(media=photos[0], caption=profile_text, parse_mode="Markdown")
                await context.bot.send_media_group(chat_id=user_id, media=media)
                await query.message.reply_text("👆 הפרופיל שלך | _Your profile_",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await query.message.reply_text(profile_text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "menu_settings":
        await show_settings_menu(query.message, user_id, lang)
        return

    if data.startswith("settings_lang_"):
        new_lang = data.replace("settings_lang_", "")
        update_user_setting(user_id, "language", new_lang)
        lang = new_lang
        msg = "✅ השפה שונתה לעברית!" if new_lang == "he" else "✅ Language changed to English!"
        await query.message.reply_text(msg)
        await show_settings_menu(query.message, user_id, lang)
        return

    if data.startswith("settings_age_"):
        val = int(data.replace("settings_age_", ""))
        update_user_setting(user_id, "show_age", val)
        msg = ("✅ הגיל שלך יוצג בפרופיל" if val else "✅ הגיל שלך יוסתר מהפרופיל") if lang == "he" else \
              ("✅ Your age will be shown" if val else "✅ Your age will be hidden")
        await query.message.reply_text(msg)
        await show_settings_menu(query.message, user_id, lang)
        return

    if data.startswith("settings_notif_"):
        val = int(data.replace("settings_notif_", ""))
        update_user_setting(user_id, "notifications", val)
        msg = ("✅ התראות הופעלו" if val else "✅ התראות כובו") if lang == "he" else \
              ("✅ Notifications enabled" if val else "✅ Notifications disabled")
        await query.message.reply_text(msg)
        await show_settings_menu(query.message, user_id, lang)
        return

    if data == "settings_edit_bio":
        WAITING_EDIT_BIO.add(user_id)
        msg = "✏️ *ערוך ביו*\n\nכתוב/י ביו חדש (עד 300 תווים):" if lang == "he" else "✏️ *Edit bio*\n\nWrite your new bio (max 300 chars):"
        kb = [[InlineKeyboardButton("❌ ביטול | Cancel", callback_data="settings_cancel_edit")]]
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "settings_edit_photos":
        from database.db import get_user_photos as gup
        photos = gup(user_id)
        msg_he = f"📸 *ערוך תמונות*\n\nיש לך {len(photos)} תמונות כרגע (מינימום 1, מקסימום 5)."
        msg_en = f"📸 *Edit photos*\n\nYou have {len(photos)} photos (min 1, max 5)."
        msg = msg_he if lang == "he" else msg_en
        kb = []
        if len(photos) < 5:
            add_label = "➕ הוסף תמונה" if lang == "he" else "➕ Add photo"
            kb.append([InlineKeyboardButton(add_label, callback_data="settings_add_photo")])
        if len(photos) > 1:
            del_label = "🗑 מחק תמונה" if lang == "he" else "🗑 Delete photo"
            kb.append([InlineKeyboardButton(del_label, callback_data="settings_delete_photo")])
        kb.append([InlineKeyboardButton("🔙 חזרה | Back", callback_data="menu_settings")])
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "settings_add_photo":
        WAITING_EDIT_PHOTOS.add(user_id)
        msg = "📸 שלח/י תמונה חדשה:" if lang == "he" else "📸 Send your new photo:"
        kb = [[InlineKeyboardButton("❌ ביטול | Cancel", callback_data="settings_cancel_edit")]]
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "settings_delete_photo":
        from database.db import get_user_photos as gup
        photos = gup(user_id)
        msg = "🗑 *בחר/י תמונה למחיקה:*\n\n" if lang == "he" else "🗑 *Choose photo to delete:*\n\n"
        kb = []
        for i, _ in enumerate(photos):
            kb.append([InlineKeyboardButton(f"תמונה {i+1} | Photo {i+1}", callback_data=f"settings_del_photo_{i}")])
        kb.append([InlineKeyboardButton("🔙 חזרה | Back", callback_data="settings_edit_photos")])
        # Send photos so user can see them
        for i, fid in enumerate(photos):
            await query.message.reply_photo(photo=fid, caption=f"תמונה {i+1} | Photo {i+1}")
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("settings_del_photo_"):
        idx = int(data.replace("settings_del_photo_", ""))
        from database.db import get_user_photos as gup, get_conn
        photos = gup(user_id)
        if len(photos) <= 1:
            msg = "❌ לא ניתן למחוק - חייבת להישאר לפחות תמונה אחת!" if lang == "he" else "❌ Cannot delete - must keep at least one photo!"
            await query.message.reply_text(msg)
            return
        file_to_del = photos[idx]
        conn = get_conn()
        conn.execute("DELETE FROM user_photos WHERE user_id = ? AND file_id = ?", (user_id, file_to_del))
        conn.commit()
        conn.close()
        msg = f"✅ תמונה {idx+1} נמחקה!" if lang == "he" else f"✅ Photo {idx+1} deleted!"
        await query.message.reply_text(msg)
        await show_settings_menu(query.message, user_id, lang)
        return

    if data == "settings_cancel_edit":
        WAITING_EDIT_BIO.discard(user_id)
        WAITING_EDIT_PHOTOS.discard(user_id)
        await show_settings_menu(query.message, user_id, lang)
        return

    if data == "menu_settings":
        await show_settings_menu(query.message, user_id, lang)
        return

    if data == "menu_report":
        msg = (
            "🚨 *דיווח על משתמש*\n\nשלח: `/report [ID]`\n\nאת ה-ID תוכל/י לבקש מהמשתמש ישירות."
            if lang == "he" else
            "🚨 *Report a user*\n\nSend: `/report [ID]`\n\nYou can ask the user for their ID directly."
        )
        kb = [[InlineKeyboardButton("🔙 חזרה | Back", callback_data="menu_back")]]
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "menu_bug":
        WAITING_BUG.add(user_id)
        msg = "🐛 *דיווח תקלה*\n\nתאר/י את הבעיה:" if lang == "he" else "🐛 *Report a bug*\n\nDescribe the issue:"
        await query.message.reply_text(msg, parse_mode="Markdown")
        return

    if data == "menu_delete":
        yes = "🗑 כן, מחק" if lang == "he" else "🗑 Yes, delete"
        no = "❌ ביטול" if lang == "he" else "❌ Cancel"
        msg = (
            "⚠️ *האם אתה בטוח?*\n\nהפרופיל יימחק. ניתן להירשם מחדש בעתיד."
            if lang == "he" else
            "⚠️ *Are you sure?*\n\nYour profile will be deleted. You can register again later."
        )
        keyboard = [[
            InlineKeyboardButton(yes, callback_data="confirm_delete"),
            InlineKeyboardButton(no, callback_data="cancel_delete")
        ]]
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return


async def show_settings_menu(message, user_id, lang):
    settings = get_user_settings(user_id)
    show_age = settings.get("show_age", 1)
    notif = settings.get("notifications", 1)

    if lang == "he":
        title = "⚙️ *הגדרות*"
        lang_label = "🌐 שפה: עברית ✅" if lang == "he" else "🌐 שפה: English ✅"
        age_label = f"👁 הצג גיל: {'כן ✅' if show_age else 'לא ❌'}"
        notif_label = f"🔔 התראות: {'פועל ✅' if notif else 'כבוי ❌'}"
    else:
        title = "⚙️ *Settings*"
        lang_label = "🌐 Language: English ✅"
        age_label = f"👁 Show age: {'Yes ✅' if show_age else 'No ❌'}"
        notif_label = f"🔔 Notifications: {'On ✅' if notif else 'Off ❌'}"

    edit_bio = "✏️ ערוך ביו" if lang == "he" else "✏️ Edit bio"
    edit_photos = "📸 ערוך תמונות" if lang == "he" else "📸 Edit photos"
    keyboard = [
        [InlineKeyboardButton("🇮🇱 עברית" + (" ✅" if lang == "he" else ""), callback_data="settings_lang_he"),
         InlineKeyboardButton("🇬🇧 English" + (" ✅" if lang == "en" else ""), callback_data="settings_lang_en")],
        [InlineKeyboardButton(age_label, callback_data=f"settings_age_{0 if show_age else 1}")],
        [InlineKeyboardButton(notif_label, callback_data=f"settings_notif_{0 if notif else 1}")],
        [InlineKeyboardButton(edit_bio, callback_data="settings_edit_bio"),
         InlineKeyboardButton(edit_photos, callback_data="settings_edit_photos")],
        [InlineKeyboardButton("🔙 חזרה | Back", callback_data="menu_back")]
    ]
    await message.reply_text(
        f"{title}\n\n{lang_label}\n{age_label}\n{notif_label}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_delete_confirm(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = get_user_settings(user_id).get("language", "he")
    if query.data == "confirm_delete":
        delete_user_self(user_id)
        msg = (
            "🗑 *החשבון נמחק*\n\nתודה שהיית חלק מ-Flirt40! 💋\nכדי להצטרף שוב: /start"
            if lang == "he" else
            "🗑 *Account deleted*\n\nThank you for being part of Flirt40! 💋\nTo rejoin: /start"
        )
        await query.edit_message_text(msg, parse_mode="Markdown")
    else:
        await query.edit_message_text("✅ ביטול | Cancelled")


async def handle_message(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id

    # Edit bio
    if update.message.text and user_id in WAITING_EDIT_BIO:
        bio = update.message.text.strip()
        if len(bio) > 300:
            await update.message.reply_text("❌ עד 300 תווים | Max 300 chars")
            return
        WAITING_EDIT_BIO.discard(user_id)
        from database.db import get_conn
        conn = get_conn()
        conn.execute("UPDATE users SET bio = ? WHERE user_id = ?", (bio, user_id))
        conn.commit()
        conn.close()
        lang = get_user_settings(user_id).get("language", "he")
        msg = "✅ הביו עודכן!" if lang == "he" else "✅ Bio updated!"
        await update.message.reply_text(msg)
        await send_main_menu(context, user_id)
        return

    if update.message.text and user_id in WAITING_REPORT_REASON:
        target_id = WAITING_REPORT_REASON.pop(user_id)
        WAITING_REPORT_EVIDENCE[user_id] = {"target_id": target_id, "reason": update.message.text.strip()}
        await update.message.reply_text("📎 שלח/י תמונת הוכחה, או /skip אם אין")
        return

    if user_id in WAITING_REPORT_EVIDENCE:
        data = WAITING_REPORT_EVIDENCE.pop(user_id)
        evidence = update.message.photo[-1].file_id if update.message.photo else None
        add_report(user_id, data["target_id"], data["reason"], evidence)
        await update.message.reply_text("✅ *הדיווח התקבל!* ההנהלה תבדוק בהקדם.", parse_mode="Markdown")
        admin_id = int(os.environ.get("ADMIN_ID", "0"))
        if admin_id:
            from database.db import get_user as gu
            reporter = gu(user_id)
            reported = gu(data["target_id"])
            kb = [[
                InlineKeyboardButton("⏸ השעה", callback_data=f"suspend_{data['target_id']}"),
                InlineKeyboardButton("🚫 חסום", callback_data=f"block_{data['target_id']}")
            ], [
                InlineKeyboardButton("💬 מדווח", callback_data=f"msg_to_{user_id}"),
                InlineKeyboardButton("💬 מדוּוח", callback_data=f"msg_to_{data['target_id']}")
            ]]
            text = (f"🚨 *דיווח חדש*\n\n"
                    f"👤 מדווח: {reporter['name'] if reporter else user_id}\n"
                    f"👤 מדוּוח: {reported['name'] if reported else data['target_id']}\n"
                    f"📝 {data['reason']}")
            if evidence:
                try:
                    await context.bot.send_photo(chat_id=admin_id, photo=evidence,
                        caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
                    return
                except Exception:
                    pass
            await context.bot.send_message(chat_id=admin_id, text=text,
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if update.message.text and user_id in WAITING_BUG:
        WAITING_BUG.discard(user_id)
        add_bug_report(user_id, update.message.text.strip())
        await update.message.reply_text("✅ *תודה! הדיווח התקבל.*", parse_mode="Markdown")
        return

    if not update.message.text:
        return

    handled = await handle_chat_message(update, context)
    if handled:
        return
    handled = await handle_like_message_text(update, context)
    if handled:
        return
    await handle_appeal_message(update, context)


async def handle_photo_message(update, context):
    user_id = update.effective_user.id
    if user_id in WAITING_REPORT_EVIDENCE:
        await handle_message(update, context)
        return
    if user_id in WAITING_EDIT_PHOTOS:
        WAITING_EDIT_PHOTOS.discard(user_id)
        from database.db import get_user_photos as gup, get_conn
        photos = gup(user_id)
        if len(photos) >= 5:
            await update.message.reply_text("❌ כבר יש 5 תמונות - המקסימום! מחק תמונה קודם.")
            return
        file_id = update.message.photo[-1].file_id
        conn = get_conn()
        pos = len(photos)
        conn.execute("INSERT INTO user_photos (user_id, file_id, position) VALUES (?, ?, ?)",
                     (user_id, file_id, pos))
        conn.commit()
        conn.close()
        lang = get_user_settings(user_id).get("language", "he")
        msg = f"✅ תמונה נוספה! יש לך עכשיו {pos+1} תמונות." if lang == "he" else f"✅ Photo added! You now have {pos+1} photos."
        await update.message.reply_text(msg)
        await send_main_menu(context, user_id)
        return
    await handle_chat_message(update, context)


async def pre_checkout(update, context):
    await update.pre_checkout_query.answer(ok=True)


async def report_command(update, context):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user or user["status"] != "approved":
        await update.message.reply_text("❌ עליך להיות מאושר")
        return
    args = context.args
    if not args:
        await update.message.reply_text("🚨 שלח: `/report [ID]`", parse_mode="Markdown")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID לא תקין")
        return
    if target_id == user_id:
        await update.message.reply_text("❌ לא ניתן לדווח על עצמך")
        return
    WAITING_REPORT_REASON[user_id] = target_id
    await update.message.reply_text("📝 מה סיבת הדיווח? תאר/י בקצרה:")


async def skip_command(update, context):
    user_id = update.effective_user.id
    if user_id in WAITING_REPORT_EVIDENCE:
        data = WAITING_REPORT_EVIDENCE.pop(user_id)
        add_report(user_id, data["target_id"], data["reason"], None)
        await update.message.reply_text("✅ הדיווח התקבל.")


async def bug_command(update, context):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user or user["status"] != "approved":
        await update.message.reply_text("❌ עליך להיות מאושר")
        return
    WAITING_BUG.add(user_id)
    await update.message.reply_text("🐛 תאר/י את הבעיה:")


async def delete_command(update, context):
    keyboard = [[
        InlineKeyboardButton("🗑 כן, מחק", callback_data="confirm_delete"),
        InlineKeyboardButton("❌ ביטול", callback_data="cancel_delete")
    ]]
    await update.message.reply_text(
        "⚠️ *מחיקת חשבון*\n\nהפרופיל יימחק. להמשיך?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def menu_command(update, context):
    user = get_user(update.effective_user.id)
    if not user or user["status"] != "approved":
        await update.message.reply_text("❌ עליך להיות מאושר | /start")
        return
    await send_main_menu(context, update.effective_user.id)


# ── Web Admin ──
flask_app = Flask(__name__)
flask_app.secret_key = os.environ.get("WEB_SECRET_KEY", "flirt40secret")
ADMIN_WEB_PASSWORD = os.environ.get("ADMIN_WEB_PASSWORD", "admin123")

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated

@flask_app.route("/login", methods=["GET", "POST"])
def web_login():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == ADMIN_WEB_PASSWORD:
            session["logged_in"] = True
            return redirect("/")
        error = "סיסמה שגויה"
    return f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8">
<title>Flirt40 Admin</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#0d0d0d;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}}.box{{background:#1a1a1a;border:1px solid #333;border-radius:16px;padding:48px;width:360px;text-align:center}}h1{{font-size:2rem;margin-bottom:8px}}p{{color:#888;margin-bottom:32px}}input{{width:100%;padding:14px;background:#111;border:1px solid #333;border-radius:10px;color:#fff;font-size:1rem;margin-bottom:16px;outline:none;text-align:center}}input:focus{{border-color:#e91e8c}}button{{width:100%;padding:14px;background:#e91e8c;border:none;border-radius:10px;color:#fff;font-size:1rem;font-weight:bold;cursor:pointer}}.err{{color:#f44;font-size:.85rem;margin-top:12px}}</style></head>
<body><div class="box"><h1>💋 Flirt40</h1><p>פאנל ניהול</p>
<form method="POST"><input type="password" name="password" placeholder="סיסמה" autofocus><button>כניסה</button></form>
{f'<p class="err">{error}</p>' if error else ''}</div></body></html>"""

@flask_app.route("/logout")
def web_logout():
    session.clear()
    return redirect("/login")

@flask_app.route("/")
@login_required
def web_index():
    from database.db import get_conn, get_stats
    stats = get_stats()
    return f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Flirt40 Admin</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#0d0d0d;color:#fff;font-family:sans-serif}}
nav{{background:#1a1a1a;border-bottom:1px solid #2a2a2a;padding:16px 32px;display:flex;align-items:center;justify-content:space-between}}
nav h1{{color:#e91e8c;font-size:1.4rem}}nav a{{color:#aaa;text-decoration:none;margin-right:20px}}
.container{{max-width:1200px;margin:0 auto;padding:32px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:40px}}
.stat{{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:12px;padding:24px;text-align:center}}
.num{{font-size:2.5rem;font-weight:bold;color:#e91e8c}}.label{{color:#888;font-size:.85rem;margin-top:4px}}
.btn{{display:inline-block;padding:10px 20px;background:#e91e8c;color:#fff;border-radius:8px;text-decoration:none;font-size:.9rem;font-weight:bold;margin:4px}}
.btn-out{{background:transparent;border:1px solid #e91e8c;color:#e91e8c}}
</style></head><body>
<nav><h1>💋 Flirt40 Admin</h1><div><a href="/">🏠 ראשי</a><a href="/users">👥 משתמשים</a><a href="/reports">🚨 דיווחים</a><a href="/logout">יציאה</a></div></nav>
<div class="container">
<div class="stats">
<div class="stat"><div class="num">{stats["total"]}</div><div class="label">סה"כ משתמשים</div></div>
<div class="stat"><div class="num" style="color:#f39c12">{stats["pending"]}</div><div class="label">ממתינים</div></div>
<div class="stat"><div class="num" style="color:#2ecc71">{stats["approved"]}</div><div class="label">מאושרים</div></div>
<div class="stat"><div class="num" style="color:#e74c3c">{stats["blocked"]}</div><div class="label">חסומים</div></div>
<div class="stat"><div class="num" style="color:#e91e8c">{stats["reports"]}</div><div class="label">דיווחים</div></div>
<div class="stat"><div class="num" style="color:#9b59b6">{stats["matches"]}</div><div class="label">התאמות</div></div>
</div>
<a href="/users?status=pending" class="btn">⏳ ממתינים</a>
<a href="/users" class="btn btn-out">👥 כל המשתמשים</a>
<a href="/reports" class="btn btn-out">🚨 דיווחים</a>
</div></body></html>"""

@flask_app.route("/users")
@login_required
def web_users():
    from database.db import get_conn
    REGIONS = {{"north":"צפון","center":"מרכז","south":"דרום"}}
    status_filter = request.args.get("status","")
    search = request.args.get("search","")
    page = int(request.args.get("page",1))
    per_page = 12
    conn = get_conn()
    where = "WHERE 1=1"
    params = []
    if status_filter:
        where += " AND status=?"
        params.append(status_filter)
    if search:
        try:
            uid = int(search)
            where += " AND user_id=?"
            params.append(uid)
        except ValueError:
            where += " AND LOWER(name) LIKE LOWER(?)"
            params.append(f"%{{search}}%")
    total = conn.execute(f"SELECT COUNT(*) as c FROM users {{where}}", params).fetchone()["c"]
    users_list = conn.execute(f"SELECT * FROM users {{where}} ORDER BY created_at DESC LIMIT ? OFFSET ?", params+[per_page,(page-1)*per_page]).fetchall()
    conn.close()
    cards = ""
    for u in users_list:
        ge = "👩" if u["gender"]=="female" else "👨"
        reg = REGIONS.get(u.get("region",""),"")
        un = f"@{{u['username']}}" if u.get("username") else "אין"
        st = {{"approved":"✅","pending":"⏳","rejected":"❌","deleted":"🗑"}}.get(u["status"],"❓")
        flags = ""
        if u.get("is_blocked"): flags += " 🚫"
        if u.get("is_suspended"): flags += " ⏸"
        if u.get("is_premium"): flags += " ⭐"
        cards += f'''<div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:12px;padding:16px">
<div style="font-size:1.1rem;font-weight:bold;margin-bottom:8px">{{ge}} {{u["name"]}}, {{u["age"]}}</div>
<div style="color:#aaa;font-size:.8rem">📍 {{reg}} {{u.get("city","")}} | {{st}}{{flags}}</div>
<div style="color:#aaa;font-size:.8rem">📱 {{un}} | 🆔 <code>{{u["user_id"]}}</code></div>
<div style="color:#ccc;font-size:.85rem;margin:8px 0">{{(u.get("bio") or "")[:80]}}</div>
<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px">
<a href="/user/{{u["user_id"]}}" style="padding:6px 12px;border-radius:6px;background:#2a2a2a;color:#fff;text-decoration:none;font-size:.78rem">👁 פרטים</a>
{'<a href="/action/approve/'+str(u["user_id"])+'" style="padding:6px 12px;border-radius:6px;background:#1a5c2e;color:#2ecc71;text-decoration:none;font-size:.78rem">✅ אשר</a>' if u["status"]=="pending" else ""}
{'<a href="/action/unblock/'+str(u["user_id"])+'" style="padding:6px 12px;border-radius:6px;background:#1a5c2e;color:#2ecc71;text-decoration:none;font-size:.78rem">🔓 שחרר</a>' if u.get("is_blocked") else '<a href="/action/block/'+str(u["user_id"])+'" style="padding:6px 12px;border-radius:6px;background:#5c1a1a;color:#e74c3c;text-decoration:none;font-size:.78rem">🚫 חסום</a>'}
</div></div>'''
    total_pages = max(1,(total+per_page-1)//per_page)
    pag = "".join([f'<a href="?page={{p}}&status={{status_filter}}&search={{search}}" style="display:inline-block;padding:8px 14px;margin:2px;background:{{"#e91e8c" if p==page else "#1a1a1a"}};color:#fff;border-radius:6px;text-decoration:none">{{p}}</a>' for p in range(1,total_pages+1)])
    return f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>משתמשים</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#0d0d0d;color:#fff;font-family:sans-serif}}
nav{{background:#1a1a1a;border-bottom:1px solid #2a2a2a;padding:16px 32px;display:flex;align-items:center;justify-content:space-between}}
nav h1{{color:#e91e8c}}nav a{{color:#aaa;text-decoration:none;margin-right:20px}}
.container{{max-width:1400px;margin:0 auto;padding:32px}}
.filters{{display:flex;gap:12px;margin-bottom:28px;flex-wrap:wrap;align-items:center}}
.filters input{{padding:10px 16px;background:#1a1a1a;border:1px solid #333;border-radius:8px;color:#fff;width:250px}}
.fa{{padding:10px 18px;background:#1a1a1a;border:1px solid #333;border-radius:8px;color:#aaa;text-decoration:none;font-size:.85rem}}
.fa.active{{background:#e91e8c;color:#fff;border-color:#e91e8c}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:20px}}
button{{padding:10px 18px;background:#e91e8c;border:none;border-radius:8px;color:#fff;cursor:pointer}}
code{{background:#111;padding:2px 6px;border-radius:4px;font-size:.75rem}}</style></head><body>
<nav><h1>💋 Flirt40 Admin</h1><div><a href="/">🏠</a><a href="/users">👥 משתמשים</a><a href="/reports">🚨 דיווחים</a><a href="/logout">יציאה</a></div></nav>
<div class="container">
<form method="GET" class="filters">
<input type="text" name="search" placeholder="🔍 שם או ID..." value="{{search}}">
<a href="/users" class="fa{" active" if not status_filter else ""}">הכל</a>
<a href="/users?status=pending" class="fa{" active" if status_filter=="pending" else ""}">⏳ ממתינים</a>
<a href="/users?status=approved" class="fa{" active" if status_filter=="approved" else ""}">✅ מאושרים</a>
<button type="submit">חפש</button></form>
<p style="color:#888;margin-bottom:16px">{{total}} משתמשים</p>
<div class="grid">{{cards}}</div>
<div style="margin-top:32px;text-align:center">{{pag}}</div>
</div></body></html>"""

@flask_app.route("/user/<int:user_id>")
@login_required
def web_user_detail(user_id):
    from database.db import get_conn
    REGIONS = {{"north":"צפון","center":"מרכז","south":"דרום"}}
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return "לא נמצא", 404
    reports = conn.execute("SELECT r.*,u.name as rname FROM reports r LEFT JOIN users u ON r.reporter_id=u.user_id WHERE r.reported_id=? ORDER BY r.created_at DESC", (user_id,)).fetchall()
    conn.close()
    ge = "👩" if user["gender"]=="female" else "👨"
    reg = REGIONS.get(user.get("region",""),"")
    un = f"@{{user['username']}}" if user.get("username") else "אין"
    sc = {{"approved":"#2ecc71","pending":"#f39c12","rejected":"#e74c3c","deleted":"#888"}}.get(user["status"],"#fff")
    reps = "".join([f'<div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:16px;margin-bottom:12px"><div style="color:#aaa;font-size:.8rem">מדווח: {{r.get("rname","?")}} | {{str(r.get("created_at",""))[:10]}}</div><div style="margin-top:8px">{{r.get("reason","")}}</div></div>' for r in reports])
    return f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>{{user["name"]}}</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#0d0d0d;color:#fff;font-family:sans-serif}}
nav{{background:#1a1a1a;border-bottom:1px solid #2a2a2a;padding:16px 32px;display:flex;align-items:center;justify-content:space-between}}
nav h1{{color:#e91e8c}}nav a{{color:#aaa;text-decoration:none;margin-right:20px}}
.container{{max-width:900px;margin:0 auto;padding:32px}}
.btn{{padding:10px 20px;border-radius:8px;text-decoration:none;font-size:.9rem;font-weight:bold;margin:4px;display:inline-block}}
code{{background:#111;padding:2px 8px;border-radius:4px}}</style></head><body>
<nav><h1>💋 Flirt40 Admin</h1><div><a href="/">🏠</a><a href="/users">← חזרה</a><a href="/logout">יציאה</a></div></nav>
<div class="container">
<div style="font-size:1.8rem;font-weight:bold;margin-bottom:16px">{{ge}} {{user["name"]}}, {{user["age"]}}</div>
<div style="color:#aaa;margin-bottom:8px">📍 {{reg}} - {{user.get("city","")}}</div>
<div style="color:#aaa;margin-bottom:8px">📱 {{un}}</div>
<div style="color:#aaa;margin-bottom:8px">🆔 <code>{{user_id}}</code></div>
<div style="margin-bottom:8px">סטטוס: <span style="color:{{sc}}">{{user["status"]}}</span>{{"| 🚫 חסום" if user.get("is_blocked") else ""}}{{"| ⏸ מושעה" if user.get("is_suspended") else ""}}{{"| ⭐ פרמיום" if user.get("is_premium") else ""}}</div>
<div style="background:#1a1a1a;border-radius:8px;padding:16px;margin:16px 0">{{user.get("bio","")}}</div>
<div style="margin-bottom:24px">
{'<a href="/action/approve/'+str(user_id)+'" class="btn" style="background:#1a5c2e;color:#2ecc71">✅ אשר</a>' if user["status"]=="pending" else ""}
{'<a href="/action/unblock/'+str(user_id)+'" class="btn" style="background:#1a5c2e;color:#2ecc71">🔓 שחרר</a>' if user.get("is_blocked") else '<a href="/action/block/'+str(user_id)+'" class="btn" style="background:#5c1a1a;color:#e74c3c">🚫 חסום</a>'}
{'<a href="/action/unsuspend/'+str(user_id)+'" class="btn" style="background:#5c3a1a;color:#e67e22">▶️ שחרר השעיה</a>' if user.get("is_suspended") else '<a href="/action/suspend/'+str(user_id)+'" class="btn" style="background:#5c3a1a;color:#e67e22">⏸ השעה</a>'}
<a href="/action/delete/{{user_id}}" class="btn" style="background:#5c1a1a;color:#e74c3c" onclick="return confirm('למחוק?')">🗑 מחק</a>
</div>
{f'<h3 style="margin-bottom:16px">דיווחים ({{len(reports)}})</h3>{{reps}}' if reports else '<p style="color:#555">אין דיווחים.</p>'}
</div></body></html>"""

@flask_app.route("/action/<action>/<int:user_id>")
@login_required
def web_action(action, user_id):
    from database.db import get_conn
    conn = get_conn()
    if action == "approve": conn.execute("UPDATE users SET status='approved' WHERE user_id=?", (user_id,))
    elif action == "block": conn.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (user_id,))
    elif action == "unblock": conn.execute("UPDATE users SET is_blocked=0,is_suspended=0,status='approved' WHERE user_id=?", (user_id,))
    elif action == "suspend": conn.execute("UPDATE users SET is_suspended=1 WHERE user_id=?", (user_id,))
    elif action == "unsuspend": conn.execute("UPDATE users SET is_suspended=0 WHERE user_id=?", (user_id,))
    elif action == "delete": conn.execute("UPDATE users SET status='deleted' WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or "/users")

@flask_app.route("/reports")
@login_required
def web_reports():
    from database.db import get_conn
    conn = get_conn()
    reps = conn.execute("SELECT r.*,u1.name as rname,u2.name as dname FROM reports r LEFT JOIN users u1 ON r.reporter_id=u1.user_id LEFT JOIN users u2 ON r.reported_id=u2.user_id WHERE r.status='pending' ORDER BY r.created_at DESC").fetchall()
    conn.close()
    rows = "".join([f'<tr><td>{{r.get("rname","?")}}</td><td><a href="/user/{{r["reported_id"]}}" style="color:#e91e8c">{{r.get("dname","?")}}</a></td><td>{{r.get("reason","")}}</td><td>{{str(r.get("created_at",""))[:10]}}</td><td><a href="/action/suspend/{{r["reported_id"]}}" style="color:#e67e22;text-decoration:none;margin-left:8px">⏸</a><a href="/action/block/{{r["reported_id"]}}" style="color:#e74c3c;text-decoration:none;margin-left:8px">🚫</a><a href="/report/close/{{r["id"]}}" style="color:#2ecc71;text-decoration:none">✅</a></td></tr>' for r in reps])
    return f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>דיווחים</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#0d0d0d;color:#fff;font-family:sans-serif}}
nav{{background:#1a1a1a;border-bottom:1px solid #2a2a2a;padding:16px 32px;display:flex;align-items:center;justify-content:space-between}}
nav h1{{color:#e91e8c}}nav a{{color:#aaa;text-decoration:none;margin-right:20px}}
.container{{max-width:1200px;margin:0 auto;padding:32px}}
table{{width:100%;border-collapse:collapse}}th{{background:#1a1a1a;padding:12px 16px;text-align:right;color:#888;font-size:.85rem}}
td{{padding:14px 16px;border-bottom:1px solid #1a1a1a;font-size:.9rem}}</style></head><body>
<nav><h1>💋 Flirt40 Admin</h1><div><a href="/">🏠</a><a href="/users">👥</a><a href="/reports">🚨 דיווחים</a><a href="/logout">יציאה</a></div></nav>
<div class="container"><h2 style="margin-bottom:24px">🚨 דיווחים ({{len(reps)}})</h2>
{{'<table><tr><th>מדווח</th><th>מדוּוח</th><th>סיבה</th><th>תאריך</th><th>פעולה</th></tr>'+rows+'</table>' if reps else '<p style="color:#555">אין דיווחים.</p>'}}
</div></body></html>"""

@flask_app.route("/report/close/<int:report_id>")
@login_required
def web_close_report(report_id):
    from database.db import get_conn
    conn = get_conn()
    conn.execute("UPDATE reports SET status='closed' WHERE id=?", (report_id,))
    conn.commit()
    conn.close()
    return redirect("/reports")

def run_web():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    registration_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GENDER: [CallbackQueryHandler(get_gender, pattern="^gender_")],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            REGION: [CallbackQueryHandler(get_region, pattern="^region_")],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)],
            PHOTOS: [
                MessageHandler(filters.PHOTO, get_photos),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_photos),
                CommandHandler("done", get_photos)
            ],
            ID_CARD: [MessageHandler(filters.PHOTO | filters.Document.ALL, get_id_card)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
        per_message=False,
    )

    app.add_handler(registration_conv)
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("browse", show_next_profile))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("skip", skip_command))
    app.add_handler(CommandHandler("bug", bug_command))
    app.add_handler(CommandHandler("delete", delete_command))

    app.add_handler(CallbackQueryHandler(handle_menu_callbacks, pattern="^(menu_|settings_)"))
    app.add_handler(CallbackQueryHandler(handle_delete_confirm, pattern="^(confirm|cancel)_delete$"))
    app.add_handler(CallbackQueryHandler(handle_like_dislike, pattern="^(like|dislike|like_msg)_"))
    app.add_handler(CallbackQueryHandler(handle_chat_consent, pattern="^chat_(consent|decline)_"))
    app.add_handler(CallbackQueryHandler(handle_chat_callbacks, pattern="^(end_chat|share_details)_"))
    app.add_handler(CallbackQueryHandler(handle_region_filter, pattern="^filter_region_"))
    app.add_handler(CallbackQueryHandler(handle_admin_callback,
        pattern="^(approve|reject|block|unblock|suspend|unsuspend|admin_|delete_id|view_id|appeal_|broadcast|gift|revoke|report_|bug_|msg_|noop)"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))

    async def error_handler(update, context):
        import traceback
        err = traceback.format_exc()
        logger.error(f"Exception: {context.error}\n{err}")
        admin_id = int(os.environ.get("ADMIN_ID", "0"))
        if admin_id:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🚨 שגיאה בבוט:\n`{str(context.error)[:500]}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    app.add_error_handler(error_handler)
    # Start web admin in background thread
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    logger.info("Flirt40 Bot + Web Admin started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
