from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (
    get_user, get_next_profile, mark_seen,
    add_like, check_mutual_like, save_match, get_conn
)


async def show_next_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        if update.message:
            await update.message.reply_text(
                "❌ לא נמצא פרופיל. השתמש ב /start להרשמה.\n"
                "_No profile found. Use /start to register._"
            )
        return

    if user["is_blocked"]:
        if update.message:
            await update.message.reply_text("⛔ חשבונך חסום | _Your account is blocked_")
        return

    if user["status"] != "approved":
        if update.message:
            await update.message.reply_text(
                "⏳ פרופילך עדיין ממתין לאישור | _Your profile is still pending approval_"
            )
        return

    profile = get_next_profile(user_id, user["gender"])

    if not profile:
        msg = (
            "😔 *אין יותר פרופילים לצפייה כרגע*\n"
            "_No more profiles to view right now_\n\n"
            "חזור מאוחר יותר! | _Come back later!_"
        )
        if update.message:
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
        return

    mark_seen(user_id, profile["user_id"])
    await _send_profile_card(context, user_id, profile)


async def _send_profile_card(context, chat_id, profile):
    gender_emoji = "👩" if profile["gender"] == "female" else "👨"
    caption = (
        f"{gender_emoji} *{profile['name']}*, גיל {profile['age']}\n"
        f"📍 {profile['city']}\n\n"
        f"📝 {profile['bio']}"
    )
    keyboard = [[
        InlineKeyboardButton("❤️ כן / Yes", callback_data=f"like_{profile['user_id']}"),
        InlineKeyboardButton("❌ לא / No", callback_data=f"dislike_{profile['user_id']}")
    ]]
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=profile["photo_file_id"],
        caption=caption,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_like_dislike(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    action, target_id = query.data.split("_", 1)
    target_id = int(target_id)

    user = get_user(user_id)
    if not user or user["is_blocked"] or user["status"] != "approved":
        return

    await query.edit_message_reply_markup(reply_markup=None)

    if action == "like":
        add_like(user_id, target_id)

        if check_mutual_like(user_id, target_id):
            save_match(user_id, target_id)
            target = get_user(target_id)

            # Send match notification to current user - with consent button
            keyboard_me = [[
                InlineKeyboardButton(
                    "💬 כן, אני רוצה לדבר! | Yes, I want to chat!",
                    callback_data=f"chat_consent_{user_id}_{target_id}"
                ),
                InlineKeyboardButton("❌ לא תודה | No thanks", callback_data=f"chat_decline_{user_id}_{target_id}")
            ]]
            await context.bot.send_photo(
                chat_id=user_id,
                photo=target["photo_file_id"],
                caption=(
                    f"🎉 *יש התאמה! It's a Match!*\n\n"
                    f"🇮🇱 אתה ו-*{target['name']}* אהבתם אחד את השני!\n"
                    f"🇬🇧 You and *{target['name']}* liked each other!\n\n"
                    f"האם תרצה לדבר איתו/איתה?\n"
                    f"_Would you like to start a conversation?_"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard_me)
            )

            # Send match notification to target - with consent button
            keyboard_them = [[
                InlineKeyboardButton(
                    "💬 כן, אני רוצה לדבר! | Yes, I want to chat!",
                    callback_data=f"chat_consent_{target_id}_{user_id}"
                ),
                InlineKeyboardButton("❌ לא תודה | No thanks", callback_data=f"chat_decline_{target_id}_{user_id}")
            ]]
            await context.bot.send_photo(
                chat_id=target_id,
                photo=user["photo_file_id"],
                caption=(
                    f"🎉 *יש התאמה! It's a Match!*\n\n"
                    f"🇮🇱 אתה ו-*{user['name']}* אהבתם אחד את השני!\n"
                    f"🇬🇧 You and *{user['name']}* liked each other!\n\n"
                    f"האם תרצה לדבר איתו/איתה?\n"
                    f"_Would you like to start a conversation?_"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard_them)
            )
        else:
            await query.message.reply_text(
                "❤️ לייקת! נמשיך? | _Liked! Keep going?_\n/browse"
            )
    else:
        await query.message.reply_text(
            "👋 עוברים הלאה | _Moving on..._"
        )

    # Auto show next profile
    viewer = get_user(user_id)
    if viewer and viewer["status"] == "approved" and not viewer["is_blocked"]:
        profile = get_next_profile(user_id, viewer["gender"])
        if profile:
            mark_seen(user_id, profile["user_id"])
            await _send_profile_card(context, user_id, profile)


async def handle_chat_consent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split("_")
    action = parts[1]  # consent or decline
    requester_id = int(parts[2])
    partner_id = int(parts[3])

    requester = get_user(requester_id)
    partner = get_user(partner_id)

    if not requester or not partner:
        return

    await query.edit_message_reply_markup(reply_markup=None)

    if action == "consent":
        # Mark consent in DB
        _save_chat_consent(requester_id, partner_id)

        # Check if both consented
        if _check_both_consented(requester_id, partner_id):
            # Both agreed - reveal contact info
            await context.bot.send_message(
                chat_id=requester_id,
                text=(
                    f"💬 *שניכם רוצים לדבר! You both want to chat!*\n\n"
                    f"🇮🇱 צרו קשר עם {partner['name']} ישירות:\n"
                    f"👤 @{partner['username'] or 'אין שם משתמש - חפש לפי שם'}\n\n"
                    f"🇬🇧 Contact {partner['name']} directly:\n"
                    f"👤 @{partner['username'] or 'No username - search by name'}"
                ),
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                chat_id=partner_id,
                text=(
                    f"💬 *שניכם רוצים לדבר! You both want to chat!*\n\n"
                    f"🇮🇱 צרו קשר עם {requester['name']} ישירות:\n"
                    f"👤 @{requester['username'] or 'אין שם משתמש - חפש לפי שם'}\n\n"
                    f"🇬🇧 Contact {requester['name']} directly:\n"
                    f"👤 @{requester['username'] or 'No username - search by name'}"
                ),
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                chat_id=requester_id,
                text=(
                    "⏳ *בחרת לדבר!*\n"
                    "_You want to chat!_\n\n"
                    "🇮🇱 נמתין לתשובה של הצד השני...\n"
                    "🇬🇧 Waiting for the other person to respond..."
                ),
                parse_mode="Markdown"
            )
    else:
        await context.bot.send_message(
            chat_id=requester_id,
            text=(
                "👋 *בחרת לא לדבר הפעם*\n"
                "_You chose not to chat this time_\n\n"
                "המשך לגלוש! | _Keep browsing!_\n/browse"
            ),
            parse_mode="Markdown"
        )


def _save_chat_consent(user_id, partner_id):
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_consents (
            user_id INTEGER,
            partner_id INTEGER,
            PRIMARY KEY (user_id, partner_id)
        )
    """)
    conn.execute(
        "INSERT OR IGNORE INTO chat_consents (user_id, partner_id) VALUES (?, ?)",
        (user_id, partner_id)
    )
    conn.commit()
    conn.close()


def _check_both_consented(user1_id, user2_id):
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_consents (
            user_id INTEGER,
            partner_id INTEGER,
            PRIMARY KEY (user_id, partner_id)
        )
    """)
    r1 = conn.execute(
        "SELECT 1 FROM chat_consents WHERE user_id=? AND partner_id=?",
        (user1_id, user2_id)
    ).fetchone()
    r2 = conn.execute(
        "SELECT 1 FROM chat_consents WHERE user_id=? AND partner_id=?",
        (user2_id, user1_id)
    ).fetchone()
    conn.close()
    return r1 is not None and r2 is not None
