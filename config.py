# config.py
import os

# Telegram Bot API credentials (Replace these with real values)
API_ID = "YOUR_API_ID"  # Get from my.telegram.org
API_HASH = "YOUR_API_HASH"  # Get from my.telegram.org
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Get from BotFather

# Bot configuration
DOWNLOAD_DIR = "downloads"
MAX_CONCURRENT_DOWNLOADS = 5

# Admin settings (Add your Telegram user IDs)
ADMIN_IDS = {123456789, 987654321}  # Multiple admin Telegram user IDs

# Channels (Replace with your channel usernames and IDs)
FORCE_CHANNELS = [
    "@YourChannelUsername1",
    "@YourChannelUsername2"
]
LOGS_CHANNEL_ID = -1001234567890  # Numeric ID of logs channel
UPDATES_CHANNEL = "@YourUpdatesChannel"

# Supported platforms
SUPPORTED_PLATFORMS = [
    "youtube", "vimeo", "dailymotion", "instagram", "x.com", "twitter.com",
    "facebook.com", "tiktok.com"
]

# MongoDB configuration
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "telegram_bot"

# YouTube Premium account (optional; leave blank if not used)
YOUTUBE_PREMIUM_USERNAME = "your_youtube_email@example.com"
YOUTUBE_PREMIUM_PASSWORD = "your_youtube_password"

# Ensure download directory exists
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
