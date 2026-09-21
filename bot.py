import os
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN n'est pas configuré.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL n'est pas configuré.")


# =========================
# DATABASE
# =========================

def get_db():
    return psycopg2.connect(DATABASE_URL)


def init_database():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id BIGINT PRIMARY KEY,
            first_name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            city TEXT NOT NULL,
            description TEXT,
            photo_id TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            liker_id BIGINT NOT NULL,
            liked_id BIGINT NOT NULL,
            UNIQUE(liker_id, liked_id)
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


# =========================
# PROFILE
# =========================

FIRST_NAME, AGE, GENDER, CITY, DESCRIPTION, PHOTO = range(6)


async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT first_name, age, gender, city, description, photo_id "
        "FROM profiles WHERE user_id = %s",
        (user_id,)
    )
    profile = cur.fetchone()
    cur.close()
    conn.close()

    if profile:
        first_name, age, gender, city, description, photo_id = profile

        text = (
            f"👤 {first_name}, {age} ans\n"
            f"⚧ {gender}\n"
            f"📍 {city}\n\n"
            f"💬 {description or ''}"
        )

        if photo_id:
            await update.message.reply_photo(
                photo=photo_id,
                caption=text
            )
        else:
            await update.message.reply_text(text)

        return ConversationHandler.END

    await update.message.reply_text("👤 Quel est ton prénom ?")
    return FIRST_NAME


async def get_first_name(update, context):
    context.user_data["first_name"] = update.message.text
    await update.message.reply_text("🎂 Quel âge as-tu ?")
    return AGE


async def get_age(update, context):
    try:
        age = int(update.message.text)
        if age < 18:
            await update.message.reply_text("⚠️ MIRO DATING est réservé aux personnes de 18 ans et plus.")
            return AGE

        context.user_data["age"] = age
        keyboard = [
            [
                InlineKeyboardButton("Homme", callback_data="gender_Homme"),
                InlineKeyboardButton("Femme", callback_data="gender_Femme"),
            ]
        ]

        await update.message.reply_text(
            "⚧ Quel est ton sexe ?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return GENDER

    except ValueError:
        await update.message.reply_text("Entre un âge valide, par exemple 26.")
        return AGE


async def get_gender(update, context):
    query = update.callback_query
    await query.answer()

    context.user_data["gender"] = query.data.replace("gender_", "")

    await query.message.reply_text("📍 Dans quelle ville habites-tu ?")
    return CITY


async def get_city(update, context):
    context.user_data["city"] = update.message.text
    await update.message.reply_text("💬 Présente-toi en quelques mots.")
    return DESCRIPTION


async def get_description(update, context):
    context.user_data["description"] = update.message.text

    await update.message.reply_text(
        "📸 Envoie maintenant une photo de profil."
    )
    return PHOTO


async def get_photo(update, context):
    if not update.message.photo:
        await update.message.reply_text("📸 Envoie une photo, s'il te plaît.")
        return PHOTO

    photo_id = update.message.photo[-1].file_id
    context.user_data["photo_id"] = photo_id

    data = context.user_data
    user_id = update.effective_user.id

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO profiles
        (user_id, first_name, age, gender, city, description, photo_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET
            first_name = EXCLUDED.first_name,
            age = EXCLUDED.age,
            gender = EXCLUDED.gender,
            city = EXCLUDED.city,
            description = EXCLUDED.description,
            photo_id = EXCLUDED.photo_id
    """, (
        user_id,
        data["first_name"],
        data["age"],
        data["gender"],
        data["city"],
        data["description"],
        data["photo_id"],
    ))

    conn.commit()
    cur.close()
    conn.close()

    await update.message.reply_text(
        "❤️ Ton profil MIRO DATING est créé !\n\n"
        "Utilise /decouvrir pour découvrir des personnes."
    )

    context.user_data.clear()
    return ConversationHandler.END


# =========================
# DISCOVERY
# =========================

def get_next_profile(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, first_name, age, gender, city, description, photo_id
        FROM profiles
        WHERE user_id != %s
        AND user_id NOT IN (
            SELECT liked_id
            FROM likes
            WHERE liker_id = %s
        )
        ORDER BY user_id
        LIMIT 1
    """, (user_id, user_id))

    profile = cur.fetchone()

    cur.close()
    conn.close()

    return profile


async def envoyer_profil(message, profile):
    user_id, first_name, age, gender, city, description, photo_id = profile

    text = (
        f"👤 {first_name}, {age} ans\n"
        f"⚧ {gender}\n"
        f"📍 {city}\n\n"
        f"💬 {description or ''}"
    )

    keyboard = [
        [
            InlineKeyboardButton("❤️ J'aime", callback_data=f"like_{user_id}"),
            InlineKeyboardButton("❌ Passer", callback_data=f"pass_{user_id}"),
        ]
    ]

    markup = InlineKeyboardMarkup(keyboard)

    if photo_id:
        await message.reply_photo(
            photo=photo_id,
            caption=text,
            reply_markup=markup
        )
    else:
        await message.reply_text(
            text,
            reply_markup=markup
        )


async def decouvrir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    profile = get_next_profile(user_id)

    if not profile:
        await update.message.reply_text(
            "😔 Il n'y a plus de profils à découvrir pour le moment."
        )
        return

    await envoyer_profil(update.message, profile)


# =========================
# LIKE / PASS
# =========================

async def traiter_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    action, target_id = query.data.split("_")
    target_id = int(target_id)

    conn = get_db()
    cur = conn.cursor()

    if action == "pass":
        cur.execute("""
            INSERT INTO likes (liker_id, liked_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (user_id, target_id))

        conn.commit()

        cur.execute("""
            SELECT user_id, first_name, age, gender, city, description, photo_id
            FROM profiles
            WHERE user_id != %s
            AND user_id NOT IN (
                SELECT liked_id FROM likes WHERE liker_id = %s
            )
            ORDER BY user_id
            LIMIT 1
        """, (user_id, user_id))

        next_profile = cur.fetchone()

        cur.close()
        conn.close()

        if next_profile:
            await envoyer_profil(query.message, next_profile)
        else:
            await query.message.reply_text(
                "😔 Il n'y a plus de profils à découvrir."
            )

        return

    # LIKE
    cur.execute("""
        INSERT INTO likes (liker_id, liked_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (user_id, target_id))

    cur.execute("""
        SELECT 1
        FROM likes
        WHERE liker_id = %s AND liked_id = %s
    """, (target_id, user_id))

    is_match = cur.fetchone() is not None

    if is_match:
        cur.execute(
            "SELECT first_name FROM profiles WHERE user_id = %s",
            (target_id,)
        )
        target_profile = cur.fetchone()

        target_name = target_profile[0] if target_profile else "cette personne"

        conn.commit()
        cur.close()
        conn.close()

        keyboard = [
            [
                InlineKeyboardButton(
                    "💬 Écrire",
                    callback_data=f"message_{target_id}"
                )
            ]
        ]

        await query.message.reply_text(
            f"💕 MATCH !\n\n"
            f"Toi et {target_name} vous vous êtes aimés !\n\n"
            f"Vous pouvez maintenant discuter.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    else:
        conn.commit()

        cur.execute("""
            SELECT user_id, first_name, age, gender, city, description, photo_id
            FROM profiles
            WHERE user_id != %s
            AND user_id NOT IN (
                SELECT liked_id FROM likes WHERE liker_id = %s
            )
            ORDER BY user_id
            LIMIT 1
        """, (user_id, user_id))

        next_profile = cur.fetchone()

        cur.close()
        conn.close()

        await query.message.reply_text("❤️ J'aime !")

        if next_profile:
            await envoyer_profil(query.message, next_profile)
        else:
            await query.message.reply_text(
                "😔 Il n'y a plus de profils à découvrir."
            )


# =========================
# MESSAGING
# =========================

async def commencer_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    target_id = int(query.data.split("_")[1])
    user_id = query.from_user.id

    conn = get_db()
    cur = conn.cursor()

    # Vérifie que les deux personnes se sont bien likées
    cur.execute("""
        SELECT 1
        FROM likes
        WHERE liker_id = %s AND liked_id = %s
    """, (user_id, target_id))

    like1 = cur.fetchone()

    cur.execute("""
        SELECT 1
        FROM likes
        WHERE liker_id = %s AND liked_id = %s
    """, (target_id, user_id))

    like2 = cur.fetchone()

    cur.close()
    conn.close()

    if not like1 or not like2:
        await query.message.reply_text(
            "⚠️ Vous devez avoir un match pour discuter."
        )
        return

    context.user_data["message_target"] = target_id

    await query.message.reply_text(
        "💬 Écris ton message.\n\n"
        "Il sera envoyé à ton match."
    )


async def envoyer_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id = context.user_data.get("message_target")

    if not target_id:
        return

    sender_id = update.effective_user.id

    conn = get_db()
    cur = conn.cursor()

    # Vérifie encore le match
    cur.execute("""
        SELECT 1
        FROM likes
        WHERE liker_id = %s AND liked_id = %s
    """, (sender_id, target_id))
    like1 = cur.fetchone()

    cur.execute("""
        SELECT 1
        FROM likes
        WHERE liker_id = %s AND liked_id = %s
    """, (target_id, sender_id))
    like2 = cur.fetchone()

    cur.close()
    conn.close()

    if not like1 or not like2:
        context.user_data.pop("message_target", None)
        await update.message.reply_text(
            "⚠️ Ce match n'est plus disponible."
        )
        return

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"💌 Message de {update.effective_user.first_name} :\n\n"
                f"{update.message.text}"
            )
        )

        await update.message.reply_text("✅ Message envoyé.")

    except Exception:
        await update.message.reply_text(
            "⚠️ Impossible d'envoyer le message pour le moment."
        )

    context.user_data.pop("message_target", None)


# =========================
# CANCEL
# =========================

async def annuler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Action annulée.")
    return ConversationHandler.END


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❤️ Bienvenue sur MIRO DATING !\n\n"
        "👤 /profil — créer ou voir ton profil\n"
        "🔎 /decouvrir — découvrir des profils"
    )


# =========================
# MAIN
# =========================

def main():
    init_database()

    app = Application.builder().token(BOT_TOKEN).build()

    profile_conversation = ConversationHandler(
        entry_points=[CommandHandler("profil", profil)],
        states={
            FIRST_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_first_name)
            ],
            AGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)
            ],
            GENDER: [
                CallbackQueryHandler(get_gender, pattern=r"^gender_")
            ],
            CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)
            ],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)
            ],
            PHOTO: [
                MessageHandler(filters.PHOTO, get_photo)
            ],
        },
        fallbacks=[CommandHandler("annuler", annuler)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(profile_conversation)
    app.add_handler(CommandHandler("decouvrir", decouvrir))

    app.add_handler(
        CallbackQueryHandler(
            traiter_action,
            pattern=r"^(like|pass)_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            commencer_message,
            pattern=r"^message_"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            envoyer_message
        )
    )

    print("MIRO DATING démarré.")
    app.run_polling()


if __name__ == "__main__":
    main()
