from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (
    get_pending_users, approve_user, reject_user,
    block_user, unblock_user, delete_id_card,
    get_user, get_stats, add_appeal,
    get_pending_appeals, resolve_appeal,
    set_premium, revoke_premium, add_bonus_likes, add_bonus_likes_all,
    get_all_approved_users
)
import os

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

# States for admin broadcast/gift
WAITING_BROADCAST = {}  # admin_id -> target ("all" or user_id)
WAITING_GIFT_AMOUNT = {}  # admin_id -> target
WAITING_REJECT_REASON = {}  # admin_id -> user_id


def is_admin(user_id):
    return user_id == ADMIN_ID


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ אין לך הרשאה.")
        return

    stats = get_stats()
    keyboard = [
        [InlineKeyboardButton(f"📋 בקשות ממתינות ({stats['pending']})", callback_data="appeal_list_pending")],
        [InlineKeyboardButton(f"⚠️ ערעורים ({len(get_pending_appeals())})", callback_data="appeal_list_appeals")],
        [InlineKeyboardButton("📢 שלח הודעה לכולם", callback_data="broadcast_all"),
         InlineKeyboardButton("📩 שלח למשתמש ספציפי", callback_data="broadcast_user")],
        [InlineKeyboardButton("🎁 תן לייקים לכולם", callback_data="gift_likes_all"),
         InlineKeyboardButton("🎁 תן לייקים למשתמש", callback_data="gift_likes_user")],
        [InlineKeyboardButton("⭐ תן פרמיום למשתמש", callback_data="gift_premium_user"),
         InlineKeyboardButton("❌ הסר פרמיום", callback_data="revoke_premium_user")],
        [InlineKeyboardButton("📊 סטטיסטיקות", callback_data="appeal_stats")]
    ]

    await update.message.reply_text(
        f"🛡️ *פאנל ניהול Flirt40*\n\n"
        f"👥 סה\"כ: {stats['total']} | ⏳ ממתינים: {stats['pending']}\n"
        f"✅ מאושרים: {stats['approved']} | 🚫 חסומים: {stats['blocked']}\n"
        f"⭐ פרמיום: {stats['premium']} | 💕 מאצ'ים: {stats['matches']}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        return

    data = query.data

    if data.startswith("approve_"):
        user_id = int(data.replace("approve_", ""))
        approve_user(user_id)
        user = get_user(user_id)
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n✅ *אושר*", parse_mode="Markdown"
        )
        premium_features = (
            "✅ לייקים ללא הגבלה\n"
            "✅ הפרופיל שלך מופיע ראשון\n"
            "✅ שלח הודעה עם כל לייק\n"
            "✅ ראה מי לייקד אותך\n\n"
        ) if user and user["is_premium"] else ""

        bonus_msg = f"\n🎁 יש לך {user['bonus_likes']} לייקים בונוס!" if user and user["bonus_likes"] > 0 else ""

        bonus_msg2 = f"\n\n🎁 יש לך {user['bonus_likes']} לייקים בונוס מוכנים לשימוש!" if user and user["bonus_likes"] > 0 else ""
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "✅ *פרופילך אושר! Your profile is approved!*\n\n"
                "💋 ברוך הבא ל-Flirt40! Welcome to Flirt40!\n\n"
                f"{premium_features}"
                "📌 *פקודות זמינות | Available commands:*\n"
                "/browse - גלוש בפרופילים | Browse profiles\n"
                "/premium - שדרג לפרמיום | Upgrade to Premium\n"
                "/status - הסטטוס שלך | Your status\n"
                "/filter - סנן לפי אזור (פרמיום) | Filter by region"
                + bonus_msg2
            ),
            parse_mode="Markdown"
        )

    elif data.startswith("reject_"):
        user_id = int(data.replace("reject_", ""))
        WAITING_REJECT_REASON[ADMIN_ID] = user_id
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✍️ כתוב סיבת דחייה למשתמש {user_id} (או שלח 'דלג' לסיבה ברירת מחדל):"
        )

    elif data.startswith("block_") and not data.startswith("block_list"):
        user_id = int(data.replace("block_", ""))
        block_user(user_id)
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n🚫 *חסום*", parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "⛔ *חשבונך חסום | Your account is blocked*\n\n"
                "אם אתה חושב שזו טעות, שלח הודעה עם הסברך.\n"
                "_If you think this is a mistake, send a message explaining your case._"
            ),
            parse_mode="Markdown"
        )

    elif data.startswith("unblock_"):
        user_id = int(data.replace("unblock_", ""))
        unblock_user(user_id)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ משתמש {user_id} שוחרר.")
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ *החסימה הוסרה! | Block removed!*\n\nתוכל להמשיך להשתמש בבוט. /browse",
            parse_mode="Markdown"
        )

    elif data.startswith("view_id_"):
        user_id = int(data.replace("view_id_", ""))
        user = get_user(user_id)
        if user and user["id_card_file_id"]:
            keyboard = [[InlineKeyboardButton("🗑 מחק תז", callback_data=f"delete_id_{user_id}")]]
            await context.bot.send_photo(
                chat_id=ADMIN_ID, photo=user["id_card_file_id"],
                caption=f"🪪 תז של {user['name']}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_message(chat_id=ADMIN_ID, text="❌ תז לא נמצא או נמחק.")

    elif data.startswith("delete_id_"):
        user_id = int(data.replace("delete_id_", ""))
        delete_id_card(user_id)
        await query.edit_message_caption(caption="🗑 תז נמחק.")

    elif data == "appeal_list_pending":
        pending = get_pending_users()
        if not pending:
            await context.bot.send_message(chat_id=ADMIN_ID, text="✅ אין בקשות ממתינות!")
            return
        for user in pending[:5]:
            keyboard = [[
                InlineKeyboardButton("✅ אשר", callback_data=f"approve_{user['user_id']}"),
                InlineKeyboardButton("❌ דחה", callback_data=f"reject_{user['user_id']}")
            ], [
                InlineKeyboardButton("🚫 חסום", callback_data=f"block_{user['user_id']}"),
                InlineKeyboardButton("🪪 צפה בתז", callback_data=f"view_id_{user['user_id']}")
            ]]
            gender_text = "👩 אישה" if user["gender"] == "female" else "👨 גבר"
            await context.bot.send_photo(
                chat_id=ADMIN_ID, photo=user["photo_file_id"],
                caption=(
                    f"📋 *בקשה ממתינה*\n\n"
                    f"👤 {user['name']}, גיל {user['age']}\n"
                    f"📍 {user['city']} | {gender_text}\n"
                    f"📝 {user['bio']}\n"
                    f"🆔 `{user['user_id']}`"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif data == "appeal_list_appeals":
        appeals = get_pending_appeals()
        if not appeals:
            await context.bot.send_message(chat_id=ADMIN_ID, text="✅ אין ערעורים!")
            return
        for appeal in appeals:
            keyboard = [[
                InlineKeyboardButton("✅ שחרר", callback_data=f"unblock_{appeal['user_id']}"),
                InlineKeyboardButton("❌ דחה", callback_data=f"appeal_reject_{appeal['id']}")
            ]]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ *ערעור*\n\n👤 {appeal['name']}, גיל {appeal['age']}\n🆔 `{appeal['user_id']}`\n\n💬 {appeal['message']}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif data.startswith("appeal_reject_"):
        appeal_id = int(data.replace("appeal_reject_", ""))
        resolve_appeal(appeal_id, "rejected")
        await query.edit_message_text("❌ הערעור נדחה.")

    elif data == "appeal_stats":
        stats = get_stats()
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📊 *סטטיסטיקות Flirt40*\n\n"
                f"👥 סה\"כ: {stats['total']}\n⏳ ממתינים: {stats['pending']}\n"
                f"✅ מאושרים: {stats['approved']}\n🚫 חסומים: {stats['blocked']}\n"
                f"⭐ פרמיום: {stats['premium']}\n💕 מאצ'ים: {stats['matches']}"
            ),
            parse_mode="Markdown"
        )

    # Broadcast
    elif data == "broadcast_all":
        WAITING_BROADCAST[ADMIN_ID] = "all"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב את ההודעה לשליחה לכל המשתמשים:")

    elif data == "broadcast_user":
        WAITING_BROADCAST[ADMIN_ID] = "ask_id"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב את ה-Telegram ID של המשתמש:")

    # Gifts
    elif data == "gift_likes_all":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "all_likes"
        await context.bot.send_message(chat_id=ADMIN_ID, text="🎁 כמה לייקים בונוס לתת לכולם?")

    elif data == "gift_likes_user":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "ask_user_likes"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב את ה-Telegram ID של המשתמש:")

    elif data == "gift_premium_user":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "ask_user_premium"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב את ה-Telegram ID של המשתמש:")

    elif data == "revoke_premium_user":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "ask_revoke_premium"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב את ה-Telegram ID של המשתמש:")


async def handle_appeal_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text

    # Admin actions
    if is_admin(user_id):
        # Handle reject reason
        if user_id in WAITING_REJECT_REASON:
            target_id = WAITING_REJECT_REASON.pop(user_id)
            reject_user(target_id)
            reason = "" if message_text.strip() == "דלג" else f"\n\nסיבה: {message_text}"
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"❌ *בקשתך נדחתה | Your request was rejected*{reason}\n\n"
                    "ניתן לנסות שוב עם פרטים מדויקים יותר: /start\n"
                    "_You can try again with more accurate details._"
                ),
                parse_mode="Markdown"
            )
            await update.message.reply_text("✅ המשתמש נדחה והודעה נשלחה.")
            return

        # Handle broadcast
        if user_id in WAITING_BROADCAST:
            state = WAITING_BROADCAST.get(user_id)
            if state == "all":
                WAITING_BROADCAST.pop(user_id)
                users = get_all_approved_users()
                sent, failed = 0, 0
                for u in users:
                    try:
                        await context.bot.send_message(chat_id=u["user_id"], text=message_text)
                        sent += 1
                    except Exception:
                        failed += 1
                await update.message.reply_text(f"✅ נשלח ל-{sent} משתמשים. נכשל: {failed}")
                return
            elif state == "ask_id":
                try:
                    WAITING_BROADCAST[user_id] = f"user_{message_text.strip()}"
                    await update.message.reply_text("✍️ עכשיו כתוב את ההודעה:")
                except Exception:
                    await update.message.reply_text("❌ ID לא תקין")
                    WAITING_BROADCAST.pop(user_id)
                return
            elif state and state.startswith("user_"):
                target_id = int(state.replace("user_", ""))
                WAITING_BROADCAST.pop(user_id)
                try:
                    await context.bot.send_message(chat_id=target_id, text=message_text)
                    await update.message.reply_text("✅ ההודעה נשלחה!")
                except Exception:
                    await update.message.reply_text("❌ לא ניתן לשלוח למשתמש זה.")
                return

        # Handle gifts
        if user_id in WAITING_GIFT_AMOUNT:
            state = WAITING_GIFT_AMOUNT.get(user_id)

            if state == "all_likes":
                WAITING_GIFT_AMOUNT.pop(user_id)
                try:
                    amount = int(message_text.strip())
                    affected = add_bonus_likes_all(amount)
                    users = get_all_approved_users()
                    for u in users:
                        try:
                            await context.bot.send_message(
                                chat_id=u["user_id"],
                                text=(
                                    f"🎁 *מתנה מהנהלת Flirt40!*\n\n"
                                    f"קיבלת {amount} לייקים בונוס! 🎉\n"
                                    f"_Gift from Flirt40! You received {amount} bonus likes!_"
                                ),
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass
                    await update.message.reply_text(f"✅ ניתנו {amount} לייקים ל-{affected} משתמשים!")
                except ValueError:
                    await update.message.reply_text("❌ מספר לא תקין")
                return

            elif state == "ask_user_likes":
                WAITING_GIFT_AMOUNT[user_id] = f"user_likes_{message_text.strip()}"
                await update.message.reply_text("✍️ כמה לייקים לתת?")
                return

            elif state and state.startswith("user_likes_"):
                target_id = int(state.replace("user_likes_", ""))
                WAITING_GIFT_AMOUNT.pop(user_id)
                try:
                    amount = int(message_text.strip())
                    add_bonus_likes(target_id, amount)
                    target = get_user(target_id)
                    await context.bot.send_message(
                        chat_id=target_id,
                        text=(
                            f"🎁 *מתנה מהנהלת Flirt40!*\n\n"
                            f"קיבלת {amount} לייקים בונוס! 🎉\n"
                            f"_You received {amount} bonus likes from Flirt40!_"
                        ),
                        parse_mode="Markdown"
                    )
                    await update.message.reply_text(f"✅ ניתנו {amount} לייקים ל-{target['name'] if target else target_id}!")
                except Exception as e:
                    await update.message.reply_text(f"❌ שגיאה: {e}")
                return

            elif state == "ask_user_premium":
                WAITING_GIFT_AMOUNT[user_id] = f"user_premium_{message_text.strip()}"
                await update.message.reply_text("✍️ כמה ימי פרמיום לתת? (ברירת מחדל: 30)")
                return

            elif state and state.startswith("user_premium_"):
                target_id = int(state.replace("user_premium_", ""))
                WAITING_GIFT_AMOUNT.pop(user_id)
                try:
                    days = int(message_text.strip()) if message_text.strip().isdigit() else 30
                    until = set_premium(target_id, days)
                    target = get_user(target_id)
                    await context.bot.send_message(
                        chat_id=target_id,
                        text=(
                            f"⭐ *קיבלת פרמיום מהנהלת Flirt40!*\n\n"
                            f"הפיצ'רים הבאים נפתחו לך:\n"
                            f"✅ לייקים ללא הגבלה\n"
                            f"✅ הפרופיל שלך מופיע ראשון\n"
                            f"✅ שלח הודעה עם כל לייק\n"
                            f"✅ ראה מי לייקד אותך\n\n"
                            f"⏰ תוקף עד: {until.strftime('%d/%m/%Y')}\n\n"
                            f"_You received Premium from Flirt40! Valid until {until.strftime('%d/%m/%Y')}_"
                        ),
                        parse_mode="Markdown"
                    )
                    await update.message.reply_text(f"✅ פרמיום ניתן ל-{target['name'] if target else target_id} ל-{days} ימים!")
                except Exception as e:
                    await update.message.reply_text(f"❌ שגיאה: {e}")
                return

            elif state == "ask_revoke_premium":
                WAITING_GIFT_AMOUNT.pop(user_id)
                try:
                    target_id = int(message_text.strip())
                    revoke_premium(target_id)
                    await update.message.reply_text(f"✅ פרמיום הוסר ממשתמש {target_id}")
                except Exception:
                    await update.message.reply_text("❌ ID לא תקין")
                return

    # Regular user - check if blocked (appeal)
    user = get_user(user_id)
    if user and user["is_blocked"]:
        add_appeal(user_id, message_text)
        await update.message.reply_text(
            "📨 הערעור שלך התקבל ויבדק בקרוב.\n_Your appeal has been received and will be reviewed._",
            parse_mode="Markdown"
        )
        if ADMIN_ID:
            keyboard = [[
                InlineKeyboardButton("✅ שחרר", callback_data=f"unblock_{user_id}"),
                InlineKeyboardButton("❌ דחה", callback_data=f"block_{user_id}")
            ]]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ *ערעור חדש*\n\n👤 {user['name']}, גיל {user['age']}\n🆔 `{user_id}`\n\n💬 {message_text}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
