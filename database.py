# database.py
from collections import defaultdict
import time

# In-memory storage (replace with SQLite/MongoDB for persistence)
users_data = {}
stats_data = defaultdict(list)

def get_user_data(user_id):
    """
    Retrieve user data. If user doesn't exist, return default settings.
    """
    if user_id not in users_data:
        users_data[user_id] = {
            "language": "en",
            "default_quality": None,
            "audio_only": False,
            "upload_format": "MP4",
            "edit_metadata": False,
            "last_active": time.time()
        }
    return users_data[user_id]

def update_user_data(user_id, data):
    """
    Update user data with new settings.
    """
    if user_id not in users_data:
        users_data[user_id] = {
            "language": "en",
            "default_quality": None,
            "audio_only": False,
            "upload_format": "MP4",
            "edit_metadata": False,
            "last_active": time.time()
        }
    users_data[user_id].update(data)
    users_data[user_id]["last_active"] = time.time()

def log_stat(user_id, size_mb, duration):
    """
    Log statistics for a download.
    """
    stats_data[user_id].append({
        "size_mb": size_mb,
        "duration": duration,
        "timestamp": time.time()
    })

def get_total_users():
    """
    Return the total number of unique users.
    """
    return len(users_data)

def get_user_activity(user_id):
    """
    Return user activity: number of videos, total size, and last active time.
    """
    if user_id not in stats_data:
        return 0, 0.0, users_data.get(user_id, {}).get("last_active", 0)
    videos = len(stats_data[user_id])
    total_size = sum(stat["size_mb"] for stat in stats_data[user_id])
    last_active = users_data.get(user_id, {}).get("last_active", 0)
    return videos, total_size, last_active

def get_bot_stats():
    """
    Return overall bot statistics: total videos, total size, total time.
    """
    total_videos = sum(len(stats) for stats in stats_data.values())
    total_size = sum(stat["size_mb"] for stats in stats_data.values() for stat in stats)
    total_time = sum(stat["duration"] for stats in stats_data.values() for stat in stats)
    return {"total_videos": total_videos, "total_size": total_size, "total_time": total_time}

def get_all_user_ids():
    """
    Return a list of all user IDs.
    """
    return list(users_data.keys())
