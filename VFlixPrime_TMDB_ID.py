import logging
import requests
import base64
import os
from telegram import Update
from telegram.ext import CallbackContext
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    Filters,
    CallbackContext
)

# 🔐 Decode token
encoded_t = "NzYzNTQ0OTAwNTpBQUVYdFRMVllHdmxILW9pVklROGZRZEtHcEpGX2YxM010OA=="
decoded_t = base64.b64decode(encoded_t.encode()).decode()

# 🌐 API base
API_BASE = 'http://localhost:5019'


# 🛠 Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define your authorized user ID
AUTH_USERS = {
    1098159752: "VFlix Prime",
    7679947132: "H2R",
    748585747: "YMCINEMA",
    325082758: "ISHA"
}
ADMIN_CONTACT = "@vflixprime2"  # Replace with your actual admin contact

# STRM paths mapped to user IDs
STRM_BASE_PATHS = {
    1098159752: "/tmp/opt/jellyfin/STRM/m3u8/GDriveSharer/HubCloudProxy/Movies/",  # Overridden path
    7679947132: "/tmp/opt/jellyfin/STRM/m3u8/GDriveSharer/HubCloudProxy/Movies",
    748585747: "/tmp/opt/jellyfin/STRM/Provider/YMCINEMA/",
    325082758: "/tmp/opt/jellyfin/STRM/Provider/Isha/"
}

def is_authorized(user_id):
    return user_id == AUTH_ID

def handle_request(user_id):
    if user_id in AUTH_USERS:
        name = AUTH_USERS[user_id]
        path = STRM_BASE_PATHS.get(user_id, "/tmp/opt/jellyfin/STRM/m3u8/GDriveSharer/HubCloudProxy/Movies/")
        return f"Welcome {name}, Bot is running...\nAssigned STRM path: {path}"
    else:
        return f"You don't have auth. Contact admin {ADMIN_CONTACT}"


# 🟢 /start command


def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in AUTH_USERS:
        name = AUTH_USERS[user_id]
        update.message.reply_text(f"Welcome {name}, VFlixPrime Bot! Send a TMDB ID to fetch stream links.")
    else:
        update.message.reply_text(f"You don't have auth. Contact admin {ADMIN_CONTACT}")

# 📥 Handle TMDB ID input
def handle_tmdb_id(update: Update, context: CallbackContext):
    tmdb_id = update.message.text.strip()

    # Show loading message
    loading_msg = update.message.reply_text("⏳ Loading details...")

    try:
        resp = requests.get(f"{API_BASE}/fetch_all/{tmdb_id}").json()

        if "error" in resp:
            loading_msg.edit_text("❌ Failed to fetch data. Please check the TMDB ID.")
            return

        title = resp.get("title", "Unknown Title")
        release_year = resp.get("release_year", "N/A")
        imdb_id = resp.get("imdb_id", "N/A")
        hindi_link = resp.get("Hindi_URL", "")
        english_link = resp.get("English_URL", "")

        # Save links in context for button callback
        context.user_data["stream_data"] = {
            "tmdb_id": tmdb_id,
            "title": title,
            "Hindi_URL": hindi_link,
            "English_URL": english_link
        }

        # Buttons
        keyboard = [
            [InlineKeyboardButton("🇮🇳 Hindi", callback_data="create_hindi")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="create_english")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Edit loading message with movie info + buttons
        reply_text = (
            f"🎬 *{title}* ({release_year})\n"
            f"TMDB ID: `{tmdb_id}`\nIMDB ID: `{imdb_id}`\n\n"
            f"🇮🇳 Hindi Link:\n{hindi_link}\n\n"
            f"🇬🇧 English Link:\n{english_link}\n\n"
            f"Choose a stream to save:"
        )
        loading_msg.edit_text(reply_text, parse_mode='Markdown', reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error fetching links: {e}")
        loading_msg.edit_text("❌ Something went wrong. Please try again later.")

# 📁 Create .strm file on button click
def handle_button_click(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id
    user_name = AUTH_USERS.get(user_id)
    strm_path = STRM_BASE_PATHS.get(user_id)

    if not user_name or not strm_path:
        query.edit_message_text(f"❌ You don't have auth. Contact admin {ADMIN_CONTACT}")
        return

    data = context.user_data.get("stream_data", {})
    tmdb_id = data.get("tmdb_id")
    title = data.get("title", "Unknown")
    lang = "Hindi" if query.data == "create_hindi" else "English"
    redirect_base = "https://cstream.vflix.life"
    lang_path = f"/fetch_hindi/{tmdb_id}" if lang == "Hindi" else f"/fetch_english/{tmdb_id}"
    stream_url = f"{redirect_base}{lang_path}"

    if not stream_url or stream_url == "Not found":
        query.edit_message_text(f"❌ {lang} stream not found.")
        return

    # Sanitize filename
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    filename = f"{safe_title}_{tmdb_id}.strm"
    filepath = os.path.join(strm_path, filename)

    try:
        os.makedirs(strm_path, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(stream_url)

        query.edit_message_text(
            f"✅ {lang} stream saved for *{user_name}*:\n`{safe_title}_{tmdb_id}`",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        query.edit_message_text("❌ Failed to save stream file.")


# 🚀 Main function
def main():
    updater = Updater(decoded_t, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_tmdb_id))
    dp.add_handler(CallbackQueryHandler(handle_button_click))

    updater.start_polling()
    logger.info("Bot started...")
    updater.idle()

if __name__ == '__main__':
    main()
