# downloader.py
import os
import asyncio
import time
import ffmpeg
from yt_dlp import YoutubeDL
from config import DOWNLOAD_DIR, YOUTUBE_PREMIUM_USERNAME, YOUTUBE_PREMIUM_PASSWORD
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def download_progress_hook(d, context, status_msg, task_id, lang):
    if d['status'] == 'downloading':
        percent = float(d.get('_percent_str', '0%').replace('%', ''))
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        downloaded = d.get('downloaded_bytes', 0) / (1024 * 1024)
        total = d.get('total_bytes', 0) / (1024 * 1024) if d.get('total_bytes') else 'Unknown'
        progress_bar = "█" * int(percent // 10) + "░" * (10 - int(percent // 10))
        progress_text = (
            f"**Downloading**\n"
            f"Progress: [{progress_bar}] {percent:.1f}%\n"
            f"Speed: {speed}\n"
            f"ETA: {eta}\n"
            f"Size: {downloaded:.2f} MB / {total if isinstance(total, str) else f'{total:.2f} MB'}"
        )
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{task_id}")]]
        await status_msg.edit_text(progress_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def upload_progress_hook(file_path, context, status_msg, total_size, lang):
    uploaded = 0
    start_time = time.time()
    while uploaded < total_size:
        await asyncio.sleep(1)  # Update every second
        uploaded = min(uploaded + (1024 * 1024), total_size)  # Simulate upload (adjust based on real upload logic)
        percent = (uploaded / total_size) * 100
        elapsed = time.time() - start_time
        speed = uploaded / (1024 * elapsed) if elapsed > 0 else 0  # MB/s
        eta = (total_size - uploaded) / (speed * 1024 * 1024) if speed > 0 else 0
        progress_bar = "█" * int(percent // 10) + "░" * (10 - int(percent // 10))
        progress_text = (
            f"**Uploading**\n"
            f"Progress: [{progress_bar}] {percent:.1f}%\n"
            f"Speed: {speed:.2f} MB/s\n"
            f"ETA: {int(eta)}s\n"
            f"Size: {uploaded / (1024 * 1024):.2f} MB / {total_size / (1024 * 1024):.2f} MB"
        )
        await status_msg.edit_text(progress_text, parse_mode='Markdown')

async def download_and_upload(url, format_id, user_id, chat_id, context, status_msg, prefix="", lang="en"):
    from languages import MESSAGES
    start_time = time.time()
    user_data = database.get_user_data(user_id)
    upload_format = user_data.get("upload_format", "MP4").lower()
    task_id = f"{user_id}_{chat_id}_{url}"

    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'progress_hooks': [lambda d: download_progress_hook(d, context, status_msg, task_id, lang)],
        'ratelimit': 500000,
        'writesubtitles': True,
        'subtitleslangs': ['en'],
    }
    if YOUTUBE_PREMIUM_USERNAME and YOUTUBE_PREMIUM_PASSWORD and "youtube" in url:
        ydl_opts.update({
            'username': YOUTUBE_PREMIUM_USERNAME,
            'password': YOUTUBE_PREMIUM_PASSWORD,
        })

    if format_id == "audio_only":
        ydl_opts.update({
            'format': 'bestaudio',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
        })
    else:
        ydl_opts.update({
            'format': format_id,
            'merge_output_format': upload_format,
            'writethumbnail': True,
        })

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            thumbnail = file_path.rsplit('.', 1)[0] + '.jpg' if format_id != "audio_only" else None
            subtitles = file_path.rsplit('.', 1)[0] + '.en.srt' if os.path.exists(file_path.rsplit('.', 1)[0] + '.en.srt') else None

        title = info.get('title', 'Video')
        if user_data.get("edit_metadata", False):
            await context.bot.send_message(chat_id, f"**{MESSAGES[lang]['edit_title_prompt'].format(title)}**", parse_mode='Markdown')
            context.user_data[f"metadata_{task_id}"] = {
                "file_path": file_path, "thumbnail": thumbnail, "subtitles": subtitles,
                "url": url, "format_id": format_id, "status_msg": status_msg, "prefix": prefix,
                "start_time": start_time, "title": title
            }
            return

        await process_file(file_path, thumbnail, subtitles, url, format_id, user_id, chat_id, context, status_msg, prefix, start_time, info)

    except Exception as e:
        await status_msg.edit_text(f"**Error: {str(e)}**", parse_mode='Markdown')
        await log_to_channel(context, f"Download failed for {url}: {str(e)}")
        if os.path.exists(file_path):
            os.remove(file_path)

async def process_file(file_path, thumbnail, subtitles, url, format_id, user_id, chat_id, context, status_msg, prefix, start_time, info):
    from languages import MESSAGES
    user_data = database.get_user_data(user_id)
    upload_format = user_data.get("upload_format", "MP4").lower()
    lang = user_data.get("language", "en")

    preview_path = file_path.rsplit('.', 1)[0] + '_preview.mp4'
    try:
        ffmpeg.input(file_path).output(preview_path, t=10, c='copy').run(quiet=True)
        with open(preview_path, 'rb') as preview:
            await context.bot.send_video(chat_id, preview, caption=f"**{prefix} {MESSAGES[lang]['preview']}**", parse_mode='Markdown')
        os.remove(preview_path)
    except:
        print("Preview generation failed")

    file_size = os.path.getsize(file_path) / (1024 * 1024)
    if file_size > 1000:
        compressed_path = file_path.rsplit('.', 1)[0] + '_comp.' + upload_format
        ffmpeg.input(file_path).output(compressed_path, vcodec='libx264', crf=23).run(quiet=True)
        os.remove(file_path)
        file_path = compressed_path

    if subtitles and format_id != "audio_only":
        subbed_path = file_path.rsplit('.', 1)[0] + '_sub.' + upload_format
        ffmpeg.input(file_path).output(subbed_path, vf=f"subtitles={subtitles}").run(quiet=True)
        os.remove(file_path)
        file_path = subbed_path

    final_path = os.path.join(DOWNLOAD_DIR, f"{info['title']}.{upload_format if format_id != 'audio_only' else 'mp3'}")
    os.rename(file_path, final_path)

    file_size = os.path.getsize(final_path)
    if file_size > 2000 * 1024 * 1024:  # 2GB limit
        await status_msg.edit_text(f"**{prefix} {MESSAGES[lang]['too_large'].format(file_size / (1024 * 1024))}**", parse_mode='Markdown')
        os.remove(final_path)
        return

    # Simulate upload progress (replace with real upload logic if available)
    await upload_progress_hook(final_path, context, status_msg, file_size, lang)

    with open(final_path, 'rb') as f:
        if format_id == "audio_only":
            await context.bot.send_audio(chat_id, f, title=info['title'], caption=f"**{prefix} {info['title']}**", parse_mode='Markdown')
        else:
            await context.bot.send_video(chat_id, f, caption=f"**{prefix} {info['title']}**", supports_streaming=True, parse_mode='Markdown')
    
    if thumbnail:
        with open(thumbnail, 'rb') as t:
            await context.bot.send_photo(chat_id, t, caption=f"**Thumbnail for {info['title']}**", parse_mode='Markdown')

    from utils import log_to_channel
    await log_to_channel(context, f"User {user_id} downloaded: {info['title']} ({file_size / (1024 * 1024):.2f}MB)", final_path)

    from database import log_stat
    log_stat(user_id, file_size / (1024 * 1024), time.time() - start_time)

    os.remove(final_path)
    if thumbnail:
        os.remove(thumbnail)
    if subtitles:
        os.remove(subtitles)
    await status_msg.delete()
