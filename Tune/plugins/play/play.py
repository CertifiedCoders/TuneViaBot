# Authored By Certified Coders © 2025

import asyncio
import random
import string

from pyrogram import filters
from pyrogram.errors import FloodWait, RandomIdDuplicate
from pyrogram.types import InlineKeyboardMarkup, InputMediaPhoto, Message
from pytgcalls.exceptions import NoActiveGroupCall

import config
from config import AYU, BANNED_USERS, lyrical
from Tune import Apple, SoundCloud, Spotify, Telegram, YouTube, app
from Tune.core.call import StreamController
from Tune.utils import seconds_to_min, time_to_seconds
from Tune.utils.channelplay import get_channeplayCB
from Tune.utils.decorators.language import languageCB
from Tune.utils.decorators.play import PlayWrapper
from Tune.utils.errors import capture_err, capture_callback_err
from Tune.utils.formatters import formats
from Tune.utils.inline import (
    botplaylist_markup,
    livestream_markup,
    playlist_markup,
    slider_markup,
    track_markup,
)
from Tune.utils.logger import play_logs
from Tune.utils.stream.stream import stream


async def _create_mystic_message(message_or_callback, channel, _):
    text = _["play_2"].format(channel) if channel else random.choice(AYU)
    try:
        return await message_or_callback.reply_text(text)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await message_or_callback.reply_text(text)
    except RandomIdDuplicate:
        chat_id = message_or_callback.message.chat.id if hasattr(message_or_callback, 'message') else message_or_callback.chat.id
        return await app.send_message(chat_id, text)


def _format_error(e, _):
    return e if type(e).__name__ == "AssistantErr" else _["general_2"].format(type(e).__name__)


async def _handle_stream_error(_, mystic, e):
    err = _format_error(e, _) or _["general_2"].format(type(e).__name__)
    return await mystic.edit_text(err)


def _check_duration_limit(duration_sec):
    return duration_sec and duration_sec > config.DURATION_LIMIT


async def _process_telegram_audio(_, message, mystic, user_id, user_name, chat_id, fplay):
    audio_telegram = (
        (message.reply_to_message.audio or message.reply_to_message.voice)
        if message.reply_to_message
        else None
    )
    if not audio_telegram:
        return False

    if audio_telegram.file_size > config.TG_AUDIO_FILESIZE_LIMIT:
        await mystic.edit_text(_["play_5"])
        return True

    if audio_telegram.duration > config.DURATION_LIMIT:
        await mystic.edit_text(_["play_6"].format(config.DURATION_LIMIT_MIN, app.mention))
        return True

    file_path = await Telegram.get_filepath(audio=audio_telegram)
    downloaded = await Telegram.download(_, message, mystic, file_path)
    if not downloaded:
        return True

    message_link = await Telegram.get_link(message)
    file_name = await Telegram.get_filename(audio_telegram, audio=True)
    dur = await Telegram.get_duration(audio_telegram, file_path)

    details = {
        "title": file_name,
        "link": message_link,
        "path": file_path,
        "dur": dur,
    }

    try:
        await stream(
            _,
            mystic,
            user_id,
            details,
            chat_id,
            user_name,
            message.chat.id,
            streamtype="telegram",
            forceplay=bool(fplay),
        )
    except Exception as e:
        await _handle_stream_error(_, mystic, e)
        return True

    caption_query = message.reply_to_message.caption or "—"
    await play_logs(message, streamtype="Telegram [Audio]", query=caption_query)
    await mystic.delete()
    return True


async def _process_telegram_video(_, message, mystic, user_id, user_name, chat_id, fplay):
    video_telegram = (
        (message.reply_to_message.video or message.reply_to_message.document)
        if message.reply_to_message
        else None
    )
    if not video_telegram:
        return False

    if message.reply_to_message.document:
        try:
            ext = (video_telegram.file_name or "").split(".")[-1]
            if ext.lower() not in formats:
                await mystic.edit_text(_["play_7"].format(" | ".join(formats)))
                return True
        except Exception:
            await mystic.edit_text(_["play_7"].format(" | ".join(formats)))
            return True

    if video_telegram.file_size > config.TG_VIDEO_FILESIZE_LIMIT:
        await mystic.edit_text(_["play_8"])
        return True

    file_path = await Telegram.get_filepath(video=video_telegram)
    downloaded = await Telegram.download(_, message, mystic, file_path)
    if not downloaded:
        return True

    message_link = await Telegram.get_link(message)
    file_name = await Telegram.get_filename(video_telegram)
    dur = await Telegram.get_duration(video_telegram, file_path)

    details = {
        "title": file_name,
        "link": message_link,
        "path": file_path,
        "dur": dur,
    }

    try:
        await stream(
            _,
            mystic,
            user_id,
            details,
            chat_id,
            user_name,
            message.chat.id,
            video=True,
            streamtype="telegram",
            forceplay=bool(fplay),
        )
    except Exception as e:
        await _handle_stream_error(_, mystic, e)
        return True

    caption_query = message.reply_to_message.caption or "—"
    await play_logs(message, streamtype="Telegram [Video]", query=caption_query)
    await mystic.delete()
    return True


@app.on_message(
    filters.command(
        [
            "play",
            "vplay",
            "cplay",
            "cvplay",
            "playforce",
            "vplayforce",
            "cplayforce",
            "cvplayforce",
        ]
    )
    & filters.group
    & ~BANNED_USERS
)
@PlayWrapper
@capture_err
async def play_command(
    client,
    message: Message,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):
    mystic = await _create_mystic_message(message, channel, _)

    plist_id, plist_type, spotify, slider = None, None, None, None
    internal_type, log_label = None, None
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    if await _process_telegram_audio(_, message, mystic, user_id, user_name, chat_id, fplay):
        return

    if await _process_telegram_video(_, message, mystic, user_id, user_name, chat_id, fplay):
        return

    if url:
        if await YouTube.exists(url):
            if "playlist" in url:
                try:
                    details = await YouTube.playlist(url, config.PLAYLIST_FETCH_LIMIT, user_id)
                except Exception as e:
                    return await mystic.edit_text(f"{_['play_3']}\nʀᴇᴀsᴏɴ: {e}")

                plist_type = "yt"
                plist_id = (url.split("="))[1].split("&")[0] if "&" in url else (url.split("="))[1]
                img = config.PLAYLIST_IMG_URL
                cap = _["play_9"]
                internal_type = "playlist"
                log_label = "Youtube playlist"
            else:
                # Check if it's a live stream
                is_live = await YouTube.is_live(url)
                try:
                    if is_live:
                        # Use live_track() for live videos
                        details, track_id = await YouTube.live_track(url)
                    else:
                        # Use regular track() for normal videos
                        details, track_id = await YouTube.track(url)
                except Exception as e:
                    return await mystic.edit_text(f"{_['play_3']}\nʀᴇᴀsᴏɴ: {e}")

                img = details["thumb"]
                u = url.lower()
                
                # Handle live streams
                if is_live:
                    internal_type = "live"
                    log_label = "Youtube Live Stream"
                    cap = _["play_10"].format(details["title"], "Live Track")
                else:
                    internal_type = "youtube"
                    log_label = "Youtube shorts" if "youtube.com/shorts/" in u else "Youtube Track"
                    cap = _["play_10"].format(details["title"], details.get("duration_min", "Unknown"))

        elif await Spotify.valid(url):
            spotify = True
            if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
                return await mystic.edit_text("»  sᴘᴏᴛɪғʏ ɪs ɴᴏᴛ sᴜᴘᴘᴏʀᴛᴇᴅ ʏᴇᴛ.\n\nᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.")

            if "track" in url:
                try:
                    details, track_id = await Spotify.track(url)
                except Exception as e:
                    return await mystic.edit_text(f"{_['play_3']}\nʀᴇᴀsᴏɴ: {e}")

                img = details["thumb"]
                cap = _["play_10"].format(details["title"], details["duration_min"])
                internal_type = "youtube"
                log_label = "Spotify Track"

            elif "playlist" in url:
                try:
                    details, plist_id = await Spotify.playlist(url)
                except Exception as e:
                    return await mystic.edit_text(f"{_['play_3']}\nʀᴇᴀsᴏɴ: {e}")

                plist_type = "spplay"
                img = config.SPOTIFY_PLAYLIST_IMG_URL
                cap = _["play_11"].format(app.mention, message.from_user.mention)
                internal_type = "playlist"
                log_label = "Spotify playlist"

            elif "album" in url:
                try:
                    details, plist_id = await Spotify.album(url)
                except Exception as e:
                    return await mystic.edit_text(f"{_['play_3']}\nʀᴇᴀsᴏɴ: {e}")

                plist_type = "spalbum"
                img = config.SPOTIFY_ALBUM_IMG_URL
                cap = _["play_11"].format(app.mention, message.from_user.mention)
                internal_type = "playlist"
                log_label = "Spotify album"

            elif "artist" in url:
                try:
                    details, plist_id = await Spotify.artist(url)
                except Exception as e:
                    return await mystic.edit_text(f"{_['play_3']}\nʀᴇᴀsᴏɴ: {e}")

                plist_type = "spartist"
                img = config.SPOTIFY_ARTIST_IMG_URL
                cap = _["play_11"].format(message.from_user.first_name)
                internal_type = "playlist"
                log_label = "Spotify artist"

            else:
                return await mystic.edit_text(_["play_15"])

        elif await Apple.valid(url):
            if "album" in url or "/song/" in url:
                try:
                    details, track_id = await Apple.track(url)
                except Exception as e:
                    return await mystic.edit_text(f"{_['play_3']}\nʀᴇᴀsᴏɴ: {e}")

                img = details["thumb"]
                cap = _["play_10"].format(details["title"], details["duration_min"])
                internal_type = "youtube"
                log_label = "Apple Music"

            elif "playlist" in url:
                spotify = True
                try:
                    details, plist_id = await Apple.playlist(url)
                except Exception as e:
                    return await mystic.edit_text(f"{_['play_3']}\nʀᴇᴀsᴏɴ: {e}")

                plist_type = "apple"
                img = url
                cap = _["play_12"].format(app.mention, message.from_user.mention)
                internal_type = "playlist"
                log_label = "Apple Music playlist"

            else:
                return await mystic.edit_text(_["play_3"])

        elif await SoundCloud.valid(url):
            if await SoundCloud.is_playlist(url):
                try:
                    details = await SoundCloud.playlist(url, config.PLAYLIST_FETCH_LIMIT, user_id)
                except Exception as e:
                    return await mystic.edit_text(f"{_['play_3']}\nʀᴇᴀsᴏɴ: {e}")

                plist_type = "scplay"
                plist_id = url
                img = config.PLAYLIST_IMG_URL
                cap = _["play_9"]
                internal_type = "playlist"
                log_label = "SoundCloud playlist"
            else:
                try:
                    result = await SoundCloud.download(url)
                    if result is False or not isinstance(result, tuple):
                        return await mystic.edit_text(_["play_3"])
                    details, track_path = result
                except Exception as e:
                    return await mystic.edit_text(f"{_['play_3']}\nʀᴇᴀsᴏɴ: {e}")

                if not details or details.get("duration_sec", 0) > config.DURATION_LIMIT:
                    return await mystic.edit_text(_["play_6"].format(config.DURATION_LIMIT_MIN, app.mention))

                try:
                    internal_type = "soundcloud"
                    await stream(
                        _,
                        mystic,
                        user_id,
                        details,
                        chat_id,
                        user_name,
                        message.chat.id,
                        streamtype=internal_type,
                        forceplay=bool(fplay),
                    )
                except Exception as e:
                    await _handle_stream_error(_, mystic, e)
                    return

                await play_logs(message, streamtype="Soundcloud")
                return await mystic.delete()

        else:
            try:
                await StreamController.stream_call(url)
            except NoActiveGroupCall:
                await mystic.edit_text(_["black_9"])
                return await app.send_message(chat_id=config.LOGGER_ID, text=_["play_17"])
            except Exception as e:
                return await mystic.edit_text(_["general_2"].format(type(e).__name__))

            try:
                await mystic.edit_text(_["str_2"])
            except Exception:
                pass

            try:
                internal_type = "index"
                await stream(
                    _,
                    mystic,
                    user_id,
                    url,
                    chat_id,
                    user_name,
                    message.chat.id,
                    video=bool(video),
                    streamtype=internal_type,
                    forceplay=bool(fplay),
                )
            except Exception as e:
                await _handle_stream_error(_, mystic, e)
                return

            return await play_logs(message, streamtype="M3U8 or Index Link")

    else:
        if len(message.command) < 2:
            buttons = botplaylist_markup(_)
            return await mystic.edit_text(_["play_18"], reply_markup=InlineKeyboardMarkup(buttons))

        slider = True
        query = message.text.split(None, 1)[1]
        if "-v" in query:
            query = query.replace("-v", "")

        try:
            details, track_id = await YouTube.track(query)
        except Exception as e:
            return await mystic.edit_text(f"{_['play_3']}\nʀᴇᴀsᴏɴ: {e}")

        internal_type = "youtube"
        log_label = "Youtube Track"

    if str(playmode) == "Direct":
        if not plist_type:
            # Check if it's a live stream (internal_type is already set)
            if internal_type == "live":
                # Live streams don't need duration check, proceed directly
                pass
            elif details.get("duration_min"):
                duration_sec = time_to_seconds(details["duration_min"])
                if _check_duration_limit(duration_sec):
                    return await mystic.edit_text(_["play_6"].format(config.DURATION_LIMIT_MIN, app.mention))
            else:
                buttons = livestream_markup(
                    _,
                    track_id,
                    user_id,
                    "v" if video else "a",
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                return await mystic.edit_text(_["play_13"], reply_markup=InlineKeyboardMarkup(buttons))

        try:
            await stream(
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,
                video=bool(video),
                streamtype=internal_type,
                spotify=spotify,
                forceplay=bool(fplay),
            )
        except Exception as e:
            await _handle_stream_error(_, mystic, e)
            return

        await mystic.delete()
        return await play_logs(message, streamtype=log_label)

    else:
        if plist_type:
            ran_hash = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
            lyrical[ran_hash] = plist_id
            buttons = playlist_markup(_, ran_hash, user_id, plist_type, "c" if channel else "g", "f" if fplay else "d")
            await mystic.delete()
            photo = details["thumb"] if plist_type == "yt" else (details if plist_type == "apple" else img)
            await message.reply_photo(photo=photo, caption=cap, reply_markup=InlineKeyboardMarkup(buttons))
            plist_label_map = {
                "yt": "Youtube playlist",
                "scplay": "SoundCloud playlist",
                "spplay": "Spotify playlist",
                "spalbum": "Spotify album",
                "spartist": "Spotify artist",
                "apple": "Apple Music playlist",
            }
            return await play_logs(message, streamtype=plist_label_map.get(plist_type, "Playlist"))

        else:
            if slider:
                buttons = slider_markup(_, track_id, user_id, query, 0, "c" if channel else "g", "f" if fplay else "d")
                await mystic.delete()
                await message.reply_photo(
                    photo=details["thumb"],
                    caption=_["play_10"].format(details["title"].title(), details["duration_min"]),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype="Searched on YouTube")

            else:
                buttons = track_markup(_, track_id, user_id, "c" if channel else "g", "f" if fplay else "d")
                await mystic.delete()
                await message.reply_photo(
                    photo=details["thumb"],
                    caption=_["play_10"].format(details["title"], details["duration_min"]),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype="URL Search Inline")


@app.on_callback_query(filters.regex("MusicStream") & ~BANNED_USERS)
@languageCB
@capture_callback_err
async def play_music(client, CallbackQuery, _):
    try:
        callback_data = CallbackQuery.data.split(None, 1)[1]
        vidid, user_id, mode, cplay, fplay = callback_data.split("|")

        if CallbackQuery.from_user.id != int(user_id):
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)

        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
        user_name = CallbackQuery.from_user.first_name
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()

        mystic = await _create_mystic_message(CallbackQuery.message, channel, _)

        details, track_id = await YouTube.track(vidid, videoid=vidid)

        if details.get("duration_min"):
            duration_sec = time_to_seconds(details["duration_min"])
            if _check_duration_limit(duration_sec):
                return await mystic.edit_text(_["play_6"].format(config.DURATION_LIMIT_MIN, app.mention))
        else:
            buttons = livestream_markup(_, track_id, CallbackQuery.from_user.id, mode, "c" if cplay == "c" else "g", "f" if fplay else "d")
            return await mystic.edit_text(_["play_13"], reply_markup=InlineKeyboardMarkup(buttons))

        video = mode == "v"
        forceplay = fplay == "f"

        await stream(
            _,
            mystic,
            CallbackQuery.from_user.id,
            details,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            bool(video),
            streamtype="youtube",
            forceplay=bool(forceplay),
        )

        await mystic.delete()

    except Exception as e:
        err = _format_error(e, _)
        return await CallbackQuery.message.reply_text(err)


@app.on_callback_query(filters.regex("AnonymousAdmin") & ~BANNED_USERS)
@capture_callback_err
async def anonymous_check(client, CallbackQuery):
    try:
        await CallbackQuery.answer(
            "» ʀᴇᴠᴇʀᴛ ʙᴀᴄᴋ ᴛᴏ ᴜsᴇʀ ᴀᴄᴄᴏᴜɴᴛ :\n\n"
            "ᴏᴘᴇɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ sᴇᴛᴛɪɴɢs.\n"
            "-> ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs\n-> ᴄʟɪᴄᴋ ᴏɴ ʏᴏᴜʀ ɴᴀᴍᴇ\n"
            "-> ᴜɴᴄʜᴇᴄᴋ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴs.",
            show_alert=True,
        )
    except Exception:
        pass


@app.on_callback_query(filters.regex("TuneViaPlaylists") & ~BANNED_USERS)
@languageCB
@capture_callback_err
async def play_playlists_command(client, CallbackQuery, _):
    try:
        callback_data = CallbackQuery.data.split(None, 1)[1]
        videoid, user_id, ptype, mode, cplay, fplay = callback_data.split("|")

        if CallbackQuery.from_user.id != int(user_id):
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)

        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
        user_name = CallbackQuery.from_user.first_name
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()

        mystic = await _create_mystic_message(CallbackQuery.message, channel, _)

        videoid = lyrical.get(videoid)
        video = mode == "v"
        forceplay = fplay == "f"
        spotify = True

        if ptype == "yt":
            spotify = False
            result = await YouTube.playlist("", config.PLAYLIST_FETCH_LIMIT, CallbackQuery.from_user.id, videoid=videoid)
            internal_type = "playlist"
            log_label = "Youtube playlist"
        elif ptype == "scplay":
            spotify = False
            result = await SoundCloud.playlist(videoid, config.PLAYLIST_FETCH_LIMIT, CallbackQuery.from_user.id)
            internal_type = "playlist"
            log_label = "SoundCloud playlist"
        elif ptype == "spplay":
            result, _ = await Spotify.playlist(videoid)
            internal_type = "playlist"
            log_label = "Spotify playlist"
        elif ptype == "spalbum":
            result, _ = await Spotify.album(videoid)
            internal_type = "playlist"
            log_label = "Spotify album"
        elif ptype == "spartist":
            result, _ = await Spotify.artist(videoid)
            internal_type = "playlist"
            log_label = "Spotify artist"
        elif ptype == "apple":
            result, _ = await Apple.playlist(videoid, True)
            internal_type = "playlist"
            log_label = "Apple Music playlist"
        else:
            return

        await stream(
            _,
            mystic,
            CallbackQuery.from_user.id,
            result,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            bool(video),
            streamtype=internal_type,
            spotify=spotify,
            forceplay=bool(forceplay),
        )

        await play_logs(CallbackQuery.message, streamtype=log_label)
        await mystic.delete()

    except Exception as e:
        err = _format_error(e, _)
        return await CallbackQuery.message.reply_text(err)


@app.on_callback_query(filters.regex("slider") & ~BANNED_USERS)
@languageCB
@capture_callback_err
async def slider_queries(client, CallbackQuery, _):
    try:
        callback_data = CallbackQuery.data.split(None, 1)[1]
        what, rtype, query, user_id, cplay, fplay = callback_data.split("|")

        if CallbackQuery.from_user.id != int(user_id):
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)

        rtype = int(rtype)
        query_type = (rtype + 1) if what == "F" else (rtype - 1)

        if query_type > 9:
            query_type = 0
        if query_type < 0:
            query_type = 9

        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)

        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        med = InputMediaPhoto(media=thumbnail, caption=_["play_10"].format(title.title(), duration_min))

        await CallbackQuery.edit_message_media(media=med, reply_markup=InlineKeyboardMarkup(buttons))
        await CallbackQuery.answer(_["playcb_2"])

    except Exception:
        pass
