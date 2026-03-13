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
    handle_premium_purchase, handle_successful_payment,
    handle_like_message_text, handle_region_filter
)
from handlers.admin import admin_panel, handle_admin_callback, handle_appeal_message
from handlers.chat import handle_chat_message, handle_chat_callbacks
from database.db import init_db, get_user, get_likes_status, REGIONS, add_report, add_bug_report, delete_user_self

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

# States for report flow
WAITING_REPORT = {}  # user_id -> target_id
WAITING_REPORT_REASON = {}  # user_id -> target_id
WAITING_REPORT_EVIDENCE = {}  # user_id -> {target_id, reason}
WAITING_BUG = set()


async def handle_message(update, context):
    if not update.message:
        return

    user_id = update.effective_user.id

    # Check report flow
    if update.message.text and user_id in WAITING_REPORT_REASON:
        target_id = WAITING_REPORT_REASON.pop(user_id)
        reason = update.message.text.strip()
        WAITING_REPORT_EVIDENCE[user_id] = {"target_id": target_id, "reason": reason}
        await update.message.reply_text(
            "📎 *שלח/י תמונת הוכחה | Send evidence photo*\n\n"
            "_(אופציונלי - שלח/י /skip אם אין | Optional - send /skip if none)_",
            parse_mode="Markdown"
        )
        return

    if user_id in WAITING_REPORT_EVIDENCE:
        data = WAITING_REPORT_EVIDENCE.pop(user_id)
        evidence_file_id = None
        if update.message.photo:
            evidence_file_id = update.message.photo[-1].file_id
        add_report(user_id, data["target_id"], data["reason"], evidence_file_id)
        await update.message.reply_text(
            "✅ *הדיווח התקבל! | Report received!*\n\n"
            "ההנהלה תבדוק את הדיווח בהקדם.\n_Admin will review your report shortly._",
            parse_mode="Markdown"
        )
        # Notify admin
        from os import environ
        admin_id = int(environ.get("ADMIN_ID", "0"))
        if admin_id:
            reporter = get_user(user_id)
            reported = get_user(data["target_id"])
            keyboard = [[
                InlineKeyboardButton("⏸ השעה", callback_data=f"suspend_{data['target_id']}"),
                InlineKeyboardButton("🚫 חסום", callback_data=f"block_{data['target_id']}")
            ], [
                InlineKeyboardButton("💬 שוחח עם מדווח", callback_data=f"msg_to_{user_id}"),
                InlineKeyboardButton("💬 שוחח עם מדוּוח", callback_data=f"msg_to_{data['target_id']}")
            ], [
                InlineKeyboardButton("✅ סגור", callback_data=f"report_close_0")
            ]]
            text = (
                f"🚨 *דיווח חדש*\n\n"
                f"👤 מדווח: {reporter['name'] if reporter else user_id}\n"
                f"👤 מדוּוח: {reported['name'] if reported else data['target_id']}\n"
                f"📝 סיבה: {data['reason']}"
            )
            if evidence_file_id:
                try:
                    await context.bot.send_photo(
                        chat_id=admin_id, photo=evidence_file_id,
                        caption=text, parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return
                except Exception:
                    pass
            await context.bot.send_message(
                chat_id=admin_id, text=text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return

    # Bug report
    if update.message.text and user_id in WAITING_BUG:
        WAITING_BUG.discard(user_id)
        add_bug_report(user_id, update.message.text.strip())
        await update.message.reply_text(
            "✅ *דיווח התקלה התקבל! | Bug report received!*\n\n"
            "תודה! נבדוק ונשפר. | _Thank you! We'll look into it._",
            parse_mode="Markdown"
        )
        return

    if not update.message.text:
        return

    # Chat > like message > admin/appeal
    handled = await handle_chat_message(update, context)
    if handled:
        return
    handled = await handle_like_message_text(update, context)
    if handled:
        return
    await handle_appeal_message(update, context)


async def handle_photo_message(update, context):
    user_id = update.effective_user.id
    # Check if waiting for report evidence
    if user_id in WAITING_REPORT_EVIDENCE:
        await handle_message(update, context)
        return
    # Otherwise try chat forwarding
    await handle_chat_message(update, context)


async def pre_checkout(update, context):
    await update.pre_checkout_query.answer(ok=True)


async def status_command(update, context):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("❌ לא נרשמת | _Not registered_ - /start")
        return
    likes = get_likes_status(user_id)
    if not likes:
        return
    if likes["type"] == "premium":
        likes_text = "⭐ פרמיום - ללא הגבלה"
    else:
        likes_text = f"❤️ {likes['daily_remaining']} לייקים היום + {likes['bonus_likes']} בונוס"
    region_name = REGIONS.get(user["region"], "")
    premium_text = "⭐ פרמיום" if user["is_premium"] else "חינמי"
    await update.message.reply_text(
        f"👤 *{user['name']}*, גיל {user['age']}\n"
        f"📍 {region_name} - {user['city']}\n"
        f"🏷 {premium_text}\n"
        f"🔢 {likes_text}",
        parse_mode="Markdown"
    )


async def report_command(update, context):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user or user["status"] != "approved":
        await update.message.reply_text("❌ עליך להיות מאושר כדי לדווח | _Must be approved to report_")
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "🚨 *דיווח על משתמש | Report a user*\n\n"
            "שלח: `/report [ID של המשתמש]`\n"
            "_Send: /report [user ID]_\n\n"
            "את ה-ID תוכל/י לבקש מהמשתמש או לראות בשיחה.",
            parse_mode="Markdown"
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID לא תקין | _Invalid ID_")
        return

    if target_id == user_id:
        await update.message.reply_text("❌ לא ניתן לדווח על עצמך | _Can't report yourself_")
        return

    WAITING_REPORT_REASON[user_id] = target_id
    await update.message.reply_text(
        "📝 *מה סיבת הדיווח? | What's the reason?*\n\n"
        "תאר/י בקצרה מה קרה | _Briefly describe what happened:_",
        parse_mode="Markdown"
    )


async def skip_evidence(update, context):
    user_id = update.effective_user.id
    if user_id in WAITING_REPORT_EVIDENCE:
        data = WAITING_REPORT_EVIDENCE.pop(user_id)
        add_report(user_id, data["target_id"], data["reason"], None)
        await update.message.reply_text(
            "✅ *הדיווח התקבל! | Report received!*\n\n"
            "ההנהלה תבדוק בהקדם. | _Admin will review shortly._",
            parse_mode="Markdown"
        )


async def bug_command(update, context):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user or user["status"] != "approved":
        await update.message.reply_text("❌ עליך להיות מאושר | _Must be approved_")
        return
    WAITING_BUG.add(user_id)
    await update.message.reply_text(
        "🐛 *דיווח על תקלה | Report a bug*\n\n"
        "תאר/י את התקלה שנתקלת בה | _Describe the issue you encountered:_",
        parse_mode="Markdown"
    )


async def delete_command(update, context):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("❌ לא נמצא חשבון | _No account found_")
        return

    keyboard = [[
        InlineKeyboardButton("🗑 כן, מחק את החשבון שלי", callback_data="confirm_delete"),
        InlineKeyboardButton("❌ לא, ביטול", callback_data="cancel_delete")
    ]]
    await update.message.reply_text(
        "⚠️ *האם אתה בטוח? | Are you sure?*\n\n"
        "🇮🇱 פרופילך יימחק ולא יופיע יותר. ניתן להירשם מחדש בעתיד.\n"
        "🇬🇧 Your profile will be deleted. You can register again in the future.",
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
            "🇮🇱 פרופילך נמחק. אם תרצה/י להצטרף שוב בעתיד, שלח/י /start.\n"
            "🇬🇧 Your profile has been deleted. To rejoin in the future, send /start.\n\n"
            "תודה שהיית חלק מ-Flirt40! 💋\n_Thank you for being part of Flirt40!_",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text("✅ הביטול בוצע | _Cancelled_")


async def filter_command(update, context):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user or not user["is_premium"]:
        await update.message.reply_text(
            "⭐ *פיצ'ר פרמיום | Premium Feature*\n\n"
            "בחירת אזור זמינה לפרמיום בלבד.\n_Region filter is Premium only._\n\n"
            "/premium - שדרג עכשיו",
            parse_mode="Markdown"
        )
        return
    keyboard = [
        [InlineKeyboardButton("🌿 צפון", callback_data="filter_region_north"),
         InlineKeyboardButton("🏙 מרכז", callback_data="filter_region_center"),
         InlineKeyboardButton("🌵 דרום", callback_data="filter_region_south")],
        [InlineKeyboardButton("🇮🇱 כל הארץ", callback_data="filter_region_all")]
    ]
    await update.message.reply_text(
        "📍 *בחר/י אזור לגלישה | Select region:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


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
    app.add_handler(CommandHandler("premium", handle_premium_purchase))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("filter", filter_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("skip", skip_evidence))
    app.add_handler(CommandHandler("bug", bug_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CallbackQueryHandler(handle_delete_confirm, pattern="^(confirm|cancel)_delete$"))
    app.add_handler(CallbackQueryHandler(handle_like_dislike, pattern="^(like|dislike|like_msg)_"))
    app.add_handler(CallbackQueryHandler(handle_chat_consent, pattern="^chat_(consent|decline)_"))
    app.add_handler(CallbackQueryHandler(handle_chat_callbacks, pattern="^(end_chat|share_details)_"))
    app.add_handler(CallbackQueryHandler(handle_premium_purchase, pattern="^buy_premium$"))
    app.add_handler(CallbackQueryHandler(handle_region_filter, pattern="^filter_region_"))
    app.add_handler(CallbackQueryHandler(handle_admin_callback,
                    pattern="^(approve|reject|block|unblock|suspend|unsuspend|delete_id|view_id|appeal_|broadcast|gift|revoke|admin_|report_|bug_|msg_)"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))

    logger.info("Flirt40 Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
