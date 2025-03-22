# database.py
import pymongo
from config import MONGO_URI, DB_NAME

mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
users_collection = db["users"]
stats_collection = db["stats"]

def get_user_data(user_id):
    return users_collection.find_one({"user_id": user_id}) or {}

def update_user_data(user_id, data):
    users_collection.update_one({"user_id": user_id}, {"$set": data}, upsert=True)

def log_stat(user_id, video_size, time_taken):
    stats_collection.insert_one({
        "user_id": user_id,
        "videos": 1,
        "total_size": video_size,
        "total_time": time_taken,
        "timestamp": time.time()
    })

def get_total_users():
    return users_collection.count_documents({})

def get_user_activity(user_id):
    stats = stats_collection.find({"user_id": user_id})
    total_videos = sum(stat["videos"] for stat in stats)
    total_size = sum(stat["total_size"] for stat in stats)
    last_active = max((stat["timestamp"] for stat in stats), default=0)
    return total_videos, total_size, last_active

def get_bot_stats():
    stats = stats_collection.aggregate([
        {"$group": {"_id": None, "total_videos": {"$sum": "$videos"}, "total_size": {"$sum": "$total_size"}, "total_time": {"$sum": "$total_time"}}}
    ])
    return stats.next() if stats.alive else {"total_videos": 0, "total_size": 0, "total_time": 0}
