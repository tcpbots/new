# downloader.py
import os
import asyncio
import time
import ffmpeg
from yt_dlp import YoutubeDL
from config import DOWNLOAD_DIR, YOUTUBE_PREMIUM_USERNAME, YOUTUBE_PREMIUM_PASSWORD
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_user_data, log_stat
from utils import log_to_channel

# Example links for testing
EXAMPLE_LINKS = {
    "youtube": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "instagram": "https://www.instagram.com/p/CzXvY5uL5Qw/",
    "x.com": "https://x.com/CenterOfBrain/status/1234567890123456789",
    "twitter.com": "https://twitter.com/CenterOfBrain/status/1234567890123456789",
    "vimeo": "https://vimeo.com/123456789",
    "dailymotion": "https://www.dailymotion.com/video/x123456",
    "facebook": "https://www.facebook.com/watch/?v=1264642511461150",
    "tiktok": "https://www.tiktok.com/@user/video/1234567890123456789"
}

async def download_progress_hook(d, context, status_msg, task_id, lang):
    """
    Update the progress bar during download.
    """
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
    """
    Show a progress bar during upload.
    """
    uploaded = 0
    start_time = time.time()
    chunk_size = 1024 * 1024  # 1MB chunks for faster updates
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            uploaded += len(chunk)
            percent = (uploaded / total_size) * 100
            elapsed = time.time() - start_time
            speed = uploaded / (1024 * 1024 * elapsed) if elapsed > 0 else 0  # MB/s
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
            await asyncio.sleep(0.1)  # Small delay to prevent flooding Telegram API
    await status_msg.edit_text("**Upload Complete!**", parse_mode='Markdown')

async def download_and_upload(url, format_id, user_id, chat_id, context, status_msg, prefix="", lang="en"):
    from languages import MESSAGES
    start_time = time.time()
    user_data = get_user_data(user_id)
    upload_format = user_data.get("upload_format", "MP4").lower()
    enable_compression = user_data.get("compression", False)  # New setting
    task_id = f"{user_id}_{chat_id}_{url}"

    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'progress_hooks': [lambda d: download_progress_hook(d, context, status_msg, task_id, lang)],
        'writesubtitles': True,
        'subtitleslangs': ['en'],
        'noplaylist': True,
        'retries': 10,  # Increased retries for reliability
        'quiet': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        },
        'socket_timeout': 30,  # Increase timeout for better handling of slow connections
    }

    # Remove rate limit to maximize download speed
    # ydl_opts['ratelimit'] = 500000  # Removed to use full VPS speed

    if YOUTUBE_PREMIUM_USERNAME and YOUTUBE_PREMIUM_PASSWORD and any(platform in url for platform in ["youtube", "facebook"]):
        ydl_opts.update({
            'username': YOUTUBE_PREMIUM_USERNAME,
            'password': YOUTUBE_PREMIUM_PASSWORD,
        })

    if format_id == "audio_only":
        ydl_opts.update({
            'format': 'bestaudio/best',  # Best audio quality
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
        })
    else:
        ydl_opts.update({
            'format': f'{format_id}+bestaudio/best',  # Best video + audio
            'merge_output_format': upload_format,
            'writethumbnail': True,
        })

    file_path = None
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            thumbnail = file_path.rsplit('.', 1)[0] + '.jpg' if format_id != "audio_only" and os.path.exists(file_path.rsplit('.', 1)[0] + '.jpg') else None
            subtitles = file_path.rsplit('.', 1)[0] + '.en.srt' if os.path.exists(file_path.rsplit('.', 1)[0] + '.en.srt') else None

        title = info.get('title', 'Video')
        if user_data.get("edit_metadata", False):
            await context.bot.send_message(chat_id, MESSAGES[lang]["edit_title_prompt"].format(title), parse_mode='Markdown')
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
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

async def process_file(file_path, thumbnail, subtitles, url, format_id, user_id, chat_id, context, status_msg, prefix, start_time, info):
    from languages import MESSAGES
    user_data = get_user_data(user_id)
    upload_format = user_data.get("upload_format", "MP4").lower()
    enable_compression = user_data.get("compression", False)  # New setting
    lang = user_data.get("language", "en")

    # Removed preview generation as requested
    # preview_path = file_path.rsplit('.', 1)[0] + '_preview.mp4'
    # try:
    #     ffmpeg.input(file_path).output(preview_path, t=10, c='copy').run(quiet=True)
    #     with open(preview_path, 'rb') as preview:
    #         await context.bot.send_video(chat_id, preview, caption=f"**{prefix} {MESSAGES[lang]['preview']}**", parse_mode='Markdown')
    #     os.remove(preview_path)
    # except Exception as e:
    #     print(f"Preview generation failed: {str(e)}")

    file_size = os.path.getsize(file_path) / (1024 * 1024)
    if enable_compression and file_size > 1000:  # Compress only if enabled in settings
        compressed_path = file_path.rsplit('.', 1)[0] + '_comp.' + upload_format
        ffmpeg.input(file_path).output(compressed_path, vcodec='libx264', crf=23).run(quiet=True)
        os.remove(file_path)
        file_path = compressed_path

    if subtitles and format_id != "audio_only":
        subbed_path = file_path.rsplit('.', 1)[0] + '_sub.' + upload_format
        ffmpeg.input(file_path).output(subbed_path, vf=f"subtitles={subtitles}").run(quiet=True)
        os.remove(file_path)
        file_path = subbed_path

    final_path = os.path.join(DOWNLOAD_DIR, f"{info['title'].replace('/', '_').replace(':', '_')}.{upload_format if format_id != 'audio_only' else 'mp3'}")
    os.rename(file_path, final_path)

    file_size = os.path.getsize(final_path)
    if file_size > 2000 * 1024 * 1024:  # 2GB limit for Telegram
        await status_msg.edit_text(MESSAGES[lang]["too_large"].format(file_size / (1024 * 1024)), parse_mode='Markdown')
        os.remove(final_path)
        return

    await upload_progress_hook(final_path, context, status_msg, file_size, lang)

    with open(final_path, 'rb') as f:
        if format_id == "audio_only":
            await context.bot.send_audio(chat_id, f, title=info['title'], caption=f"**{prefix} {info['title']}**", parse_mode='Markdown')
        else:
            await context.bot.send_video(chat_id, f, caption=f"**{prefix} {info['title']}**", supports_streaming=True, parse_mode='Markdown')
    
    if thumbnail:
        with open(thumbnail, 'rb') as t:
            await context.bot.send_photo(chat_id, t, caption=f"**Thumbnail for {info['title']}**", parse_mode='Markdown')

    await log_to_channel(context, f"User {user_id} downloaded: {info['title']} ({file_size / (1024 * 1024):.2f}MB)", final_path)

    log_stat(user_id, file_size / (1024 * 1024), time.time() - start_time)

    os.remove(final_path)
    if thumbnail and os.path.exists(thumbnail):
        os.remove(thumbnail)
    if subtitles and os.path.exists(subtitles):
        os.remove(subtitles)
    await status_msg.delete()
