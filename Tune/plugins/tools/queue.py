# Authored By Certified Coders © 2025

import asyncio
import os

from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, InputMediaPhoto, Message

import config
from Tune import app
from Tune.misc import db
from Tune.utils import TuneBin, get_channeplayCB, seconds_to_min
from Tune.utils.database import get_cmode, is_active_chat, is_music_playing
from Tune.utils.decorators.language import language, languageCB
from Tune.utils.inline import queue_back_markup, queue_markup
from Tune.utils.thumbnails import get_thumb
from Tune.platforms.Soundcloud import is_soundcloud_url
from config import BANNED_USERS

basic = {}


def get_duration(playing):
    file_path = playing[0]["file"]
    if "index_" in file_path or "live_" in file_path:
        return "Unknown"
    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        return "Unknown"
    return "Inline"


async def _get_queue_image(file: str, videoid: str, typo: str):
    if "live_" in file:
        return await get_thumb(videoid)
    elif "vid_" in file:
        return await get_thumb(videoid)
    elif "index_" in file:
        return config.STREAM_IMG_URL
    elif videoid == "telegram":
        return config.TELEGRAM_AUDIO_URL if typo == "Audio" else config.TELEGRAM_VIDEO_URL
    elif videoid == "soundcloud":
        thumb_source = videoid if is_soundcloud_url(videoid) else "soundcloud"
        return await get_thumb(thumb_source)
    else:
        return await get_thumb(videoid)


async def _update_queue_loop(_, chat_id, videoid, DUR, cplay, mystic):
    try:
        while db[chat_id][0]["vidid"] == videoid:
            await asyncio.sleep(5)
            if not await is_active_chat(chat_id):
                break
            if not basic.get(videoid):
                break
            if not await is_music_playing(chat_id):
                continue
            try:
                buttons = queue_markup(
                    _,
                    DUR,
                    cplay,
                    videoid,
                    seconds_to_min(db[chat_id][0]["played"]),
                    db[chat_id][0]["dur"],
                )
                await mystic.edit_reply_markup(reply_markup=buttons)
            except FloodWait:
                pass
    except Exception:
        return


@app.on_message(
    filters.command(["queue", "cqueue", "player", "cplayer", "playing", "cplaying"])
    & filters.group
    & ~BANNED_USERS
)
@language
async def get_queue(client, message: Message, _):
    if message.command[0][0] == "c":
        chat_id = await get_cmode(message.chat.id)
        if chat_id is None:
            return await message.reply_text(_["setting_7"])
        try:
            await app.get_chat(chat_id)
        except Exception as e:
            return await message.reply_text(_["cplay_4"].format(e))
        cplay = True
    else:
        chat_id = message.chat.id
        cplay = False

    if not await is_active_chat(chat_id):
        return await message.reply_text(_["general_5"])

    got = db.get(chat_id)
    if not got:
        return await message.reply_text(_["queue_2"])

    file = got[0]["file"]
    videoid = got[0]["vidid"]
    user = got[0]["by"]
    title = got[0]["title"].title()
    typo = got[0]["streamtype"].title()
    DUR = get_duration(got)

    IMAGE = await _get_queue_image(file, videoid, typo)
    send = _["queue_6"] if DUR == "Unknown" else _["queue_7"]
    cap = _["queue_8"].format(app.mention, title, typo, user, send)

    cplay_str = "c" if cplay else "g"
    if DUR == "Unknown":
        upl = queue_markup(_, DUR, cplay_str, videoid)
    else:
        upl = queue_markup(_, DUR, cplay_str, videoid, seconds_to_min(got[0]["played"]), got[0]["dur"])

    basic[videoid] = True
    mystic = await message.reply_photo(IMAGE, caption=cap, reply_markup=upl)

    if DUR != "Unknown":
        await _update_queue_loop(_, chat_id, videoid, DUR, cplay_str, mystic)


@app.on_callback_query(filters.regex("GetTimer") & ~BANNED_USERS)
async def quite_timer(client, CallbackQuery: CallbackQuery):
    try:
        await CallbackQuery.answer()
    except Exception:
        pass


@app.on_callback_query(filters.regex("GetQueued") & ~BANNED_USERS)
@languageCB
async def queued_tracks(client, CallbackQuery: CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    what, videoid = callback_request.split("|")

    try:
        chat_id, channel = await get_channeplayCB(_, what, CallbackQuery)
    except Exception:
        return

    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)

    got = db.get(chat_id)
    if not got:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)

    if len(got) == 1:
        return await CallbackQuery.answer(_["queue_5"], show_alert=True)

    await CallbackQuery.answer()
    basic[videoid] = False
    buttons = queue_back_markup(_, what)
    med = InputMediaPhoto(media="https://files.catbox.moe/70ak97.jpg", caption=_["queue_1"])
    await CallbackQuery.edit_message_media(media=med)

    msg = ""
    for j, x in enumerate(got, 1):
        if j == 1:
            msg += f'Streaming :\n\n✨ Title : {x["title"]}\nDuration : {x["dur"]}\nBy : {x["by"]}\n\n'
        elif j == 2:
            msg += f'Queued :\n\n✨ Title : {x["title"]}\nDuration : {x["dur"]}\nBy : {x["by"]}\n\n'
        else:
            msg += f'✨ Title : {x["title"]}\nDuration : {x["dur"]}\nBy : {x["by"]}\n\n'

    if "Queued" in msg:
        if len(msg) < 700:
            await asyncio.sleep(1)
            return await CallbackQuery.edit_message_text(msg, reply_markup=buttons)
        if "✨" in msg:
            msg = msg.replace("✨", "")
        link = await TuneBin(msg)
        med = InputMediaPhoto(media=link, caption=_["queue_3"].format(link))
        await CallbackQuery.edit_message_media(media=med, reply_markup=buttons)
    else:
        await asyncio.sleep(1)
        return await CallbackQuery.edit_message_text(msg, reply_markup=buttons)


@app.on_callback_query(filters.regex("queue_back_timer") & ~BANNED_USERS)
@languageCB
async def queue_back(client, CallbackQuery: CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    cplay = callback_data.split(None, 1)[1]

    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except Exception:
        return

    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)

    got = db.get(chat_id)
    if not got:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)

    await CallbackQuery.answer(_["set_cb_5"], show_alert=True)

    file = got[0]["file"]
    videoid = got[0]["vidid"]
    user = got[0]["by"]
    title = got[0]["title"].title()
    typo = got[0]["streamtype"].title()
    DUR = get_duration(got)

    IMAGE = await _get_queue_image(file, videoid, typo)
    send = _["queue_6"] if DUR == "Unknown" else _["queue_7"]
    cap = _["queue_8"].format(app.mention, title, typo, user, send)

    if DUR == "Unknown":
        upl = queue_markup(_, DUR, cplay, videoid)
    else:
        upl = queue_markup(_, DUR, cplay, videoid, seconds_to_min(got[0]["played"]), got[0]["dur"])

    basic[videoid] = True
    med = InputMediaPhoto(media=IMAGE, caption=cap)
    mystic = await CallbackQuery.edit_message_media(media=med, reply_markup=upl)

    if DUR != "Unknown":
        await _update_queue_loop(_, chat_id, videoid, DUR, cplay, mystic)
