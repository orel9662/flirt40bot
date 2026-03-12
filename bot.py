import logging
import os
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)
from handlers.registration import (
    start, get_gender, get_name, get_age, get_city,
    get_bio, get_photo, get_id_card,
    GENDER, NAME, AGE, CITY, BIO, PHOTO, ID_CARD
)
from handlers.matching import show_next_profile, handle_like_dislike, handle_chat_consent
from handlers.admin import admin_panel, handle_admin_callback, handle_appeal_message
from database.db import init_db

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

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
        allow_reentry=True
    )

    app.add_handler(registration_conv)
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("browse", show_next_profile))
    app.add_handler(CallbackQueryHandler(handle_like_dislike, pattern="^(like|dislike)_"))
    app.add_handler(CallbackQueryHandler(handle_chat_consent, pattern="^chat_(consent|decline)_"))
    app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^(approve|reject|block|unblock|delete_id|view_id|appeal_)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_appeal_message))

    logger.info("💋 Flirt40 Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
