# downloader.py
import os
import asyncio
import time
import hashlib
import re
from yt_dlp import YoutubeDL
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import DOWNLOAD_DIR, YOUTUBE_PREMIUM_USERNAME, YOUTUBE_PREMIUM_PASSWORD
from database import get_user_data, log_stat, get_thumbnail
from utils import log_to_channel

# Shared state for progress updates
progress_data = {}

def sanitize_filename(filename, max_length=100):
    """
    Sanitize and shorten the filename to avoid 'File name too long' errors.
    """
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)  # Remove invalid characters
    filename = filename.replace(' ', '_')  # Replace spaces with underscores
    filename = filename.encode('ascii', 'ignore').decode('ascii')  # Remove non-ASCII characters
    if len(filename) > max_length:
        filename = filename[:max_length]  # Shorten to max_length
    return filename

def strip_ansi_codes(text):
    """
    Remove ANSI color codes from a string.
    """
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def download_progress_hook(d, task_id):
    """
    Synchronous progress hook for yt_dlp to update shared progress data.
    """
    if d['status'] == 'downloading':
        try:
            percent_str = strip_ansi_codes(d.get('_percent_str', '0%')).replace('%', '').strip()
            percent = float(percent_str)
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            downloaded = d.get('downloaded_bytes', 0) / (1024 * 1024)  # Convert to MB
            total = d.get('total_bytes', 0) / (1024 * 1024) if d.get('total_bytes') else 'Unknown'
            progress_data[task_id] = {
                'percent': percent,
                'speed': speed,
                'eta': eta,
                'downloaded': downloaded,
                'total': total
            }
        except (ValueError, TypeError) as e:
            print(f"Error in download_progress_hook: {str(e)}")
            progress_data[task_id] = {
                'percent': 0,
                'speed': 'N/A',
                'eta': 'N/A',
                'downloaded': 0,
                'total': 'Unknown'
            }

async def update_download_progress(context, status_msg, task_id):
    """
    Async task to periodically update the download progress bar.
    """
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
            f"📥 **Downloading...**\n"
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
        await asyncio.sleep(1)  # Update every 1 second for responsiveness

async def upload_progress_hook(file_path, context, status_msg, total_size):
    """
    Show a progress bar during upload.
    """
    uploaded = 0
    start_time = time.time()
    chunk_size = 50 * 1024 * 1024  # 50MB chunks for faster uploads
    last_update = start_time
    update_interval = 1.0  # Update every 1 second

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
                speed = uploaded / (1024 * 1024 * elapsed) if elapsed > 0 else 0
                eta = (total_size - uploaded) / (speed * 1024 * 1024) if speed > 0 else 0
                progress_bar = "█" * int(percent // 10) + "░" * (10 - int(percent // 10))
                progress_text = (
                    f"📤 **Uploading...**\n"
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

    await status_msg.edit_text("✅ **Upload complete!**", parse_mode='Markdown')

async def download_and_upload(url, format_id, user_id, chat_id, context, status_msg):
    """
    Download a video/audio from the given URL and upload it to Telegram.
    """
    start_time = time.time()
    user_data = get_user_data(user_id)
    task_id = f"{user_id}_{chat_id}_{url}"

    # Quality mapping for yt-dlp format codes
    quality_map = {
        "best": "bestvideo",
        "1080p": "137",  # 1080p format code for YouTube
        "720p": "136",   # 720p
        "480p": "135",   # 480p
        "360p": "134",   # 360p
        "240p": "133",   # 240p
        "audio_only": "bestaudio/best"
    }
    format_id = quality_map.get(format_id, "bestvideo")

    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'progress_hooks': [lambda d: download_progress_hook(d, task_id)],
        'noplaylist': True,
        'retries': 10,
        'quiet': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        },
        'socket_timeout': 60,
        'concurrent_fragments': 8,  # Increase for faster downloads
        'format_sort': ['res', 'vcodec:h264'],  # Prefer H.264 for compatibility
    }

    # Limit the title length to avoid file name issues
    ydl_opts['outtmpl'] = {
        'default': f'{DOWNLOAD_DIR}/%(title).100s.%(ext)s',
        'pl_thumbnail': f'{DOWNLOAD_DIR}/%(title).100s.%(ext)s'
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
            'merge_output_format': user_data.get("upload_format", "mp4"),
            'writethumbnail': True,
        })

    if user_data.get("multi_audio", False):
        ydl_opts['postprocessors'] = ydl_opts.get('postprocessors', []) + [{'key': 'FFmpegMergeAudio'}]

    if user_data.get("subtitles", False):
        ydl_opts.update({
            'writesubtitles': True,
            'subtitleslangs': ['en', 'all'],
            'writeautomaticsub': True,
        })

    progress_task = asyncio.create_task(update_download_progress(context, status_msg, task_id))
    file_path = None
    thumbnail = None
    subtitles = None

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            raw_filename = ydl.prepare_filename(info)
            base_filename = os.path.splitext(raw_filename)[0]
            ext = os.path.splitext(raw_filename)[1]
            sanitized_base = sanitize_filename(base_filename)
            file_path = f"{sanitized_base}{ext}"
            if raw_filename != file_path:
                os.rename(raw_filename, file_path)

            thumbnail = f"{sanitized_base}.jpg" if format_id != "bestaudio/best" and os.path.exists(f"{base_filename}.jpg") else None
            if thumbnail and thumbnail != f"{base_filename}.jpg":
                os.rename(f"{base_filename}.jpg", thumbnail)

            subtitles = f"{sanitized_base}.en.srt" if user_data.get("subtitles", False) and os.path.exists(f"{base_filename}.en.srt") else None
            if subtitles and subtitles != f"{base_filename}.en.srt":
                os.rename(f"{base_filename}.en.srt", subtitles)

        await progress_task

        # Handle metadata edit
        title = info.get('title', 'Video')
        if user_data.get("metadata_edit", False):
            await context.bot.send_message(
                chat_id,
                f"📝 **Current title:** {title}\nReply with a new title to edit, or skip to continue.",
                parse_mode='Markdown'
            )
            context.user_data[f"metadata_{task_id}"] = {
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
            return

        # Handle file rename
        filename = os.path.basename(file_path)
        if user_data.get("file_rename", False):
            await context.bot.send_message(
                chat_id,
                f"📝 **Current filename:** {filename}\nReply with a new filename (without extension), or skip to continue.",
                parse_mode='Markdown'
            )
            context.user_data[f"rename_{task_id}"] = {
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
            return

        await process_file(
            file_path, thumbnail, subtitles, url, format_id, user_id, chat_id,
            context, status_msg, start_time, title, info
        )

    except Exception as e:
        progress_task.cancel()
        error_msg = str(e)[:1000]
        await status_msg.edit_text(f"❌ **Error:** {error_msg}")
        await log_to_channel(context, f"Download failed for {url} (user {user_id}): {str(e)}")
        raise

    finally:
        for path in [file_path, thumbnail, subtitles]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"Failed to clean up file {path}: {str(e)}")

async def process_file(file_path, thumbnail, subtitles, url, format_id, user_id, chat_id, context, status_msg, start_time, title, info):
    """
    Process the downloaded file: apply settings and upload to Telegram.
    """
    user_data = get_user_data(user_id)
    upload_format = user_data.get("upload_format", "mp4")
    custom_thumbnail = get_thumbnail(user_id)

    # Use custom thumbnail if available
    if custom_thumbnail and os.path.exists(custom_thumbnail):
        thumbnail = custom_thumbnail

    final_path = os.path.join(
        DOWNLOAD_DIR,
        f"{sanitize_filename(title)}.{upload_format if format_id != 'bestaudio/best' else 'mp3'}"
    )
    os.rename(file_path, final_path)

    file_size = os.path.getsize(final_path)
    if file_size > 2000 * 1024 * 1024:
        await status_msg.edit_text(
            f"❌ **File too large ({file_size / (1024 * 1024):.2f} MB). Telegram's limit is 2000 MB.**",
            parse_mode='Markdown'
        )
        return

    await upload_progress_hook(final_path, context, status_msg, file_size)

    with open(final_path, 'rb') as f:
        if format_id == "bestaudio/best":
            await context.bot.send_audio(
                chat_id,
                f,
                title=title,
                caption=f"🎵 **{title}**",
                parse_mode='Markdown'
            )
        else:
            await context.bot.send_video(
                chat_id,
                f,
                caption=f"🎥 **{title}**",
                supports_streaming=True,
                parse_mode='Markdown',
                thumb=open(thumbnail, 'rb') if thumbnail else None
            )

    if thumbnail and not custom_thumbnail:
        with open(thumbnail, 'rb') as t:
            await context.bot.send_photo(
                chat_id,
                t,
                caption=f"🖼️ **Thumbnail for {title}**",
                parse_mode='Markdown'
            )

    if subtitles:
        with open(subtitles, 'rb') as s:
            await context.bot.send_document(
                chat_id,
                s,
                caption=f"📜 **Subtitles for {title}**",
                parse_mode='Markdown'
            )

    await log_to_channel(
        context,
        f"User {user_id} downloaded: {title} ({file_size / (1024 * 1024):.2f}MB)",
        final_path
    )

    log_stat(user_id, file_size / (1024 * 1024), time.time() - start_time)
    await status_msg.delete()
