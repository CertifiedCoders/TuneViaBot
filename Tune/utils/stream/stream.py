import os
from random import randint
from typing import Union

from pyrogram.types import InlineKeyboardMarkup

import config
from Tune import Carbon, YouTube, app
from Tune.core.call import Jarvis
from Tune.misc import db
from Tune.utils.database import add_active_video_chat, is_active_chat
from Tune.utils.exceptions import AssistantErr
from Tune.utils.inline import aq_markup, close_markup, stream_markup
from Tune.utils.pastebin import JarvisBin
from Tune.utils.stream.queue import put_queue, put_queue_index
from Tune.utils.thumbnails import get_thumb


async def clear_db_if_needed(chat_id: int, forceplay: bool):
    """
    If forceplay is not True, reset the chat's DB queue.
    """
    if not forceplay:
        db[chat_id] = []


async def queue_or_join(
    _,
    mystic,
    chat_id: int,
    original_chat_id: int,
    file_path_or_tag: str,
    title: str,
    duration_min: str,
    user_name: str,
    vidid_or_tag: str,
    user_id: int,
    stream_kind: str,         # "audio"/"video"
    forceplay: bool,
    streamtype: str = "",
    thumbnail: str = None
):
    """
    Unify 'if is_active_chat -> put_queue else -> Jarvis.join_call + put_queue + send UI'
    """
    if await is_active_chat(chat_id):
        # Just put the track in queue
        await put_queue(
            chat_id,
            original_chat_id,
            file_path_or_tag,
            title,
            duration_min,
            user_name,
            vidid_or_tag,
            user_id,
            stream_kind,
        )
        position = len(db.get(chat_id)) - 1
        button = aq_markup(_, chat_id)
        await app.send_message(
            chat_id=original_chat_id,
            text=_["queue_4"].format(position, title[:27], duration_min, user_name),
            reply_markup=InlineKeyboardMarkup(button),
        )
    else:
        # brand new stream in this chat
        await clear_db_if_needed(chat_id, forceplay)
        # join the voice chat
        video_bool = True if stream_kind == "video" else None
        await Jarvis.join_call(
            chat_id, original_chat_id, file_path_or_tag,
            video=video_bool, image=thumbnail
        )
        # put in queue
        await put_queue(
            chat_id,
            original_chat_id,
            file_path_or_tag,
            title,
            duration_min,
            user_name,
            vidid_or_tag,
            user_id,
            stream_kind,
            forceplay=forceplay,
        )
        # Possibly set active video chat
        if stream_kind == "video" and streamtype == "telegram":
            await add_active_video_chat(chat_id)

        # Send UI
        if streamtype == "telegram":
            # Telegram
            art = config.TELEGRAM_VIDEO_URL if stream_kind == "video" else config.TELEGRAM_AUDIO_URL
            link = file_path_or_tag  # or we might have a separate link param
            run = await app.send_photo(
                original_chat_id,
                photo=art,
                caption=_["stream_1"].format(link, title[:23], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        elif streamtype == "soundcloud":
            # soundcloud image
            run = await app.send_photo(
                original_chat_id,
                photo=config.SOUNCLOUD_IMG_URL,
                caption=_["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], duration_min, user_name
                ),
                reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        elif streamtype == "index":
            # index or m3u8
            run = await app.send_photo(
                original_chat_id,
                photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(user_name),
                reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await mystic.delete()
        else:
            # typical case (youtube, live, etc.)
            # get a thumbnail if we have a video id
            if "vid_" in file_path_or_tag or "live_" in file_path_or_tag or ".mp4" in file_path_or_tag:
                # might attempt get_thumb
                pass

            run = await app.send_photo(
                original_chat_id,
                photo=thumbnail if thumbnail else (config.TELEGRAM_AUDIO_URL if stream_kind == "audio" else config.TELEGRAM_VIDEO_URL),
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{vidid_or_tag}",
                    title[:23],
                    duration_min,
                    user_name,
                ),
                reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"


async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
):
    """
    The main stream orchestrator:
    - If playlist, handles up to PLAYLIST_FETCH_LIMIT tracks
    - Otherwise, handles single youtube, soundcloud, telegram, live, or index links
    """
    if not result:
        return

    # if forceplay => forcibly stop existing stream
    if forceplay:
        await Jarvis.force_stop_stream(chat_id)

    # --------------------------------------------------
    # 1) If 'playlist'
    # --------------------------------------------------
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0

        for search in result:
            # We handle up to PLAYLIST_FETCH_LIMIT
            if count == config.PLAYLIST_FETCH_LIMIT:
                break

            try:
                (
                    title,
                    duration_min,
                    duration_sec,
                    thumbnail,
                    vidid,
                ) = await YouTube.details(search, (False if spotify else True))
            except:
                continue
            if str(duration_min) == "None" or duration_sec > config.DURATION_LIMIT:
                continue

            # If there's an active chat, just put in queue
            # else join + queue
            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                )
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            else:
                await clear_db_if_needed(chat_id, forceplay)
                # download or get direct
                try:
                    file_path, direct = await YouTube.download(vidid, mystic, video=True if video else None, videoid=True)
                except:
                    raise AssistantErr(_["play_14"])

                await Jarvis.join_call(chat_id, original_chat_id, file_path, video=True if video else None, image=thumbnail)
                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path if direct else f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                    forceplay=forceplay,
                )
                img = await get_thumb(vidid)
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{vidid}",
                        title[:23],
                        duration_min,
                        user_name,
                    ),
                    reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

        if count == 0:
            return
        else:
            link = await JarvisBin(msg)
            lines = msg.count("\n")
            if lines >= 17:
                short_msg = "\n".join(msg.split("\n")[:17])
            else:
                short_msg = msg
            carbon = await Carbon.generate(short_msg, randint(100, 10000000))
            upl = close_markup(_)
            return await app.send_photo(
                original_chat_id,
                photo=carbon,
                caption=_["play_21"].format(position, link),
                reply_markup=upl,
            )

    # --------------------------------------------------
    # 2) Single track logic
    # --------------------------------------------------
    elif streamtype == "youtube":
        link = result["link"]
        vidid = result["vidid"]
        title = result["title"].title()
        duration_min = result["duration_min"]
        thumbnail = result["thumb"]

        # Download or direct
        try:
            file_path, direct = await YouTube.download(vidid, mystic, video=video, videoid=True)
        except:
            raise AssistantErr(_["play_14"])

        file_path_or_tag = file_path if direct else f"vid_{vidid}"
        await queue_or_join(
            _,
            mystic,
            chat_id,
            original_chat_id,
            file_path_or_tag,
            title,
            duration_min,
            user_name,
            vidid,
            user_id,
            "video" if video else "audio",
            forceplay,
            streamtype="youtube",
            thumbnail=thumbnail
        )

    elif streamtype == "soundcloud":
        file_path = result["filepath"]
        title = result["title"]
        duration_min = result["duration_min"]

        await queue_or_join(
            _,
            mystic,
            chat_id,
            original_chat_id,
            file_path,
            title,
            duration_min,
            user_name,
            "soundcloud",
            user_id,
            "audio",
            forceplay,
            streamtype="soundcloud"
        )

    elif streamtype == "telegram":
        file_path = result["path"]
        link = result["link"]
        title = result["title"].title()
        duration_min = result["dur"]
        await queue_or_join(
            _,
            mystic,
            chat_id,
            original_chat_id,
            file_path,
            title,
            duration_min,
            user_name,
            "telegram",
            user_id,
            "video" if video else "audio",
            forceplay,
            streamtype="telegram"
        )

    elif streamtype == "live":
        link = result["link"]
        vidid = result["vidid"]
        title = result["title"].title()
        thumb = result["thumb"]
        duration_min = "Live Track"

        # We get the direct link via .video or .download
        try:
            # 'live_xxx' logic below does YouTube.video
            pass
        except:
            raise AssistantErr(_["str_3"])

        # We'll unify usage
        # We'll forcibly do Jarvis.join_call or put_queue
        # But your code specifically calls YouTube.video after is_active...
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            await clear_db_if_needed(chat_id, forceplay)
            n, file_path = await YouTube.video(link)
            if n == 0:
                raise AssistantErr(_["str_3"])

            await Jarvis.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=True if video else None,
                image=thumb if thumb else None
            )
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            img = await get_thumb(vidid)
            run = await app.send_photo(
                original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    title[:23],
                    duration_min,
                    user_name,
                ),
                reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    elif streamtype == "index":
        # typical m3u8 or direct link
        link = result
        title = "ɪɴᴅᴇx ᴏʀ ᴍ3ᴜ8 ʟɪɴᴋ"
        duration_min = "00:00"

        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await mystic.edit_text(
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            await clear_db_if_needed(chat_id, forceplay)
            await Jarvis.join_call(
                chat_id,
                original_chat_id,
                link,
                video=True if video else None,
            )
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            run = await app.send_photo(
                original_chat_id,
                photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(user_name),
                reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await mystic.delete()
