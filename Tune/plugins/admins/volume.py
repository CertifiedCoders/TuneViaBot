# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS
from Tune import app
from Tune.core.call import StreamController
from Tune.utils.database import is_music_playing
from Tune.utils.admin_filters import admin_filter
from Tune.utils.exceptions import AssistantErr


@app.on_message(filters.command(["volume", "vol", "setvolume"]) & filters.group & admin_filter & ~BANNED_USERS)
async def set_volume(client, message: Message):
    chat_id = message.chat.id
    
    if not await is_music_playing(chat_id):
        return await message.reply_text("❌ No active voice chat or music is not playing.")
    
    if len(message.command) < 2:
        return await message.reply_text(
            "**Usage:** `/volume <0-200>`\n\n"
            "**Volume Levels:**\n"
            "• `0` = 0% (Muted)\n"
            "• `50` = 25%\n"
            "• `100` = 50% (Default)\n"
            "• `150` = 75%\n"
            "• `200` = 100% (Maximum)"
        )
    
    try:
        volume = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Invalid volume value. Please provide a number between 0 and 200.")
    
    try:
        await StreamController.change_volume_call(chat_id, volume)
        volume_percent = round(volume / 2, 1)
        await message.reply_text(
            f"✅ **Volume changed successfully!**\n\n"
            f"🎚️ **Current Volume:** `{volume}` ({volume_percent}%)"
        )
    except AssistantErr as e:
        await message.reply_text(f"❌ {str(e)}")
    except Exception as e:
        await message.reply_text(f"❌ Failed to change volume.\n<b>Error:</b> {e}")

