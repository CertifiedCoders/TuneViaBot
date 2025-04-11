import random
import string
import asyncio

from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message
)
from pytgcalls.exceptions import NoActiveGroupCall

import config
from config import BANNED_USERS, lyrical
from Tune import Apple, Resso, SoundCloud, Spotify, Telegram, YouTube, app
from Tune.core.call import Jarvis
from Tune.utils import seconds_to_min, time_to_seconds
from Tune.utils.channelplay import get_channeplayCB
from Tune.utils.decorators.language import languageCB
from Tune.utils.decorators.play import PlayWrapper
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


@app.on_message(
    filters.command([
        "play", "vplay", "cplay", "cvplay",
        "playforce", "vplayforce", "cplayforce", "cvplayforce"
    ])
    & filters.group
    & ~BANNED_USERS
)
@PlayWrapper
async def play_commnd(
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
    mystic = await message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )

    asyncio.create_task(
        process_playback(
            client, message, mystic, _,
            chat_id, video, channel, playmode, url, fplay
        )
    )


async def process_playback(
    client,
    message,
    mystic,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):
    plist_id = None
    slider = None
    plist_type = None
    spotify = None
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    # --------------------------------------------------
    # 1) Telegram Audio (replied audio/voice)
    # --------------------------------------------------
    audio_telegram = (
        (message.reply_to_message.audio or message.reply_to_message.voice)
        if message.reply_to_message
        else None
    )
    if audio_telegram:
        if audio_telegram.file_size > 104857600:  # 100 MB limit
            return await mystic.edit_text(_["play_5"])

        duration_min = seconds_to_min(audio_telegram.duration)
        if audio_telegram.duration > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
            )

        file_path = await Telegram.get_filepath(audio=audio_telegram)
        downloaded = await Telegram.download(_, message, mystic, file_path)
        if downloaded:
            message_link = await Telegram.get_link(message)
            file_name = await Telegram.get_filename(audio_telegram, audio=True)
            dur = await Telegram.get_duration(audio_telegram, file_path)
            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
                # You can add "thumb": "some_url" if you have a thumb
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
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
                return await mystic.edit_text(err)

            # directly convert 🦋 --> photo if you have a thumbnail
            return await convert_processing_to_photo(
                mystic,
                details.get("thumb"),  # or None
                f"**{details['title']}**\nDuration: {duration_min}"
            )
        return

    # --------------------------------------------------
    # 2) Telegram Video (replied video/document)
    # --------------------------------------------------
    video_telegram = (
        (message.reply_to_message.video or message.reply_to_message.document)
        if message.reply_to_message
        else None
    )
    if video_telegram:
        # Validate format if it's a document
        if message.reply_to_message.document:
            try:
                ext = video_telegram.file_name.split(".")[-1]
                if ext.lower() not in formats:
                    return await mystic.edit_text(
                        _["play_7"].format(f"{' | '.join(formats)}")
                    )
            except:
                return await mystic.edit_text(
                    _["play_7"].format(f"{' | '.join(formats)}")
                )

        # Check TG video file size
        if video_telegram.file_size > config.TG_VIDEO_FILESIZE_LIMIT:
            return await mystic.edit_text(_["play_8"])

        file_path = await Telegram.get_filepath(video=video_telegram)
        downloaded = await Telegram.download(_, message, mystic, file_path)
        if downloaded:
            message_link = await Telegram.get_link(message)
            file_name = await Telegram.get_filename(video_telegram)
            dur = await Telegram.get_duration(video_telegram, file_path)
            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
                # "thumb": "..." if you want
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
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
                return await mystic.edit_text(err)

            # replace 🦋 => photo
            return await convert_processing_to_photo(
                mystic,
                details.get("thumb"),
                f"**{details['title']}**\nDuration: {dur}"
            )
        return

    # --------------------------------------------------
    # 3) If user gave a direct URL (YouTube, Spotify, Apple, etc.)
    # --------------------------------------------------
    if url:
        # NOTE: 'img' and 'cap' will be used for final edits
        img = None
        cap = None

        # --- YOUTUBE URL DETECTED ---
        if await YouTube.exists(url):
            if "playlist" in url:
                try:
                    details = await YouTube.playlist(
                        url,
                        config.PLAYLIST_FETCH_LIMIT,
                        message.from_user.id,
                    )
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "yt"
                if "&" in url:
                    plist_id = (url.split("="))[1].split("&")[0]
                else:
                    plist_id = (url.split("="))[1]
                img = config.PLAYLIST_IMG_URL
                cap = _["play_9"]
            else:
                try:
                    details, track_id = await YouTube.track(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                img = details["thumb"]
                cap = _["play_10"].format(details["title"], details["duration_min"])

        # --- SPOTIFY URL DETECTED ---
        elif await Spotify.valid(url):
            spotify = True
            if not config.SPOTIFY_CLIENT_ID and not config.SPOTIFY_CLIENT_SECRET:
                return await mystic.edit_text(
                    "» sᴘᴏᴛɪғʏ ɪs ɴᴏᴛ sᴜᴘᴘᴏʀᴛᴇᴅ ʏᴇᴛ.\n\nᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ."
                )
            if "track" in url:
                try:
                    details, track_id = await Spotify.track(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                img = details["thumb"]
                cap = _["play_10"].format(details["title"], details["duration_min"])
            elif "playlist" in url:
                try:
                    details, plist_id = await Spotify.playlist(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spplay"
                img = config.SPOTIFY_PLAYLIST_IMG_URL
                cap = _["play_11"].format(app.mention, message.from_user.mention)
            elif "album" in url:
                try:
                    details, plist_id = await Spotify.album(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spalbum"
                img = config.SPOTIFY_ALBUM_IMG_URL
                cap = _["play_11"].format(app.mention, message.from_user.mention)
            elif "artist" in url:
                try:
                    details, plist_id = await Spotify.artist(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spartist"
                img = config.SPOTIFY_ARTIST_IMG_URL
                cap = _["play_11"].format(message.from_user.first_name)
            else:
                return await mystic.edit_text(_["play_15"])

        # --- APPLE URL DETECTED ---
        elif await Apple.valid(url):
            if "album" in url:
                try:
                    details, track_id = await Apple.track(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                img = details["thumb"]
                cap = _["play_10"].format(details["title"], details["duration_min"])
            elif "playlist" in url:
                spotify = True
                try:
                    details, plist_id = await Apple.playlist(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "apple"
                cap = _["play_12"].format(app.mention, message.from_user.mention)
                img = url
            else:
                return await mystic.edit_text(_["play_3"])

        # --- RESSO URL DETECTED ---
        elif await Resso.valid(url):
            try:
                details, track_id = await Resso.track(url)
            except:
                return await mystic.edit_text(_["play_3"])
            streamtype = "youtube"
            img = details["thumb"]
            cap = _["play_10"].format(details["title"], details["duration_min"])

        # --- SOUNDCLOUD URL DETECTED ---
        elif await SoundCloud.valid(url):
            try:
                details, track_path = await SoundCloud.download(url)
            except:
                return await mystic.edit_text(_["play_3"])
            duration_sec = details["duration_sec"]
            if duration_sec > config.DURATION_LIMIT:
                return await mystic.edit_text(
                    _["play_6"].format(
                        config.DURATION_LIMIT_MIN,
                        app.mention,
                    )
                )
            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype="soundcloud",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
                return await mystic.edit_text(err)

            # turn 🦋 into photo message if we have a 'thumb'
            return await convert_processing_to_photo(
                mystic,
                details.get("thumb"),
                _["play_10"].format(
                    details["title"],
                    details.get("duration_min", "Unknown"),
                )
            )

        else:
            # fallback: maybe index/m3u8 link?
            try:
                await Jarvis.stream_call(url)
            except NoActiveGroupCall:
                await mystic.edit_text(_["black_9"])
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=_["play_17"],
                )
            except Exception as e:
                return await mystic.edit_text(_["general_2"].format(type(e).__name__))

            await mystic.edit_text(_["str_2"])
            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    url,
                    chat_id,
                    user_name,
                    message.chat.id,
                    video=video,
                    streamtype="index",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
                return await mystic.edit_text(err)
            return await play_logs(message, streamtype="M3u8 or Index Link")

    else:
        # --------------------------------------------------
        # 4) No URL => parse /play <query> with FAST SEARCH
        # --------------------------------------------------
        if len(message.command) < 2:
            buttons = botplaylist_markup(_)
            return await mystic.edit_text(
                _["play_18"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )

        slider = True
        query = message.text.split(None, 1)[1]
        if "-v" in query:
            query = query.replace("-v", "")

        try:
            details, track_id = await YouTube.track(query)
        except:
            return await mystic.edit_text(_["play_3"])

        streamtype = "youtube"

    # --------------------------------------------------
    # 5) We have details from platform or text-based search
    # --------------------------------------------------
    if str(playmode) == "Direct":
        if not plist_type:
            if details.get("duration_min"):
                duration_sec = time_to_seconds(details["duration_min"])
                if duration_sec and duration_sec > config.DURATION_LIMIT:
                    return await mystic.edit_text(
                        _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
                    )
            else:
                buttons = livestream_markup(
                    _,
                    track_id,
                    user_id,
                    "v" if video else "a",
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                return await mystic.edit_text(
                    _["play_13"],
                    reply_markup=InlineKeyboardMarkup(buttons),
                )

        try:
            await stream(
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,
                video=video,
                streamtype=streamtype,
                spotify=spotify,
                forceplay=fplay,
            )
        except Exception as e:
            ex_type = type(e).__name__
            err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
            return await mystic.edit_text(err)

        # Instead of text, convert to photo
        return await convert_processing_to_photo(
            mystic,
            details.get("thumb"),
            _["play_10"].format(
                details["title"],
                details.get("duration_min", "Unknown"),
            )
        )

    else:
        # Playlist or slider flow
        if plist_type:
            ran_hash = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )
            lyrical[ran_hash] = plist_id
            buttons = playlist_markup(
                _,
                ran_hash,
                user_id,
                plist_type,
                "c" if channel else "g",
                "f" if fplay else "d",
            )
            # If you want to transform 🦋 into a photo as well:
            await mystic.edit_text("Playlist loaded - see new message!")
            await message.reply_photo(
                photo=details["thumb"] if plist_type == "yt" else (details if plist_type == "apple" else None),
                caption=cap,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return await play_logs(message, streamtype=f"Playlist : {plist_type}")

        else:
            if slider:
                buttons = slider_markup(
                    _,
                    track_id,
                    user_id,
                    query,
                    0,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                await mystic.edit_text("Slider found - see new message!")
                await message.reply_photo(
                    photo=details["thumb"],
                    caption=_["play_10"].format(
                        details["title"].title(),
                        details["duration_min"],
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype="Searched on Youtube")
            else:
                await mystic.edit_text("Single track - see new message!")
                buttons = track_markup(
                    _,
                    track_id,
                    user_id,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                await message.reply_photo(
                    photo=details["thumb"],
                    caption=_["play_10"].format(
                        details["title"],
                        details["duration_min"],
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype="URL Searched Inline")


# ------------------------------------------------------
# Convert existing text -> photo with new caption
# ------------------------------------------------------
async def convert_processing_to_photo(mystic: Message, thumb: str, caption: str):
    """
    Replaces the existing text-based message with a photo-based message.
    If no 'thumb' is provided (None), we just do .edit_text(...) fallback.
    """
    if not thumb:
        # fallback if there's no thumbnail
        return await mystic.edit_text(caption)

    try:
        return await mystic.edit_media(
            media=InputMediaPhoto(media=thumb, caption=caption)
        )
    except Exception as e:
        # if edit_media fails (e.g. invalid thumb), fallback to text
        return await mystic.edit_text(f"{caption}\n(Thumb error: {e})")


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@app.on_callback_query(filters.regex("MusicStream") & ~BANNED_USERS)
@languageCB
async def play_music(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    vidid, user_id, mode, cplay, fplay = callback_request.split("|")

    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return

    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except:
        return

    user_name = CallbackQuery.from_user.first_name

    try:
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()
    except:
        pass

    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )

    try:
        details, track_id = await YouTube.track(vidid, True)
    except:
        return await mystic.edit_text(_["play_3"])

    if details["duration_min"]:
        duration_sec = time_to_seconds(details["duration_min"])
        if duration_sec and duration_sec > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
            )
    else:
        # Possibly a livestream?
        buttons = livestream_markup(
            _,
            track_id,
            CallbackQuery.from_user.id,
            mode,
            "c" if cplay == "c" else "g",
            "f" if fplay else "d",
        )
        return await mystic.edit_text(
            _["play_13"],
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None

    try:
        await stream(
            _,
            mystic,
            CallbackQuery.from_user.id,
            details,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="youtube",
            forceplay=ffplay,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
        return await mystic.edit_text(err)

    # Directly convert to photo
    return await convert_processing_to_photo(
        mystic,
        details.get("thumb"),
        _["play_10"].format(
            details["title"],
            details.get("duration_min", "Unknown"),
        )
    )


@app.on_callback_query(filters.regex("AnonymousAdmin") & ~BANNED_USERS)
async def anonymous_check(client, CallbackQuery):
    """Warn user that they must revert from Anonymous Admin."""
    try:
        await CallbackQuery.answer(
            "» ʀᴇᴠᴇʀᴛ ʙᴀᴄᴋ ᴛᴏ ᴜsᴇʀ ᴀᴄᴄᴏᴜɴᴛ :\n\n"
            "ᴏᴘᴇɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ sᴇᴛᴛɪɴɢs.\n"
            "-> ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs\n-> ᴄʟɪᴄᴋ ᴏɴ ʏᴏᴜʀ ɴᴀᴍᴇ\n-> ᴜɴᴄʜᴇᴄᴋ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴs.",
            show_alert=True,
        )
    except:
        pass


@app.on_callback_query(filters.regex("TuneViaPlaylists") & ~BANNED_USERS)
@languageCB
async def play_playlists_command(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    (
        videoid,
        user_id,
        ptype,
        mode,
        cplay,
        fplay,
    ) = callback_request.split("|")

    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return

    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except:
        return

    user_name = CallbackQuery.from_user.first_name
    await CallbackQuery.message.delete()

    try:
        await CallbackQuery.answer()
    except:
        pass

    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )

    videoid = lyrical.get(videoid)
    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None
    spotify = True

    if ptype == "yt":
        spotify = False
        try:
            result = await YouTube.playlist(
                videoid,
                config.PLAYLIST_FETCH_LIMIT,
                CallbackQuery.from_user.id,
                True,
            )
        except:
            return await mystic.edit_text(_["play_3"])

    elif ptype == "spplay":
        try:
            result, spotify_id = await Spotify.playlist(videoid)
        except:
            return await mystic.edit_text(_["play_3"])

    elif ptype == "spalbum":
        try:
            result, spotify_id = await Spotify.album(videoid)
        except:
            return await mystic.edit_text(_["play_3"])

    elif ptype == "spartist":
        try:
            result, spotify_id = await Spotify.artist(videoid)
        except:
            return await mystic.edit_text(_["play_3"])

    elif ptype == "apple":
        try:
            result, apple_id = await Apple.playlist(videoid, True)
        except:
            return await mystic.edit_text(_["play_3"])
    else:
        # Unhandled ptype?
        return

    try:
        await stream(
            _,
            mystic,
            user_id,
            result,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="playlist",
            spotify=spotify,
            forceplay=ffplay,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
        return await mystic.edit_text(err)

    # Convert to photo if you have result's thumb or just edit text
    return await convert_processing_to_photo(
        mystic,
        None,  # If you have a result thumbnail, pass it here
        "**Playlist Streaming!**"
    )


@app.on_callback_query(filters.regex("slider") & ~BANNED_USERS)
@languageCB
async def slider_queries(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    (
        what,
        rtype,
        query,
        user_id,
        cplay,
        fplay,
    ) = callback_request.split("|")

    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return

    what = str(what)
    rtype = int(rtype)

    if what == "F":
        if rtype == 9:
            query_type = 0
        else:
            query_type = rtype + 1
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except:
            pass
        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        med = InputMediaPhoto(
            media=thumbnail,
            caption=_["play_10"].format(
                title.title(),
                duration_min,
            ),
        )
        return await CallbackQuery.edit_message_media(
            media=med,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif what == "B":
        if rtype == 0:
            query_type = 9
        else:
            query_type = rtype - 1
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except:
            pass
        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        med = InputMediaPhoto(
            media=thumbnail,
            caption=_["play_10"].format(
                title.title(),
                duration_min,
            ),
        )
        return await CallbackQuery.edit_message_media(
            media=med,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
