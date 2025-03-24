# database.py
from pymongo import MongoClient
from config import MONGO_URI, MONGO_DB_NAME

# Initialize MongoDB client
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

# Collections
users_collection = db["users"]
stats_collection = db["stats"]
banned_users_collection = db["banned_users"]
thumbnails_collection = db["thumbnails"]

# Initialize stats if not present
if stats_collection.count_documents({}) == 0:
    stats_collection.insert_one({
        "total_videos": 0,
        "total_size": 0.0,
        "total_time": 0.0,
        "global_task_limit": 2
    })

def get_user_data(user_id):
    """
    Get user data from MongoDB, initializing with defaults if not present.
    """
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        default_data = {
            "user_id": user_id,
            "default_quality": "best",
            "compression": False,
            "audio_only": False,
            "upload_format": "mp4",
            "metadata_edit": False,
            "file_rename": False,
            "multi_audio": False,
            "subtitles": False,
            "active_downloads": 0
        }
        users_collection.insert_one(default_data)
        return default_data
    return user

def update_user_data(user_id, data):
    """
    Update user data in MongoDB.
    """
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": data},
        upsert=True
    )

def log_stat(user_id, size_mb, time_taken):
    """
    Log download statistics in MongoDB.
    """
    stats_collection.update_one(
        {},
        {
            "$inc": {
                "total_videos": 1,
                "total_size": size_mb,
                "total_time": time_taken
            }
        },
        upsert=True
    )

def get_bot_stats():
    """
    Get bot statistics from MongoDB.
    """
    stats = stats_collection.find_one({})
    if not stats:
        return {"total_videos": 0, "total_size": 0.0, "total_time": 0.0}
    return {
        "total_videos": stats.get("total_videos", 0),
        "total_size": stats.get("total_size", 0.0),
        "total_time": stats.get("total_time", 0.0)
    }

def get_total_users():
    """
    Get total number of users from MongoDB.
    """
    return users_collection.count_documents({})

def ban_user(user_id):
    """
    Ban a user by adding them to the banned_users collection.
    """
    banned_users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id}},
        upsert=True
    )

def unban_user(user_id):
    """
    Unban a user by removing them from the banned_users collection.
    """
    banned_users_collection.delete_one({"user_id": user_id})

def is_banned(user_id):
    """
    Check if a user is banned.
    """
    return banned_users_collection.find_one({"user_id": user_id}) is not None

def set_task_limit(limit):
    """
    Set the global task limit for concurrent downloads in MongoDB.
    """
    stats_collection.update_one(
        {},
        {"$set": {"global_task_limit": limit}},
        upsert=True
    )

def get_task_limit():
    """
    Get the global task limit from MongoDB.
    """
    stats = stats_collection.find_one({})
    return stats.get("global_task_limit", 2) if stats else 2

def set_thumbnail(user_id, thumbnail_path):
    """
    Set a custom thumbnail for a user in MongoDB.
    """
    thumbnails_collection.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "thumbnail_path": thumbnail_path}},
        upsert=True
    )

def get_thumbnail(user_id):
    """
    Get the custom thumbnail for a user from MongoDB.
    """
    thumbnail = thumbnails_collection.find_one({"user_id": user_id})
    return thumbnail.get("thumbnail_path") if thumbnail else None

def delete_thumbnail(user_id):
    """
    Delete the custom thumbnail for a user from MongoDB and the filesystem.
    """
    thumbnail = thumbnails_collection.find_one({"user_id": user_id})
    if thumbnail:
        path = thumbnail.get("thumbnail_path")
        if path and os.path.exists(path):
            os.remove(path)
        thumbnails_collection.delete_one({"user_id": user_id})
