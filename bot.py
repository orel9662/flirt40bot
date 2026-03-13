import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler,
    PreCheckoutQueryHandler, filters
)
from handlers.registration import (
    start, get_gender, get_name, get_age, get_region, get_city,
    get_bio, get_photos, get_id_card,
    GENDER, NAME, AGE, REGION, CITY, BIO, PHOTOS, ID_CARD
)
from handlers.matching import (
    show_next_profile, handle_like_dislike, handle_chat_consent,
    handle_like_message_text, handle_region_filter
)
from handlers.admin import admin_panel, handle_admin_callback, handle_appeal_message, _send_main_menu
from handlers.chat import handle_chat_message, handle_chat_callbacks
from database.db import (
    init_db, get_user, get_likes_status, REGIONS,
    add_report, add_bug_report, delete_user_self, track_premium_interest
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

WAITING_REPORT_REASON = {}
WAITING_REPORT_EVIDENCE = {}
WAITING_BUG = set()


async def handle_menu_callbacks(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data == "menu_browse":
        await show_next_profile(update, context)

    elif data == "menu_premium":
        track_premium_interest(user_id)
        keyboard = [
            [InlineKeyboardButton("💰 רכישה | Purchase", callback_data="menu_premium_buy")],
            [InlineKeyboardButton("🔙 חזרה לתפריט", callback_data="menu_back")]
        ]
        await query.message.reply_text(
            "⭐ *Flirt40 Premium*\n\n"
            "✅ לייקים ללא הגבלה\n"
            "✅ הפרופיל מופיע ראשון\n"
            "✅ שלח הודעה עם כל לייק\n"
            "✅ בחר אזור / טווח קילומטרים\n"
            "✅ ראה מי לייקד אותך\n\n"
            "⏰ תוקף: 30 יום | ~50₪/חודש",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "menu_premium_buy":
        track_premium_interest(user_id)
        back_kb2 = [[InlineKeyboardButton("🔙 חזרה לתפריט", callback_data="menu_back")]]
        await query.message.reply_text(
            "🚧 *הפיצ'ר בפיתוח | Feature in development*\n\n"
            "🇮🇱 אנחנו עובדים על מערכת התשלומים ונשמח לראותך כשהיא תהיה מוכנה!\n"
            "🇬🇧 We're working on the payment system and look forward to seeing you when it's ready!\n\n"
            "💌 נשלח לך הודעה כשהפרמיום יהיה זמין.\n_We'll message you when Premium is available._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(back_kb2)
        )

    elif data == "menu_back":
        await _send_main_menu(context, user_id)
        return

    elif data == "menu_status":
        user = get_user(user_id)
        if not user:
            await query.message.reply_text("❌ לא נמצא חשבון")
            return
        likes = get_likes_status(user_id)
        if likes and likes["type"] == "premium":
            likes_text = "⭐ פרמיום - ללא הגבלה"
        elif likes:
            likes_text = f"❤️ {likes['daily_remaining']} לייקים היום + {likes['bonus_likes']} בונוס"
        else:
            likes_text = "?"
        region_name = REGIONS.get(user["region"], "")
        back_kb = [[InlineKeyboardButton("🔙 חזרה לתפריט", callback_data="menu_back")]]
        await query.message.reply_text(
            f"👤 *{user['name']}*, גיל {user['age']}\n"
            f"📍 {region_name} - {user['city']}\n"
            f"🏷 {'⭐ פרמיום' if user['is_premium'] else 'חינמי'}\n"
            f"🔢 {likes_text}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(back_kb)
        )

    elif data == "menu_report":
        await query.message.reply_text(
            "🚨 *דיווח על משתמש*\n\n"
            "שלח: `/report [ID של המשתמש]`\n\n"
            "את ה-ID תוכל/י לבקש ישירות מהמשתמש.",
            parse_mode="Markdown"
        )

    elif data == "menu_bug":
        WAITING_BUG.add(user_id)
        await query.message.reply_text(
            "🐛 *דיווח תקלה | Report a bug*\n\nתאר/י את הבעיה:",
            parse_mode="Markdown"
        )

    elif data == "menu_delete":
        keyboard = [[
            InlineKeyboardButton("🗑 כן, מחק", callback_data="confirm_delete"),
            InlineKeyboardButton("❌ ביטול", callback_data="cancel_delete")
        ]]
        await query.message.reply_text(
            "⚠️ *האם אתה בטוח? | Are you sure?*\n\n"
            "🇮🇱 הפרופיל יימחק. ניתן להירשם מחדש בעתיד.\n"
            "🇬🇧 Your profile will be deleted. You can register again later.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def handle_delete_confirm(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if query.data == "confirm_delete":
        delete_user_self(user_id)
        await query.edit_message_text(
            "🗑 *החשבון נמחק | Account deleted*\n\n"
            "תודה שהיית חלק מ-Flirt40! 💋\n"
            "כדי להצטרף שוב: /start",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text("✅ ביטול | Cancelled")


async def handle_message(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id

    if update.message.text and user_id in WAITING_REPORT_REASON:
        target_id = WAITING_REPORT_REASON.pop(user_id)
        reason = update.message.text.strip()
        WAITING_REPORT_EVIDENCE[user_id] = {"target_id": target_id, "reason": reason}
        await update.message.reply_text(
            "📎 שלח/י תמונת הוכחה, או /skip אם אין\n_Send evidence photo or /skip_",
            parse_mode="Markdown"
        )
        return

    if user_id in WAITING_REPORT_EVIDENCE:
        data = WAITING_REPORT_EVIDENCE.pop(user_id)
        evidence = update.message.photo[-1].file_id if update.message.photo else None
        add_report(user_id, data["target_id"], data["reason"], evidence)
        await update.message.reply_text(
            "✅ *הדיווח התקבל!*\nההנהלה תבדוק בהקדם. | _Admin will review shortly._",
            parse_mode="Markdown"
        )
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
        await update.message.reply_text(
            "✅ *דיווח התקלה התקבל! תודה!*\n_Bug report received! Thank you!_",
            parse_mode="Markdown"
        )
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
    await handle_chat_message(update, context)


async def pre_checkout(update, context):
    await update.pre_checkout_query.answer(ok=True)


async def report_command(update, context):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user or user["status"] != "approved":
        await update.message.reply_text("❌ עליך להיות מאושר | _Must be approved_")
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
    await update.message.reply_text("📝 מה סיבת הדיווח? תאר/י בקצרה:", parse_mode="Markdown")


async def skip_command(update, context):
    user_id = update.effective_user.id
    if user_id in WAITING_REPORT_EVIDENCE:
        data = WAITING_REPORT_EVIDENCE.pop(user_id)
        add_report(user_id, data["target_id"], data["reason"], None)
        await update.message.reply_text("✅ הדיווח התקבל ללא תמונה.")


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
        "⚠️ *מחיקת חשבון | Delete account*\n\nהפרופיל יימחק. להמשיך?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def menu_command(update, context):
    user = get_user(update.effective_user.id)
    if not user or user["status"] != "approved":
        await update.message.reply_text("❌ עליך להיות מאושר | /start")
        return
    await _send_main_menu(context, update.effective_user.id)


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

    # Menu callbacks
    app.add_handler(CallbackQueryHandler(handle_menu_callbacks, pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(handle_delete_confirm, pattern="^(confirm|cancel)_delete$"))

    # Matching callbacks
    app.add_handler(CallbackQueryHandler(handle_like_dislike, pattern="^(like|dislike|like_msg)_"))
    app.add_handler(CallbackQueryHandler(handle_chat_consent, pattern="^chat_(consent|decline)_"))
    app.add_handler(CallbackQueryHandler(handle_chat_callbacks, pattern="^(end_chat|share_details)_"))
    app.add_handler(CallbackQueryHandler(handle_region_filter, pattern="^filter_region_"))

    # Admin callbacks
    app.add_handler(CallbackQueryHandler(handle_admin_callback,
        pattern="^(approve|reject|block|unblock|suspend|unsuspend|admin_|delete_id|view_id|appeal_|broadcast|gift|revoke|report_|bug_|msg_|noop)"))

    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))

    logger.info("Flirt40 Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
