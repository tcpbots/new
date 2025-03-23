# bot.py
import asyncio
import logging
import re
import hashlib
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
    MAX_CONCURRENT_DOWNLOADS,
)
from downloader import download_and_upload, progress_data
from utils import check_subscription, log_to_channel
from database import get_user_data, update_user_data, get_bot_stats, get_total_users
from languages import MESSAGES

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# URL validation regex
URL_REGEX = r'https?://[^\s<>"]+|www\.[^\s<>"]+'

# Conversation states for settings
SELECT_LANGUAGE, TOGGLE_COMPRESSION, SELECT_QUALITY = range(3)

# Queue for managing concurrent downloads
download_queue = []
active_downloads = 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Start command to initialize the bot and check subscription.
    """
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    lang = user_data.get("language", "en")

    if not await check_subscription(context, user_id):
        keyboard = [
            [InlineKeyboardButton(f"Join {channel}", url=f"https://t.me/{channel[1:]}")]
            for channel in FORCE_CHANNELS
        ]
        keyboard.append([InlineKeyboardButton("✅ I have joined", callback_data="check_subscription")])
        await update.message.reply_text(
            MESSAGES[lang]["join_channels"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return

    welcome_message = (
        f"**{MESSAGES[lang]['welcome']}**\n"
        f"{MESSAGES[lang]['send_url']}\n\n"
        f"**Features**:\n"
        f"- Quality selection\n"
        f"- Multiple formats\n"
        f"- Audio-only downloads\n"
        f"- And more!"
    )
    keyboard = [
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    await update.message.reply_text(
        welcome_message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback to recheck subscription after user joins channels.
    """
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    lang = user_data.get("language", "en")

    if await check_subscription(context, user_id):
        welcome_message = (
            f"**{MESSAGES[lang]['welcome']}**\n"
            f"{MESSAGES[lang]['send_url']}\n\n"
            f"**Features**:\n"
            f"- Quality selection\n"
            f"- Multiple formats\n"
            f"- Audio-only downloads\n"
            f"- And more!"
        )
        keyboard = [
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("📊 Stats", callback_data="stats")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        await update.callback_query.message.edit_text(
            welcome_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await update.callback_query.answer(MESSAGES[lang]["join_all_channels"])

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle incoming URLs and queue them for download.
    """
    global active_downloads
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message = update.message
    text = message.text
    user_data = get_user_data(user_id)
    lang = user_data.get("language", "en")

    if not await check_subscription(context, user_id):
        keyboard = [
            [InlineKeyboardButton(f"Join {channel}", url=f"https://t.me/{channel[1:]}")]
            for channel in FORCE_CHANNELS
        ]
        keyboard.append([InlineKeyboardButton("✅ I have joined", callback_data="check_subscription")])
        await message.reply_text(
            MESSAGES[lang]["join_channels"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return

    urls = re.findall(URL_REGEX, text)
    if not urls:
        await message.reply_text(MESSAGES[lang]["invalid_url"])
        return

    # Add URLs to the queue
    for url in urls:
        if not any(platform in url.lower() for platform in SUPPORTED_PLATFORMS):
            await message.reply_text(MESSAGES[lang]["unsupported_platform"])
            continue
        download_queue.append((url, user_id, chat_id, message, lang))

    await message.reply_text(f"{MESSAGES[lang]['processing_videos'].format(len(urls))}")

    # Process the queue
    while download_queue and active_downloads < MAX_CONCURRENT_DOWNLOADS:
        url, user_id, chat_id, message, lang = download_queue.pop(0)
        active_downloads += 1
        status_msg = await message.reply_text(MESSAGES[lang]["processing_request"])
        format_id = user_data.get("default_quality", "bestvideo") if not user_data.get("audio_only", False) else "audio_only"

        # Create a task for downloading and uploading
        task = asyncio.create_task(
            download_and_upload(url, format_id, user_id, chat_id, context, status_msg, lang=lang)
        )
        task.add_done_callback(lambda _: globals().update(active_downloads=active_downloads - 1))

async def cancel_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Cancel an ongoing download.
    """
    query = update.callback_query
    user_data = get_user_data(update.effective_user.id)
    lang = user_data.get("language", "en")
    await query.answer()
    short_task_id = query.data.split("_", 1)[1]
    for task_id in list(progress_data.keys()):
        if hashlib.md5(task_id.encode()).hexdigest()[:10] == short_task_id:
            progress_data.pop(task_id, None)
            await query.message.edit_text(MESSAGES[lang]["download_cancelled"])
            break

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show bot statistics.
    """
    user_data = get_user_data(update.effective_user.id)
    lang = user_data.get("language", "en")
    stats = get_bot_stats()
    total_videos = stats["total_videos"]
    total_size = stats["total_size"]
    total_time = stats["total_time"]
    await update.message.reply_text(
        f"**{MESSAGES[lang]['bot_stats']}**\n"
        f"{MESSAGES[lang]['total_videos']}: {total_videos}\n"
        f"{MESSAGES[lang]['total_size']}: {total_size:.2f} MB\n"
        f"{MESSAGES[lang]['total_time']}: {total_time:.2f} s",
        parse_mode='Markdown'
    )

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show total number of users.
    """
    user_data = get_user_data(update.effective_user.id)
    lang = user_data.get("language", "en")
    total_users = get_total_users()
    await update.message.reply_text(f"{MESSAGES[lang]['total_users']}: {total_users}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show help message with available commands.
    """
    user_data = get_user_data(update.effective_user.id)
    lang = user_data.get("language", "en")
    supported_platforms = ", ".join(SUPPORTED_PLATFORMS)
    help_text = (
        f"{MESSAGES[lang]['help_message']}\n\n"
        f"**{MESSAGES[lang]['supported_platforms']}**: {supported_platforms}\n\n"
        f"**{MESSAGES[lang]['commands']}**:\n"
        f"/start - {MESSAGES[lang]['start_command']}\n"
        f"/stats - {MESSAGES[lang]['stats_command']}\n"
        f"/users - {MESSAGES[lang]['users_command']}\n"
        f"/settings - {MESSAGES[lang]['settings_command']}\n"
        f"/help - {MESSAGES[lang]['help_command']}"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start the settings conversation.
    """
    user_data = get_user_data(update.effective_user.id)
    lang = user_data.get("language", "en")
    keyboard = [
        [InlineKeyboardButton("🌐 Language", callback_data="set_language")],
        [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
        [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
        [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
    ]
    await update.message.reply_text(
        MESSAGES[lang]["settings_menu"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return SELECT_LANGUAGE

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle settings menu callbacks.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    user_data get_user_data(user_id)
    lang = user_data.get("language", "en")
    await query.answer()

    if query.data == "close_settings":
        await query.message.delete()
        return ConversationHandler.END

    elif query.data == "set_language":
        keyboard = [
            [InlineKeyboardButton("English", callback_data="lang_en"),
             InlineKeyboardButton("Hindi", callback_data="lang_hi")],
            [InlineKeyboardButton("Back", callback_data="back_to_settings")]
        ]
        await query.message.edit_text(
            MESSAGES[lang]["select_language"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SELECT_LANGUAGE

    elif query.data == "toggle_compression":
        current = user_data.get("compression", False)
        update_user_data(user_id, {"compression": not current})
        keyboard = [
            [InlineKeyboardButton("🌐 Language", callback_data="set_language")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            MESSAGES[lang]["compression_toggled"].format("On" if not current else "Off"),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SELECT_LANGUAGE

    elif query.data == "set_quality":
        keyboard = [
            [InlineKeyboardButton("Best Video", callback_data="quality_bestvideo"),
             InlineKeyboardButton("720p", callback_data="quality_720p")],
            [InlineKeyboardButton("480p", callback_data="quality_480p"),
             InlineKeyboardButton("Audio Only", callback_data="quality_audio_only")],
            [InlineKeyboardButton("Back", callback_data="back_to_settings")]
        ]
        await query.message.edit_text(
            MESSAGES[lang]["select_quality"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SELECT_QUALITY

    elif query.data == "back_to_settings":
        keyboard = [
            [InlineKeyboardButton("🌐 Language", callback_data="set_language")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            MESSAGES[lang]["settings_menu"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SELECT_LANGUAGE

    elif query.data.startswith("lang_"):
        new_lang = query.data.split("_")[1]
        update_user_data(user_id, {"language": new_lang})
        keyboard = [
            [InlineKeyboardButton("🌐 Language", callback_data="set_language")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            MESSAGES[new_lang]["language_updated"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SELECT_LANGUAGE

    elif query.data.startswith("quality_"):
        quality = query.data.split("_")[1]
        if quality == "audio_only":
            update_user_data(user_id, {"audio_only": True, "default_quality": "audio_only"})
        else:
            update_user_data(user_id, {"audio_only": False, "default_quality": quality})
        keyboard = [
            [InlineKeyboardButton("🌐 Language", callback_data="set_language")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            MESSAGES[lang]["quality_updated"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SELECT_LANGUAGE

    return SELECT_LANGUAGE

async def startup_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Send a message to LOGS_CHANNEL_ID when the bot starts on the VPS.
    """
    try:
        startup_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await context.bot.send_message(
            LOGS_CHANNEL_ID,
            f"Bot started on VPS at {startup_time}\n"
            f"Supported platforms: {', '.join(SUPPORTED_PLATFORMS)}\n"
            f"Max concurrent downloads: {MAX_CONCURRENT_DOWNLOADS}"
        )
    except Exception as e:
        logger.error(f"Failed to send startup message: {str(e)}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle generic button callbacks.
    """
    query = update.callback_query
    user_data = get_user_data(update.effective_user.id)
    lang = user_data.get("language", "en")
    await query.answer()

    if query.data == "stats":
        stats = get_bot_stats()
        total_videos = stats["total_videos"]
        total_size = stats["total_size"]
        total_time = stats["total_time"]
        await query.message.edit_text(
            f"**{MESSAGES[lang]['bot_stats']}**\n"
            f"{MESSAGES[lang]['total_videos']}: {total_videos}\n"
            f"{MESSAGES[lang]['total_size']}: {total_size:.2f} MB\n"
            f"{MESSAGES[lang]['total_time']}: {total_time:.2f} s",
            parse_mode='Markdown'
        )

    elif query.data == "help":
        supported_platforms = ", ".join(SUPPORTED_PLATFORMS)
        help_text = (
            f"{MESSAGES[lang]['help_message']}\n\n"
            f"**{MESSAGES[lang]['supported_platforms']}**: {supported_platforms}\n\n"
            f"**{MESSAGES[lang]['commands']}**:\n"
            f"/start - {MESSAGES[lang]['start_command']}\n"
            f"/stats - {MESSAGES[lang]['stats_command']}\n"
            f"/users - {MESSAGES[lang]['users_command']}\n"
            f"/settings - {MESSAGES[lang]['settings_command']}\n"
            f"/help - {MESSAGES[lang]['help_command']}"
        )
        await query.message.edit_text(help_text, parse_mode='Markdown')

    elif query.data == "settings":
        keyboard = [
            [InlineKeyboardButton("🌐 Language", callback_data="set_language")],
            [InlineKeyboardButton("🗜️ Compression", callback_data="toggle_compression")],
            [InlineKeyboardButton("🎥 Default Quality", callback_data="set_quality")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ]
        await query.message.edit_text(
            MESSAGES[lang]["settings_menu"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle errors and log them.
    """
    user_id = update.effective_user.id if update.effective_user else "Unknown"
    error = str(context.error)
    logger.error(f"Update {update} caused error {error}")
    await log_to_channel(context, f"Error for user {user_id}: {error[:1000]}")
    if update.message:
        user_data = get_user_data(user_id)
        lang = user_data.get("language", "en")
        await update.message.reply_text(
            MESSAGES[lang]["error_occurred"].format(error[:1000])
        )

def main() -> None:
    """
    Main function to start the bot.
    """
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler for settings
    settings_conv = ConversationHandler(
        entry_points=[CommandHandler("settings", settings)],
        states={
            SELECT_LANGUAGE: [CallbackQueryHandler(settings_callback)],
            TOGGLE_COMPRESSION: [CallbackQueryHandler(settings_callback)],
            SELECT_QUALITY: [CallbackQueryHandler(settings_callback)],
        },
        fallbacks=[],
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex(URL_REGEX), handle_url))
    application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="check_subscription"))
    application.add_handler(CallbackQueryHandler(cancel_download, pattern="cancel_"))
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^(stats|help|settings)$"))
    application.add_handler(settings_conv)
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("users", users))
    application.add_handler(CommandHandler("help", help_command))

    # Error handler
    application.add_error_handler(error_handler)

    # Send startup message when the bot starts
    application.job_queue.run_once(startup_message, 0)

    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
