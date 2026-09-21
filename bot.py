import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❤️ Bienvenue sur MIRO DATING !\n\n"
        "Trouve des personnes, découvre des profils et fais de nouvelles rencontres.\n\n"
        "Utilise /profil pour commencer."
    )


async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👤 Création de ton profil MIRO DATING\n\n"
        "Cette fonctionnalité sera bientôt disponible."
    )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN n'est pas configuré.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profil", profil))

    print("MIRO DATING démarre !")
    app.run_polling()


if __name__ == "__main__":
    main()
