from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (
    get_pending_users, approve_user, reject_user,
    block_user, unblock_user, suspend_user, unsuspend_user,
    delete_id_card, get_user, get_stats, add_appeal,
    get_pending_appeals, resolve_appeal,
    set_premium, revoke_premium, add_bonus_likes, add_bonus_likes_all,
    get_all_approved_users, get_pending_reports, resolve_report,
    get_open_bug_reports, get_user_photos, RULES_TEXT
)
import os

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

WAITING_BROADCAST = {}
WAITING_GIFT_AMOUNT = {}
WAITING_REJECT_REASON = {}
WAITING_MESSAGE_USER = {}  # admin direct message to user


def is_admin(user_id):
    return user_id == ADMIN_ID


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ אין לך הרשאה.")
        return

    stats = get_stats()
    keyboard = [
        [InlineKeyboardButton(f"📋 בקשות ממתינות ({stats['pending']})", callback_data="admin_pending")],
        [InlineKeyboardButton(f"🚨 דיווחים ({stats['reports']})", callback_data="admin_reports"),
         InlineKeyboardButton(f"🐛 תקלות ({stats['bugs']})", callback_data="admin_bugs")],
        [InlineKeyboardButton(f"⚠️ ערעורים ({len(get_pending_appeals())})", callback_data="appeal_list_appeals")],
        [InlineKeyboardButton("📢 שלח לכולם", callback_data="broadcast_all"),
         InlineKeyboardButton("📩 שלח למשתמש", callback_data="broadcast_user")],
        [InlineKeyboardButton("💬 שוחח עם משתמש", callback_data="msg_user")],
        [InlineKeyboardButton("🎁 לייקים לכולם", callback_data="gift_likes_all"),
         InlineKeyboardButton("🎁 לייקים למשתמש", callback_data="gift_likes_user")],
        [InlineKeyboardButton("⭐ תן פרמיום", callback_data="gift_premium_user"),
         InlineKeyboardButton("❌ הסר פרמיום", callback_data="revoke_premium_user")],
        [InlineKeyboardButton("📊 סטטיסטיקות", callback_data="appeal_stats")]
    ]

    await update.message.reply_text(
        f"🛡️ *פאנל ניהול Flirt40*\n\n"
        f"👥 סה\"כ: {stats['total']} | ⏳ ממתינים: {stats['pending']}\n"
        f"✅ מאושרים: {stats['approved']} | 🚫 חסומים: {stats['blocked']}\n"
        f"⏸ מושעים: {stats['suspended']} | ⭐ פרמיום: {stats['premium']}\n"
        f"💕 מאצ'ים: {stats['matches']} | 🗑 נמחקו: {stats['deleted']}\n"
        f"🚨 דיווחים: {stats['reports']} | 🐛 תקלות: {stats['bugs']}",
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
            caption=(query.message.caption or "") + "\n\n✅ *אושר*", parse_mode="Markdown"
        )
        bonus_msg = f"\n\n🎁 יש לך {user['bonus_likes']} לייקים בונוס!" if user and user["bonus_likes"] > 0 else ""
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "✅ *פרופילך אושר! Your profile is approved!*\n\n"
                "💋 ברוך הבא ל-Flirt40! | _Welcome to Flirt40!_\n\n"
                + RULES_TEXT +
                "\n\n📌 *פקודות | Commands:*\n"
                "/browse - גלוש בפרופילים\n"
                "/premium - שדרג לפרמיום\n"
                "/status - הסטטוס שלך\n"
                "/report - דווח על משתמש\n"
                "/bug - דווח על תקלה\n"
                "/delete - מחק את החשבון שלך"
                + bonus_msg
            ),
            parse_mode="Markdown"
        )

    elif data.startswith("reject_"):
        user_id = int(data.replace("reject_", ""))
        WAITING_REJECT_REASON[ADMIN_ID] = user_id
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✍️ כתוב סיבת דחייה למשתמש {user_id} (או 'דלג' לברירת מחדל):"
        )

    elif data.startswith("block_") and "_" not in data.replace("block_", ""):
        user_id = int(data.replace("block_", ""))
        block_user(user_id)
        try:
            await query.edit_message_caption(
                caption=(query.message.caption or "") + "\n\n🚫 *חסום*", parse_mode="Markdown"
            )
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "⛔ *חשבונך חסום | Your account is blocked*\n\n"
                "אם אתה חושב שזו טעות, שלח הודעה.\n"
                "_If you think this is a mistake, send a message._"
            ),
            parse_mode="Markdown"
        )

    elif data.startswith("suspend_"):
        user_id = int(data.replace("suspend_", ""))
        suspend_user(user_id)
        try:
            await query.edit_message_text(query.message.text + "\n\n⏸ *הושעה*", parse_mode="Markdown")
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "⏸ *חשבונך הושעה זמנית | Account suspended*\n\n"
                "🇮🇱 חשבונך הושעה עקב דיווח עד להודעה חדשה. ההנהלה תיצור איתך קשר.\n"
                "🇬🇧 Your account was suspended due to a report. Admin will contact you."
            ),
            parse_mode="Markdown"
        )

    elif data.startswith("unsuspend_"):
        user_id = int(data.replace("unsuspend_", ""))
        unsuspend_user(user_id)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ משתמש {user_id} שוחרר מהשעיה.")
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ *ההשעיה הוסרה! | Suspension lifted!*\n\nתוכל להמשיך להשתמש בבוט. /browse",
            parse_mode="Markdown"
        )

    elif data.startswith("unblock_"):
        user_id = int(data.replace("unblock_", ""))
        unblock_user(user_id)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ משתמש {user_id} שוחרר.")
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ *החסימה הוסרה! | Block removed!*\n\n/browse",
            parse_mode="Markdown"
        )

    elif data.startswith("view_id_"):
        user_id = int(data.replace("view_id_", ""))
        user = get_user(user_id)
        if user and user["id_card_file_id"]:
            keyboard = [[InlineKeyboardButton("🗑 מחק תז", callback_data=f"delete_id_{user_id}")]]
            await context.bot.send_photo(
                chat_id=ADMIN_ID, photo=user["id_card_file_id"],
                caption=f"🪪 תז של {user['name']} | 🆔 `{user_id}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_message(chat_id=ADMIN_ID, text="❌ תז לא נמצא.")

    elif data.startswith("delete_id_"):
        user_id = int(data.replace("delete_id_", ""))
        delete_id_card(user_id)
        await query.edit_message_caption(caption="🗑 תז נמחק.")

    elif data == "admin_pending":
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
                InlineKeyboardButton("🪪 תז", callback_data=f"view_id_{user['user_id']}")
            ]]
            gender_text = "👩 אישה" if user["gender"] == "female" else "👨 גבר"
            region_name = user["region"] or ""
            photos = get_user_photos(user["user_id"])
            caption = (
                f"📋 *בקשה ממתינה*\n\n"
                f"👤 {user['name']}, גיל {user['age']}\n"
                f"📍 {region_name} - {user['city']} | {gender_text}\n"
                f"📝 {user['bio']}\n"
                f"🆔 `{user['user_id']}`"
            )
            if photos:
                await context.bot.send_photo(
                    chat_id=ADMIN_ID, photo=photos[0], caption=caption,
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await context.bot.send_message(
                    chat_id=ADMIN_ID, text=caption,
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
                )

    elif data == "admin_reports":
        reports = get_pending_reports()
        if not reports:
            await context.bot.send_message(chat_id=ADMIN_ID, text="✅ אין דיווחים ממתינים!")
            return
        for r in reports[:5]:
            keyboard = [[
                InlineKeyboardButton("⏸ השעה", callback_data=f"suspend_{r['reported_id']}"),
                InlineKeyboardButton("🚫 חסום", callback_data=f"block_{r['reported_id']}")
            ], [
                InlineKeyboardButton("💬 שוחח עם מדווח", callback_data=f"msg_to_{r['reporter_id']}"),
                InlineKeyboardButton("💬 שוחח עם מדוּוח", callback_data=f"msg_to_{r['reported_id']}")
            ], [
                InlineKeyboardButton("✅ סגור דיווח", callback_data=f"report_close_{r['id']}")
            ]]
            text = (
                f"🚨 *דיווח חדש*\n\n"
                f"👤 מדווח: {r['reporter_name'] or r['reporter_id']}\n"
                f"👤 מדוּוח: {r['reported_name'] or r['reported_id']}, גיל {r['reported_age'] or '?'}\n"
                f"📝 סיבה: {r['reason']}\n"
                f"🆔 ID מדוּוח: `{r['reported_id']}`"
            )
            if r["evidence_file_id"]:
                try:
                    await context.bot.send_photo(
                        chat_id=ADMIN_ID, photo=r["evidence_file_id"],
                        caption=text, parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID, text=text, parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
            else:
                await context.bot.send_message(
                    chat_id=ADMIN_ID, text=text, parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

    elif data.startswith("report_close_"):
        report_id = int(data.replace("report_close_", ""))
        resolve_report(report_id, "closed")
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=ADMIN_ID, text="✅ דיווח נסגר.")

    elif data == "admin_bugs":
        bugs = get_open_bug_reports()
        if not bugs:
            await context.bot.send_message(chat_id=ADMIN_ID, text="✅ אין תקלות פתוחות!")
            return
        for b in bugs[:5]:
            keyboard = [[
                InlineKeyboardButton("✅ סמן כטופל", callback_data=f"bug_close_{b['id']}"),
                InlineKeyboardButton("💬 השב למשתמש", callback_data=f"msg_to_{b['user_id']}")
            ]]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🐛 *דיווח תקלה*\n\n"
                    f"👤 {b['name'] or b['user_id']}\n"
                    f"🆔 `{b['user_id']}`\n\n"
                    f"📝 {b['description']}"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif data.startswith("bug_close_"):
        bug_id = int(data.replace("bug_close_", ""))
        conn = __import__('database.db', fromlist=['get_conn']).get_conn()
        conn.execute("UPDATE bug_reports SET status = 'closed' WHERE id = ?", (bug_id,))
        conn.commit()
        conn.close()
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=ADMIN_ID, text="✅ תקלה סומנה כטופלה.")

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
        await query.edit_message_reply_markup(reply_markup=None)

    elif data == "appeal_stats":
        stats = get_stats()
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📊 *סטטיסטיקות Flirt40*\n\n"
                f"👥 סה\"כ: {stats['total']}\n⏳ ממתינים: {stats['pending']}\n"
                f"✅ מאושרים: {stats['approved']}\n🚫 חסומים: {stats['blocked']}\n"
                f"⏸ מושעים: {stats['suspended']}\n⭐ פרמיום: {stats['premium']}\n"
                f"💕 מאצ'ים: {stats['matches']}\n🗑 נמחקו: {stats['deleted']}"
            ),
            parse_mode="Markdown"
        )

    elif data == "broadcast_all":
        WAITING_BROADCAST[ADMIN_ID] = "all"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב הודעה לכל המשתמשים:")

    elif data == "broadcast_user":
        WAITING_BROADCAST[ADMIN_ID] = "ask_id"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב את ה-ID של המשתמש:")

    elif data == "msg_user":
        WAITING_MESSAGE_USER[ADMIN_ID] = "ask_id"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב את ה-ID של המשתמש לשיחה:")

    elif data.startswith("msg_to_"):
        target_id = int(data.replace("msg_to_", ""))
        WAITING_MESSAGE_USER[ADMIN_ID] = f"send_{target_id}"
        user = get_user(target_id)
        name = user["name"] if user else target_id
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✍️ כתוב הודעה ל-{name} (`{target_id}`):",
            parse_mode="Markdown"
        )

    elif data == "gift_likes_all":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "all_likes"
        await context.bot.send_message(chat_id=ADMIN_ID, text="🎁 כמה לייקים בונוס לכולם?")

    elif data == "gift_likes_user":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "ask_user_likes"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב את ה-ID:")

    elif data == "gift_premium_user":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "ask_user_premium"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב את ה-ID:")

    elif data == "revoke_premium_user":
        WAITING_GIFT_AMOUNT[ADMIN_ID] = "ask_revoke_premium"
        await context.bot.send_message(chat_id=ADMIN_ID, text="✍️ כתוב את ה-ID:")


async def handle_appeal_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text if update.message and update.message.text else ""

    if is_admin(user_id):
        # Reject reason
        if user_id in WAITING_REJECT_REASON:
            target_id = WAITING_REJECT_REASON.pop(user_id)
            reject_user(target_id)
            reason = "" if message_text.strip() == "דלג" else f"\n\nסיבה: {message_text}"
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"❌ *בקשתך נדחתה | Request rejected*{reason}\n\n"
                    "ניתן לנסות שוב: /start\n_You can try again: /start_"
                ),
                parse_mode="Markdown"
            )
            await update.message.reply_text("✅ נדחה.")
            return

        # Direct message to user
        if user_id in WAITING_MESSAGE_USER:
            state = WAITING_MESSAGE_USER.get(user_id)
            if state == "ask_id":
                try:
                    WAITING_MESSAGE_USER[user_id] = f"send_{message_text.strip()}"
                    await update.message.reply_text("✍️ כתוב את ההודעה:")
                except Exception:
                    await update.message.reply_text("❌ ID לא תקין")
                    WAITING_MESSAGE_USER.pop(user_id)
                return
            elif state and state.startswith("send_"):
                target_id = int(state.replace("send_", ""))
                WAITING_MESSAGE_USER.pop(user_id)
                try:
                    await context.bot.send_message(
                        chat_id=target_id,
                        text=f"📨 *הודעה מהנהלת Flirt40:*\n\n{message_text}",
                        parse_mode="Markdown"
                    )
                    await update.message.reply_text("✅ ההודעה נשלחה!")
                except Exception:
                    await update.message.reply_text("❌ לא ניתן לשלוח.")
                return

        # Broadcast
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
                await update.message.reply_text(f"✅ נשלח ל-{sent}. נכשל: {failed}")
                return
            elif state == "ask_id":
                WAITING_BROADCAST[user_id] = f"user_{message_text.strip()}"
                await update.message.reply_text("✍️ כתוב את ההודעה:")
                return
            elif state and state.startswith("user_"):
                target_id = int(state.replace("user_", ""))
                WAITING_BROADCAST.pop(user_id)
                try:
                    await context.bot.send_message(chat_id=target_id, text=message_text)
                    await update.message.reply_text("✅ נשלח!")
                except Exception:
                    await update.message.reply_text("❌ לא ניתן לשלוח.")
                return

        # Gifts
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
                                text=f"🎁 *מתנה מהנהלת Flirt40!*\nקיבלת {amount} לייקים בונוס! 🎉\n_Gift from Flirt40! {amount} bonus likes!_",
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
                await update.message.reply_text("✍️ כמה לייקים?")
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
                        text=f"🎁 *מתנה מהנהלת Flirt40!*\nקיבלת {amount} לייקים בונוס! 🎉",
                        parse_mode="Markdown"
                    )
                    await update.message.reply_text(f"✅ ניתנו {amount} לייקים!")
                except Exception as e:
                    await update.message.reply_text(f"❌ שגיאה: {e}")
                return
            elif state == "ask_user_premium":
                WAITING_GIFT_AMOUNT[user_id] = f"user_premium_{message_text.strip()}"
                await update.message.reply_text("✍️ כמה ימים? (ברירת מחדל: 30)")
                return
            elif state and state.startswith("user_premium_"):
                target_id = int(state.replace("user_premium_", ""))
                WAITING_GIFT_AMOUNT.pop(user_id)
                try:
                    days = int(message_text.strip()) if message_text.strip().isdigit() else 30
                    until = set_premium(target_id, days)
                    await context.bot.send_message(
                        chat_id=target_id,
                        text=(
                            f"⭐ *קיבלת פרמיום מהנהלת Flirt40!*\n\n"
                            f"✅ לייקים ללא הגבלה\n✅ הפרופיל מופיע ראשון\n"
                            f"✅ שלח הודעה עם לייק\n✅ סנן לפי אזור\n\n"
                            f"⏰ תוקף עד: {until.strftime('%d/%m/%Y')}"
                        ),
                        parse_mode="Markdown"
                    )
                    await update.message.reply_text(f"✅ פרמיום ניתן ל-{days} ימים!")
                except Exception as e:
                    await update.message.reply_text(f"❌ שגיאה: {e}")
                return
            elif state == "ask_revoke_premium":
                WAITING_GIFT_AMOUNT.pop(user_id)
                try:
                    target_id = int(message_text.strip())
                    revoke_premium(target_id)
                    await update.message.reply_text(f"✅ פרמיום הוסר.")
                except Exception:
                    await update.message.reply_text("❌ ID לא תקין")
                return

    # Regular user - blocked appeal
    user = get_user(user_id)
    if user and user["is_blocked"]:
        add_appeal(user_id, message_text)
        await update.message.reply_text(
            "📨 הערעור שלך התקבל ויבדק בקרוב.\n_Your appeal has been received._",
            parse_mode="Markdown"
        )
        if ADMIN_ID:
            keyboard = [[
                InlineKeyboardButton("✅ שחרר", callback_data=f"unblock_{user_id}"),
                InlineKeyboardButton("❌ דחה", callback_data=f"block_{user_id}")
            ]]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ *ערעור חדש*\n\n👤 {user['name']}\n🆔 `{user_id}`\n\n💬 {message_text}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
