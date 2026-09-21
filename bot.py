import os
import logging
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

# =========================
# CONFIGURATION
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN n'est pas configuré.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL n'est pas configuré.")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# =========================
# BASE DE DONNÉES
# =========================

def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id BIGINT PRIMARY KEY,
            prenom TEXT NOT NULL,
            age INTEGER NOT NULL,
            sexe TEXT NOT NULL,
            ville TEXT NOT NULL,
            description TEXT NOT NULL,
            photo_id TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            user_id BIGINT NOT NULL,
            liked_user_id BIGINT NOT NULL,
            PRIMARY KEY (user_id, liked_user_id)
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


def save_profile(user_id, prenom, age, sexe, ville, description, photo_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO profiles
        (user_id, prenom, age, sexe, ville, description, photo_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET
            prenom = EXCLUDED.prenom,
            age = EXCLUDED.age,
            sexe = EXCLUDED.sexe,
            ville = EXCLUDED.ville,
            description = EXCLUDED.description,
            photo_id = EXCLUDED.photo_id
    """, (
        user_id,
        prenom,
        age,
        sexe,
        ville,
        description,
        photo_id,
    ))

    conn.commit()
    cur.close()
    conn.close()


def get_profile(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, prenom, age, sexe, ville, description, photo_id
        FROM profiles
        WHERE user_id = %s
    """, (user_id,))

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row


def get_other_profiles(user_id, seen_ids):
    conn = get_connection()
    cur = conn.cursor()

    if seen_ids:
        cur.execute("""
            SELECT user_id, prenom, age, sexe, ville, description, photo_id
            FROM profiles
            WHERE user_id != %s
            AND NOT (user_id = ANY(%s))
            ORDER BY user_id
            LIMIT 1
        """, (user_id, list(seen_ids)))
    else:
        cur.execute("""
            SELECT user_id, prenom, age, sexe, ville, description, photo_id
            FROM profiles
            WHERE user_id != %s
            ORDER BY user_id
            LIMIT 1
        """, (user_id,))

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row


def add_like(user_id, liked_user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO likes (user_id, liked_user_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (user_id, liked_user_id))

    conn.commit()
    cur.close()
    conn.close()


def is_match(user_id, other_user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 1
        FROM likes
        WHERE user_id = %s
        AND liked_user_id = %s
    """, (other_user_id, user_id))

    result = cur.fetchone()

    cur.close()
    conn.close()

    return result is not None


# =========================
# ÉTAPES DU PROFIL
# =========================

PRENOM, AGE, SEXE, VILLE, DESCRIPTION, PHOTO = range(6)


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❤️ Bienvenue sur MIRO DATING !\n\n"
        "Trouve des personnes, découvre des profils et fais de nouvelles rencontres.\n\n"
        "👤 /profil — créer ton profil\n"
        "🔎 /decouvrir — découvrir des profils"
    )


# =========================
# CRÉATION DU PROFIL
# =========================

async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "👤 Création de ton profil MIRO DATING\n\n"
        "Quel est ton prénom ?"
    )

    return PRENOM


async def recevoir_prenom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["prenom"] = update.message.text.strip()

    await update.message.reply_text(
        "🎂 Quel âge as-tu ?"
    )

    return AGE


async def recevoir_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texte = update.message.text.strip()

    if not texte.isdigit():
        await update.message.reply_text(
            "⚠️ Entre ton âge uniquement en chiffres."
        )
        return AGE

    age = int(texte)

    if age < 18 or age > 100:
        await update.message.reply_text(
            "⚠️ L'âge doit être compris entre 18 et 100 ans."
        )
        return AGE

    context.user_data["age"] = age

    await update.message.reply_text(
        "👤 Quel est ton sexe ?\n\n"
        "Écris : Homme ou Femme"
    )

    return SEXE


async def recevoir_sexe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sexe = update.message.text.strip().lower()

    if sexe not in ["homme", "femme"]:
        await update.message.reply_text(
            "⚠️ Réponds simplement : Homme ou Femme."
        )
        return SEXE

    context.user_data["sexe"] = sexe.capitalize()

    await update.message.reply_text(
        "📍 Dans quelle ville habites-tu ?"
    )

    return VILLE


async def recevoir_ville(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ville"] = update.message.text.strip()

    await update.message.reply_text(
        "💬 Présente-toi en quelques mots."
    )

    return DESCRIPTION


async def recevoir_description(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    context.user_data["description"] = update.message.text.strip()

    await update.message.reply_text(
        "📸 Envoie maintenant une photo pour ton profil."
    )

    return PHOTO


async def recevoir_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text(
            "⚠️ Merci d'envoyer une photo."
        )
        return PHOTO

    photo = update.message.photo[-1]
    user_id = update.effective_user.id

    save_profile(
        user_id,
        context.user_data["prenom"],
        context.user_data["age"],
        context.user_data["sexe"],
        context.user_data["ville"],
        context.user_data["description"],
        photo.file_id,
    )

    await update.message.reply_photo(
        photo=photo.file_id,
        caption=(
            "❤️ TON PROFIL MIRO DATING\n\n"
            f"👤 {context.user_data['prenom']}, "
            f"{context.user_data['age']} ans\n"
            f"⚧ {context.user_data['sexe']}\n"
            f"📍 {context.user_data['ville']}\n\n"
            f"💬 {context.user_data['description']}"
        ),
    )

    await update.message.reply_text(
        "✅ Ton profil est enregistré définitivement.\n\n"
        "Utilise /decouvrir pour découvrir d'autres profils. ❤️"
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================
# DÉCOUVRIR
# =========================

async def decouvrir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not get_profile(user_id):
        await update.message.reply_text(
            "⚠️ Crée d'abord ton profil avec /profil."
        )
        return

    context.user_data.setdefault("vus", set())

    profil = get_other_profiles(
        user_id,
        context.user_data["vus"]
    )

    if not profil:
        await update.message.reply_text(
            "🔎 Tu as vu tous les profils disponibles pour le moment. ❤️"
        )
        return

    await envoyer_profil(update, context, profil)


async def envoyer_profil(update, context, profil):
    candidat_id, prenom, age, sexe, ville, description, photo_id = profil

    context.user_data["profil_actuel"] = candidat_id

    keyboard = [[
        InlineKeyboardButton(
            "❤️ J'aime",
            callback_data=f"like_{candidat_id}"
        ),
        InlineKeyboardButton(
            "❌ Passer",
            callback_data=f"pass_{candidat_id}"
        ),
    ]]

    await update.message.reply_photo(
        photo=photo_id,
        caption=(
            f"👤 {prenom}, {age} ans\n"
            f"⚧ {sexe}\n"
            f"📍 {ville}\n\n"
            f"💬 {description}"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =========================
# LIKE / PASSER
# =========================

async def traiter_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    action, candidat = query.data.split("_")
    candidat_id = int(candidat)

    context.user_data.setdefault("vus", set()).add(candidat_id)

    if action == "like":
        add_like(user_id, candidat_id)

        if is_match(user_id, candidat_id):
            profil = get_profile(candidat_id)

            await query.message.reply_text(
                f"💕 MATCH !\n\n"
                f"Toi et {profil[1]} vous vous êtes aimés ! ❤️"
            )

            try:
                await context.bot.send_message(
                    chat_id=candidat_id,
                    text=(
                        "💕 MATCH !\n\n"
                        "Vous vous êtes aimés mutuellement ! ❤️"
                    ),
                )
            except Exception:
                pass
        else:
            await query.message.reply_text(
                "❤️ J'aime enregistré !"
            )

    else:
        await query.message.reply_text(
            "❌ Profil passé."
        )

    # Afficher le suivant
    profil_suivant = get_other_profiles(
        user_id,
        context.user_data["vus"]
    )

    if profil_suivant:
        await envoyer_profil(
            query,
            context,
            profil_suivant
        )
    else:
        await query.message.reply_text(
            "🔎 Il n'y a plus de profils disponibles pour le moment. ❤️"
        )


# =========================
# ANNULER
# =========================

async def annuler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Création du profil annulée."
    )

    return ConversationHandler.END


# =========================
# MAIN
# =========================

def main():
    init_database()

    application = Application.builder().token(BOT_TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("profil", profil)
        ],
        states={
            PRENOM: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    recevoir_prenom
                )
            ],
            AGE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    recevoir_age
                )
            ],
            SEXE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    recevoir_sexe
                )
            ],
            VILLE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    recevoir_ville
                )
            ],
            DESCRIPTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    recevoir_description
                )
            ],
            PHOTO: [
                MessageHandler(
                    filters.PHOTO,
                    recevoir_photo
                )
            ],
        },
        fallbacks=[
            CommandHandler("annuler", annuler)
        ],
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(conversation)

    application.add_handler(
        CommandHandler("decouvrir", decouvrir)
    )

    application.add_handler(
        CallbackQueryHandler(
            traiter_action,
            pattern=r"^(like_|pass_)"
        )
    )

    print("❤️ MIRO DATING est en ligne !")

    application.run_polling()


if __name__ == "__main__":
    main()
