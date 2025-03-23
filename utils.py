# utils.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from config import LOG_CHANNEL  # Assuming LOG_CHANNEL is defined in config.py

async def log_to_channel(context, message, file_path=None):
    """
    Log a message to the specified Telegram channel.
    Optionally send a file if file_path is provided.
    """
    try:
        if file_path:
            with open(file_path, 'rb') as f:
                await context.bot.send_document(LOG_CHANNEL, f, caption=message)
        else:
            await context.bot.send_message(LOG_CHANNEL, message)
    except Exception as e:
        print(f"Failed to log to channel: {str(e)}")

async def check_subscription(context, user_id):
    """
    Check if a user is subscribed to all required channels.
    """
    from config import FORCE_CHANNELS
    try:
        for channel in FORCE_CHANNELS:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        return True
    except Exception as e:
        print(f"Error checking subscription for {user_id}: {str(e)}")
        return False
