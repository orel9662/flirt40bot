from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (
    get_pending_users, approve_user, reject_user,
    block_user, unblock_user, delete_id_card,
    get_user, get_stats, add_appeal,
    get_pending_appeals, resolve_appeal
)
import os

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))


def is_admin(user_id):
    return user_id == ADMIN_ID


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ אין לך הרשאה.")
        return

    stats = get_stats()
    pending = get_pending_users()
    appeals = get_pending_appeals()

    keyboard = [
        [InlineKeyboardButton(f"📋 בקשות ממתינות ({stats['pending']})", callback_data="appeal_list_pending")],
        [InlineKeyboardButton(f"⚠️ ערעורים ({len(appeals)})", callback_data="appeal_list_appeals")],
        [InlineKeyboardButton("📊 סטטיסטיקות", callback_data="appeal_stats")]
    ]

    await update.message.reply_text(
        f"🛡️ *פאנל ניהול*\n\n"
        f"👥 סה\"כ משתמשים: {stats['total']}\n"
        f"⏳ ממתינים לאישור: {stats['pending']}\n"
        f"✅ מאושרים: {stats['approved']}\n"
        f"🚫 חסומים: {stats['blocked']}\n"
        f"💕 התאמות: {stats['matches']}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        return

    data = query.data

    # Approve user
    if data.startswith("approve_"):
        user_id = int(data.replace("approve_", ""))
        approve_user(user_id)
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n✅ *אושר*",
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ *פרופילך אושר!*\n\nברוך הבא! השתמש ב /browse כדי להתחיל לגלוש בפרופילים. 🎉",
            parse_mode="Markdown"
        )

    # Reject user
    elif data.startswith("reject_"):
        user_id = int(data.replace("reject_", ""))
        reject_user(user_id)
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n❌ *נדחה*",
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ בקשת ההצטרפות שלך נדחתה.\n\n"
                 "הסיבות האפשריות: פרטים לא תואמים לתז, תמונה לא ברורה, או אי עמידה בתנאי הגיל.\n\n"
                 "ניתן לנסות שוב עם פרטים מדויקים יותר: /start"
        )

    # Block user
    elif data.startswith("block_") and not data.startswith("block_list"):
        user_id = int(data.replace("block_", ""))
        block_user(user_id)
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n🚫 *חסום*",
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=user_id,
            text="⛔ חשבונך נחסם.\n\n"
                 "אם אתה חושב שזו טעות, שלח הודעה עם הסברך ונבדוק את הערעור."
        )

    # Unblock user
    elif data.startswith("unblock_"):
        user_id = int(data.replace("unblock_", ""))
        unblock_user(user_id)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✅ משתמש {user_id} שוחרר מחסימה."
        )
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ החסימה שלך הוסרה! תוכל להמשיך להשתמש בבוט. השתמש ב /browse"
        )

    # View ID card
    elif data.startswith("view_id_"):
        user_id = int(data.replace("view_id_", ""))
        user = get_user(user_id)
        if user and user["id_card_file_id"]:
            keyboard = [[
                InlineKeyboardButton("🗑 מחק תז", callback_data=f"delete_id_{user_id}")
            ]]
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=user["id_card_file_id"],
                caption=f"🪪 תעודת זהות של {user['name']}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="❌ תז לא נמצא או כבר נמחק."
            )

    # Delete ID card
    elif data.startswith("delete_id_"):
        user_id = int(data.replace("delete_id_", ""))
        delete_id_card(user_id)
        await query.edit_message_caption(
            caption="🗑 תז נמחק בהצלחה."
        )

    # List pending users
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
                chat_id=ADMIN_ID,
                photo=user["photo_file_id"],
                caption=(
                    f"📋 *בקשה ממתינה*\n\n"
                    f"👤 {user['name']}, גיל {user['age']}\n"
                    f"📍 {user['city']}\n"
                    f"{gender_text}\n"
                    f"📝 {user['bio']}\n"
                    f"🆔 `{user['user_id']}`"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # List appeals
    elif data == "appeal_list_appeals":
        appeals = get_pending_appeals()
        if not appeals:
            await context.bot.send_message(chat_id=ADMIN_ID, text="✅ אין ערעורים פתוחים!")
            return
        for appeal in appeals:
            keyboard = [[
                InlineKeyboardButton("✅ שחרר חסימה", callback_data=f"unblock_{appeal['user_id']}"),
                InlineKeyboardButton("❌ דחה ערעור", callback_data=f"appeal_reject_{appeal['id']}")
            ]]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"⚠️ *ערעור חדש*\n\n"
                    f"👤 {appeal['name']}, גיל {appeal['age']}\n"
                    f"🆔 `{appeal['user_id']}`\n\n"
                    f"💬 הודעה:\n{appeal['message']}"
                ),
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
                f"📊 *סטטיסטיקות*\n\n"
                f"👥 סה\"כ משתמשים: {stats['total']}\n"
                f"⏳ ממתינים: {stats['pending']}\n"
                f"✅ מאושרים: {stats['approved']}\n"
                f"🚫 חסומים: {stats['blocked']}\n"
                f"💕 התאמות: {stats['matches']}"
            ),
            parse_mode="Markdown"
        )


async def handle_appeal_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages from blocked users (appeals)"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        return

    if user["is_blocked"]:
        message = update.message.text
        add_appeal(user_id, message)
        await update.message.reply_text(
            "📨 הערעור שלך התקבל ויבדק בקרוב.\n"
            "נחזור אליך עם תשובה."
        )
        # Notify admin
        if ADMIN_ID:
            keyboard = [[
                InlineKeyboardButton("✅ שחרר חסימה", callback_data=f"unblock_{user_id}"),
                InlineKeyboardButton("❌ דחה", callback_data=f"block_{user_id}")
            ]]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"⚠️ *ערעור חדש על חסימה*\n\n"
                    f"👤 {user['name']}, גיל {user['age']}\n"
                    f"🆔 `{user_id}`\n\n"
                    f"💬 {message}"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
