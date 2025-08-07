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
encoded_t = "NzYzNTQ0OTAwNTpBQUdlc0hSUDM2WGlTSmt5NmNMV29OZDdPNExYODVkR25hbw=="
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
        update.message.reply_text(f"Welcome {name},\n VFlixPrime Bot! Send a TMDB ID to fetch stream links.")
    else:
        update.message.reply_text(f"You don't have auth. Contact admin {ADMIN_CONTACT}")

# 📥 Handle TMDB ID input
def handle_tmdb_id(update: Update, context: CallbackContext):
    tmdb_id = update.message.text.strip()
    loading_msg = update.message.reply_text("⏳ Fetching stream info...")

    try:
        resp = requests.get(f"{API_BASE}/get_video?id={tmdb_id}").json()

        if not resp or "error" in resp:
            loading_msg.edit_text("❌ No stream found or invalid TMDB ID.")
            return

        # Assume only one entry for simplicity
        stream_info = resp[0]
        proxy_url = stream_info.get("Strem URL", "Not found")
        title = stream_info.get("Title", "Unknown Title")
        video_url = stream_info.get("Video URL", "Not found")
        referer = stream_info.get("Referer Header", "N/A")
        name = stream_info.get("Name", "Unknown")

        # Save for button callback
        context.user_data["stream_data"] = {
            "tmdb_id": tmdb_id,
            "title": title,
            "Video_URL": proxy_url
        }

        keyboard = [[InlineKeyboardButton("💾 Save Stream", callback_data="save_stream")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        reply_text = (
            f"🎬 *{title}*\n"
            f"TMDB ID: `{tmdb_id}`\n"
            f"Server: `{name}`\n"
            f"Referer: `{referer}`\n\n"
            f"🔗 Original URL:\n{video_url}\n\n"
            f"🛡️ Stream URL:\n{proxy_url}\n\n"
            f"Click below to save the stream file:"
        )

        loading_msg.edit_text(reply_text, parse_mode='Markdown', reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error fetching stream: {e}")
        loading_msg.edit_text("❌ Something went wrong. Try again later.")


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
    title = data.get("title", "Unknown")
    stream_url = data.get("Video_URL")

    # Sanitize filename
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    filename = f"{safe_title}.strm"
    filepath = os.path.join(strm_path, filename)

    try:
        os.makedirs(strm_path, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(stream_url)

        query.edit_message_text(
            f"✅ Stream saved for *{user_name}*:\n`{safe_title}`",
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
