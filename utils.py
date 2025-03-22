# utils.py
from config import LOGS_CHANNEL_ID, FORCE_CHANNELS

async def check_subscription(context, user_id):
    try:
        for channel in FORCE_CHANNELS:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except Exception as e:
        print(f"Error checking subscription: {str(e)}")
        return False

async def log_to_channel(context, message, file_path=None):
    try:
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                await context.bot.send_document(LOGS_CHANNEL_ID, f, caption=message)
        else:
            await context.bot.send_message(LOGS_CHANNEL_ID, message)
    except Exception as e:
        print(f"Log failed: {str(e)} - {message}")
