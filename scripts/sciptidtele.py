from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8702137869:AAEK7xHpRCgKUJJ4zhQM0CBLp4fF6lqNAtY"  # tu bot token

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Esto muestra tu user ID
    await update.message.reply_text(f"Tu user ID es: {update.message.from_user.id}")
    print("User ID:", update.message.from_user.id)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # Comando /start
    app.add_handler(CommandHandler("start", start))

    print("Bot corriendo, envía /start en Telegram para obtener tu ID...")
    app.run_polling()
