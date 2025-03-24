# config.py
import os

# Bot token from BotFather (required for python-telegram-bot)
BOT_TOKEN = "7728132142:AAGk_57f_5laLd0CuQbcsrdqavdtsWBd0cU"  # Replace with your bot token

# API ID and API Hash (not required for python-telegram-bot, but included for potential use with pyrogram/telethon)
API_ID = 17760082   # Replace with your API ID (get from my.telegram.org)
API_HASH = "c3fc3cd44886967cf3c0e8585b5cad1c"  # Replace with your API Hash (get from my.telegram.org)

# MongoDB connection details
MONGO_URI = "mongodb+srv://Shivayfile:jub9vtXuBrJYkw8e@databasefiletolink.k2rei.mongodb.net/?retryWrites=true&w=majority
"  # Replace with your MongoDB URI (e.g., mongodb+srv://user:pass@cluster0.mongodb.net/)
MONGO_DB_NAME = "video_downloader_bot"  # Database name for the bot

# List of supported platforms for video downloads
SUPPORTED_PLATFORMS = [
    "youtube", "instagram", "tiktok", "facebook", "twitter", "x.com",
    "vimeo", "dailymotion", "reddit", "pinterest", "soundcloud"
]

# Channels users must join to use the bot (forced subscriptions)
FORCE_CHANNELS = ["@tcp_bots", "@ds_bots"]  # Replace with your channel usernames

# Channel ID for logging bot activities (e.g., errors, downloads, restarts)
LOGS_CHANNEL_ID = -1002667837026  # Replace with your logs channel ID

# List of admin user IDs who can access admin commands
ADMIN_IDS = [1809710185, 6116993643]  # Replace with admin user IDs

# Directory to store downloaded files temporarily
DOWNLOAD_DIR = "downloads"

# Default maximum number of concurrent downloads per user
DEFAULT_TASK_LIMIT = 2

# Optional: Credentials for premium accounts (e.g., YouTube Premium, Facebook)
YOUTUBE_PREMIUM_USERNAME = None  # Replace with username if needed
YOUTUBE_PREMIUM_PASSWORD = None  # Replace with password if needed

# Maximum file size allowed by Telegram (in bytes)
# Telegram's limit for bots is 2000 MB (2 GB)
MAX_FILE_SIZE = 2000 * 1024 * 1024  # 2000 MB in bytes

# Supported upload formats
SUPPORTED_UPLOAD_FORMATS = ["mp4", "mkv", "webm"]

# Create the downloads directory if it doesn't exist
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
