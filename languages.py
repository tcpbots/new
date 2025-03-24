# languages.py
MESSAGES = {
    "en": {
        # General messages
        "welcome": "🎉 **Welcome to the Ultimate Video Downloader Bot!** 🎉\n\n"
                   "📥 **Send a video URL to download it instantly!**\n"
                   "🌐 **Supported Platforms**: {0}\n"
                   "📋 **Features**:\n"
                   "  - Download videos in multiple qualities\n"
                   "  - Extract audio as MP3\n"
                   "  - Custom thumbnails, metadata editing, and more!\n\n"
                   "⚙️ Use the buttons below to explore more!",
        "send_url": "📥 **Send a video URL to download it instantly!**",
        "help_message": "❓ **Send a video URL to download it.**\n\n"
                        "🌐 **Supported platforms**: {0}\n\n"
                        "📋 **Commands**:\n"
                        "  /start - 🚀 Start the bot\n"
                        "  /stats - 📊 Show bot statistics\n"
                        "  /users - 👥 Show total users\n"
                        "  /settings - ⚙️ Open settings menu\n"
                        "  /help - ❓ Show this help message\n"
                        "  /about - ℹ️ About the bot\n"
                        "  /setthumbnail - 🖼️ Set a custom thumbnail\n"
                        "  /delthumbnail - 🖼️ Delete the custom thumbnail\n"
                        "  /info - ℹ️ Show bot info",
        "error_occurred": "❌ **An error occurred:** {0}",
        "about_message": "ℹ️ **About the Bot**\n\n"
                         "This bot allows you to download videos from various platforms with advanced features like quality selection, metadata editing, and more!\n"
                         "Developed by @YourCreator",
        "info_message": "ℹ️ **Bot Info**\n\n"
                        "Task Limit: {0}\n"
                        "Active Downloads: {1}\n"
                        "Supported Platforms: {2}",

        # Subscription-related messages
        "join_channels": "🔒 **Please join the following channels to use this bot:**",
        "join_all_channels": "⚠️ **Please join all required channels first!**",

        # URL handling messages
        "invalid_url": "❌ **Please send a valid URL!**",
        "unsupported_platform": "⚠️ **Unsupported platform. Try a different link.**",
        "processing_videos": "⏳ **Processing {0} video(s)...**",
        "processing_request": "⏳ **Processing your request...**",

        # Download-related messages
        "downloading": "📥 **Downloading...**",
        "uploading": "📤 **Uploading...**",
        "upload_complete": "✅ **Upload complete!**",
        "download_cancelled": "🚫 **Download cancelled.**",
        "too_large": "❌ **File too large ({0:.2f} MB). Telegram's limit is 2000 MB.**",
        "thumbnail_for": "🖼️ **Thumbnail for {0}**",
        "error": "❌ **Error**",

        # Settings-related messages
        "settings_menu": "⚙️ **Settings Menu**",
        "select_language": "🌐 **Select your language:**",
        "compression_toggled": "🗜️ **Compression turned {0}.**",
        "select_quality": "🎥 **Select default quality:**",
        "language_updated": "✅ **Language updated successfully!**",
        "quality_updated": "✅ **Quality updated successfully!**",
        "thumbnail_setting": "🖼️ **Thumbnail Setting**",
        "upload_format": "📤 **Upload Format**",
        "select_format": "📂 **Select upload format:**",
        "format_updated": "✅ **Upload format updated to {0}!**",
        "metadata_info": "📝 **Metadata Info:** {0}",
        "metadata_edit_prompt": "📝 **Current title:** {0}\nReply with a new title to edit, or skip to continue.",
        "metadata_updated": "✅ **Metadata updated successfully!**",
        "file_rename_prompt": "📝 **Current filename:** {0}\nReply with a new filename (without extension), or skip to continue.",
        "file_renamed": "✅ **File renamed to {0}!**",
        "multi_audio": "🎵 **Multi-Audio Download:** {0}",
        "subtitles": "📜 **Subtitles Download:** {0}",
        "thumbnail_set": "✅ **Thumbnail set successfully!**",
        "thumbnail_deleted": "✅ **Thumbnail deleted successfully!**",
        "no_thumbnail": "❌ **No custom thumbnail set!**",
        "send_thumbnail_photo": "🖼️ **Please send a photo to set as your custom thumbnail.**",
        "invalid_thumbnail": "❌ **Please send a photo!**",

        # Statistics and user count messages
        "bot_stats": "📊 **Bot Statistics**\n\n"
                     "🎥 Total videos: {0}\n"
                     "💾 Total size: {1:.2f} MB\n"
                     "⏱️ Total time: {2:.2f} s",
        "total_users": "👥 **Total users:** {0}",

        # Admin messages
        "admin_menu": "🔐 **Admin Panel**",
        "broadcast_prompt": "📢 **Enter the message to broadcast:**",
        "broadcast_success": "✅ **Broadcast sent to {0} users!**",
        "ban_prompt": "🚫 **Enter the user ID to ban:**",
        "user_banned": "✅ **User {0} has been banned!**",
        "unban_prompt": "🔓 **Enter the user ID to unban:**",
        "user_unbanned": "✅ **User {0} has been unbanned!**",
        "task_limit_prompt": "📋 **Enter the new task limit for all users:**",
        "task_limit_updated": "✅ **Task limit updated to {0}!**",
        "restart_success": "🔄 **Bot restarted successfully!**",
        "no_permission": "❌ **You don't have permission to use this command!**",
        "invalid_user_id": "❌ **Please enter a valid user ID!**",
        "invalid_task_limit": "❌ **Task limit must be at least 1!**",
        "invalid_number": "❌ **Please enter a valid number!**",
        "user_banned_message": "🚫 **You are banned from using this bot!**",

        # Guide messages
        "download_guide": "📥 **Download Guide** 📥\n\n"
                          "1️⃣ **Step 1**: Send a URL from platforms like {0}.\n"
                          "2️⃣ **Step 2**: Choose your preferred quality in Settings.\n"
                          "3️⃣ **Step 3**: Wait for the bot to download and upload the video.\n"
                          "4️⃣ **Step 4**: Cancel a download using the 'Cancel' button if needed.\n\n"
                          "💡 **Tip:** Enable compression in settings to reduce file sizes!",

        # Startup message
        "startup_message": "🚀 **Bot started at {0}**\n"
                           "🌐 **Supported platforms:** {1}\n"
                           "📥 **Default task limit:** {2}"
    }
}

def get_message(lang_id, lang="en", *args):
    """
    Retrieve a message by key and format it with the provided arguments.
    """
    message = MESSAGES.get(lang_id, {}).get("en", msg_id)  # Fallback to English if lang not found
    return message.format(*args) if args else message
