import logging
import os
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler,
    PreCheckoutQueryHandler, filters
)
from handlers.registration import (
    start, get_gender, get_name, get_age, get_city,
    get_bio, get_photo, get_id_card,
    GENDER, NAME, AGE, CITY, BIO, PHOTO, ID_CARD
)
from handlers.matching import (
    show_next_profile, handle_like_dislike, handle_chat_consent,
    handle_premium_purchase, handle_successful_payment,
    handle_like_message_text
)
from handlers.admin import admin_panel, handle_admin_callback, handle_appeal_message
from handlers.chat import handle_chat_message, handle_chat_callbacks
from database.db import init_db

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")


async def handle_message(update, context):
    """Route text messages - priority: chat > like message > admin > appeal."""
    if not update.message or not update.message.text:
        return

    # 1. Protected chat
    handled = await handle_chat_message(update, context)
    if handled:
        return

    # 2. Premium like message
    handled = await handle_like_message_text(update, context)
    if handled:
        return

    # 3. Admin actions + appeal
    await handle_appeal_message(update, context)


async def pre_checkout(update, context):
    await update.pre_checkout_query.answer(ok=True)


async def status_command(update, context):
    from database.db import get_user, get_likes_status
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("❌ לא נרשמת | _Not registered_ - /start")
        return

    likes = get_likes_status(user_id)
    if likes["type"] == "premium":
        likes_text = "⭐ פרמיום - ללא הגבלה"
    else:
        likes_text = f"❤️ {likes['daily_remaining']} לייקים היום + {likes['bonus_likes']} בונוס"

    premium_text = "⭐ פרמיום" if user["is_premium"] else "חינמי"
    await update.message.reply_text(
        f"👤 *{user['name']}*, גיל {user['age']}\n"
        f"📍 {user['city']}\n"
        f"🏷 {premium_text}\n"
        f"🔢 {likes_text}",
        parse_mode="Markdown"
    )


def main():
    init_db()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    registration_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GENDER: [CallbackQueryHandler(get_gender, pattern="^gender_")],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
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
    app.add_handler(CallbackQueryHandler(handle_like_dislike, pattern="^(like|dislike|like_msg)_"))
    app.add_handler(CallbackQueryHandler(handle_chat_consent, pattern="^chat_(consent|decline)_"))
    app.add_handler(CallbackQueryHandler(handle_chat_callbacks, pattern="^(end_chat|share_details)_"))
    app.add_handler(CallbackQueryHandler(handle_premium_purchase, pattern="^buy_premium$"))
    app.add_handler(CallbackQueryHandler(handle_admin_callback,
                    pattern="^(approve|reject|block|unblock|delete_id|view_id|appeal_|broadcast|gift|revoke)"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_chat_message))

    logger.info("Flirt40 Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
