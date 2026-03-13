from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes
from database.db import (
    get_user, get_next_profile, mark_seen, add_like,
    check_mutual_like, save_match, get_conn,
    check_and_use_like, get_likes_status, PREMIUM_PRICE_STARS
)
from handlers.chat import start_chat_session

# States for premium like message
WAITING_LIKE_MESSAGE = {}  # user_id -> target_id


async def show_next_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        if update.message:
            await update.message.reply_text("❌ השתמש ב /start להרשמה | _Use /start to register_")
        return
    if user["is_blocked"]:
        if update.message:
            await update.message.reply_text("⛔ חשבונך חסום | _Your account is blocked_")
        return
    if user["status"] != "approved":
        if update.message:
            await update.message.reply_text("⏳ פרופילך ממתין לאישור | _Pending approval_")
        return

    profile = get_next_profile(user_id, user["gender"])
    if not profile:
        msg = "😔 *אין יותר פרופילים כרגע* | _No more profiles right now_\n\nחזור מאוחר יותר! | _Come back later!_"
        if update.message:
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
        return

    mark_seen(user_id, profile["user_id"])
    await _send_profile_card(context, user_id, profile, user["is_premium"])


async def _send_profile_card(context, chat_id, profile, is_premium=False):
    gender_emoji = "👩" if profile["gender"] == "female" else "👨"
    premium_badge = "⭐ " if profile["is_premium"] else ""
    caption = (
        f"{gender_emoji} {premium_badge}*{profile['name']}*, גיל {profile['age']}\n"
        f"📍 {profile['city']}\n\n"
        f"📝 {profile['bio']}"
    )
    buttons = [
        InlineKeyboardButton("❤️ כן / Yes", callback_data=f"like_{profile['user_id']}"),
        InlineKeyboardButton("❌ לא / No", callback_data=f"dislike_{profile['user_id']}")
    ]
    if is_premium:
        keyboard = [buttons, [
            InlineKeyboardButton("💌 שלח הודעה עם לייק | Send message with like",
                                 callback_data=f"like_msg_{profile['user_id']}")
        ]]
    else:
        keyboard = [buttons]

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
    data = query.data

    # Handle like with message request
    if data.startswith("like_msg_"):
        target_id = int(data.replace("like_msg_", ""))
        WAITING_LIKE_MESSAGE[user_id] = target_id
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "💌 *כתוב/י הודעה קצרה לשלוח עם הלייק | Write a short message to send with your like*\n"
            "_(עד 200 תווים | max 200 chars)_",
            parse_mode="Markdown"
        )
        return

    action, target_id = data.split("_", 1)
    target_id = int(target_id)

    user = get_user(user_id)
    if not user or user["is_blocked"] or user["status"] != "approved":
        return

    await query.edit_message_reply_markup(reply_markup=None)

    if action == "like":
        await _process_like(update, context, user_id, target_id, user, query)
    else:
        await query.message.reply_text("👋 עוברים הלאה | _Moving on..._")
        await _show_next_auto(context, user_id, user["gender"], user["is_premium"])


async def handle_like_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text message sent as like message by premium user."""
    user_id = update.effective_user.id
    if user_id not in WAITING_LIKE_MESSAGE:
        return False

    target_id = WAITING_LIKE_MESSAGE.pop(user_id)
    message = update.message.text.strip()[:200]

    user = get_user(user_id)
    if not user:
        return True

    await _process_like(update, context, user_id, target_id, user, None, message=message)
    return True


async def _process_like(update, context, user_id, target_id, user, query, message=None):
    can_like, remaining = check_and_use_like(user_id)

    if not can_like:
        keyboard = [[InlineKeyboardButton(
            "⭐ שדרג לפרמיום | Upgrade to Premium",
            callback_data="buy_premium"
        )]]
        text = (
            "❌ *נגמרו הלייקים להיום! | No more likes today!*\n\n"
            "🇮🇱 יש לך 10 לייקים חינמיים ביום. שדרג לפרמיום ללייקים ללא הגבלה!\n"
            "🇬🇧 You have 10 free likes per day. Upgrade to Premium for unlimited likes!"
        )
        if query:
            await query.message.reply_text(text, parse_mode="Markdown",
                                           reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    add_like(user_id, target_id, message)

    # Notify target about the like message (if any)
    if message:
        target = get_user(target_id)
        if target:
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=(
                        f"💌 *{user['name']} שלח/ה לך הודעה עם לייק!*\n\n"
                        f"_{message}_\n\n"
                        f"_Browse profiles to see them: /browse_"
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    # Likes remaining message
    if remaining == -1:
        likes_text = "⭐ _פרמיום - לייקים ללא הגבלה_"
    elif remaining == 0:
        likes_text = "⚠️ _נגמרו הלייקים להיום | No more likes today_"
    else:
        likes_text = f"❤️ נשארו לך {remaining} לייקים היום | _{remaining} likes left today_"

    reply_text = f"❤️ לייקת! | _Liked!_\n\n{likes_text}"
    if query:
        await query.message.reply_text(reply_text, parse_mode="Markdown")
    else:
        await update.message.reply_text(reply_text, parse_mode="Markdown")

    if check_mutual_like(user_id, target_id):
        save_match(user_id, target_id)
        target = get_user(target_id)
        like_msg_from_target = None
        like_msg_from_user = message

        keyboard = [[
            InlineKeyboardButton("💬 כן! | Yes!", callback_data=f"chat_consent_{user_id}_{target_id}"),
            InlineKeyboardButton("❌ לא תודה | No", callback_data=f"chat_decline_{user_id}_{target_id}")
        ]]

        match_caption_user = (
            f"🎉 *יש התאמה! It's a Match!*\n\n"
            f"אתה ו-*{target['name']}* אהבתם אחד את השני!\n"
            f"רוצה להתחיל שיחה מוגנת?\n\n"
            f"_You and *{target['name']}* liked each other! Want to start a protected chat?_"
        )
        match_caption_target = (
            f"🎉 *יש התאמה! It's a Match!*\n\n"
            f"אתה ו-*{user['name']}* אהבתם אחד את השני!\n"
            f"רוצה להתחיל שיחה מוגנת?\n\n"
            f"_You and *{user['name']}* liked each other! Want to start a protected chat?_"
        )

        await context.bot.send_photo(chat_id=user_id, photo=target["photo_file_id"],
                                     caption=match_caption_user, parse_mode="Markdown",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
        await context.bot.send_photo(chat_id=target_id, photo=user["photo_file_id"],
                                     caption=match_caption_target, parse_mode="Markdown",
                                     reply_markup=InlineKeyboardMarkup(keyboard))

    await _show_next_auto(context, user_id, user["gender"], user["is_premium"])


async def _show_next_auto(context, user_id, gender, is_premium):
    profile = get_next_profile(user_id, gender)
    if profile:
        mark_seen(user_id, profile["user_id"])
        await _send_profile_card(context, user_id, profile, is_premium)


async def handle_premium_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    await context.bot.send_invoice(
        chat_id=user_id,
        title="Flirt40 Premium ⭐",
        description=(
            "✅ לייקים ללא הגבלה\n"
            "✅ הפרופיל שלך מופיע ראשון\n"
            "✅ שלח הודעה עם כל לייק\n"
            "✅ ביטול לייק בטעות\n"
            "✅ ראה מי לייקד אותך\n\n"
            "תוקף: 30 יום"
        ),
        payload="premium_monthly",
        currency="XTR",
        prices=[LabeledPrice("Flirt40 Premium - חודש", PREMIUM_PRICE_STARS)]
    )


async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.db import set_premium
    user_id = update.effective_user.id
    until = set_premium(user_id)

    await update.message.reply_text(
        "🎉 *תשלום התקבל! Payment received!*\n\n"
        "⭐ *ברוך הבא לפרמיום! Welcome to Premium!*\n\n"
        "הפיצ'רים הבאים נפתחו לך:\n"
        "✅ לייקים ללא הגבלה\n"
        "✅ הפרופיל שלך מופיע ראשון\n"
        "✅ שלח הודעה עם כל לייק\n"
        "✅ ביטול לייק בטעות\n"
        "✅ ראה מי לייקד אותך\n\n"
        f"⏰ תוקף עד: {until.strftime('%d/%m/%Y')}\n\n"
        "השתמש ב /browse כדי להתחיל! | _Use /browse to start!_",
        parse_mode="Markdown"
    )


async def handle_chat_consent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("chat_consent_"):
        rest = data.replace("chat_consent_", "")
        ids = rest.split("_")
        requester_id, partner_id = int(ids[0]), int(ids[1])
        action = "consent"
    elif data.startswith("chat_decline_"):
        rest = data.replace("chat_decline_", "")
        ids = rest.split("_")
        requester_id, partner_id = int(ids[0]), int(ids[1])
        action = "decline"
    else:
        return

    user = get_user(requester_id)
    partner = get_user(partner_id)
    if not user or not partner:
        return

    await query.edit_message_reply_markup(reply_markup=None)

    if action == "consent":
        _save_chat_consent(requester_id, partner_id)
        if _check_both_consented(requester_id, partner_id):
            start_chat_session(requester_id, partner_id)
            for uid, puid in [(requester_id, partner_id), (partner_id, requester_id)]:
                p = get_user(puid)
                await context.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"💬 *שיחה מוגנת התחילה! | Protected chat started!*\n\n"
                        f"🇮🇱 אתה מדבר עם *{p['name']}*. הפרטים שלך לא נחשפים.\n"
                        f"כתוב/י כרגיל ואני אעביר את ההודעות.\n\n"
                        f"🇬🇧 You're chatting with *{p['name']}*. Your details are hidden.\n"
                        f"Just type and I'll forward your messages."
                    ),
                    parse_mode="Markdown"
                )
        else:
            await context.bot.send_message(
                chat_id=requester_id,
                text="⏳ בחרת לדבר! נמתין לתשובה של הצד השני...\n_You want to chat! Waiting for the other person..._",
                parse_mode="Markdown"
            )
    else:
        await context.bot.send_message(
            chat_id=requester_id,
            text="👋 בחרת לא לדבר הפעם. המשך לגלוש! /browse\n_You chose not to chat. Keep browsing!_",
            parse_mode="Markdown"
        )


def _save_chat_consent(user_id, partner_id):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO chat_consents (user_id, partner_id) VALUES (?, ?)", (user_id, partner_id))
    conn.commit()
    conn.close()


def _check_both_consented(user1_id, user2_id):
    conn = get_conn()
    r1 = conn.execute("SELECT 1 FROM chat_consents WHERE user_id=? AND partner_id=?", (user1_id, user2_id)).fetchone()
    r2 = conn.execute("SELECT 1 FROM chat_consents WHERE user_id=? AND partner_id=?", (user2_id, user1_id)).fetchone()
    conn.close()
    return r1 is not None and r2 is not None
