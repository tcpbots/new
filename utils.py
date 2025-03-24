# utils.py
import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import FORCE_CHANNELS, LOGS_CHANNEL_ID, ADMIN_IDS

logger = logging.getLogger(__name__)

async def check_subscription(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """
    Check if the user is subscribed to all required channels.
    """
    try:
        for channel in FORCE_CHANNELS:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        return True
    except Exception as e:
        logger.error(f"Error checking subscription for user {user_id}: {str(e)}")
        return False

async def log_to_channel(context: ContextTypes.DEFAULT_TYPE, message: str, file_path: str = None):
    """
    Log a message to the logs channel, optionally with a file.
    """
    try:
        if file_path:
            with open(file_path, 'rb') as f:
                await context.bot.send_document(LOGS_CHANNEL_ID, f, caption=message)
        else:
            await context.bot.send_message(LOGS_CHANNEL_ID, message)
    except Exception as e:
        logger.error(f"Failed to log to channel: {str(e)}")

def is_admin(user_id: int) -> bool:
    """
    Check if the user is an admin.
    """
    return user_id in ADMIN_IDS
