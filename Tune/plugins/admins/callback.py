import asyncio
import random

from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

import config
from config import (
    BANNED_USERS,
    SOUNCLOUD_IMG_URL,
    STREAM_IMG_URL,
    SUPPORT_CHAT,
    TELEGRAM_AUDIO_URL,
    TELEGRAM_VIDEO_URL,
    adminlist,
    confirmer,
    votemode,
)
from strings import get_string
from Tune import YouTube, app
from Tune.core.call import Jarvis
from Tune.misc import SUDOERS, db
from Tune.utils.database import (
    get_active_chats,
    get_assistant,
    get_lang,
    get_upvote_count,
    is_active_chat,
    is_music_playing,
    is_muted,
    is_nonadmin_chat,
    music_off,
    music_on,
    mute_off,
    mute_on,
    set_loop,
)
from Tune.utils.decorators.language import languageCB
from Tune.utils.formatters import seconds_to_min
from Tune.utils.inline import close_markup, stream_markup, stream_markup_timer
from Tune.utils.stream.autoclear import auto_clean
from Tune.utils.thumbnails import get_thumb

checker = {}
upvoters = {}


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
            "Fᴀɪʟʟᴇᴅ ᴛᴏ ᴜɴʙᴀɴ ᴍʏ ᴀssɪssᴛᴀɴᴛ ʙᴇᴄᴀᴜsᴇ ɪ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ʙᴀɴ ᴘᴏᴡᴇʀ\n\n➻ Pʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴍᴇ ʙᴀɴ ᴘᴏᴡᴇʀ sᴏ ᴛʜᴀᴛ ɪ ᴄᴀɴ ᴜɴʙᴀɴ ᴍʏ ᴀssɪssᴛᴀɴᴛ ɪᴅ",
            show_alert=True,
        )


@app.on_callback_query(filters.regex("ADMIN") & ~BANNED_USERS)
@languageCB
async def manage_callback(client, callback: CallbackQuery, _):
    callback_data = callback.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    command, chat_info = callback_request.split("|")

    counter = None
    if "_" in str(chat_info):
        parts = chat_info.split("_")
        chat = parts[0]
        counter = parts[1]
    else:
        chat = chat_info
    chat_id = int(chat)

    if not await is_active_chat(chat_id):
        return await callback.answer(_["general_5"], show_alert=True)

    user_mention = callback.from_user.mention

    if command == "UpVote":
        if chat_id not in votemode:
            votemode[chat_id] = {}
        if chat_id not in upvoters:
            upvoters[chat_id] = {}

        message_id = callback.message.id
        if message_id not in upvoters[chat_id]:
            upvoters[chat_id][message_id] = []
        if message_id not in votemode[chat_id]:
            votemode[chat_id][message_id] = 0

        if callback.from_user.id in upvoters[chat_id][message_id]:
            upvoters[chat_id][message_id].remove(callback.from_user.id)
            votemode[chat_id][message_id] -= 1
        else:
            upvoters[chat_id][message_id].append(callback.from_user.id)
            votemode[chat_id][message_id] += 1

        required_upvotes = await get_upvote_count(chat_id)
        current_upvotes = int(votemode[chat_id][message_id])
        if current_upvotes >= required_upvotes:
            votemode[chat_id][message_id] = required_upvotes
            try:
                exists = confirmer[chat_id][message_id]
                current = db[chat_id][0]
            except Exception:
                return await callback.edit_message_text("ғᴀɪʟᴇᴅ.")
            try:
                if (
                    current["vidid"] != exists["vidid"]
                    or current["file"] != exists["file"]
                ):
                    return await callback.edit_message_text(_["admin_35"])
            except Exception:
                return await callback.edit_message_text(_["admin_36"])
            try:
                await callback.edit_message_text(_["admin_37"].format(required_upvotes))
            except Exception:
                pass
            command = counter if counter is not None else command
            user_mention = "ᴜᴘᴠᴏᴛᴇs"
        else:
            if callback.from_user.id in upvoters[chat_id][message_id]:
                await callback.answer(_["admin_38"], show_alert=True)
            else:
                await callback.answer(_["admin_39"], show_alert=True)
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=f"👍 {current_upvotes}",
                            callback_data=f"ADMIN  UpVote|{chat_id}_{counter if counter is not None else chat_id}",
                        )
                    ]
                ]
            )
            await callback.answer(_["admin_40"], show_alert=True)
            return await callback.edit_message_reply_markup(reply_markup=upl)
    else:
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        if not is_non_admin and callback.from_user.id not in SUDOERS:
            admins = adminlist.get(callback.message.chat.id)
            if not admins:
                return await callback.answer(_["admin_13"], show_alert=True)
            if callback.from_user.id not in admins:
                return await callback.answer(_["admin_14"], show_alert=True)

    if command == "Pause":
        if not await is_music_playing(chat_id):
            return await callback.answer(_["admin_1"], show_alert=True)
        await callback.answer()
        await music_off(chat_id)
        await Jarvis.pause_stream(chat_id)
        await callback.message.reply_text(
            _["admin_2"].format(user_mention), reply_markup=close_markup(_)
        )

    elif command == "Resume":
        if await is_music_playing(chat_id):
            return await callback.answer(_["admin_3"], show_alert=True)
        await callback.answer()
        await music_on(chat_id)
        await Jarvis.resume_stream(chat_id)
        await callback.message.reply_text(
            _["admin_4"].format(user_mention), reply_markup=close_markup(_)
        )

    elif command in ["Stop", "End"]:
        await callback.answer()
        await Jarvis.stop_stream(chat_id)
        await set_loop(chat_id, 0)
        await callback.message.reply_text(
            _["admin_5"].format(user_mention), reply_markup=close_markup(_)
        )
        await callback.message.delete()

    elif command == "Mute":
        if await is_muted(chat_id):
            return await callback.answer(_["admin_45"], show_alert=True)
        await callback.answer()
        await mute_on(chat_id)
        await Jarvis.mute_stream(chat_id)
        await callback.message.reply_text(_["admin_46"].format(user_mention))

    elif command == "Unmute":
        if not await is_muted(chat_id):
            return await callback.answer(_["admin_47"], show_alert=True)
        await callback.answer()
        await mute_off(chat_id)
        await Jarvis.unmute_stream(chat_id)
        await callback.message.reply_text(_["admin_48"].format(user_mention))

    elif command == "Loop":
        await callback.answer()
        await set_loop(chat_id, 3)
        await callback.message.reply_text(_["admin_41"].format(user_mention, 3))

    elif command == "Shuffle":
        playlist = db.get(chat_id)
        if not playlist:
            return await callback.answer(_["admin_42"], show_alert=True)
        try:
            popped = playlist.pop(0)
        except Exception:
            return await callback.answer(_["admin_43"], show_alert=True)
        playlist = db.get(chat_id)
        if not playlist:
            playlist.insert(0, popped)
            return await callback.answer(_["admin_43"], show_alert=True)
        await callback.answer()
        random.shuffle(playlist)
        playlist.insert(0, popped)
        await callback.message.reply_text(_["admin_44"].format(user_mention))

    elif command in ["Skip", "Replay"]:
        playlist = db.get(chat_id)
        if command == "Skip":
            text_msg = f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {user_mention} 🥀"
            try:
                popped = playlist.pop(0)
                if popped:
                    await auto_clean(popped)
                if not playlist:
                    await callback.edit_message_text(
                        f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {user_mention} 🥀"
                    )
                    await callback.message.reply_text(
                        text=_["admin_6"].format(
                            user_mention, callback.message.chat.title
                        ),
                        reply_markup=close_markup(_),
                    )
                    return await Jarvis.stop_stream(chat_id)
            except Exception:
                try:
                    await callback.edit_message_text(
                        f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {user_mention} 🥀"
                    )
                    await callback.message.reply_text(
                        text=_["admin_6"].format(
                            user_mention, callback.message.chat.title
                        ),
                        reply_markup=close_markup(_),
                    )
                    return await Jarvis.stop_stream(chat_id)
                except Exception:
                    return
        else:
            text_msg = f"➻ sᴛʀᴇᴀᴍ ʀᴇ-ᴘʟᴀʏᴇᴅ 🎄\n│ \n└ʙʏ : {user_mention} 🥀"

        await callback.answer()
        if not playlist:
            return await callback.answer(_["queue_2"], show_alert=True)

        current_track = playlist[0]
        queued = current_track["file"]
        title = current_track["title"].title()
        user = current_track["by"]
        duration = current_track["dur"]
        streamtype = current_track["streamtype"]
        videoid = current_track["vidid"]
        status = True if str(streamtype) == "video" else None

        db[chat_id][0]["played"] = 0

        old_duration = current_track.get("old_dur")
        if old_duration:
            db[chat_id][0]["dur"] = old_duration
            db[chat_id][0]["seconds"] = current_track["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0

        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                return await callback.message.reply_text(
                    text=_["admin_7"].format(title),
                    reply_markup=close_markup(_),
                )
            try:
                image = await YouTube.thumbnail(videoid, True)
            except Exception:
                image = None
            try:
                await Jarvis.skip_stream(chat_id, link, video=status, image=image)
            except Exception:
                return await callback.message.reply_text(_["call_6"])
            buttons = stream_markup(_, chat_id)
            img = await get_thumb(videoid)
            run = await callback.message.reply_photo(
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    duration,
                    user,
                ),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await callback.edit_message_text(text_msg, reply_markup=close_markup(_))

        elif "vid_" in queued:
            mystic = await callback.message.reply_text(
                _["call_7"], disable_web_page_preview=True
            )
            try:
                file_path, direct = await YouTube.download(
                    videoid, mystic, videoid=True, video=status
                )
            except Exception:
                return await mystic.edit_text(_["call_6"])
            try:
                image = await YouTube.thumbnail(videoid, True)
            except Exception:
                image = None
            try:
                await Jarvis.skip_stream(chat_id, file_path, video=status, image=image)
            except Exception:
                return await mystic.edit_text(_["call_6"])
            buttons = stream_markup(_, chat_id)
            img = await get_thumb(videoid)
            run = await callback.message.reply_photo(
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    duration,
                    user,
                ),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
            await callback.edit_message_text(text_msg, reply_markup=close_markup(_))
            await mystic.delete()

        elif "index_" in queued:
            try:
                await Jarvis.skip_stream(chat_id, videoid, video=status)
            except Exception:
                return await callback.message.reply_text(_["call_6"])
            buttons = stream_markup(_, chat_id)
            run = await callback.message.reply_photo(
                photo=STREAM_IMG_URL,
                caption=_["stream_2"].format(user),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await callback.edit_message_text(text_msg, reply_markup=close_markup(_))

        else:
            if videoid in ["telegram", "soundcloud"]:
                image = None
            else:
                try:
                    image = await YouTube.thumbnail(videoid, True)
                except Exception:
                    image = None
            try:
                await Jarvis.skip_stream(chat_id, queued, video=status, image=image)
            except Exception:
                return await callback.message.reply_text(_["call_6"])
            if videoid == "telegram":
                buttons = stream_markup(_, chat_id)
                run = await callback.message.reply_photo(
                    photo=(
                        TELEGRAM_AUDIO_URL
                        if str(streamtype) == "audio"
                        else TELEGRAM_VIDEO_URL
                    ),
                    caption=_["stream_1"].format(
                        SUPPORT_CHAT, title[:23], duration, user
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            elif videoid == "soundcloud":
                buttons = stream_markup(_, chat_id)
                run = await callback.message.reply_photo(
                    photo=(
                        SOUNCLOUD_IMG_URL
                        if str(streamtype) == "audio"
                        else TELEGRAM_VIDEO_URL
                    ),
                    caption=_["stream_1"].format(
                        SUPPORT_CHAT, title[:23], duration, user
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            else:
                buttons = stream_markup(_, chat_id)
                img = await get_thumb(videoid)
                run = await callback.message.reply_photo(
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        duration,
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            await callback.edit_message_text(text_msg, reply_markup=close_markup(_))

    else:
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
        if int(command) in [1, 2]:
            duration_to_skip = 10
        else:
            duration_to_skip = 30
        duration = playing[0]["dur"]
        if int(command) in [1, 3]:
            if (duration_played - duration_to_skip) <= 10:
                bet = seconds_to_min(duration_played)
                return await callback.answer(
                    f"» ʙᴏᴛ ɪs ᴜɴᴀʙʟᴇ ᴛᴏ sᴇᴇᴋ ʙᴇᴄᴀᴜsᴇ ᴛʜᴇ ᴅᴜʀᴀᴛɪᴏɴ ᴇxᴄᴇᴇᴅs.\n\n"
                    f"ᴄᴜʀʀᴇɴᴛʟʏ ᴩʟᴀʏᴇᴅ :** {bet}** ᴍɪɴᴜᴛᴇs ᴏᴜᴛ ᴏғ **{duration}** ᴍɪɴᴜᴛᴇs.",
                    show_alert=True,
                )
            to_seek = duration_played - duration_to_skip + 1
        else:
            if (duration_seconds - (duration_played + duration_to_skip)) <= 10:
                bet = seconds_to_min(duration_played)
                return await callback.answer(
                    f"» ʙᴏᴛ ɪs ᴜɴᴀʙʟᴇ ᴛᴏ sᴇᴇᴋ ʙᴇᴄᴀᴜsᴇ ᴛʜᴇ ᴅᴜʀᴀᴛɪᴏɴ ᴇxᴄᴇᴇᴅs.\n\n"
                    f"ᴄᴜʀʀᴇɴᴛʟʏ ᴩʟᴀʏᴇᴅ :** {bet}** ᴍɪɴᴜᴛᴇs ᴏᴜᴛ ᴏғ **{duration}** ᴍɪɴᴜᴛᴇs.",
                    show_alert=True,
                )
            to_seek = duration_played + duration_to_skip + 1
        await callback.answer()
        mystic = await callback.message.reply_text(_["admin_24"])
        if "vid_" in file_path:
            n, file_path = await YouTube.video(playing[0]["vidid"], True)
            if n == 0:
                return await mystic.edit_text(_["admin_22"])
        try:
            await Jarvis.seek_stream(
                chat_id,
                file_path,
                seconds_to_min(to_seek),
                duration,
                playing[0]["streamtype"],
            )
        except Exception:
            return await mystic.edit_text(_["admin_26"])
        if int(command) in [1, 3]:
            db[chat_id][0]["played"] -= duration_to_skip
        else:
            db[chat_id][0]["played"] += duration_to_skip
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
                    await mystic.edit_reply_markup(
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                except Exception:
                    continue
            except Exception:
                continue


asyncio.create_task(markup_timer())
