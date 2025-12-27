# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from Tune import YouTube, app
from Tune.core.call import StreamController
from Tune.misc import db
from Tune.utils import AdminRightsCheck, seconds_to_min
from Tune.utils.inline import close_markup
from config import BANNED_USERS


@app.on_message(
    filters.command(["seek", "cseek", "seekback", "cseekback"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def seek_comm(cli, message: Message, _, chat_id):
    if len(message.command) == 1:
        return await message.reply_text(_["admin_20"])
    
    query = message.text.split(None, 1)[1].strip()
    if not query.isnumeric():
        return await message.reply_text(_["admin_21"])
    
    playing = db.get(chat_id)
    if not playing:
        return await message.reply_text(_["queue_2"])
    
    track = playing[0]
    duration_seconds = int(track["seconds"])
    if duration_seconds == 0:
        return await message.reply_text(_["admin_22"])
    
    duration_played = int(track["played"])
    duration_to_skip = int(query)
    is_backward = "back" in message.command[0]
    
    if is_backward:
        new_position = duration_played - duration_to_skip
        if new_position <= 10:
            return await message.reply_text(
                text=_["admin_23"].format(seconds_to_min(duration_played), track["dur"]),
                reply_markup=close_markup(_),
            )
    else:
        new_position = duration_played + duration_to_skip
        if (duration_seconds - new_position) <= 10:
            return await message.reply_text(
                text=_["admin_23"].format(seconds_to_min(duration_played), track["dur"]),
                reply_markup=close_markup(_),
            )
    
    file_path = track["file"]
    if "index_" in file_path or "live_" in file_path:
        return await message.reply_text(_["admin_22"])
    
    if track.get("speed_path"):
        file_path = track["speed_path"]
    elif "vid_" in file_path:
        n, file_path = await YouTube.video("", videoid=track["vidid"])
        if n == 0:
            return await message.reply_text(_["admin_22"])
    
    to_seek = new_position + 1
    mystic = await message.reply_text(_["admin_24"])
    
    try:
        await StreamController.seek_stream(
            chat_id,
            file_path,
            seconds_to_min(to_seek),
            track["dur"],
            track["streamtype"],
        )
    except Exception:
        return await mystic.edit_text(_["admin_26"], reply_markup=close_markup(_))
    
    db[chat_id][0]["played"] = new_position
    await mystic.edit_text(
        text=_["admin_25"].format(seconds_to_min(to_seek), message.from_user.mention),
        reply_markup=close_markup(_),
    )
