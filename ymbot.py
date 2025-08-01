import os
import asyncio
import aiohttp  # Asynchronous HTTP requests
import aiofiles
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import re

SAVE_FOLDER = "/tmp/opt/jellyfin/STRM/Provider/YMCINEMA/"  # Folder path to save .strm files

# 🔥 Replace with your bot token
TELEGRAM_BOT_TOKEN = "8421654704:AAGL2__OCKWDmwe_9UHqY_Uc0WzFy4UQG9M"

# 🔥 Telegram group ID for logs
#TELEGRAM_GROUP_ID = "-1002661622618"  # Replace with your group ID
TELEGRAM_GROUP_ID = "-1002873454819"
# 🔥 Current domains
HUBCLOUD_DOMAIN = "https://hubcloud.one"
GDFLIX_DOMAIN = "https://new6.gdflix.dad"

# 🔥 Supported HubCloud and GDFlix domains
HUBCLOUD_DOMAINS = [
    "https://hubcloud.lol",
    "https://hubcloud.ink",
    "https://hubcloud.dad",
    "https://hubcloud.art",
    "https://hubcloud.cc",
    "https://hubcloud.vip",
    "https://hubcloud.co",
    "https://hubcloud.net",
    "https://hubcloud.xyz",
    "https://hubcloud.one",
    "https://hubcloud.space"
]

GDFLIX_DOMAINS = [
    "https://new1.gdflix.dad",
    "https://new2.gdflix.dad",
    "https://new3.gdflix.dad",
    "https://new4.gdflix.dad",
    "https://new5.gdflix.dad",
    "https://new6.gdflix.dad",
    "https://new7.gdflix.dad",
    "https://new8.gdflix.dad",
    "https://new9.gdflix.dad",
    "https://new10.gdflix.dad",
    "https://new11.gdflix.dad"
]

# Ensure save folder exists
if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)

# ✅ Normalize HubCloud URLs
def normalize_hubcloud_url(url):
    """Convert all supported HubCloud domains to the current domain."""
    for domain in HUBCLOUD_DOMAINS:
        if url.startswith(domain):
            return url.replace(domain, HUBCLOUD_DOMAIN)
    return url  # Return original if no match

# ✅ Normalize GDFlix URLs
def normalize_gdflix_url(url):
    """Convert all supported GDFlix domains to the current domain."""
    for domain in GDFLIX_DOMAINS:
        if url.startswith(domain):
            return url.replace(domain, GDFLIX_DOMAIN)
    return url  # Return original if no match

# ✅ Fetch title from URL
async def fetch_title(url):
    """Asynchronously fetch and clean the webpage title."""
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    title = soup.title.string.strip() if soup.title else "Unknown"
                    return title
        except Exception as e:
            print(f"Failed to extract title: {e}")
            return "Unknown"

# ✅ Create HubCloud .strm file
async def create_hub_strm_file(title, url):
    """Create .strm file for HubCloud."""
    filename = os.path.join(SAVE_FOLDER, f"{title}.strm")
    content = f"https://hubcloud-r2-dev.hdmovielover.workers.dev/download?url={url}"

    async with aiofiles.open(filename, "w") as file:
        await file.write(content)
    
    return filename

# ✅ Create GDFlix .strm file
async def create_gd_strm_file(title, url):
    """Create .strm file for GDFlix."""
    filename = os.path.join(SAVE_FOLDER, f"{title}.strm")
    content = f"https://h2r-gdflix-xdirect.hdmovielover.workers.dev/?url={url}"

    async with aiofiles.open(filename, "w") as file:
        await file.write(content)
    
    return filename

# ✅ Send log to Telegram group
async def send_log_to_group(bot, title, filename):
    """Send the uploaded log message to the Telegram group."""
    message = f"✅ **YM Uploaded Successfully**\n🎥 Title: `{title}`"
    await bot.send_message(chat_id=TELEGRAM_GROUP_ID, text=message, parse_mode="Markdown")

# ✅ /start handler
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message with instructions."""
    message = (
        "👋 **Welcome to the VFlix - YM CINEMA HubCloud Bot!**\n\n"
        "📌 **Usage:**\n"
        "`/hub <HubCloud URL>` → Uploads HubCloud links\n"
        "✅ Examples:\n"
        "`/hub https://hubcloud.ink/drive/xyz123`"
    )
    await update.message.reply_text(message, parse_mode="Markdown")

# ✅ /hub handler
async def hub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /hub command and generate .strm files concurrently."""
    if len(context.args) == 0:
        message = (
        "📌 **Usage:**\n"
        "`/hub <HubCloud URL>` → Uploads HubCloud links\n"
        "✅ Example:\n"
        "`/hub https://hubcloud.ink/drive/xyz123`\n"
        "The bot will upload the file in VFlix Prime Server."
        )
        await update.message.reply_text(message, parse_mode="Markdown")
        #await update.message.reply_text("❌ Please provide a valid HubCloud URL.")
        return

    url = context.args[0]

    # Normalize the URL
    normalized_url = normalize_hubcloud_url(url)

    # Validate Hubcloud domain
    if not normalized_url.startswith(f"{HUBCLOUD_DOMAIN}/drive/"):
        await update.message.reply_text("❌ Invalid HubCloud link.")
        return

    # Fetch title and create .strm file
    title = await fetch_title(normalized_url)

    if title == "Unknown":
        await update.message.reply_text("❌ Failed to fetch the title. Please try again.")
        return

    filename = await create_hub_strm_file(title, normalized_url)
    
    reply = (
        f"✅ **Uploaded Successfully**\n🎥 Title: `{title}`"
    )
    await update.message.reply_text(reply, parse_mode="Markdown")

    # ✅ Send log to Telegram group
    await send_log_to_group(context.bot, title, os.path.basename(filename))
async def gdseries_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /gdseries command for multi-episode extraction."""
    if len(context.args) == 0:
        message = (
            "📌 **Usage:**\n"
            "`/gdseries <GDFlix URL>` → Extracts episode links & creates .strm files\n\n"
            "✅ Example:\n"
            "`/gdseries https://new4.gdflix.dad/pack/xyz123`\n\n"
            "The bot will organize files correctly for Jellyfin/Kodi."
        )
        await update.message.reply_text(message, parse_mode="Markdown")
        return

    url = context.args[0]
    
    # Normalize the URL
    normalized_url = normalize_gdflix_url(url)

    # Fetch the webpage content asynchronously
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        async with session.get(normalized_url, headers=headers, timeout=10) as response:
            if response.status != 200:
                await update.message.reply_text("❌ Failed to fetch the page.")
                return
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")

    # Extract and format series title dynamically
    raw_title = soup.title.text.strip()
    cleaned_title = re.sub(r"^[^|]*\| ", "", raw_title)  # Remove "GDFlix |"
    series_match = re.search(r'([\w\s]+)\.?S\d+', cleaned_title, re.IGNORECASE)
    series_folder = series_match.group(1) + " " + series_match.group(0).split('.')[-1] if series_match else "Unknown_Series"

    # Create folder dynamically
    series_path = os.path.join(SAVE_FOLDER, series_folder)
    os.makedirs(series_path, exist_ok=True)

    # Extract episode links and create .strm files
    episode_links = []
    for a_tag in soup.select("li.list-group-item a"):
        href = a_tag.get("href")
        episode_match = re.search(r'E\d+', a_tag.text)
        if episode_match:
            episode_name = episode_match.group() + ".strm"
            episode_link = f"https://h2r-gdflix-xdirect.hdmovielover.workers.dev/?url={normalize_gdflix_url(url + href)}"
            episode_links.append((episode_name, episode_link))

    # Save episodes to .strm files
    for ep_name, ep_link in episode_links:
        ep_file_path = os.path.join(series_path, ep_name)
        async with aiofiles.open(ep_file_path, "w") as file:
            await file.write(ep_link)

    message = f"✅ **Series Extracted Successfully**\n🎥 **Title:** `{series_folder}`\n📂 Episodes saved in `{series_folder}`"
    await update.message.reply_text(message, parse_mode="Markdown")

    # ✅ Send log to Telegram group
    await send_log_to_group(context.bot, series_folder, series_folder)
    
# ✅ /gd handler with domain and structure validation
async def gd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /gd command with domain and URL structure validation."""
    if len(context.args) == 0:
        message = (
        "📌 **Usage:**\n"
        "`/gd <GDFlix URL>` → Uploads GDFlix links\n\n"
        "✅ Example:\n"
        "`/gd https://new4.gdflix.dad/file/abc456`\n\n"
        "The bot will upload the file in VFlix Prime Server."
        )
        await update.message.reply_text(message, parse_mode="Markdown")
        #await update.message.reply_text("❌ Please provide a valid GDFlix URL.")
        return

    url = context.args[0]

    # Normalize the URL
    normalized_url = normalize_gdflix_url(url)

    # Validate GDFlix domain
    if not normalized_url.startswith(f"{GDFLIX_DOMAIN}/file/"):
        await update.message.reply_text("❌ Invalid GDFlix link Structure.")
        return

    # Fetch the title
    title = await fetch_title(normalized_url)

    if title == "Unknown" or title == "GDFlix | Google Drive Files Sharing Platform":
        await update.message.reply_text("❌ Invalid GDFlix link. Please provide a valid link.")
        return

    # Remove "GDFlix | " from the title
    final_title = title.replace("GDFlix | ", "")

    # Create .strm file
    filename = await create_gd_strm_file(final_title, normalized_url)
    
    reply = (
        f"✅ **Uploaded Successfully**\n🎥 Title: `{final_title}`"
    )
    await update.message.reply_text(reply, parse_mode="Markdown")

    # ✅ Send log to Telegram group
    await send_log_to_group(context.bot, final_title, os.path.basename(filename))

# ✅ Main bot loop
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("hub", hub_command))
    app.add_handler(CommandHandler("gd", gd_command))
    app.add_handler(CommandHandler("gdseries", gdseries_command))

    print("Bot is running with domain and structure validation...")
    app.run_polling()

if __name__ == "__main__":
    main()
