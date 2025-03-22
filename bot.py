# bot.py
import asyncio
import time
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import BOT_TOKEN, ADMIN_IDS, FORCE_CHANNELS, UPDATES_CHANNEL, SUPPORTED_PLATFORMS, MAX_CONCURRENT_DOWNLOADS
from database import get_user_data, update_user_data, get_total_users, get_user_activity, get_bot_stats, get_all_user_ids  # Import database functions
from downloader import download_and_upload, process_file, EXAMPLE_LINKS
from utils import check_subscription, log_to_channel
from languages import MESSAGES
from yt_dlp import YoutubeDL

QUALITY_OPTIONS = ["144p", "360p", "720p", "1080p", "audio_only"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    lang = get_user_data(user_id).get("language", "en")
    if not await check_subscription(context, user_id):
        keyboard = [
            [InlineKeyboardButton("Join Channels", url=f"https://t.me/{channel[1:]}") for channel in FORCE_CHANNELS[:2]],
            [InlineKeyboardButton("Check Subscription", callback_data="check_sub")]
        ]
        if len(FORCE_CHANNELS) > 2:
            keyboard.insert(1, [InlineKeyboardButton("Join Channels", url=f"https://t.me/{channel[1:]}") for channel in FORCE_CHANNELS[2:4]])
        await update.message.reply_text(
            MESSAGES[lang]["subscribe"].format(", ".join(FORCE_CHANNELS)),
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )
        await log_to_channel(context, f"User {user_id} attempted /start but isn't subscribed.")
        return
    
    keyboard = [
        [InlineKeyboardButton("Help", callback_data="show_help"), InlineKeyboardButton("Updates", url=f"https://t.me/{UPDATES_CHANNEL[1:]}")],
        [InlineKeyboardButton("About", callback_data="show_about"), InlineKeyboardButton("Settings", callback_data="show_settings")],
        [InlineKeyboardButton("Platforms", callback_data="show_platforms")]
    ]
    await update.message.reply_text(MESSAGES[lang]["welcome"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    await log_to_channel(context, f"User {user_id} started the bot successfully.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    lang = get_user_data(user_id).get("language", "en")
    await update.message.reply_text(MESSAGES[lang]["help"], parse_mode='Markdown')

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    lang = get_user_data(user_id).get("language", "en")
    await update.message.reply_text(MESSAGES[lang]["about"], parse_mode='Markdown')

async def platforms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    lang = get_user_data(user_id).get("language", "en")
    await update.message.reply_text(MESSAGES[lang]["platforms"], parse_mode='Markdown')

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    lang = get_user_data(user_id).get("language", "en")
    if not await check_subscription(context, user_id):
        await update.message.reply_text(MESSAGES[lang]["subscribe"].format(", ".join(FORCE_CHANNELS)), parse_mode='Markdown')
        return

    user_data = get_user_data(user_id)
    current_quality = user_data.get("default_quality", "Not set")
    current_audio = "Yes" if user_data.get("audio_only", False) else "No"
    current_format = user_data.get("upload_format", "MP4")
    current_metadata = "Yes" if user_data.get("edit_metadata", False) else "No"
    current_lang = "English" if lang == "en" else "Spanish"

    keyboard = [
        [InlineKeyboardButton(f"Quality: **{current_quality}**", callback_data="set_quality"), InlineKeyboardButton(f"Audio Only: **{current_audio}**", callback_data="toggle_audio")],
        [InlineKeyboardButton(f"Format: **{current_format}**", callback_data="set_format"), InlineKeyboardButton(f"Metadata: **{current_metadata}**", callback_data="toggle_metadata")],
        [InlineKeyboardButton(f"Language: **{current_lang}**", callback_data="set_language")]
    ]
    await update.message.reply_text("**Settings**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    lang = get_user_data(user_id).get("language", "en")
    if not await check_subscription(context, user_id):
        keyboard = [
            [InlineKeyboardButton("Join Channels", url=f"https://t.me/{channel[1:]}") for channel in FORCE_CHANNELS[:2]],
            [InlineKeyboardButton("Check Subscription", callback_data="check_sub")]
        ]
        if len(FORCE_CHANNELS) > 2:
            keyboard.insert(1, [InlineKeyboardButton("Join Channels", url=f"https://t.me/{channel[1:]}") for channel in FORCE_CHANNELS[2:4]])
        await update.message.reply_text(
            MESSAGES[lang]["subscribe"].format(", ".join(FORCE_CHANNELS)),
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )
        return

    if context.user_data.get("metadata"):
        task_id = context.user_data["metadata"]
        new_title = update.message.text.strip()
        if new_title != "/skip":
            info = {"title": new_title}
        else:
            info = {"title": context.user_data[task_id]["title"]}
        await process_file(
            context.user_data[task_id]["file_path"], context.user_data[task_id]["thumbnail"],
            context.user_data[task_id]["subtitles"], context.user_data[task_id]["url"],
            context.user_data[task_id]["format_id"], user_id, chat_id, context,
            context.user_data[task_id]["status_msg"], context.user_data[task_id]["prefix"],
            context.user_data[task_id]["start_time"], info
        )
        del context.user_data[task_id]
        del context.user_data["metadata"]
        return

    text = update.message.text.strip()
    urls = re.findall(r'(https?://(?:www\.)?[^\s]+\.[^\s/]+(?:/[^\s]*)?)', text)
    valid_urls = [url for url in urls if any(platform in url.lower() for platform in SUPPORTED_PLATFORMS)]
    if not valid_urls:
        await update.message.reply_text(MESSAGES[lang]["invalid_url"], parse_mode='Markdown')
        await update.message.reply_text(f"**Supported platforms**: {', '.join(SUPPORTED_PLATFORMS)}\n**Example**: {EXAMPLE_LINKS['youtube']}", parse_mode='Markdown')
        return

    await update.message.reply_text(f"**Processing {len(valid_urls)} video(s)...**", parse_mode='Markdown')
    await log_to_channel(context, f"User {user_id} submitted {len(valid_urls)} URL(s): {valid_urls}")

    tasks = []
    active_downloads = context.bot_data.get("active_downloads", {})
    for url in valid_urls:
        if len(active_downloads) >= MAX_CONCURRENT_DOWNLOADS:
            await update.message.reply_text("**Max concurrent downloads reached. Please wait.**", parse_mode='Markdown')
            break
        task = asyncio.create_task(process_single_url(user_id, chat_id, url, context))
        tasks.append(task)
        active_downloads[task] = url
    context.bot_data["active_downloads"] = active_downloads

    await asyncio.gather(*tasks, return_exceptions=True)
    for task in tasks:
        active_downloads.pop(task, None)

async def process_single_url(user_id, chat_id, url, context):
    async with asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS):
        user_data = get_user_data(user_id)
        default_quality = user_data.get("default_quality")
        audio_only = user_data.get("audio_only", False)
        lang = user_data.get("language", "en")

        status_msg = await context.bot.send_message(chat_id, "**Processing your request...**", parse_mode='Markdown')

        try:
            with YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                is_playlist = 'entries' in info

            if is_playlist:
                entries = info['entries']
                for i, entry in enumerate(entries, 1):
                    if len(context.bot_data.get("active_downloads", {})) >= MAX_CONCURRENT_DOWNLOADS:
                        await status_msg.edit_text("**Max concurrent downloads reached. Stopping playlist processing.**", parse_mode='Markdown')
                        break
                    await process_video(entry['webpage_url'], user_id, chat_id, context, status_msg, f"Video {i}/{len(entries)}", lang)
            else:
                await process_video(url, user_id, chat_id, context, status_msg, "", lang)
        except Exception as e:
            await status_msg.edit_text(MESSAGES[lang]["invalid_url"] + f"\n**Error**: {str(e)}", parse_mode='Markdown')
            await log_to_channel(context, f"Error processing {url} for user {user_id}: {str(e)}")

async def process_video(url, user_id, chat_id, context, status_msg, prefix, lang):
    try:
        with YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [f for f in info['formats'] if f.get('ext') == 'mp4' and f.get('acodec') != 'none'] or info['formats']

        user_data = get_user_data(user_id)
        default_quality = user_data.get("default_quality")
        audio_only = user_data.get("audio_only", False)

        if audio_only:
            format_id = "audio_only"
            await download_and_upload(url, format_id, user_id, chat_id, context, status_msg, prefix, lang)
        elif default_quality and default_quality in QUALITY_OPTIONS:
            format_id = next((f['format_id'] for f in formats if default_quality[:-1] in str(f.get('height', ''))), formats[0]['format_id'])
            await download_and_upload(url, format_id, user_id, chat_id, context, status_msg, prefix, lang)
        else:
            keyboard = [
                [InlineKeyboardButton("144p", callback_data=f"q_144p_{url}"), InlineKeyboardButton("360p", callback_data=f"q_360p_{url}")],
                [InlineKeyboardButton("720p", callback_data=f"q_720p_{url}"), InlineKeyboardButton("1080p", callback_data=f"q_1080p_{url}")],
                [InlineKeyboardButton("Audio Only", callback_data=f"q_audio_only_{url}")]
            ]
            await status_msg.edit_text(f"**{prefix} Choose quality:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            context.user_data[f"pending_{user_id}_{chat_id}_{url}"] = (url, status_msg, prefix, lang)

    except Exception as e:
        await status_msg.edit_text(MESSAGES[lang]["invalid_url"] + f"\n**Error**: {str(e)}", parse_mode='Markdown')
        await log_to_channel(context, f"Error for user {user_id} with {url}: {str(e)}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message or update.effective_user.id not in ADMIN_IDS:
        if update.message:
            await update.message.reply_text("**Admin only.**", parse_mode='Markdown')
        return
    if not context.args:
        await update.message.reply_text("**Usage: /broadcast <message>**", parse_mode='Markdown')
        return
    message = " ".join(context.args)
    users = get_all_user_ids()  # Replace users_collection.distinct with database function
    for user_id in users:
        try:
            await context.bot.send_message(user_id, f"**Broadcast: {message}**", parse_mode='Markdown')
        except Exception as e:
            print(f"Failed to broadcast to {user_id}: {str(e)}")
    await update.message.reply_text(f"**Broadcast sent to {len(users)} users.**", parse_mode='Markdown')
    await log_to_channel(context, f"Admin {update.effective_user.id} broadcasted: {message}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message or update.effective_user.id not in ADMIN_IDS:
        if update.message:
            await update.message.reply_text("**Admin only.**", parse_mode='Markdown')
        return
    stats = get_bot_stats()
    await update.message.reply_text(
        f"**Total videos: {stats['total_videos']}**\n**Total size: {stats['total_size']:.2f} MB**\n**Total time: {stats['total_time']:.2f} s**",
        parse_mode='Markdown'
    )
    await log_to_channel(context, f"Admin {update.effective_user.id} checked stats")

async def user_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message or update.effective_user.id not in ADMIN_IDS:
        if update.message:
            await update.message.reply_text("**Admin only.**", parse_mode='Markdown')
        return
    if not context.args:
        await update.message.reply_text("**Usage: /useractivity <user_id>**", parse_mode='Markdown')
        return
    user_id = int(context.args[0])
    videos, size, last_active = get_user_activity(user_id)
    last_active_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_active)) if last_active else "Never"
    await update.message.reply_text(
        f"**User {user_id}:**\n**Videos: {videos}**\n**Total size: {size:.2f} MB**\n**Last active: {last_active_str}**",
        parse_mode='Markdown'
    )
    await log_to_channel(context, f"Admin {update.effective_user.id} checked activity for {user_id}")

async def total_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message or update.effective_user.id not in ADMIN_IDS:
        if update.message:
            await update.message.reply_text("**Admin only.**", parse_mode='Markdown')
        return
    total = get_total_users()
    await update.message.reply_text(f"**Total users: {total}**", parse_mode='Markdown')
    await log_to_channel(context, f"Admin {update.effective_user.id} checked total users")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message or update.effective_user.id not in ADMIN_IDS:
        if update.message:
            await update.message.reply_text("**Admin only.**", parse_mode='Markdown')
        return
    if not context.args:
        await update.message.reply_text("**Usage: /ban <user_id>**", parse_mode='Markdown')
        return
    user_id = int(context.args[0])
    ADMIN_IDS.discard(user_id)
    await update.message.reply_text(f"**User {user_id} banned.**", parse_mode='Markdown')
    await log_to_channel(context, f"Admin {update.effective_user.id} banned user {user_id}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query.from_user or not query.message:
        return
    user_id = query.from_user.id
    chat_id = update.effective_chat.id
    lang = get_user_data(user_id).get("language", "en")
    await query.answer()

    if query.data == "check_sub":
        if await check_subscription(context, user_id):
            await query.edit_message_text(MESSAGES[lang]["subscribed"], parse_mode='Markdown')
            await log_to_channel(context, f"User {user_id} subscribed and verified.")
        else:
            await query.edit_message_text(MESSAGES[lang]["subscribe"].format(", ".join(FORCE_CHANNELS)), parse_mode='Markdown')
    elif query.data == "show_help":
        await query.edit_message_text(MESSAGES[lang]["help"], parse_mode='Markdown')
    elif query.data == "show_about":
        await query.edit_message_text(MESSAGES[lang]["about"], parse_mode='Markdown')
    elif query.data == "show_platforms":
        await query.edit_message_text(MESSAGES[lang]["platforms"], parse_mode='Markdown')
    elif query.data == "show_settings":
        await settings(update, context)
    elif query.data == "set_quality":
        keyboard = [
            [InlineKeyboardButton("144p", callback_data="set_q_144p"), InlineKeyboardButton("360p", callback_data="set_q_360p")],
            [InlineKeyboardButton("720p", callback_data="set_q_720p"), InlineKeyboardButton("1080p", callback_data="set_q_1080p")],
            [InlineKeyboardButton("Audio Only", callback_data="set_q_audio_only")]
        ]
        await query.edit_message_text("**Choose default quality:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif query.data.startswith("set_q_"):
        quality = query.data.split("_")[2]
        update_user_data(user_id, {"default_quality": quality})
        await query.edit_message_text(f"**Default quality set to {quality}**", parse_mode='Markdown')
        await log_to_channel(context, f"User {user_id} set quality to {quality}")
    elif query.data == "toggle_audio":
        new_audio = not get_user_data(user_id).get("audio_only", False)
        update_user_data(user_id, {"audio_only": new_audio})
        await query.edit_message_text(f"**Audio-only mode {'enabled' if new_audio else 'disabled'}**", parse_mode='Markdown')
        await log_to_channel(context, f"User {user_id} set audio-only to {new_audio}")
    elif query.data == "set_format":
        keyboard = [
            [InlineKeyboardButton("MP4", callback_data="format_mp4"), InlineKeyboardButton("MKV", callback_data="format_mkv")]
        ]
        await query.edit_message_text("**Choose format:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif query.data in ["format_mp4", "format_mkv"]:
        format_choice = "MP4" if query.data == "format_mp4" else "MKV"
        update_user_data(user_id, {"upload_format": format_choice})
        await query.edit_message_text(f"**Upload format set to {format_choice}**", parse_mode='Markdown')
        await log_to_channel(context, f"User {user_id} set upload format to {format_choice}")
    elif query.data == "toggle_metadata":
        new_metadata = not get_user_data(user_id).get("edit_metadata", False)
        update_user_data(user_id, {"edit_metadata": new_metadata})
        await query.edit_message_text(f"**Metadata editing {'enabled' if new_metadata else 'disabled'}**", parse_mode='Markdown')
        await log_to_channel(context, f"User {user_id} set metadata editing to {new_metadata}")
    elif query.data == "set_language":
        keyboard = [
            [InlineKeyboardButton("English", callback_data="lang_en"), InlineKeyboardButton("Spanish", callback_data="lang_es")]
        ]
        await query.edit_message_text("**Choose language:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif query.data in ["lang_en", "lang_es"]:
        lang = "en" if query.data == "lang_en" else "es"
        update_user_data(user_id, {"language": lang})
        await query.edit_message_text(f"**Language set to {lang.capitalize()}**", parse_mode='Markdown')
        await log_to_channel(context, f"User {user_id} set language to {lang}")
    elif query.data.startswith("q_"):
        quality, url = query.data.split("_", 2)[1], "_".join(query.data.split("_")[2:])
        pending_key = f"pending_{user_id}_{chat_id}_{url}"
        if pending_key in context.user_data:
            url, status_msg, prefix, lang = context.user_data[pending_key]
            with YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = [f for f in info['formats'] if f.get('ext') == 'mp4' and f.get('acodec') != 'none'] or info['formats']
            format_id = quality if quality == "audio_only" else next(
                (f['format_id'] for f in formats if quality[:-1] in str(f.get('height', ''))), "best"
            )
            await download_and_upload(url, format_id, user_id, chat_id, context, status_msg, prefix, lang)
            del context.user_data[pending_key]
    elif query.data.startswith("cancel_"):
        task_id = query.data.split("_", 1)[1]
        active_downloads = context.bot_data.get("active_downloads", {})
        task = next((t for t, u in active_downloads.items() if f"{user_id}_{chat_id}_{u}" == task_id), None)
        if task:
            task.cancel()
            await query.edit_message_text(f"**{query.message.text.splitlines()[0]} Download cancelled.**", parse_mode='Markdown')
            await log_to_channel(context, f"User {user_id} cancelled download for {task_id}")
            active_downloads.pop(task, None)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    error_msg = f"Error occurred: {str(error)}"
    await log_to_channel(context, error_msg)
    if update and update.effective_chat:
        try:
            await context.bot.send_message(update.effective_chat.id, f"**An error occurred: {str(error)}. Please try again later.**", parse_mode='Markdown')
        except Exception as e:
            print(f"Failed to send error message: {str(e)}")
    print(error_msg)

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("platforms", platforms))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("useractivity", user_activity))
    application.add_handler(CommandHandler("totalusers", total_users))
    application.add_handler(CommandHandler("ban", ban_user))

    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_error_handler(error_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
