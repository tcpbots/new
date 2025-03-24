# bot.py
import asyncio
import logging
import re
import hashlib
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from config import (
    BOT_TOKEN,
    SUPPORTED_PLATFORMS,
    FORCE_CHANNELS,
    LOGS_CHANNEL_ID,
    ADMIN_IDS,
    DEFAULT_TASK_LIMIT,
)
from downloader import download_and_upload, progress_data
from utils import check_subscription, log_to_channel, is_admin
from database import (
    get_user_data,
    update_user_data,
    get_bot_stats,
    get_total_users,
    ban_user,
    unban_user,
    is_banned,
    set_task_limit,
    get_task_limit,
    set_thumbnail,
    get_thumbnail,
    delete_thumbnail,
)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# URL validation regex
URL_REGEX = r'https?://[^\s<>"]+|www\.[^\s<>"]+'

# Conversation states
SETTINGS, METADATA_EDIT, FILE_RENAME, BROADCAST, BAN, UNBAN, TASK_LIMIT, SET_THUMBNAIL = range(8)

# Queue for managing concurrent downloads
download_queue = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Start command to initialize the bot and check subscription.
    """
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned from using this bot!", parse_mode='Markdown')
        return

    if not await check_subscription(context, user_id):
        keyboard = [
            [InlineKeyboardButton(f"Join {channel}", url=f"https://t.me/{channel[1:]}")]
            for channel in FORCE_CHANNELS
        ]
        keyboard.append([InlineKeyboardButton("✅ I have joined", callback_data="check_subscription")])
        await update.message.reply_text(
            "🔒 **Please join the following channels to use this bot:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return

    welcome_message = (
        "🎉 **Welcome to the Ultimate Video Downloader Bot!** 🎉\n\n"
        "📥 **Send a video URL to download it instantly!**\n"
        "🌐 **Supported Platforms**: " + ", ".join(SUPPORTED_PLATFORMS) + "\n"
        "📋 **Features**:\n"
        "  - Download videos in multiple qualities\n"
        "  - Extract audio as MP3\n"
        "  - Custom thumbnails, metadata editing, and more!\n\n"
        "⚙️ Use the buttons below to explore more!"
    )
    keyboard = [
        [
            InlineKeyboardButton("📥 Download Guide", callback_data="guide"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings")
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data="stats"),
            InlineKeyboardButton("❓ Help", callback_data="help")
        ],
        [
            InlineKeyboardButton("ℹ️ About", callback_data="about"),
            InlineKeyboardButton("🌟 Support Us", url="https://t.me/your_support_channel")
        ]
    ]
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel")])
    await update.message.reply_text(
        welcome_message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show a guide on how to download videos.
    """
    query = update.callback_query
    await query.answer()
    guide_message = (
        "📥 **Download Guide** 📥\n\n"
        "1️⃣ **Step 1**: Send a URL from platforms like " + ", ".join(SUPPORTED_PLATFORMS) + ".\n"
        "2️⃣ **Step 2**: Choose your preferred quality in Settings.\n"
        "3️⃣ **Step 3**: Wait for the bot to download and upload the video.\n"
        "4️⃣ **Step 4**: Cancel a download using the 'Cancel' button if needed.\n\n"
        "💡 **Tip:** Enable compression in settings to reduce file sizes!"
    )
    keyboard = [
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            InlineKeyboardButton("🔙 Back", callback_data="back_to_start")
        ]
    ]
    await query.message.edit_text(
        guide_message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback to recheck subscription after user joins channels.
    """
    user_id = update.effective_user.id
    if await check_subscription(context, user_id):
        welcome_message = (
            "🎉 **Welcome to the Ultimate Video Downloader Bot!** 🎉\n\n"
            "📥 **Send a video URL to download it instantly!**\n"
            "🌐 **Supported Platforms**: " + ", ".join(SUPPORTED_PLATFORMS) + "\n"
            "📋 **Features**:\n"
            "  - Download videos in multiple qualities\n"
            "  - Extract audio as MP3\n"
            "  - Custom thumbnails, metadata editing, and more!\n\n"
            "⚙️ Use the buttons below to explore more!"
        )
        keyboard = [
            [
                InlineKeyboardButton("📥 Download Guide", callback_data="guide"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings")
            ],
            [
                InlineKeyboardButton("📊 Stats", callback_data="stats"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ],
            [
                InlineKeyboardButton("ℹ️ About", callback_data="about"),
                InlineKeyboardButton("🌟 Support Us", url="https://t.me/your_support_channel")
            ]
        ]
        if is_admin(user_id):
            keyboard.append([InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel")])
        await update.callback_query.message.edit_text(
            welcome_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await update.callback_query.answer("⚠️ Please join all required channels first!")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle incoming URLs and queue them for download.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message = update.message
    text = message.text
    user_data = get_user_data(user_id)

    if is_banned(user_id):
        await message.reply_text("🚫 You are banned from using this bot!", parse_mode='Markdown')
        return

    if not await check_subscription(context, user_id):
        keyboard = [
            [InlineKeyboardButton(f"Join {channel}", url=f"https://t.me/{channel[1:]}")]
            for channel in FORCE_CHANNELS
        ]
        keyboard.append([InlineKeyboardButton("✅ I have joined", callback_data="check_subscription")])
        await message.reply_text(
            "🔒 **Please join the following channels to use this bot:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return

    urls = re.findall(URL_REGEX, text)
    if not urls:
        await message.reply_text("❌ **Please send a valid URL!**")
        return

    for url in urls:
        download_queue.append((url, user_id, chat_id, message))

    await message.reply_text(f"⏳ **Processing {len(urls)} video(s)...**")

    # Process the queue
    while download_queue:
        url, user_id, chat_id, message = download_queue[0]
        user_data = get_user_data(user_id)
        if user_data["active_downloads"] >= get_task_limit():
            await asyncio.sleep(1)  # Wait until a slot is free
            continue

        download_queue.pop(0)
        user_data["active_downloads"] += 1
        update_user_data(user_id, {"active_downloads": user_data["active_downloads"]})
        status_msg = await message.reply_text("⏳ **Processing your request...**")
        format_id = user_data.get("default_quality", "best") if not user_data.get("audio_only", False) else "audio_only"

        try:
            await download_and_upload(url, format_id, user_id, chat_id, context, status_msg)
        finally:
            user_data["active_downloads"] -= 1
            update_user_data(user_id, {"active_downloads": user_data["active_downloads"]})

async def handle_metadata_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle metadata editing response.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message = update.message
    text = message.text

    for key in list(context.user_data.keys()):
        if key.startswith("metadata_"):
            data = context.user_data.pop(key)
            file_path = data["file_path"]
            thumbnail = data["thumbnail"]
            subtitles = data["subtitles"]
            url = data["url"]
            format_id = data["format_id"]
            status_msg = data["status_msg"]
            start_time = data["start_time"]
            title = text if text else data["title"]
            info = data["info"]
            info['title'] = title

            if user_data.get("file_rename", False):
                await context.bot.send_message(
                    chat_id,
                    f"📝 **Current filename:** {os.path.basename(file_path)}\nReply with a new filename (without extension), or skip to continue.",
                    parse_mode='Markdown'
                )
                context.user_data[f"rename_{key.split('_')[1]}"] = {
                    "file_path": file_path,
                    "thumbnail": thumbnail,
                    "subtitles": subtitles,
                    "url": url,
                    "format_id": format_id,
                    "status_msg": status_msg,
                    "start_time": start_time,
                    "title": title,
                    "info": info
                }
                return FILE_RENAME

            await process_file(
                file_path, thumbnail, subtitles, url, format_id, user_id, chat_id,
                context, status_msg, start_time, title, info
            )
            break

    return ConversationHandler.END

async def handle_file_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle file rename response.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message = update.message
    text = message.text

    for key in list(context.user_data.keys()):
        if key.startswith("rename_"):
            data = context.user_data.pop(key)
            file_path = data["file_path"]
            thumbnail = data["thumbnail"]
            subtitles = data["subtitles"]
            url = data["url"]
            format_id = data["format_id"]
            status_msg = data["status_msg"]
            start_time = data["start_time"]
            title = data["title"]
            info = data["info"]

            if text:
                new_filename = sanitize_filename(text)
                new_path = os.path.join(DOWNLOAD_DIR, f"{new_filename}.{file_path.split('.')[-1]}")
                os.rename(file_path, new_path)
                file_path = new_path
                await message.reply_text(f"✅ **File renamed to {new_filename}!**", parse_mode='Markdown')

            await process_file(
                file_path, thumbnail, subtitles, url, format_id, user_id, chat_id,
                context, status_msg, start_time, title, info
            )
            break

    return ConversationHandler.END

async def cancel_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Cancel an ongoing download.
    """
    query = update.callback_query
    await query.answer()
    short_task_id = query.data.split("_", 1)[1]
    for task_id in list(progress_data.keys()):
        if hashlib.md5(task_id.encode()).hexdigest()[:10] == short_task_id:
            progress_data.pop(task_id, None)
            await query.message.edit_text("🚫 **Download cancelled.**")
            break

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show bot statistics.
    """
    stats = get_bot_stats()
    total_videos = stats["total_videos"]
    total_size = stats["total_size"]
    total_time = stats["total_time"]
    await update.message.reply_text(
        f"📊 **Bot Statistics**\n\n"
        f"🎥 Total videos: {total_videos}\n"
        f"💾 Total size: {total_size:.2f} MB\n"
        f"⏱️ Total time: {total_time:.2f} s",
        parse_mode='Markdown'
    )

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show total number of users.
    """
    total_users = get_total_users()
    await update.message.reply_text(f"👥 **Total users:** {total_users}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show help message with available commands.
    """
    supported_platforms = ", ".join(SUPPORTED_PLATFORMS)
    help_text = (
        "❓ **Send a video URL to download it.**\n\n"
        f"🌐 **Supported platforms**: {supported_platforms}\n\n"
        "📋 **Commands**:\n"
        "  /start - 🚀 Start the bot\n"
        "  /stats - 📊 Show bot statistics\n"
        "  /users - 👥 Show total users\n"
        "  /settings - ⚙️ Open settings menu\n"
        "  /help - ❓ Show this help message\n"
        "  /about - ℹ️ About the bot\n"
        "  /setthumbnail - 🖼️ Set a custom thumbnail\n"
        "  /delthumbnail - 🖼️ Delete the custom thumbnail\n"
        "  /info - ℹ️ Show bot info"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show about message.
    """
    await update.message.reply_text(
        "ℹ️ **About the Bot**\n\n"
        "This bot allows you to download videos from various platforms with advanced features like quality selection, metadata editing, and more!\n"
        "Developed by @YourCreator",
        parse_mode='Markdown'
    )

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show bot info.
    """
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    task_limit = get_task_limit()
    active_downloads = user_data["active_downloads"]
    supported_platforms = ", ".join(SUPPORTED_PLATFORMS)
    await update.message.reply_text(
        f"ℹ️ **Bot Info**\n\n"
        f"Task Limit: {task_limit}\n"
        f"Active Downloads: {active_downloads}\n"
        f"Supported Platforms: {supported_platforms}",
        parse_mode='Markdown'
    )

async def set_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start the process to set a custom thumbnail.
    """
    await update.message.reply_text(
        "🖼️ **Please send a photo to set as your custom thumbnail.**",
        parse_mode='Markdown'
    )
    return SET_THUMBNAIL

async def handle_set_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle the photo sent for setting a custom thumbnail.
    """
    user_id = update.effective_user.id
    message = update.message
    if not message.photo:
        await message.reply_text("❌ **Please send a photo!**", parse_mode='Markdown')
        return SET_THUMBNAIL

    photo = message.photo[-1]  # Get the highest resolution photo
    file = await photo.get_file()
    thumbnail_path = os.path.join(DOWNLOAD_DIR, f"thumbnail_{user_id}.jpg")
    await file.download_to_drive(thumbnail_path)
    set_thumbnail(user_id, thumbnail_path)
    await message.reply_text("✅ **Thumbnail set successfully!**", parse_mode='Markdown')
    return ConversationHandler.END

async def del_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Delete the custom thumbnail for the user.
    """
    user_id = update.effective_user.id
    if get_thumbnail(user_id):
        delete_thumbnail(user_id)
        await update.message.reply_text("✅ **Thumbnail deleted successfully!**", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ **No custom thumbnail set!**", parse_mode='Markdown')

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start the settings conversation.
    """
    user_data = get_user_data(update.effective_user.id)
    keyboard = [
        [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
        [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
        [InlineKeyboardButton("📤 Upload Format", callback_data="set_format")],
        [InlineKeyboardButton("📝 Metadata Edit", callback_data="toggle_metadata")],
        [InlineKeyboardButton("📂 File Rename", callback_data="toggle_rename")],
        [InlineKeyboardButton("🎵 Multi-Audio", callback_data="toggle_multi_audio")],
        [InlineKeyboardButton("📜 Subtitles", callback_data="toggle_subtitles")],
        [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
    ]
    await update.message.reply_text(
        "⚙️ **Settings Menu**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return SETTINGS

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle settings menu callbacks.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    await query.answer()

    if query.data == "close_settings":
        await query.message.delete()
        return ConversationHandler.END

    elif query.data == "set_quality":
        keyboard = [
            [
                InlineKeyboardButton("Best", callback_data="quality_best"),
                InlineKeyboardButton("1080p", callback_data="quality_1080p"),
                InlineKeyboardButton("720p", callback_data="quality_720p")
            ],
            [
                InlineKeyboardButton("480p", callback_data="quality_480p"),
                InlineKeyboardButton("360p", callback_data="quality_360p"),
                InlineKeyboardButton("240p", callback_data="quality_240p")
            ],
            [
                InlineKeyboardButton("Audio Only", callback_data="quality_audio_only"),
                InlineKeyboardButton("🔙 Back", callback_data="back_to_settings")
            ]
        ]
        await query.message.edit_text(
            "🎥 **Select default quality:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SETTINGS

    elif query.data == "toggle_compression":
        current = user_data.get("compression", False)
        update_user_data(user_id, {"compression": not current})
        keyboard = [
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("📤 Upload Format", callback_data="set_format")],
            [InlineKeyboardButton("📝 Metadata Edit", callback_data="toggle_metadata")],
            [InlineKeyboardButton("📂 File Rename", callback_data="toggle_rename")],
            [InlineKeyboardButton("🎵 Multi-Audio", callback_data="toggle_multi_audio")],
            [InlineKeyboardButton("📜 Subtitles", callback_data="toggle_subtitles")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            f"🗜️ **Compression turned {'On' if not current else 'Off'}.**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SETTINGS

    elif query.data == "set_format":
        keyboard = [
            [
                InlineKeyboardButton("MP4", callback_data="format_mp4"),
                InlineKeyboardButton("MKV", callback_data="format_mkv"),
                InlineKeyboardButton("WEBM", callback_data="format_webm")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_settings")]
        ]
        await query.message.edit_text(
            "📂 **Select upload format:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SETTINGS

    elif query.data == "toggle_metadata":
        current = user_data.get("metadata_edit", False)
        update_user_data(user_id, {"metadata_edit": not current})
        keyboard = [
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("📤 Upload Format", callback_data="set_format")],
            [InlineKeyboardButton("📝 Metadata Edit", callback_data="toggle_metadata")],
            [InlineKeyboardButton("📂 File Rename", callback_data="toggle_rename")],
            [InlineKeyboardButton("🎵 Multi-Audio", callback_data="toggle_multi_audio")],
            [InlineKeyboardButton("📜 Subtitles", callback_data="toggle_subtitles")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            f"📝 **Metadata Edit turned {'On' if not current else 'Off'}.**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SETTINGS

    elif query.data == "toggle_rename":
        current = user_data.get("file_rename", False)
        update_user_data(user_id, {"file_rename": not current})
        keyboard = [
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("📤 Upload Format", callback_data="set_format")],
            [InlineKeyboardButton("📝 Metadata Edit", callback_data="toggle_metadata")],
            [InlineKeyboardButton("📂 File Rename", callback_data="toggle_rename")],
            [InlineKeyboardButton("🎵 Multi-Audio", callback_data="toggle_multi_audio")],
            [InlineKeyboardButton("📜 Subtitles", callback_data="toggle_subtitles")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            f"📂 **File Rename turned {'On' if not current else 'Off'}.**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SETTINGS

    elif query.data == "toggle_multi_audio":
        current = user_data.get("multi_audio", False)
        update_user_data(user_id, {"multi_audio": not current})
        keyboard = [
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("📤 Upload Format", callback_data="set_format")],
            [InlineKeyboardButton("📝 Metadata Edit", callback_data="toggle_metadata")],
            [InlineKeyboardButton("📂 File Rename", callback_data="toggle_rename")],
            [InlineKeyboardButton("🎵 Multi-Audio", callback_data="toggle_multi_audio")],
            [InlineKeyboardButton("📜 Subtitles", callback_data="toggle_subtitles")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            f"🎵 **Multi-Audio Download turned {'On' if not current else 'Off'}.**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SETTINGS

    elif query.data == "toggle_subtitles":
        current = user_data.get("subtitles", False)
        update_user_data(user_id, {"subtitles": not current})
        keyboard = [
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("📤 Upload Format", callback_data="set_format")],
            [InlineKeyboardButton("📝 Metadata Edit", callback_data="toggle_metadata")],
            [InlineKeyboardButton("📂 File Rename", callback_data="toggle_rename")],
            [InlineKeyboardButton("🎵 Multi-Audio", callback_data="toggle_multi_audio")],
            [InlineKeyboardButton("📜 Subtitles", callback_data="toggle_subtitles")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            f"📜 **Subtitles Download turned {'On' if not current else 'Off'}.**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SETTINGS

    elif query.data == "back_to_settings":
        keyboard = [
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("📤 Upload Format", callback_data="set_format")],
            [InlineKeyboardButton("📝 Metadata Edit", callback_data="toggle_metadata")],
            [InlineKeyboardButton("📂 File Rename", callback_data="toggle_rename")],
            [InlineKeyboardButton("🎵 Multi-Audio", callback_data="toggle_multi_audio")],
            [InlineKeyboardButton("📜 Subtitles", callback_data="toggle_subtitles")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            "⚙️ **Settings Menu**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SETTINGS

    elif query.data.startswith("quality_"):
        quality = query.data.split("_")[1]
        if quality == "audio_only":
            update_user_data(user_id, {"audio_only": True, "default_quality": "audio_only"})
        else:
            update_user_data(user_id, {"audio_only": False, "default_quality": quality})
        keyboard = [
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("📤 Upload Format", callback_data="set_format")],
            [InlineKeyboardButton("📝 Metadata Edit", callback_data="toggle_metadata")],
            [InlineKeyboardButton("📂 File Rename", callback_data="toggle_rename")],
            [InlineKeyboardButton("🎵 Multi-Audio", callback_data="toggle_multi_audio")],
            [InlineKeyboardButton("📜 Subtitles", callback_data="toggle_subtitles")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            "✅ **Quality updated successfully!**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SETTINGS

    elif query.data.startswith("format_"):
        format_ = query.data.split("_")[1]
        update_user_data(user_id, {"upload_format": format_})
        keyboard = [
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("📤 Upload Format", callback_data="set_format")],
            [InlineKeyboardButton("📝 Metadata Edit", callback_data="toggle_metadata")],
            [InlineKeyboardButton("📂 File Rename", callback_data="toggle_rename")],
            [InlineKeyboardButton("🎵 Multi-Audio", callback_data="toggle_multi_audio")],
            [InlineKeyboardButton("📜 Subtitles", callback_data="toggle_subtitles")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            f"✅ **Upload format updated to {format_.upper()}!**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SETTINGS

    return SETTINGS

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show the admin panel.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.answer("❌ You don't have permission to use this command!")
        return

    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="ban")],
        [InlineKeyboardButton("🔓 Unban User", callback_data="unban")],
        [InlineKeyboardButton("📋 Set Task Limit", callback_data="set_task_limit")],
        [InlineKeyboardButton("🔄 Restart Bot", callback_data="restart")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
    ]
    await query.message.edit_text(
        "🔐 **Admin Panel**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start the broadcast process.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.answer("❌ You don't have permission to use this command!")
        return ConversationHandler.END

    await query.answer()
    await query.message.edit_text("📢 **Enter the message to broadcast:**", parse_mode='Markdown')
    return BROADCAST

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle the broadcast message and send it to all users.
    """
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You don't have permission to use this command!", parse_mode='Markdown')
        return ConversationHandler.END

    message = update.message.text
    success_count = 0
    for uid in users.keys():
        if is_banned(uid):
            continue
        try:
            await context.bot.send_message(uid, message, parse_mode='Markdown')
            success_count += 1
        except Exception as e:
            await log_to_channel(context, f"Failed to broadcast to user {uid}: {str(e)}")
    await update.message.reply_text(f"✅ **Broadcast sent to {success_count} users!**", parse_mode='Markdown')
    return ConversationHandler.END

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start the ban process.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.answer("❌ You don't have permission to use this command!")
        return ConversationHandler.END

    await query.answer()
    await query.message.edit_text("🚫 **Enter the user ID to ban:**", parse_mode='Markdown')
    return BAN

async def handle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle the user ID to ban.
    """
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You don't have permission to use this command!", parse_mode='Markdown')
        return ConversationHandler.END

    try:
        target_id = int(update.message.text)
        ban_user(target_id)
        await update.message.reply_text(f"✅ **User {target_id} has been banned!**", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ **Please enter a valid user ID!**", parse_mode='Markdown')
    return ConversationHandler.END

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start the unban process.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.answer("❌ You don't have permission to use this command!")
        return ConversationHandler.END

    await query.answer()
    await query.message.edit_text("🔓 **Enter the user ID to unban:**", parse_mode='Markdown')
    return UNBAN

async def handle_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle the user ID to unban.
    """
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You don't have permission to use this command!", parse_mode='Markdown')
        return ConversationHandler.END

    try:
        target_id = int(update.message.text)
        unban_user(target_id)
        await update.message.reply_text(f"✅ **User {target_id} has been unbanned!**", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ **Please enter a valid user ID!**", parse_mode='Markdown')
    return ConversationHandler.END

async def set_task_limit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start the task limit setting process.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.answer("❌ You don't have permission to use this command!")
        return ConversationHandler.END

    await query.answer()
    await query.message.edit_text("📋 **Enter the new task limit for all users:**", parse_mode='Markdown')
    return TASK_LIMIT

async def handle_set_task_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle the new task limit.
    """
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You don't have permission to use this command!", parse_mode='Markdown')
        return ConversationHandler.END

    try:
        limit = int(update.message.text)
        if limit < 1:
            await update.message.reply_text("❌ **Task limit must be at least 1!**", parse_mode='Markdown')
            return TASK_LIMIT
        set_task_limit(limit)
        await update.message.reply_text(f"✅ **Task limit updated to {limit}!**", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ **Please enter a valid number!**", parse_mode='Markdown')
    return ConversationHandler.END

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Restart the bot.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.answer("❌ You don't have permission to use this command!")
        return

    await query.answer()
    await query.message.edit_text("🔄 **Bot restarted successfully!**", parse_mode='Markdown')
    await log_to_channel(context, "🔄 Bot restarted by admin.")
    os._exit(0)  # Restart the bot process

async def startup_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Send a message to LOGS_CHANNEL_ID when the bot starts.
    """
    try:
        startup_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await context.bot.send_message(
            LOGS_CHANNEL_ID,
            f"🚀 Bot started at {startup_time}\n"
            f"🌐 Supported platforms: {', '.join(SUPPORTED_PLATFORMS)}\n"
            f"📥 Default task limit: {DEFAULT_TASK_LIMIT}"
        )
    except Exception as e:
        logger.error(f"Failed to send startup message: {str(e)}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle generic button callbacks.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()

    if query.data == "back_to_start":
        welcome_message = (
            "🎉 **Welcome to the Ultimate Video Downloader Bot!** 🎉\n\n"
            "📥 **Send a video URL to download it instantly!**\n"
            "🌐 **Supported Platforms**: " + ", ".join(SUPPORTED_PLATFORMS) + "\n"
            "📋 **Features**:\n"
            "  - Download videos in multiple qualities\n"
            "  - Extract audio as MP3\n"
            "  - Custom thumbnails, metadata editing, and more!\n\n"
            "⚙️ Use the buttons below to explore more!"
        )
        keyboard = [
            [
                InlineKeyboardButton("📥 Download Guide", callback_data="guide"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings")
            ],
            [
                InlineKeyboardButton("📊 Stats", callback_data="stats"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ],
            [
                InlineKeyboardButton("ℹ️ About", callback_data="about"),
                InlineKeyboardButton("🌟 Support Us", url="https://t.me/your_support_channel")
            ]
        ]
        if is_admin(user_id):
            keyboard.append([InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel")])
        await query.message.edit_text(
            welcome_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    elif query.data == "guide":
        await guide(update, context)

    elif query.data == "stats":
        stats = get_bot_stats()
        total_videos = stats["total_videos"]
        total_size = stats["total_size"]
        total_time = stats["total_time"]
        await query.message.edit_text(
            f"📊 **Bot Statistics**\n\n"
            f"🎥 Total videos: {total_videos}\n"
            f"💾 Total size: {total_size:.2f} MB\n"
            f"⏱️ Total time: {total_time:.2f} s",
            parse_mode='Markdown'
        )

    elif query.data == "help":
        supported_platforms = ", ".join(SUPPORTED_PLATFORMS)
        help_text = (
            "❓ **Send a video URL to download it.**\n\n"
            f"🌐 **Supported platforms**: {supported_platforms}\n\n"
            "📋 **Commands**:\n"
            "  /start - 🚀 Start the bot\n"
            "  /stats - 📊 Show bot statistics\n"
            "  /users - 👥 Show total users\n"
            "  /settings - ⚙️ Open settings menu\n"
            "  /help - ❓ Show this help message\n"
            "  /about - ℹ️ About the bot\n"
            "  /setthumbnail - 🖼️ Set a custom thumbnail\n"
            "  /delthumbnail - 🖼️ Delete the custom thumbnail\n"
            "  /info - ℹ️ Show bot info"
        )
        await query.message.edit_text(help_text, parse_mode='Markdown')

    elif query.data == "about":
        await query.message.edit_text(
            "ℹ️ **About the Bot**\n\n"
            "This bot allows you to download videos from various platforms with advanced features like quality selection, metadata editing, and more!\n"
            "Developed by @YourCreator",
            parse_mode='Markdown'
        )

    elif query.data == "settings":
        keyboard = [
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("📤 Upload Format", callback_data="set_format")],
            [InlineKeyboardButton("📝 Metadata Edit", callback_data="toggle_metadata")],
            [InlineKeyboardButton("📂 File Rename", callback_data="toggle_rename")],
            [InlineKeyboardButton("🎵 Multi-Audio", callback_data="toggle_multi_audio")],
            [InlineKeyboardButton("📜 Subtitles", callback_data="toggle_subtitles")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            "⚙️ **Settings Menu**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    elif query.data == "admin_panel":
        await admin_panel(update, context)

    elif query.data == "broadcast":
        await broadcast(update, context)
        return BROADCAST

    elif query.data == "ban":
        await ban(update, context)
        return BAN

    elif query.data == "unban":
        await unban(update, context)
        return UNBAN

    elif query.data == "set_task_limit":
        await set_task_limit_cmd(update, context)
        return TASK_LIMIT

    elif query.data == "restart":
        await restart(update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle errors and log them.
    """
    user_id = update.effective_user.id if update.effective_user else "Unknown"
    error = str(context.error)
    logger.error(f"Update {update} caused error {error}")
    await log_to_channel(context, f"Error for user {user_id}: {error[:1000]}")
    if update.message:
        await update.message.reply_text(
            f"❌ **An error occurred:** {error[:1000]}",
            parse_mode='Markdown'
        )

def main() -> None:
    """
    Main function to start the bot.
    """
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation handlers
    settings_conv = ConversationHandler(
        entry_points=[CommandHandler("settings", settings)],
        states={
            SETTINGS: [CallbackQueryHandler(settings_callback)],
        },
        fallbacks=[],
        per_message=True
    )

    metadata_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_metadata_edit)],
        states={
            METADATA_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_metadata_edit)],
            FILE_RENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_file_rename)],
        },
        fallbacks=[],
        per_message=True
    )

    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast, pattern="broadcast")],
        states={
            BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)],
        },
        fallbacks=[],
        per_message=True
    )

    ban_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ban, pattern="ban")],
        states={
            BAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ban)],
        },
        fallbacks=[],
        per_message=True
    )

    unban_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(unban, pattern="unban")],
        states={
            UNBAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unban)],
        },
        fallbacks=[],
        per_message=True
    )

    task_limit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_task_limit_cmd, pattern="set_task_limit")],
        states={
            TASK_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_task_limit)],
        },
        fallbacks=[],
        per_message=True
    )

    set_thumbnail_conv = ConversationHandler(
        entry_points=[CommandHandler("setthumbnail", set_thumbnail)],
        states={
            SET_THUMBNAIL: [MessageHandler(filters.PHOTO, handle_set_thumbnail)],
        },
        fallbacks=[],
        per_message=True
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex(URL_REGEX), handle_url))
    application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="check_subscription"))
    application.add_handler(CallbackQueryHandler(cancel_download, pattern="cancel_"))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(settings_conv)
    application.add_handler(metadata_conv)
    application.add_handler(broadcast_conv)
    application.add_handler(ban_conv)
    application.add_handler(unban_conv)
    application.add_handler(task_limit_conv)
    application.add_handler(set_thumbnail_conv)
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("users", users))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("delthumbnail", del_thumbnail))

    # Error handler
    application.add_error_handler(error_handler)

    # Send startup message
    application.job_queue.run_once(startup_message, 0)

    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
