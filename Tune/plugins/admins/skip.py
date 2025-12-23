# Authored By Certified Coders © 2025
from pyrogram.types import InlineKeyboardMarkup, Message
from pyrogram import filters

import config
from Tune import YouTube, app
from Tune.core.call import StreamController
from Tune.misc import db, set_current_message
from Tune.platforms.Soundcloud import is_soundcloud_url
from Tune.utils.database import get_loop
from Tune.utils.decorators import AdminRightsCheck
from Tune.utils.inline import close_markup, stream_markup
from Tune.utils.stream.autoclear import auto_clean
from Tune.utils.thumbnails import get_thumb
from config import BANNED_USERS


async def stop_stream_on_empty(message: Message, _, chat_id):
    try:
        await message.reply_text(
            text=_["admin_6"].format(
                message.from_user.mention,
                message.chat.title,
            ),
            reply_markup=close_markup(_),
        )
        await StreamController.stop_stream(chat_id)
    except:
        pass


async def skip_multiple_tracks(message: Message, _, chat_id, count: int):
    loop = await get_loop(chat_id)
    if loop != 0:
        return await message.reply_text(_["admin_8"])
    
    check = db.get(chat_id)
    if not check:
        return await message.reply_text(_["queue_2"])
    
    queue_count = len(check)
    if queue_count <= 2:
        return await message.reply_text(_["admin_10"])
    
    max_skip = queue_count - 1
    if not (1 <= count <= max_skip):
        return await message.reply_text(_["admin_11"].format(max_skip))
    
    for _unused in range(count):
        try:
            popped = check.pop(0)
            if popped:
                await auto_clean(popped)
            if not check:
                await stop_stream_on_empty(message, _, chat_id)
                return True
        except:
            return await message.reply_text(_["admin_12"])
    
    return False


async def send_stream_message(message: Message, _, chat_id, check, queued, title, user, streamtype, videoid, status):
    button = stream_markup(_, chat_id)
    
    if "live_" in queued:
        n, link = await YouTube.video(videoid, True)
        if n == 0:
            return await message.reply_text(_["admin_7"].format(title))
        
        try:
            await StreamController.skip_stream(chat_id, link, video=status)
        except:
            return await message.reply_text(_["call_6"])
        
        img = await get_thumb(videoid)
        run = await message.reply_photo(
            photo=img,
            caption=_["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            ),
            reply_markup=InlineKeyboardMarkup(button),
        )
        set_current_message(chat_id, run, "tg")
    
    elif "vid_" in queued:
        mystic = await message.reply_text(_["call_7"], disable_web_page_preview=True)
        try:
            file_path, direct = await YouTube.download(
                videoid,
                mystic,
                videoid=True,
                video=status,
                title=title,
            )
        except:
            return await mystic.edit_text(_["call_6"])
        
        try:
            await StreamController.skip_stream(chat_id, file_path, video=status)
        except:
            return await mystic.edit_text(_["call_6"])
        
        img = await get_thumb(videoid)
        run = await message.reply_photo(
            photo=img,
            caption=_["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            ),
            reply_markup=InlineKeyboardMarkup(button),
        )
        set_current_message(chat_id, run, "stream")
        await mystic.delete()
    
    elif "index_" in queued:
        try:
            await StreamController.skip_stream(chat_id, videoid, video=status)
        except:
            return await message.reply_text(_["call_6"])
        
        run = await message.reply_photo(
            photo=config.STREAM_IMG_URL,
            caption=_["stream_2"].format(user),
            reply_markup=InlineKeyboardMarkup(button),
        )
        set_current_message(chat_id, run, "tg")
    
    else:
        try:
            await StreamController.skip_stream(chat_id, queued, video=status)
        except:
            return await message.reply_text(_["call_6"])
        
        if videoid == "telegram":
            photo = config.TELEGRAM_AUDIO_URL if str(streamtype) == "audio" else config.TELEGRAM_VIDEO_URL
            caption = _["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user)
            msg_type = "tg"
        elif videoid == "soundcloud":
            thumb_source = queued if is_soundcloud_url(queued) else (videoid if is_soundcloud_url(videoid) else "soundcloud")
            photo = await get_thumb(thumb_source)
            caption = _["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user)
            msg_type = "tg"
        else:
            photo = await get_thumb(videoid)
            caption = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            )
            msg_type = "stream"
        
        run = await message.reply_photo(
            photo=photo,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(button),
        )
        set_current_message(chat_id, run, msg_type)


@app.on_message(
    filters.command(["skip", "cskip", "next", "cnext"], prefixes=["/", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def skip(cli, message: Message, _, chat_id):
    if len(message.command) >= 2:
        state = message.text.split(None, 1)[1].strip()
        if not state.isnumeric():
            return await message.reply_text(_["admin_9"])
        
        stopped = await skip_multiple_tracks(message, _, chat_id, int(state))
        if stopped:
            return
        # If skip_multiple_tracks returned False, it already popped N items
        # Continue to play the next track (which is now at index 0)
    
    check = db.get(chat_id)
    if not check:
        return await message.reply_text(_["queue_2"])
    
    # Only pop if we didn't use skip_multiple_tracks (simple /skip command)
    if len(message.command) < 2:
        try:
            popped = check.pop(0)
            if popped:
                await auto_clean(popped)
            if not check:
                await stop_stream_on_empty(message, _, chat_id)
                return
        except:
            await stop_stream_on_empty(message, _, chat_id)
            return
    
    queued = check[0]["file"]
    title = check[0]["title"].title()
    user = check[0]["by"]
    streamtype = check[0]["streamtype"]
    videoid = check[0]["vidid"]
    status = True if str(streamtype) == "video" else None
    
    db[chat_id][0]["played"] = 0
    exis = check[0].get("old_dur")
    if exis:
        db[chat_id][0]["dur"] = exis
        db[chat_id][0]["seconds"] = check[0]["old_second"]
        db[chat_id][0]["speed_path"] = None
        db[chat_id][0]["speed"] = 1.0
    
    await send_stream_message(message, _, chat_id, check, queued, title, user, streamtype, videoid, status)
