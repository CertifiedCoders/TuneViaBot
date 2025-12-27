# Authored By Certified Coders © 2025

import asyncio
import os
from random import randint
from typing import Union

from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup

import config
from Tune import Carbon, SoundCloud, YouTube, app
from Tune.platforms.Soundcloud import is_soundcloud_url
from Tune.core.call import StreamController
from Tune.misc import db, set_current_message
from Tune.utils.database import add_active_video_chat, is_active_chat
from Tune.utils.exceptions import AssistantErr
from Tune.utils.inline import aq_markup, close_markup, stream_markup
from Tune.utils.pastebin import TuneBin
from Tune.utils.stream.queue import put_queue, put_queue_index
from Tune.utils.thumbnails import get_thumb
from Tune.utils.errors import capture_internal_err
from Tune.utils.tuning import DOWNLOAD_TIMEOUT, get_chat_semaphore, Track, LiveTrack

_active_downloads: dict[int, asyncio.Task] = {}
_downloads_lock = asyncio.Lock()


async def cancel_chat_downloads(chat_id: int):
    async with _downloads_lock:
        if chat_id in _active_downloads:
            task = _active_downloads[chat_id]
            if not task.done():
                task.cancel()
            del _active_downloads[chat_id]


def _get_file_identifier(vidid: str, file_path: str = None, direct: bool = False) -> str:
    if file_path and direct:
        return file_path
    if is_soundcloud_url(vidid):
        return vidid
    return f"vid_{vidid}"


def _format_duration(duration_min) -> str:
    return duration_min if duration_min is not None else "Live Track"


async def _download_track(_, vidid: str, mystic, is_video: bool, title: str, chat_id: int = None):
    is_soundcloud = is_soundcloud_url(vidid)
    sem = await get_chat_semaphore(chat_id) if chat_id else None
    async with sem if sem else asyncio.Lock():
        try:
            if is_soundcloud:
                result = await asyncio.wait_for(
                    SoundCloud.download(vidid),
                    timeout=DOWNLOAD_TIMEOUT
                )
                if result is False or not isinstance(result, tuple):
                    raise AssistantErr(_["play_14"])
                details_dict, file_path = result
                return file_path, True
            else:
                file_path, direct = await asyncio.wait_for(
                    YouTube.download("", mystic, video=is_video, videoid=vidid, title=title),
                    timeout=DOWNLOAD_TIMEOUT
                )
                if not file_path:
                    raise AssistantErr(_["play_14"])
                return file_path, direct
        except asyncio.TimeoutError:
            raise AssistantErr(_["play_14"])


async def _queue_and_notify(_, chat_id, original_chat_id, file_identifier, title, duration_min, user_name, vidid, user_id, stream_type):
    await put_queue(chat_id, original_chat_id, file_identifier, title, duration_min, user_name, vidid, user_id, stream_type)
    position = len(db.get(chat_id) or []) - 1
    button = aq_markup(_, chat_id)
    await app.send_message(
        chat_id=original_chat_id,
        text=_["queue_4"].format(position, title[:27], _format_duration(duration_min), user_name),
        reply_markup=InlineKeyboardMarkup(button),
    )


async def _send_stream_photo(_, original_chat_id, photo, caption, chat_id, markup="stream"):
    button = stream_markup(_, chat_id)
    run = await app.send_photo(
        original_chat_id,
        photo=photo,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(button),
        parse_mode=ParseMode.HTML,
    )
    set_current_message(chat_id, run, markup)


async def _ensure_queue_initialized(chat_id: int, forceplay: bool):
    if not forceplay:
        db[chat_id] = []


async def _handle_new_chat_stream(_, chat_id, original_chat_id, file_path, title, duration_min, user_name, vidid, user_id, stream_type, forceplay, is_video, thumbnail=None, file_identifier=None, direct=False):
    await _ensure_queue_initialized(chat_id, forceplay)
    await StreamController.join_call(chat_id, original_chat_id, file_path, video=is_video, image=thumbnail)
    if file_identifier is None:
        file_identifier = _get_file_identifier(vidid, file_path, direct) if not is_soundcloud_url(vidid) else file_path
    await put_queue(
        chat_id, original_chat_id, file_identifier, title, duration_min,
        user_name, vidid, user_id, stream_type, forceplay=forceplay
    )


async def _manage_download_task(chat_id: int, download_coro):
    download_task = asyncio.create_task(download_coro)
    async with _downloads_lock:
        _active_downloads[chat_id] = download_task
    try:
        return await download_task
    finally:
        async with _downloads_lock:
            _active_downloads.pop(chat_id, None)


@capture_internal_err
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
) -> None:
    if not result:
        return

    forceplay = bool(forceplay)
    is_video = bool(video)

    if forceplay:
        await StreamController.force_stop_stream(chat_id)

    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0
        is_chat_active = await is_active_chat(chat_id)
        first_song_played = False
        limit = min(len(result), config.PLAYLIST_FETCH_LIMIT)
        items_to_process = result[:limit]

        async def fetch_metadata(search_item):
            try:
                is_soundcloud = is_soundcloud_url(search_item)
                if is_soundcloud:
                    return await SoundCloud.details(search_item)
                else:
                    metadata = await YouTube.get_metadata(search_item, videoid=search_item if spotify and len(search_item) == 11 and search_item.replace("-", "").replace("_", "").isalnum() else None)
                    return metadata
            except Exception:
                return None

        metadata_tasks = [fetch_metadata(item) for item in items_to_process]
        metadata_results = await asyncio.gather(*metadata_tasks, return_exceptions=True)

        for search, metadata_result in zip(items_to_process, metadata_results):
            if count == config.PLAYLIST_FETCH_LIMIT:
                continue
            
            if isinstance(metadata_result, Exception) or metadata_result is None:
                continue

            if isinstance(metadata_result, tuple):
                try:
                    title, duration_min, duration_sec, thumbnail, vidid = metadata_result
                except (ValueError, TypeError):
                    continue
            else:
                if isinstance(metadata_result, (Track, LiveTrack)):
                    title = metadata_result.title
                    duration_min = metadata_result.duration_min
                    duration_sec = metadata_result.duration_sec
                    thumbnail = metadata_result.thumbnail or ""
                    vidid = metadata_result.id
                else:
                    continue

            if duration_min is None or str(duration_min) == "None":
                continue
            if duration_sec and duration_sec > config.DURATION_LIMIT:
                continue

            stream_type = "video" if is_video else "audio"
            file_identifier = vidid if is_soundcloud_url(vidid) else f"vid_{vidid}"

            if is_chat_active:
                await put_queue(
                    chat_id, original_chat_id, file_identifier, title, duration_min, user_name, vidid, user_id, stream_type
                )
                position = len(db.get(chat_id) or []) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            elif not first_song_played:
                download_coro = _download_track(_, vidid, mystic, is_video, title, chat_id)
                thumb_arg = metadata_result if isinstance(metadata_result, (Track, LiveTrack)) else vidid
                thumb_task = get_thumb(thumb_arg)
                try:
                    download_result, img = await asyncio.gather(
                        _manage_download_task(chat_id, download_coro), thumb_task, return_exceptions=False
                    )
                    file_path, direct = download_result
                except asyncio.CancelledError:
                    raise AssistantErr(_["play_14"])
                except AssistantErr:
                    raise
                except Exception:
                    raise AssistantErr(_["play_14"])

                await _handle_new_chat_stream(
                    _, chat_id, original_chat_id, file_path, title, duration_min,
                    user_name, vidid, user_id, stream_type, forceplay, is_video, thumbnail, direct=direct
                )
                info_url = vidid if is_soundcloud_url(vidid) else f"https://t.me/{app.username}?start=info_{vidid}"
                await _send_stream_photo(
                    _, original_chat_id, img,
                    _["stream_1"].format(info_url, title[:23], _format_duration(duration_min), user_name), chat_id
                )
                first_song_played = True
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} 0\n\n"
                is_chat_active = True

        if count == 0:
            raise AssistantErr(_["play_14"])
        link = await TuneBin(msg)
        lines = msg.count("\n")
        car = os.linesep.join(msg.split(os.linesep)[:17]) if lines >= 17 else msg
        try:
            carbon = await Carbon.generate(car, randint(100, 10000000))
            playlist_photo = carbon
        except Exception:
            playlist_photo = config.PLAYLIST_IMG_URL
        upl = close_markup(_)
        final_position = len(db.get(chat_id) or []) - 1
        if final_position < 0:
            final_position = 0
        return await app.send_photo(
            original_chat_id, photo=playlist_photo, caption=_["play_21"].format(final_position, link), reply_markup=upl
        )

    elif streamtype == "youtube":
        link = result["link"]
        vidid = result["vidid"]
        title = result["title"].title()
        duration_min = result.get("duration_min")
        thumbnail = result["thumb"]

        download_coro = YouTube.download("", mystic, video=is_video, videoid=vidid, title=title)
        thumb_task = get_thumb(vidid)
        try:
            download_result, img = await asyncio.gather(
                _manage_download_task(chat_id, download_coro), thumb_task, return_exceptions=False
            )
            file_path, direct = download_result
            if not file_path:
                raise AssistantErr(_["play_14"])
        except asyncio.CancelledError:
            raise AssistantErr(_["play_14"])
        except AssistantErr:
            raise
        except Exception:
            raise AssistantErr(_["play_14"])

        stream_type = "video" if is_video else "audio"
        file_identifier = _get_file_identifier(vidid, file_path, direct)

        if await is_active_chat(chat_id):
            await _queue_and_notify(
                _, chat_id, original_chat_id, file_identifier, title, duration_min, user_name, vidid, user_id, stream_type
            )
        else:
            await _handle_new_chat_stream(
                _, chat_id, original_chat_id, file_path, title, duration_min,
                user_name, vidid, user_id, stream_type, forceplay, is_video, thumbnail, direct=direct
            )
            await _send_stream_photo(
                _, original_chat_id, img,
                _["stream_1"].format(f"https://t.me/{app.username}?start=info_{vidid}", title[:23], _format_duration(duration_min), user_name),
                chat_id
            )

    elif streamtype == "soundcloud":
        file_path = result["filepath"]
        title = result["title"]
        duration_min = result["duration_min"]
        vidid = result.get("link") or "soundcloud"
        if not file_path:
            raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            await _queue_and_notify(
                _, chat_id, original_chat_id, file_path, title, duration_min, user_name, vidid, user_id, "audio"
            )
        else:
            await _handle_new_chat_stream(
                _, chat_id, original_chat_id, file_path, title, duration_min,
                user_name, vidid, user_id, "audio", forceplay, False
            )
            img = await get_thumb(vidid)
            await _send_stream_photo(
                _, original_chat_id, img,
                _["stream_1"].format(config.SUPPORT_CHAT, title[:23], _format_duration(duration_min), user_name), chat_id, "tg"
            )

    elif streamtype == "telegram":
        file_path = result["path"]
        link = result["link"]
        title = result["title"].title()
        duration_min = result["dur"]
        if not file_path:
            raise AssistantErr(_["play_14"])

        stream_type = "video" if is_video else "audio"

        if await is_active_chat(chat_id):
            await _queue_and_notify(
                _, chat_id, original_chat_id, file_path, title, duration_min, user_name, streamtype, user_id, stream_type
            )
        else:
            await _handle_new_chat_stream(
                _, chat_id, original_chat_id, file_path, title, duration_min,
                user_name, streamtype, user_id, stream_type, forceplay, is_video
            )
            if is_video:
                await add_active_video_chat(chat_id)
            photo = config.TELEGRAM_VIDEO_URL if is_video else config.TELEGRAM_AUDIO_URL
            await _send_stream_photo(
                _, original_chat_id, photo, _["stream_1"].format(link, title[:23], _format_duration(duration_min), user_name), chat_id, "tg"
            )

    elif streamtype == "live":
        link = result["link"]
        vidid = result["vidid"]
        title = result["title"].title()
        thumbnail = result["thumb"]
        duration_min = None

        if await is_active_chat(chat_id):
            await _queue_and_notify(
                _, chat_id, original_chat_id, f"live_{vidid}", title, duration_min, user_name, vidid, user_id,
                "video" if is_video else "audio"
            )
        else:
            try:
                n, file_path = await YouTube.video("", videoid=vidid)
                if n == 0 or not file_path:
                    raise AssistantErr(_["str_3"])
            except AssistantErr:
                raise
            except Exception:
                raise AssistantErr(_["str_3"])

            await _handle_new_chat_stream(
                _, chat_id, original_chat_id, file_path, title, duration_min,
                user_name, vidid, user_id, "video" if is_video else "audio", forceplay, is_video, thumbnail or None,
                file_identifier=f"live_{vidid}"
            )
            img = await get_thumb(vidid)
            await _send_stream_photo(
                _, original_chat_id, img,
                _["stream_1"].format(f"https://t.me/{app.username}?start=info_{vidid}", title[:23], _format_duration(duration_min), user_name),
                chat_id, "tg"
            )

    elif streamtype == "index":
        link = result
        title = "ɪɴᴅᴇx ᴏʀ ᴍ3ᴜ8 ʟɪɴᴋ"
        duration_min = "00:00"

        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id, original_chat_id, "index_url", title, duration_min, user_name, link,
                "video" if is_video else "audio"
            )
            position = len(db.get(chat_id) or []) - 1
            button = aq_markup(_, chat_id)
            await mystic.edit_text(
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            await _ensure_queue_initialized(chat_id, forceplay)
            await StreamController.join_call(chat_id, original_chat_id, link, video=is_video)
            await put_queue_index(
                chat_id, original_chat_id, "index_url", title, duration_min, user_name, link,
                "video" if is_video else "audio", forceplay=forceplay
            )
            await _send_stream_photo(
                _, original_chat_id, config.STREAM_IMG_URL, _["stream_2"].format(user_name), chat_id, "tg"
            )
            await mystic.delete()
