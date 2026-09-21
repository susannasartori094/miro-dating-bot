import os
import logging
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

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN n'est pas configuré.")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# =========================
# ÉTAPES DU PROFIL
# =========================

PRENOM, AGE, SEXE, VILLE, DESCRIPTION, PHOTO = range(6)

# Profils en mémoire
profiles = {}

# Likes :
# likes[user_id] = {user_id_1, user_id_2, ...}
likes = {}


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❤️ Bienvenue sur MIRO DATING !\n\n"
        "Trouve des personnes, découvre des profils et fais de nouvelles rencontres.\n\n"
        "Commandes disponibles :\n"
        "👤 /profil — créer ou modifier ton profil\n"
        "🔎 /decouvrir — découvrir des profils\n"
        "❌ /annuler — annuler une création de profil"
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
        "🎂 Quel âge as-tu ?\n\n"
        "Entre uniquement ton âge en chiffres."
    )

    return AGE


async def recevoir_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texte = update.message.text.strip()

    if not texte.isdigit():
        await update.message.reply_text(
            "⚠️ Entre ton âge uniquement en chiffres.\n\n"
            "Exemple : 26"
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
        "💬 Présente-toi en quelques mots.\n\n"
        "Exemple :\n"
        "« J'aime voyager, découvrir de nouveaux endroits "
        "et faire de belles rencontres. »"
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

    profiles[user_id] = {
        "prenom": context.user_data["prenom"],
        "age": context.user_data["age"],
        "sexe": context.user_data["sexe"],
        "ville": context.user_data["ville"],
        "description": context.user_data["description"],
        "photo_id": photo.file_id,
    }

    if user_id not in likes:
        likes[user_id] = set()

    profil = profiles[user_id]

    await update.message.reply_photo(
        photo=profil["photo_id"],
        caption=(
            "❤️ TON PROFIL MIRO DATING\n\n"
            f"👤 {profil['prenom']}, {profil['age']} ans\n"
            f"⚧ {profil['sexe']}\n"
            f"📍 {profil['ville']}\n\n"
            f"💬 {profil['description']}"
        ),
    )

    await update.message.reply_text(
        "✅ Ton profil MIRO DATING est créé !\n\n"
        "Utilise /decouvrir pour découvrir d'autres profils. ❤️"
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================
# DÉCOUVRIR LES PROFILS
# =========================

async def decouvrir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in profiles:
        await update.message.reply_text(
            "⚠️ Tu dois d'abord créer ton profil avec /profil."
        )
        return

    await montrer_profil(update, context, user_id)


async def montrer_profil(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int
):
    # Profils déjà likés ou passés dans cette session
    vus = context.user_data.setdefault("vus", set())

    candidats = [
        uid
        for uid in profiles
        if uid != user_id and uid not in vus
    ]

    if not candidats:
        message = (
            "🔎 Tu as vu tous les profils disponibles pour le moment.\n\n"
            "Reviens plus tard pour découvrir de nouvelles personnes. ❤️"
        )

        if update.callback_query:
            await update.callback_query.message.reply_text(message)
        else:
            await update.message.reply_text(message)

        return

    candidat_id = candidats[0]
    context.user_data["profil_actuel"] = candidat_id

    profil = profiles[candidat_id]

    keyboard = [
        [
            InlineKeyboardButton(
                "❤️ J'aime",
                callback_data=f"like_{candidat_id}"
            ),
            InlineKeyboardButton(
                "❌ Passer",
                callback_data=f"pass_{candidat_id}"
            ),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    caption = (
        f"👤 {profil['prenom']}, {profil['age']} ans\n"
        f"⚧ {profil['sexe']}\n"
        f"📍 {profil['ville']}\n\n"
        f"💬 {profil['description']}"
    )

    if update.callback_query:
        await update.callback_query.message.reply_photo(
            photo=profil["photo_id"],
            caption=caption,
            reply_markup=reply_markup,
        )
    else:
        await update.message.reply_photo(
            photo=profil["photo_id"],
            caption=caption,
            reply_markup=reply_markup,
        )


# =========================
# LIKE / PASSER
# =========================

async def traiter_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data

    if data.startswith("like_"):
        candidat_id = int(data.replace("like_", ""))

        if user_id not in likes:
            likes[user_id] = set()

        likes[user_id].add(candidat_id)

        context.user_data.setdefault("vus", set()).add(candidat_id)

        # Vérification du match
        if (
            candidat_id in likes
            and user_id in likes.get(candidat_id, set())
        ):
            candidat = profiles[candidat_id]

            await query.message.reply_text(
                f"💕 MATCH !\n\n"
                f"Toi et {candidat['prenom']} vous vous êtes aimés ! ❤️"
            )

            try:
                await context.bot.send_message(
                    chat_id=candidat_id,
                    text=(
                        "💕 MATCH !\n\n"
                        "Quelqu'un que tu as aimé t'a également aimé. ❤️\n\n"
                        "Vous pouvez maintenant commencer à discuter."
                    ),
                )
            except Exception:
                pass

        else:
            await query.message.reply_text(
                "❤️ J'aime enregistré !"
            )

    elif data.startswith("pass_"):
        candidat_id = int(data.replace("pass_", ""))

        context.user_data.setdefault("vus", set()).add(candidat_id)

        await query.message.reply_text(
            "❌ Profil passé."
        )

    await montrer_profil(query, context, user_id)


# =========================
# ANNULER
# =========================

async def annuler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Création du profil annulée.\n\n"
        "Tu peux recommencer avec /profil."
    )

    return ConversationHandler.END


# =========================
# MAIN
# =========================

def main():
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
