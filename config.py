# config.py
import os

# Telegram Bot API credentials (Replace these with real values)
API_ID = "17760082"  # Get from my.telegram.org
API_HASH = "c3fc3cd44886967cf3c0e8585b5cad1c"  # Get from my.telegram.org
BOT_TOKEN = "7728132142:AAGk_57f_5laLd0CuQbcsrdqavdtsWBd0cU"  # Get from BotFather

# Bot configuration
DOWNLOAD_DIR = "downloads"
MAX_CONCURRENT_DOWNLOADS = 5

# Admin settings (Add your Telegram user IDs)
ADMIN_IDS = {6116993643, 1809710185}  # Multiple admin Telegram user IDs

# Channels (Replace with your channel usernames and IDs)
FORCE_CHANNELS = [
    "@tcp_bots",
    "@ds_bots"
]
LOGS_CHANNEL_ID = -1002667837026  # Numeric ID of logs channel
LOG_CHANNEL = "@tcp_bots_logs"  # Added for log_to_channel function (replace with your actual log channel username)
UPDATES_CHANNEL = "@tcp_bots"

# Supported platforms (Updated to include more URL formats)
SUPPORTED_PLATFORMS = [
    "youtube", "vimeo", "dailymotion", "instagram", "x.com", "twitter.com",
    "facebook.com", "tiktok.com", "youtu.be", "fb.watch"
]

# MongoDB configuration (Optional; currently using in-memory storage in database.py)
MONGO_URI = "mongodb+srv://Shivayfile:jub9vtXuBrJYkw8e@databasefiletolink.k2rei.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "telegram_bot"

# YouTube Premium account (optional; leave blank if not used)
YOUTUBE_PREMIUM_USERNAME = "your_youtube_email@example.com"
YOUTUBE_PREMIUM_PASSWORD = "your_youtube_password"

# Ensure download directory exists
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
