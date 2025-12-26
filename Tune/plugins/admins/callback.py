# Authored By Certified Coders © 2025

import asyncio
import random
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup
from config import (
    BANNED_USERS,
    lyrical,
    STREAM_IMG_URL,
    SUPPORT_CHAT,
    TELEGRAM_AUDIO_URL,
    TELEGRAM_VIDEO_URL,
)
from strings import get_string
from Tune import YouTube, app
from Tune.core.call import StreamController
from Tune.platforms.Soundcloud import is_soundcloud_url
from Tune.misc import db, set_current_message
from Tune.utils.database import (
    get_active_chats,
    get_assistant,
    get_lang,
    is_active_chat,
    is_music_playing,
    music_off,
    music_on,
    set_loop,
)
from Tune.utils.decorators import ActualAdminCB, languageCB
from Tune.utils.formatters import seconds_to_min
from Tune.utils.inline import close_markup, stream_markup, stream_markup_timer
from Tune.utils.stream.autoclear import auto_clean
from Tune.utils.thumbnails import get_thumb

checker = {}


def parse_chat_info(chat_info: str):
    if "_" in chat_info:
        return int(chat_info.split("_")[0])
    return int(chat_info)


async def _send_stream_message(message, _, chat_id, videoid, title, duration, user, streamtype, msg_type, queued=None):
    if videoid == "telegram":
        photo = TELEGRAM_AUDIO_URL if str(streamtype) == "audio" else TELEGRAM_VIDEO_URL
        caption = _["stream_1"].format(SUPPORT_CHAT, title[:23], duration, user)
        msg_key = "tg"
    elif videoid == "soundcloud" or is_soundcloud_url(videoid):
        thumb_source = queued if queued and is_soundcloud_url(queued) else (videoid if is_soundcloud_url(videoid) else "soundcloud")
        photo = await get_thumb(thumb_source)
        caption = _["stream_1"].format(SUPPORT_CHAT, title[:23], duration, user)
        msg_key = "tg"
    elif videoid:
        photo = await get_thumb(videoid)
        caption = _["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], duration, user)
        msg_key = msg_type
    else:
        photo = STREAM_IMG_URL
        caption = _["stream_2"].format(user)
        msg_key = "tg"
    
    buttons = stream_markup(_, chat_id)
    run = await message.reply_photo(
        photo=photo,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    set_current_message(chat_id, run, msg_key)
    return run


@app.on_callback_query(filters.regex("unban_assistant"))
async def unban_assistant(_, callback: CallbackQuery):
    chat_id = callback.message.chat.id
    userbot = await get_assistant(chat_id)
    try:
        await app.unban_chat_member(chat_id, userbot.id)
        await callback.answer(
            "ᴍʏ ᴀssɪsᴛᴀɴᴛ ɪᴅ ᴜɴʙᴀɴɴᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ🥰🥳\n\n➻ ɴᴏᴡ ʏᴏᴜ ᴄᴀɴ ᴘʟᴀʏ sᴏɴɢs🫠🔉\n\nTʜᴀɴᴋ ʏᴏᴜ💗",
            show_alert=True,
        )
    except Exception:
        await callback.answer(
            "Fᴀɪʟᴇᴅ ᴛᴏ ᴜɴʙᴀɴ ᴍʏ ᴀssɪsᴛᴀɴᴛ ʙᴇᴄᴀᴜsᴇ ɪ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ʙᴀɴ ᴘᴏᴡᴇʀ\n\n➻ Pʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴍᴇ ʙᴀɴ ᴘᴏᴡᴇʀ sᴏ ᴛʜᴀᴛ ɪ ᴄᴀɴ ᴜɴʙᴀɴ ᴍʏ ᴀssɪsᴛᴀɴᴛ ɪᴅ",
            show_alert=True,
        )


@app.on_callback_query(filters.regex("stream_admin") & ~BANNED_USERS)
@languageCB
@ActualAdminCB
async def manage_callback(client, callback: CallbackQuery, _):
    data = callback.data.strip().split(None, 1)[1]
    command, chat_info = data.split("|", 1)
    chat_id = parse_chat_info(chat_info)
    if not await is_active_chat(chat_id):
        return await callback.answer(_["general_5"], show_alert=True)
    user_mention = callback.from_user.mention
    
    if command == "Pause":
        if not await is_music_playing(chat_id):
            return await callback.answer(_["admin_1"], show_alert=True)
        await callback.answer()
        await music_off(chat_id)
        await StreamController.pause_stream(chat_id)
        await callback.message.reply_text(_["admin_2"].format(user_mention), reply_markup=close_markup(_))

    elif command == "Resume":
        if await is_music_playing(chat_id):
            return await callback.answer(_["admin_3"], show_alert=True)
        await callback.answer()
        await music_on(chat_id)
        await StreamController.resume_stream(chat_id)
        await callback.message.reply_text(_["admin_4"].format(user_mention), reply_markup=close_markup(_))

    elif command in ["Stop", "End"]:
        await callback.answer()
        await StreamController.stop_stream(chat_id)
        await set_loop(chat_id, 0)
        await callback.message.reply_text(_["admin_5"].format(user_mention), reply_markup=close_markup(_))
        await callback.message.delete()

    elif command == "Loop":
        await callback.answer()
        await set_loop(chat_id, 3)
        await callback.message.reply_text(_["admin_41"].format(user_mention, 3))

    elif command == "Shuffle":
        playlist = db.get(chat_id)
        if not playlist:
            return await callback.answer(_["admin_42"], show_alert=True)
        if len(playlist) < 2:
            return await callback.answer(_["admin_43"], show_alert=True)
        try:
            popped = playlist.pop(0)
        except Exception:
            return await callback.answer(_["admin_43"], show_alert=True)
        await callback.answer()
        random.shuffle(playlist)
        playlist.insert(0, popped)
        await callback.message.reply_text(_["admin_44"].format(user_mention))

    elif command in ["Skip", "Replay"]:
        await handle_skip_replay(callback, _, chat_id, command, user_mention)
    else:
        await handle_seek(callback, _, chat_id, command, user_mention)


async def handle_skip_replay(callback: CallbackQuery, _, chat_id: int, command: str, user_mention: str):
    playlist = db.get(chat_id)
    if not playlist:
        return await callback.answer(_["queue_2"], show_alert=True)

    if command == "Skip":
        text_msg = f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {user_mention} 🥀"
        try:
            popped = playlist.pop(0)
            if popped:
                await auto_clean(popped)
        except Exception:
            pass
        if not playlist:
            await callback.edit_message_text(text_msg)
            await callback.message.reply_text(
                _["admin_6"].format(user_mention, callback.message.chat.title),
                reply_markup=close_markup(_)
            )
            return await StreamController.stop_stream(chat_id)
    else:
        text_msg = f"➻ sᴛʀᴇᴀᴍ ʀᴇᴩʟᴀʏᴇᴅ 🎄\n│ \n└ʙʏ : {user_mention} 🥀"

    await callback.answer()

    current_track = playlist[0]
    queued = current_track["file"]
    title = current_track["title"].title()
    user = current_track["by"]
    duration = current_track["dur"]
    streamtype = current_track["streamtype"]
    videoid = current_track["vidid"]
    status = True if str(streamtype) == "video" else None

    db[chat_id][0]["played"] = 0
    if current_track.get("old_dur"):
        db[chat_id][0]["dur"] = current_track["old_dur"]
        db[chat_id][0]["seconds"] = current_track["old_second"]
        db[chat_id][0]["speed_path"] = None
        db[chat_id][0]["speed"] = 1.0

    try:
        if "live_" in queued:
            n, new_link = await YouTube.video(videoid, True)
            if n == 0:
                return await callback.message.reply_text(
                    _["admin_7"].format(title),
                    reply_markup=close_markup(_)
                )
            await StreamController.skip_stream(chat_id, new_link, video=status)
            await _send_stream_message(callback.message, _, chat_id, videoid, title, duration, user, streamtype, "tg")
            await callback.edit_message_text(text_msg, reply_markup=close_markup(_))

        elif "vid_" in queued:
            mystic = await callback.message.reply_text(_["call_7"], disable_web_page_preview=True)
            try:
                file_path, direct = await YouTube.download(
                    videoid,
                    mystic,
                    videoid=videoid,
                    video=status,
                    title=title,
                )
                if not file_path:
                    return await mystic.edit_text(_["call_6"])
                await StreamController.skip_stream(chat_id, file_path, video=status)
                await _send_stream_message(callback.message, _, chat_id, videoid, title, duration, user, streamtype, "stream")
                await callback.edit_message_text(text_msg, reply_markup=close_markup(_))
                await mystic.delete()
            except Exception:
                return await mystic.edit_text(_["call_6"])

        elif "index_" in queued:
            await StreamController.skip_stream(chat_id, videoid, video=status)
            await _send_stream_message(callback.message, _, chat_id, None, title, duration, user, streamtype, "tg")
            await callback.edit_message_text(text_msg, reply_markup=close_markup(_))

        else:
            await StreamController.skip_stream(chat_id, queued, video=status)
            msg_type = "stream" if videoid and videoid not in ["telegram", "soundcloud"] and not is_soundcloud_url(videoid) else "tg"
            await _send_stream_message(callback.message, _, chat_id, videoid, title, duration, user, streamtype, msg_type, queued)
            await callback.edit_message_text(text_msg, reply_markup=close_markup(_))
    except Exception:
        return await callback.message.reply_text(_["call_6"])


async def handle_seek(callback: CallbackQuery, _, chat_id: int, command: str, user_mention: str):
    playing = db.get(chat_id)
    if not playing:
        return await callback.answer(_["queue_2"], show_alert=True)
    
    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        return await callback.answer(_["admin_22"], show_alert=True)
    
    file_path = playing[0]["file"]
    if "index_" in file_path or "live_" in file_path:
        return await callback.answer(_["admin_22"], show_alert=True)
    
    duration_played = int(playing[0]["played"])
    command_int = int(command)
    duration_to_skip = 10 if command_int in [1, 2] else 30
    duration = playing[0]["dur"]
    is_backward = command_int in [1, 3]
    
    bet = seconds_to_min(duration_played)
    error_msg = (
        f"» ʙᴏᴛ ɪs ᴜɴᴀʙʟᴇ ᴛᴏ sᴇᴇᴋ ʙᴇᴄᴀᴜsᴇ ᴛʜᴇ ᴅᴜʀᴀᴛɪᴏɴ ᴇxᴄᴇᴇᴅs.\n\n"
        f"ᴄᴜʀʀᴇɴᴛʟʏ ᴩʟᴀʏᴇᴅ :** {bet}** ᴍɪɴᴜᴛᴇs ᴏᴜᴛ ᴏғ **{duration}** ᴍɪɴᴜᴛᴇs."
    )
    
    if is_backward:
        new_position = duration_played - duration_to_skip
        if new_position <= 10:
            return await callback.answer(error_msg, show_alert=True)
        to_seek = new_position + 1
    else:
        new_position = duration_played + duration_to_skip
        if (duration_seconds - new_position) <= 10:
            return await callback.answer(error_msg, show_alert=True)
        to_seek = new_position + 1
    
    await callback.answer()
    mystic = await callback.message.reply_text(_["admin_24"])
    
    if "vid_" in file_path:
        n, file_path = await YouTube.video(playing[0]["vidid"], True)
        if n == 0:
            return await mystic.edit_text(_["admin_22"])
    
    try:
        await StreamController.seek_stream(
            chat_id,
            file_path,
            seconds_to_min(to_seek),
            duration,
            playing[0]["streamtype"],
        )
    except Exception:
        return await mystic.edit_text(_["admin_26"])
    
    db[chat_id][0]["played"] = new_position
    seek_message = _["admin_25"].format(seconds_to_min(to_seek))
    await mystic.edit_text(f"{seek_message}\n\nᴄʜᴀɴɢᴇs ᴅᴏɴᴇ ʙʏ : {user_mention} !")


async def markup_timer():
    while True:
        await asyncio.sleep(6)
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            try:
                if not await is_music_playing(chat_id):
                    continue
                playing = db.get(chat_id)
                if not playing:
                    continue
                duration_seconds = int(playing[0]["seconds"])
                if duration_seconds == 0:
                    continue
                mystic = playing[0].get("mystic")
                if not mystic:
                    continue
                if chat_id in checker and mystic.id in checker[chat_id]:
                    if checker[chat_id][mystic.id] is False:
                        continue
                try:
                    language = await get_lang(chat_id)
                    _lang = get_string(language)
                except Exception:
                    _lang = get_string("en")
                try:
                    buttons = stream_markup_timer(
                        _lang,
                        chat_id,
                        seconds_to_min(playing[0]["played"]),
                        playing[0]["dur"],
                    )
                    await mystic.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
                except Exception:
                    continue
            except Exception:
                continue


asyncio.create_task(markup_timer())


@app.on_callback_query(filters.regex("close") & ~BANNED_USERS)
async def close_menu(_, query: CallbackQuery):
    try:
        await query.answer()
        await query.message.delete()
        msg = await query.message.reply_text(f"✅ ᴄʟᴏꜱᴇᴅ ʙʏ : {query.from_user.mention}")
        await asyncio.sleep(2)
        await msg.delete()
    except Exception:
        pass


@app.on_callback_query(filters.regex("stop_downloading") & ~BANNED_USERS)
@ActualAdminCB
async def stop_download(_, query: CallbackQuery, _lang):
    task = lyrical.get(query.message.id)
    if not task:
        return await query.answer(_lang["tg_4"], show_alert=True)
    if task.done() or task.cancelled():
        return await query.answer(_lang["tg_5"], show_alert=True)
    try:
        task.cancel()
        lyrical.pop(query.message.id, None)
        await query.answer(_lang["tg_6"], show_alert=True)
        return await query.edit_message_text(_lang["tg_7"].format(query.from_user.mention))
    except Exception:
        return await query.answer(_lang["tg_8"], show_alert=True)
