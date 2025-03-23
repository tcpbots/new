# downloader.py
import os
import asyncio
import time
import ffmpeg
import hashlib
from yt_dlp import YoutubeDL
from config import DOWNLOAD_DIR, YOUTUBE_PREMIUM_USERNAME, YOUTUBE_PREMIUM_PASSWORD
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_user_data, log_stat
from utils import log_to_channel
from languages import MESSAGES

# Shared state for progress updates
progress_data = {}

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

def download_progress_hook(d, task_id):
    """
    Synchronous progress hook for yt_dlp to update shared progress data.
    """
    if d['status'] == 'downloading':
        percent = float(d.get('_percent_str', '0%').replace('%', ''))
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        downloaded = d.get('downloaded_bytes', 0) / (1024 * 1024)
        total = d.get('total_bytes', 0) / (1024 * 1024) if d.get('total_bytes') else 'Unknown'
        progress_data[task_id] = {
            'percent': percent,
            'speed': speed,
            'eta': eta,
            'downloaded': downloaded,
            'total': total
        }

async def update_download_progress(context, status_msg, task_id, lang):
    """
    Async task to periodically update the download progress bar.
    """
    # Shorten task_id for callback data to avoid Buttondatainvalid error
    short_task_id = hashlib.md5(task_id.encode()).hexdigest()[:10]
    while task_id in progress_data:
        data = progress_data.get(task_id, {})
        percent = data.get('percent', 0)
        speed = data.get('speed', 'N/A')
        eta = data.get('eta', 'N/A')
        downloaded = data.get('downloaded', 0)
        total = data.get('total', 'Unknown')
        progress_bar = "█" * int(percent // 10) + "░" * (10 - int(percent // 10))
        progress_text = (
            f"**{MESSAGES[lang]['downloading']}\n"
            f"Progress: [{progress_bar}] {percent:.1f}%\n"
            f"Speed: {speed}\n"
            f"ETA: {eta}\n"
            f"Size: {downloaded:.2f} MB / {total if isinstance(total, str) else f'{total:.2f} MB'}"
        )
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{short_task_id}")]]
        try:
            await status_msg.edit_text(
                progress_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            print(f"Failed to update progress: {str(e)}")
        await asyncio.sleep(2)  # Update every 2 seconds to reduce API calls
    # Clean up progress data
    progress_data.pop(task_id, None)

async def upload_progress_hook(file_path, context, status_msg, total_size, lang):
    """
    Show a progress bar during upload with optimized speed.
    """
    uploaded = 0
    start_time = time.time()
    chunk_size = 50 * 1024 * 1024  # 50MB chunks for faster uploads
    last_update = start_time
    update_interval = 2.0  # Update progress bar every 2 seconds

    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            uploaded += len(chunk)
            current_time = time.time()

            if current_time - last_update >= update_interval:
                percent = (uploaded / total_size) * 100
                elapsed = current_time - start_time
                speed = uploaded / (1024 * 1024 * elapsed) if elapsed > 0 else 0  # MB/s
                eta = (total_size - uploaded) / (speed * 1024 * 1024) if speed > 0 else 0
                progress_bar = "█" * int(percent // 10) + "░" * (10 - int(percent // 10))
                progress_text = (
                    f"**{MESSAGES[lang]['uploading']}\n"
                    f"Progress: [{progress_bar}] {percent:.1f}%\n"
                    f"Speed: {speed:.2f} MB/s\n"
                    f"ETA: {int(eta)}s\n"
                    f"Size: {uploaded / (1024 * 1024):.2f} MB / {total_size / (1024 * 1024):.2f} MB"
                )
                try:
                    await status_msg.edit_text(progress_text, parse_mode='Markdown')
                except Exception as e:
                    print(f"Failed to update upload progress: {str(e)}")
                last_update = current_time

    # Final update to show upload complete
    await status_msg.edit_text(f"**{MESSAGES[lang]['upload_complete']}**", parse_mode='Markdown')

async def download_and_upload(url, format_id, user_id, chat_id, context, status_msg, prefix="", lang="en"):
    """
    Download a video/audio from the given URL and upload it to Telegram.
    """
    start_time = time.time()
    user_data = get_user_data(user_id)
    upload_format = user_data.get("upload_format", "MP4").lower()
    enable_compression = user_data.get("compression", False)
    task_id = f"{user_id}_{chat_id}_{url}"

    # Map quality settings to yt_dlp format IDs
    quality_map = {
        "bestvideo": "bestvideo",
        "720p": "137",  # 720p format code for YouTube
        "480p": "135",  # 480p format code for YouTube
        "audio_only": "bestaudio/best"
    }
    format_id = quality_map.get(format_id, "bestvideo")

    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'progress_hooks': [lambda d: download_progress_hook(d, task_id)],
        'writesubtitles': True,
        'subtitleslangs': ['en'],
        'noplaylist': True,
        'retries': 10,
        'quiet': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        },
        'socket_timeout': 60,
        'external_downloader_args': {'ffmpeg': ['-threads', '4']},
        'concurrent_fragments': 4,
    }

    if YOUTUBE_PREMIUM_USERNAME and YOUTUBE_PREMIUM_PASSWORD and any(platform in url for platform in ["youtube", "facebook"]):
        ydl_opts.update({
            'username': YOUTUBE_PREMIUM_USERNAME,
            'password': YOUTUBE_PREMIUM_PASSWORD,
        })

    if format_id == "bestaudio/best":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
        })
    else:
        ydl_opts.update({
            'format': f'{format_id}+bestaudio/best',
            'merge_output_format': upload_format,
            'writethumbnail': True,
        })

    # Start the progress update task
    progress_task = asyncio.create_task(update_download_progress(context, status_msg, task_id, lang))

    file_path = None
    thumbnail = None
    subtitles = None
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            thumbnail = file_path.rsplit('.', 1)[0] + '.jpg' if format_id != "bestaudio/best" and os.path.exists(file_path.rsplit('.', 1)[0] + '.jpg') else None
            subtitles = file_path.rsplit('.', 1)[0] + '.en.srt' if os.path.exists(file_path.rsplit('.', 1)[0] + '.en.srt') else None

        # Wait for the progress task to complete
        await progress_task

        title = info.get('title', 'Video')
        if user_data.get("edit_metadata", False):
            await context.bot.send_message(
                chat_id,
                MESSAGES[lang]["edit_title_prompt"].format(title),
                parse_mode='Markdown'
            )
            context.user_data[f"metadata_{task_id}"] = {
                "file_path": file_path,
                "thumbnail": thumbnail,
                "subtitles": subtitles,
                "url": url,
                "format_id": format_id,
                "status_msg": status_msg,
                "prefix": prefix,
                "start_time": start_time,
                "title": title
            }
            return

        await process_file(
            file_path, thumbnail, subtitles, url, format_id, user_id, chat_id,
            context, status_msg, prefix, start_time, info, lang
        )

    except Exception as e:
        # Cancel the progress task
        progress_task.cancel()
        error_msg = str(e)[:1000]  # Truncate to avoid "Request Entity Too Large"
        await status_msg.edit_text(f"{MESSAGES[lang]['error']}: {error_msg}")
        await log_to_channel(context, f"Download failed for {url} (user {user_id}): {str(e)}")
        raise  # Re-raise the exception to be caught by the error handler in bot.py

    finally:
        # Clean up files in all cases
        for path in [file_path, thumbnail, subtitles]:
            if path and os.path.exists(path):
                os.remove(path)

async def process_file(file_path, thumbnail, subtitles, url, format_id, user_id, chat_id, context, status_msg, prefix, start_time, info, lang):
    """
    Process the downloaded file: compress, add subtitles, and upload to Telegram.
    """
    user_data = get_user_data(user_id)
    upload_format = user_data.get("upload_format", "MP4").lower()
    enable_compression = user_data.get("compression", False)

    final_path = None
    try:
        file_size = os.path.getsize(file_path) / (1024 * 1024)
        if enable_compression and file_size > 1000:
            compressed_path = file_path.rsplit('.', 1)[0] + '_comp.' + upload_format
            ffmpeg.input(file_path).output(compressed_path, vcodec='libx264', crf=23).run(quiet=True)
            os.remove(file_path)
            file_path = compressed_path

        if subtitles and format_id != "bestaudio/best":
            subbed_path = file_path.rsplit('.', 1)[0] + '_sub.' + upload_format
            ffmpeg.input(file_path).output(subbed_path, vf=f"subtitles={subtitles}").run(quiet=True)
            os.remove(file_path)
            file_path = subbed_path

        final_path = os.path.join(
            DOWNLOAD_DIR,
            f"{info['title'].replace('/', '_').replace(':', '_')}.{upload_format if format_id != 'bestaudio/best' else 'mp3'}"
        )
        os.rename(file_path, final_path)

        file_size = os.path.getsize(final_path)
        if file_size > 2000 * 1024 * 1024:  # Telegram's 2GB limit
            await status_msg.edit_text(
                MESSAGES[lang]["too_large"].format(file_size / (1024 * 1024)),
                parse_mode='Markdown'
            )
            return

        await upload_progress_hook(final_path, context, status_msg, file_size, lang)

        with open(final_path, 'rb') as f:
            if format_id == "bestaudio/best":
                await context.bot.send_audio(
                    chat_id,
                    f,
                    title=info['title'],
                    caption=f"**{prefix} {info['title']}**",
                    parse_mode='Markdown'
                )
            else:
                await context.bot.send_video(
                    chat_id,
                    f,
                    caption=f"**{prefix} {info['title']}**",
                    supports_streaming=True,
                    parse_mode='Markdown'
                )

        if thumbnail:
            with open(thumbnail, 'rb') as t:
                await context.bot.send_photo(
                    chat_id,
                    t,
                    caption=f"**{MESSAGES[lang]['thumbnail_for']} {info['title']}**",
                    parse_mode='Markdown'
                )

        await log_to_channel(
            context,
            f"User {user_id} downloaded: {info['title']} ({file_size / (1024 * 1024):.2f}MB)",
            final_path
        )

        log_stat(user_id, file_size / (1024 * 1024), time.time() - start_time)

    except Exception as e:
        error_msg = str(e)[:1000]
        await status_msg.edit_text(f"{MESSAGES[lang]['error']}: {error_msg}")
        await log_to_channel(context, f"Upload failed for {url} (user {user_id}): {str(e)}")
        raise

    finally:
        # Clean up files
        if final_path and os.path.exists(final_path):
            os.remove(final_path)
        await status_msg.delete()
