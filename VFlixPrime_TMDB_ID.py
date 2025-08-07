import logging
import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# 🔐 Replace with your 
import base64


encoded_t = "NzYzNTQ0OTAwNTpBQUVYdFRMVllHdmxILW9pVklROGZRZEtHcEpGX2YxM010OA=="


# Decode the token
decoded_t = base64.b64decode(encoded_t.encode()).decode()


# 🌐 Localhost API base
API_BASE = 'http://localhost:5019'

# 🛠 Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🟢 /start command
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome! Please send the TMDB ID to fetch Hindi and English stream links.")

# 📥 Handle TMDB ID input
def handle_tmdb_id(update: Update, context: CallbackContext):
    tmdb_id = update.message.text.strip()
    api_url = f"{API_BASE}/fetch_all/{tmdb_id}"

    try:
        resp = requests.get(api_url).json()

        if "error" in resp:
            update.message.reply_text("❌ Failed to fetch data. Please check the TMDB ID.")
            return

        title = resp.get("title", "Unknown Title")
        release_year = resp.get("release_year", "N/A")
        imdb_id = resp.get("imdb_id", "N/A")
        hindi_link = resp.get("Hindi_URL", "Not found")
        english_link = resp.get("English_URL", "Not found")

        reply = (
            f"🎬 *{title}* ({release_year})\n"
            f"TMDB ID: `{tmdb_id}`\nIMDB ID: `{imdb_id}`\n\n"
            f"🇮🇳 Hindi Link:\n{hindi_link}\n\n"
            f"🇬🇧 English Link:\n{english_link}"
        )
        update.message.reply_text(reply, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error fetching links: {e}")
        update.message.reply_text("❌ Something went wrong. Please try again later.")

# 🚀 Main function
def main():
    updater = Updater(decoded_t, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_tmdb_id))

    updater.start_polling()
    logger.info("Bot started...")
    updater.idle()

if __name__ == '__main__':
    main()
