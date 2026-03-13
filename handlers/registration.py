from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.db import add_user, get_user, REGIONS
import os

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

GENDER, NAME, AGE, REGION, CITY, BIO, PHOTOS, ID_CARD = range(8)
MAX_PHOTOS = 5


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    existing = get_user(user_id)

    if existing:
        if existing["is_blocked"]:
            await update.message.reply_text(
                "⛔ *חשבונך חסום | Your account is blocked*\n\n"
                "אם אתה חושב שזו טעות, שלח הודעה עם הסברך.\n"
                "_If you think this is a mistake, send a message explaining._",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        if existing["status"] == "deleted":
            await update.message.reply_text(
                "❌ *חשבונך נמחק | Your account was deleted*\n\n"
                "פנה להנהלה אם יש שאלות.\n_Contact admin if you have questions._",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        if existing["status"] == "pending":
            await update.message.reply_text(
                "⏳ *פרופילך ממתין לאישור | Your profile is pending approval*\n\n"
                "🇮🇱 ההנהלה תבדוק את פרופילך ותחזור אליך בהקדם. תקבל הודעה כשהפרופיל יאושר.\n"
                "🇬🇧 The admin will review your profile shortly. You'll receive a message once approved.\n\n"
                "🙏 תודה על הסבלנות! | _Thank you for your patience!_",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        if existing["status"] == "approved":
            await update.message.reply_text(
                f"💋 *ברוך הבא חזרה, {existing['name']}!*\n"
                "_Welcome back!_\n\n"
                "/browse - גלוש בפרופילים\n"
                "/status - הסטטוס שלך\n"
                "/premium - שדרג לפרמיום",
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
        "🇮🇱 פלטפורמת היכרויות לקשר קליל ולא מחייב בין נשים מעל גיל 40 לגברים מתחת לגיל 40.\n\n"
        "🇬🇧 A casual, no-strings-attached dating platform connecting women over 40 with men under 40.\n\n"
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
    context.user_data["photos"] = []

    await query.edit_message_text(
        "מה שמך? | *What's your name?*\n"
        "_(שם פרטי בלבד | First name only)_",
        parse_mode="Markdown"
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2 or len(name) > 30:
        await update.message.reply_text("❌ שם לא תקין | _Invalid name (2-30 chars):_")
        return NAME
    context.user_data["name"] = name
    await update.message.reply_text(
        f"שלום {name}! 👋\n\n"
        "מה גילך? | *How old are you?*\n"
        "_(מספר בלבד | numbers only)_",
        parse_mode="Markdown"
    )
    return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ מספר בלבד | _Numbers only:_")
        return AGE

    gender = context.user_data.get("gender")
    if gender == "female" and age < 40:
        await update.message.reply_text(
            "❌ *הבוט מיועד לנשים מעל גיל 40 בלבד.*\n_This bot is for women over 40 only._",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    if gender == "male" and age >= 40:
        await update.message.reply_text(
            "❌ *הבוט מיועד לגברים מתחת לגיל 40 בלבד.*\n_This bot is for men under 40 only._",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    if age < 18:
        await update.message.reply_text("❌ גיל מינימלי 18 | _Minimum age 18_")
        return ConversationHandler.END

    context.user_data["age"] = age

    keyboard = [
        [InlineKeyboardButton("🌿 צפון / North", callback_data="region_north")],
        [InlineKeyboardButton("🏙 מרכז / Center", callback_data="region_center")],
        [InlineKeyboardButton("🌵 דרום / South", callback_data="region_south")]
    ]
    await update.message.reply_text(
        "📍 *באיזה אזור אתה/את?*\n_Which region are you in?_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REGION


async def get_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region = query.data.replace("region_", "")
    context.user_data["region"] = region
    region_name = REGIONS.get(region, region)

    await query.edit_message_text(
        f"✅ {region_name}\n\n"
        "באיזו עיר? | *Which city?*",
        parse_mode="Markdown"
    )
    return CITY


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["city"] = update.message.text.strip()
    await update.message.reply_text(
        "📝 *ספר/י על עצמך | Tell us about yourself*\n\n"
        "🇮🇱 מה אתה/את מחפש/ת, תחביבים, על עצמך - עד 300 תווים\n"
        "🇬🇧 What you're looking for, hobbies, about yourself - max 300 chars",
        parse_mode="Markdown"
    )
    return BIO


async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bio = update.message.text.strip()
    if len(bio) > 300:
        await update.message.reply_text("❌ עד 300 תווים | _Max 300 chars:_")
        return BIO
    context.user_data["bio"] = bio
    context.user_data["photos"] = []

    await update.message.reply_text(
        "📸 *שלח/י תמונות פרופיל | Send profile photos*\n\n"
        "🇮🇱 שלח/י עד 5 תמונות, אחת אחת. כשסיימת שלח/י /done\n"
        "🇬🇧 Send up to 5 photos, one by one. When done, send /done\n\n"
        "_(התמונה הראשונה תהיה תמונת הפרופיל הראשית)_",
        parse_mode="Markdown"
    )
    return PHOTOS


async def get_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = context.user_data.get("photos", [])

    if update.message.text and update.message.text.strip() in ["/done", "done"]:
        if len(photos) == 0:
            await update.message.reply_text(
                "❌ שלח/י לפחות תמונה אחת | _Please send at least one photo_"
            )
            return PHOTOS
        await _ask_for_id(update, context)
        return ID_CARD

    if not update.message.photo:
        await update.message.reply_text(
            "❌ שלח/י תמונה או /done לסיום | _Send a photo or /done to finish_"
        )
        return PHOTOS

    if len(photos) >= MAX_PHOTOS:
        await update.message.reply_text(
            f"✅ כבר יש לך {MAX_PHOTOS} תמונות - שלח/י /done להמשך"
        )
        return PHOTOS

    file_id = update.message.photo[-1].file_id
    photos.append(file_id)
    context.user_data["photos"] = photos

    remaining = MAX_PHOTOS - len(photos)
    if remaining > 0:
        await update.message.reply_text(
            f"✅ תמונה {len(photos)} התקבלה!\n"
            f"אפשר לשלוח עוד {remaining} תמונות, או /done לסיום\n"
            f"_Photo {len(photos)} received! {remaining} more allowed, or /done_"
        )
    else:
        await update.message.reply_text(
            f"✅ {MAX_PHOTOS} תמונות - מקסימום!\nשלח/י /done להמשך"
        )
    return PHOTOS


async def _ask_for_id(update, context):
    await update.message.reply_text(
        "🪪 *שלח/י צילום תעודת זהות | Send your ID card*\n\n"
        "🇮🇱 *למה אנחנו צריכים את זה?*\n"
        "לאימות גיל ושם בלבד - כדי להבטיח שהקהילה שלנו אמינה ובטוחה.\n"
        "🔒 התז נגיש אך ורק להנהלה ונמחק לאחר השלמת תהליך האימות.\n\n"
        "🇬🇧 *Why do we need this?*\n"
        "For age and name verification only - to keep our community safe.\n"
        "🔒 Your ID is only accessible to admin and deleted after verification.",
        parse_mode="Markdown"
    )


async def get_id_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text:
        await update.message.reply_text(
            "❌ שלח/י צילום תעודת זהות | _Please send a photo of your ID_"
        )
        return ID_CARD

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("❌ שלח/י תמונה | _Send a photo_")
        return ID_CARD

    data = context.user_data
    bonus = add_user(
        user_id=update.effective_user.id,
        username=update.effective_user.username or "",
        gender=data["gender"],
        name=data["name"],
        age=data["age"],
        region=data["region"],
        city=data["city"],
        bio=data["bio"],
        id_card_file_id=file_id,
        photos=data.get("photos", [])
    )

    bonus_msg = ""
    if bonus > 0:
        bonus_msg = (
            f"\n\n🎁 *אתה בין {20} הנרשמים הראשונים!*\n"
            f"קיבלת {bonus} לייקים מתנה שיחכו לך לאחר האישור! 🎉\n"
            f"_You're among the first 20 users! {bonus} bonus likes await you!_"
        )

    # Send confirmation to user
    await update.message.reply_text(
        "✅ *ההרשמה התקבלה! | Registration received!*\n\n"
        "🇮🇱 פרופילך ממתין לאישור ההנהלה.\n"
        "תקבל הודעה ישירות כאן ברגע שהפרופיל יאושר. 🙏\n\n"
        "🇬🇧 Your profile is pending admin approval.\n"
        "You'll receive a message here as soon as it's approved. 🙏"
        + bonus_msg,
        parse_mode="Markdown"
    )

    # Notify admin with full profile
    if ADMIN_ID:
        photos_list = data.get("photos", [])
        gender_text = "👩 אישה" if data["gender"] == "female" else "👨 גבר"
        region_name = REGIONS.get(data["region"], data["region"])

        keyboard = [[
            InlineKeyboardButton("✅ אשר", callback_data=f"approve_{update.effective_user.id}"),
            InlineKeyboardButton("❌ דחה", callback_data=f"reject_{update.effective_user.id}")
        ], [
            InlineKeyboardButton("🚫 חסום", callback_data=f"block_{update.effective_user.id}"),
            InlineKeyboardButton("🪪 צפה בתז", callback_data=f"view_id_{update.effective_user.id}")
        ]]

        caption = (
            f"📋 *בקשת הרשמה חדשה - Flirt40*\n\n"
            f"👤 שם: {data['name']}\n"
            f"🎂 גיל: {data['age']}\n"
            f"📍 אזור: {region_name} - {data['city']}\n"
            f"{gender_text}\n"
            f"📝 {data['bio']}\n"
            f"🎁 בונוס לייקים: {bonus}\n\n"
            f"🆔 ID: `{update.effective_user.id}`"
        )

        try:
            if photos_list:
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=photos_list[0],
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                for extra_photo in photos_list[1:]:
                    await context.bot.send_photo(chat_id=ADMIN_ID, photo=extra_photo,
                                                 caption=f"📸 תמונה נוספת של {data['name']}")
            else:
                await context.bot.send_message(
                    chat_id=ADMIN_ID, text=caption,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to notify admin: {e}")

    return ConversationHandler.END
