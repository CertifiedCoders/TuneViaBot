# Authored By Certified Coders © 2025

import random

from pyrogram import filters

from Tune import YouTube, app
from Tune.utils.channelplay import get_channeplayCB
from Tune.utils.decorators.language import languageCB
from Tune.utils.errors import capture_callback_err
from Tune.utils.stream.stream import stream
from config import AYU, BANNED_USERS


@app.on_callback_query(filters.regex("LiveStream") & ~BANNED_USERS)
@languageCB
@capture_callback_err
async def play_live_stream(client, CallbackQuery, _):
    try:
        data = CallbackQuery.data.strip().split(None, 1)[1]
        vidid, user_id, mode, cplay, fplay = data.split("|")
    except (IndexError, ValueError):
        return

    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except Exception:
            return

    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except Exception:
        return

    is_video = (mode == "v")
    forceplay = (fplay == "f")
    user_name = CallbackQuery.from_user.first_name

    try:
        await CallbackQuery.message.delete()
    except Exception:
        pass
    try:
        await CallbackQuery.answer()
    except Exception:
        pass

    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else random.choice(AYU)
    )

    try:
        details, track_id = await YouTube.live_track("", videoid=vidid)
    except Exception as e:
        return await mystic.edit_text(f"{_['play_3']}\nʀᴇᴀsᴏɴ: {e}")

    if details.get("duration_min") is not None:
        return await mystic.edit_text("» ɴᴏᴛ ᴀ ʟɪᴠᴇ sᴛʀᴇᴀᴍ.")

    try:
        await stream(
            _,
            mystic,
            int(user_id),
            details,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            is_video,
            streamtype="live",
            forceplay=forceplay,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
        return await mystic.edit_text(err)

    await mystic.delete()
