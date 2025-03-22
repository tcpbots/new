# bot.py
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import BOT_TOKEN, ADMIN_IDS, FORCE_CHANNELS, UPDATES_CHANNEL, SUPPORTED_PLATFORMS, MAX_CONCURRENT_DOWNLOADS
from database import get_user_data, update_user_data, get_total_users, get_user_activity, get_bot_stats
from downloader import download_and_upload, process_file
from utils import check_subscription, log_to_channel
from languages import MESSAGES

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = get_user_data(user_id).get("language", "en")
    if not await check_subscription(context, user_id):
        keyboard = [
            [InlineKeyboardButton("Join Channels", url=f"https://t.me/{channel[1:]}") for channel in FORCE_CHANNELS],
            [InlineKeyboardButton("Check Subscription", callback_data="check_sub")]
        ]
        await update.message.reply_text(
            f"Please subscribe to {', '.join(FORCE_CHANNELS)}!", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await log_to_channel(context, f"User {user_id} attempted /start but isn't subscribed.")
        return
    
    keyboard = [
        [InlineKeyboardButton("Help", callback_data="show_help")],
        [InlineKeyboardButton("Updates", url=f"https://t.me/{UPDATES_CHANNEL[1:]}")],
        [InlineKeyboardButton("About", callback_data="show_about")],
        [InlineKeyboardButton("Settings", callback_data="show_settings")],
        [InlineKeyboardButton("Platforms", callback_data="show_platforms")]
    ]
    await update.message.reply_text(MESSAGES[lang]["welcome"], reply_markup=InlineKeyboardMarkup(keyboard))
    await log_to_channel(context, f"User {user_id} started the bot successfully.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = get_user_data(user_id).get("language", "en")
    await update.message.reply_text(MESSAGES[lang]["help"])

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = get_user_data(user_id).get("language", "en")
    await update.message.reply_text(MESSAGES[lang]["about"])

async def platforms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = get_user_data(user_id).get("language", "en")
    await update.message.reply_text(MESSAGES[lang]["platforms"])

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not await check_subscription(context, user_id):
        await update.message.reply_text(f"Please subscribe to {', '.join(FORCE_CHANNELS)} first!")
        return

    user_data = get_user_data(user_id)
    lang = user_data.get("language", "en")
    current_quality = user_data.get("default_quality", "Not set")
    current_audio = "Yes" if user_data.get("audio_only", False) else "No"
    current_format = user_data.get("upload_format", "MP4")
    current_metadata = "Yes" if user_data.get("edit_metadata", False) else "No"
    current_lang = "English" if lang == "en" else "Spanish"

    keyboard = [
        [InlineKeyboardButton(f"Quality: {current_quality}", callback_data="set_quality")],
        [InlineKeyboardButton(f"Audio Only: {current_audio}", callback_data="toggle_audio")],
        [InlineKeyboardButton(f"Format: {current_format}", callback_data="set_format")],
        [InlineKeyboardButton(f"Edit Metadata: {current_metadata}", callback_data="toggle_metadata")],
        [InlineKeyboardButton(f"Language: {current_lang}", callback_data="set_language")],
    ]
    await update.message.reply_text("Settings:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not await check_subscription(context, user_id):
        await update.message.reply_text(f"Please subscribe to {', '.join(FORCE_CHANNELS)} first!")
        return

    if context.user_data.get("setting") == "quality":
        quality = update.message.text.strip()
        update_user_data(user_id, {"default_quality": quality})
        await update.message.reply_text(f"Default quality set to {quality}")
        await log_to_channel(context, f"User {user_id} set quality to {quality}")
        del context.user_data["setting"]
        return
    elif context.user_data.get("metadata"):
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

    if user_id not in ADMIN_IDS and ADMIN_IDS:
        await update.message.reply_text("This bot is private. Contact an admin to gain access.")
        return

    text = update.message.text.strip()
    urls = [url.strip() for url in text.split('\n') if any(p in url.lower() for p in SUPPORTED_PLATFORMS)]
    if not urls:
        await update.message.reply_text("No valid URLs found.")
        return

    await update.message.reply_text(f"Processing {len(urls)} video(s)...")
    await log_to_channel(context, f"User {user_id} submitted {len(urls)} URL(s)")

    tasks = []
    active_downloads = context.bot_data.get("active_downloads", {})
    for url in urls:
        if len(active_downloads) >= MAX_CONCURRENT_DOWNLOADS:
            await update.message.reply_text("Max concurrent downloads reached. Please wait.")
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

        status_msg = await context.bot.send_message(chat_id, "Processing your request...")

        with YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            is_playlist = 'entries' in info

        if is_playlist:
            entries = info['entries']
            for i, entry in enumerate(entries, 1):
                if len(context.bot_data.get("active_downloads", {})) >= MAX_CONCURRENT_DOWNLOADS:
                    await status_msg.edit_text("Max concurrent downloads reached. Stopping playlist processing.")
                    break
                await process_video(entry['webpage_url'], user_id, chat_id, context, status_msg, f"Video {i}/{len(entries)}", lang)
        else:
            await process_video(url, user_id, chat_id, context, status_msg, "", lang)

async def process_video(url, user_id, chat_id, context, status_msg, prefix, lang):
    try:
        with YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [f for f in info['formats'] if f.get('ext') == 'mp4' and f.get('acodec') != 'none']

        user_data = get_user_data(user_id)
        default_quality = user_data.get("default_quality")
        audio_only = user_data.get("audio_only", False)

        if audio_only:
            format_id = "audio_only"
        elif default_quality:
            format_id = next((f['format_id'] for f in formats if default_quality in str(f.get('height', ''))), formats[0]['format_id'])
        else:
            keyboard = [[InlineKeyboardButton(f"{f.get('height', 'Unknown')}p", callback_data=f"{f['format_id']}")] 
                        for f in sorted(formats, key=lambda x: x.get('height', 0), reverse=True)[:5]]
            keyboard.append([InlineKeyboardButton("Audio Only (MP3)", callback_data="audio_only")])
            await status_msg.edit_text(f"{prefix} Choose quality:", reply_markup=InlineKeyboardMarkup(keyboard))
            context.user_data[f"pending_{user_id}_{chat_id}_{url}"] = (url, status_msg, prefix, lang)
            return

        await download_and_upload(url, format_id, user_id, chat_id, context, status_msg, prefix, lang)

    except Exception as e:
        await status_msg.edit_text(f"{prefix} Error: {str(e)}")
        await log_to_channel(context, f"Error for user {user_id}: {str(e)}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Admin only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    message = " ".join(context.args)
    users = users_collection.distinct("user_id")
    for user_id in users:
        try:
            await context.bot.send_message(user_id, f"Broadcast: {message}")
        except Exception as e:
            print(f"Failed to broadcast to {user_id}: {str(e)}")
    await update.message.reply_text(f"Broadcast sent to {len(users)} users.")
    await log_to_channel(context, f"Admin {update.effective_user.id} broadcasted: {message}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Admin only.")
        return
    stats = get_bot_stats()
    await update.message.reply_text(
        f"Total videos: {stats['total_videos']}\nTotal size: {stats['total_size']:.2f} MB\nTotal time: {stats['total_time']:.2f} s"
    )
    await log_to_channel(context, f"Admin {update.effective_user.id} checked stats")

async def user_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Admin only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /useractivity <user_id>")
        return
    user_id = int(context.args[0])
    videos, size, last_active = get_user_activity(user_id)
    last_active_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_active)) if last_active else "Never"
    await update.message.reply_text(
        f"User {user_id}:\nVideos: {videos}\nTotal size: {size:.2f} MB\nLast active: {last_active_str}"
    )
    await log_to_channel(context, f"Admin {update.effective_user.id} checked activity for {user_id}")

async def total_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Admin only.")
        return
    total = get_total_users()
    await update.message.reply_text(f"Total users: {total}")
    await log_to_channel(context, f"Admin {update.effective_user.id} checked total users")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Admin only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    user_id = int(context.args[0])
    ADMIN_IDS.discard(user_id)
    await update.message.reply_text(f"User {user_id} banned.")
    await log_to_channel(context, f"Admin {update.effective_user.id} banned user {user_id}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = update.effective_chat.id
    await query.answer()

    if query.data == "check_sub":
        if await check_subscription(context, user_id):
            await query.edit_message_text("Thanks for subscribing! Send a video URL to start.")
            await log_to_channel(context, f"User {user_id} subscribed and verified.")
        else:
            await query.edit_message_text(f"Please subscribe to {', '.join(FORCE_CHANNELS)} first!")
    elif query.data == "show_help":
        await help_command(update, context)
    elif query.data == "show_about":
        await about(update, context)
    elif query.data == "show_platforms":
        await platforms(update, context)
    elif query.data == "show_settings":
        await settings(update, context)
    elif query.data in ["set_quality", "toggle_audio", "set_format", "toggle_metadata", "set_language"]:
        await handle_settings(update, context, query.data)
    elif query.data in ["format_mp4", "format_mkv"]:
        format_choice = "mp4" if query.data == "format_mp4" else "mkv"
        update_user_data(user_id, {"upload_format": format_choice.upper()})
        await query.edit_message_text(f"Upload format set to {format_choice.upper()}")
        await log_to_channel(context, f"User {user_id} set upload format to {format_choice.upper()}")
    elif query.data.startswith("cancel_"):
        task_id = query.data.split("_", 1)[1]
        active_downloads = context.bot_data.get("active_downloads", {})
        task = next((t for t, u in active_downloads.items() if f"{user_id}_{chat_id}_{u}" == task_id), None)
        if task:
            task.cancel()
            await query.edit_message_text(f"{query.message.text.split()[0]} Download cancelled.")
            await log_to_channel(context, f"User {user_id} cancelled download for {task_id}")
            active_downloads.pop(task, None)
    else:
        pending_key = f"pending_{user_id}_{chat_id}"
        for key in context.user_data:
            if key.startswith(pending_key):
                url, status_msg, prefix, lang = context.user_data[key]
                if query.data in [f['format_id'] for f in YoutubeDL({'quiet': True}).extract_info(url, download=False)['formats']] or query.data == "audio_only":
                    await download_and_upload(url, query.data, user_id, chat_id, context, status_msg, prefix, lang)
                    del context.user_data[key]
                break

async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    lang = user_data.get("language", "en")

    if action == "set_quality":
        await query.edit_message_text("Send a quality (e.g., 1080p) or wait for options when downloading.")
        context.user_data["setting"] = "quality"
    elif action == "toggle_audio":
        new_audio = not user_data.get("audio_only", False)
        update_user_data(user_id, {"audio_only": new_audio})
        await query.edit_message_text(f"Audio-only mode {'enabled' if new_audio else 'disabled'}")
        await log_to_channel(context, f"User {user_id} set audio-only to {new_audio}")
    elif action == "toggle_metadata":
        new_metadata = not user_data.get("edit_metadata", False)
        update_user_data(user_id, {"edit_metadata": new_metadata})
        await query.edit_message_text(f"Metadata editing {'enabled' if new_metadata else 'disabled'}")
        await log_to_channel(context, f"User {user_id} set metadata editing to {new_metadata}")
    elif action == "set_language":
        keyboard = [
            [InlineKeyboardButton("English", callback_data="lang_en")],
            [InlineKeyboardButton("Spanish", callback_data="lang_es")],
        ]
        await query.edit_message_text("Choose language:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif action in ["lang_en", "lang_es"]:
        lang = "en" if action == "lang_en" else "es"
        update_user_data(user_id, {"language": lang})
        await query.edit_message_text(f"Language set to {lang.capitalize()}")
        await log_to_channel(context, f"User {user_id} set language to {lang}")

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

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
