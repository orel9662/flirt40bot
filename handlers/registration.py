from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.db import add_user, get_user
import os

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

GENDER, NAME, AGE, CITY, BIO, PHOTO, ID_CARD = range(7)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    existing = get_user(user_id)

    if existing:
        if existing["is_blocked"]:
            await update.message.reply_text(
                "⛔ *חשבונך חסום | Your account is blocked*\n\n"
                "🇮🇱 אם אתה חושב שזו טעות, שלח הודעה עם הסברך ונבדוק את הערעור.\n"
                "🇬🇧 If you think this is a mistake, send a message explaining your case.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        if existing["status"] == "pending":
            await update.message.reply_text(
                "⏳ *פרופילך ממתין לאישור | Your profile is pending approval*\n\n"
                "נחזור אליך בקרוב! | _We'll get back to you soon!_",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        if existing["status"] == "approved":
            await update.message.reply_text(
                f"💋 *ברוך הבא חזרה ל-Flirt40, {existing['name']}!*\n"
                f"_Welcome back to Flirt40!_\n\n"
                "השתמש ב /browse כדי לראות פרופילים.\n"
                "_Use /browse to see profiles._",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("👩 אישה / Woman", callback_data="gender_female")],
        [InlineKeyboardButton("👨 גבר / Man", callback_data="gender_male")]
    ]
    await update.message.reply_text(
        "💋 *ברוכים הבאים ל-Flirt40!*\n"
        "_Welcome to Flirt40!_\n\n"
        "🇮🇱 הבוט מיועד לנשים מעל גיל 40 שרוצות להכיר גברים צעירים יותר.\n"
        "🇬🇧 This bot is for women over 40 who want to meet younger men.\n\n"
        "⚠️ *כל משתמש חייב לאמת זהות עם צילום תז*\n"
        "_ID verification is required for all users_\n"
        "🔒 התז נשמר בסודיות ונגיש רק למנהל.\n\n"
        "בחר/י מגדר | *Select your gender:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GENDER


async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gender = query.data.replace("gender_", "")
    context.user_data["gender"] = gender

    if gender == "male":
        await query.edit_message_text(
            "👨 נרשמת כגבר | _Registered as a man_\n\n"
            "🇮🇱 הבוט מיועד לגברים מתחת לגיל 40 בלבד.\n"
            "🇬🇧 This bot is for men under 40 only.\n\n"
            "מה שמך המלא? | *What is your full name?*",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            "👩 נרשמת כאישה | _Registered as a woman_\n\n"
            "🇮🇱 הבוט מיועד לנשים מעל גיל 40 בלבד.\n"
            "🇬🇧 This bot is for women over 40 only.\n\n"
            "מה שמך המלא? | *What is your full name?*",
            parse_mode="Markdown"
        )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await update.message.reply_text(
            "❌ שם לא תקין, נסה שוב | _Invalid name, try again:_"
        )
        return NAME
    context.user_data["name"] = name
    await update.message.reply_text(
        f"✅ שלום {name}! | _Hello {name}!_\n\n"
        "מה גילך? | *How old are you?*\n"
        "_(מספר בלבד | numbers only)_",
        parse_mode="Markdown"
    )
    return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "❌ הכנס מספר בלבד | _Numbers only please:_"
        )
        return AGE

    gender = context.user_data.get("gender")

    if gender == "female" and age < 40:
        await update.message.reply_text(
            "❌ *הבוט מיועד לנשים מעל גיל 40 בלבד.*\n"
            "_This bot is for women over 40 only._\n\n"
            "גילך אינו עומד בתנאי ההצטרפות.\n"
            "_Your age does not meet the requirements._",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    if gender == "male" and age >= 40:
        await update.message.reply_text(
            "❌ *הבוט מיועד לגברים מתחת לגיל 40 בלבד.*\n"
            "_This bot is for men under 40 only._\n\n"
            "גילך אינו עומד בתנאי ההצטרפות.\n"
            "_Your age does not meet the requirements._",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    if age < 18:
        await update.message.reply_text(
            "❌ גיל מינימלי הוא 18 | _Minimum age is 18_"
        )
        return ConversationHandler.END

    context.user_data["age"] = age
    await update.message.reply_text(
        "📍 באיזו עיר אתה/את גר/ה? | *What city do you live in?*",
        parse_mode="Markdown"
    )
    return CITY


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    context.user_data["city"] = city
    await update.message.reply_text(
        "📝 *ספר/י קצת על עצמך | Tell us about yourself*\n\n"
        "🇮🇱 תחביבים, מה אתה/את מחפש/ת וכו' - עד 300 תווים\n"
        "🇬🇧 Hobbies, what you're looking for, etc. - up to 300 chars",
        parse_mode="Markdown"
    )
    return BIO


async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bio = update.message.text.strip()
    if len(bio) > 300:
        await update.message.reply_text(
            "❌ קצת ארוך מדי! עד 300 תווים | _Too long! Max 300 characters:_"
        )
        return BIO
    context.user_data["bio"] = bio
    await update.message.reply_text(
        "📸 *שלח/י תמונת פרופיל | Send a profile photo*\n\n"
        "🇮🇱 תמונה ברורה של הפנים\n"
        "🇬🇧 A clear photo of your face",
        parse_mode="Markdown"
    )
    return PHOTO


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    context.user_data["photo_file_id"] = photo.file_id
    await update.message.reply_text(
        "🪪 *שלח/י צילום תעודת זהות | Send your ID card*\n\n"
        "🇮🇱 הצילום משמש לאימות גיל, שם ותמונה בלבד.\n"
        "🔒 *נשמר בסודיות - רק המנהל רואה אותו ואף משתמש אחר לא.*\n\n"
        "🇬🇧 Used only to verify age, name and photo.\n"
        "🔒 _Completely private - only the admin can see it._",
        parse_mode="Markdown"
    )
    return ID_CARD


async def get_id_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text(
            "❌ שלח/י תמונה או קובץ | _Please send a photo or file_"
        )
        return ID_CARD

    context.user_data["id_card_file_id"] = file_id

    data = context.user_data
    add_user(
        user_id=update.effective_user.id,
        username=update.effective_user.username or "",
        gender=data["gender"],
        name=data["name"],
        age=data["age"],
        city=data["city"],
        bio=data["bio"],
        photo_file_id=data["photo_file_id"],
        id_card_file_id=data["id_card_file_id"]
    )

    await update.message.reply_text(
        "✅ *ההרשמה התקבלה! | Registration received!*\n\n"
        "🇮🇱 פרופילך ממתין לאישור המנהל. נחזור אליך תוך 24 שעות. 🙏\n"
        "🇬🇧 Your profile is pending admin approval. We'll get back to you within 24 hours. 🙏",
        parse_mode="Markdown"
    )

    if ADMIN_ID:
        gender_text = "👩 אישה / Woman" if data["gender"] == "female" else "👨 גבר / Man"
        keyboard = [
            [
                InlineKeyboardButton("✅ אשר", callback_data=f"approve_{update.effective_user.id}"),
                InlineKeyboardButton("❌ דחה", callback_data=f"reject_{update.effective_user.id}")
            ],
            [
                InlineKeyboardButton("🚫 חסום", callback_data=f"block_{update.effective_user.id}"),
                InlineKeyboardButton("🪪 צפה בתז", callback_data=f"view_id_{update.effective_user.id}")
            ]
        ]
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=data["photo_file_id"],
            caption=(
                f"📋 *בקשת הרשמה חדשה - Flirt40*\n\n"
                f"👤 שם: {data['name']}\n"
                f"🎂 גיל: {data['age']}\n"
                f"📍 עיר: {data['city']}\n"
                f"{gender_text}\n"
                f"📝 {data['bio']}\n\n"
                f"🆔 Telegram ID: `{update.effective_user.id}`\n"
                f"@{update.effective_user.username or 'אין'}"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return ConversationHandler.END
