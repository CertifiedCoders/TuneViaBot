import os
import re

import yt_dlp
from pykeyboard import InlineKeyboard
from pyrogram import filters
from pyrogram.enums import ChatAction
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaAudio,
    InputMediaVideo,
    Message,
)

from config import BANNED_USERS, SONG_DOWNLOAD_DURATION, SONG_DOWNLOAD_DURATION_LIMIT
from Tune import YouTube, app
from Tune.utils.decorators.language import language, languageCB
from Tune.utils.formatters import convert_bytes
from Tune.utils.inline.song import song_markup

cookies_file = "Tune/cookies/cookies.txt"


# Group command: Invite users to start the bot privately
@app.on_message(filters.command("song") & filters.group & ~BANNED_USERS)
@language
async def song_command_group(client, message: Message, lang):
    buttons = [
        [
            InlineKeyboardButton(
                text=lang["SG_B_1"], url=f"https://t.me/{app.username}?start=song"
            )
        ]
    ]
    await message.reply_text(lang["song_1"], reply_markup=InlineKeyboardMarkup(buttons))


# Private command: Search or download song
@app.on_message(filters.command("song") & filters.private & ~BANNED_USERS)
@language
async def song_command_private(client, message: Message, lang):
    await message.delete()
    url = await YouTube.url(message)

    # Check if valid URL or query
    if not url and len(message.command) < 2:
        return await message.reply_text(lang["song_2"])

    query = url or message.text.split(None, 1)[1]
    if url and not await YouTube.exists(url):
        return await message.reply_text(lang["song_5"])

    status = await message.reply_text(lang["play_1"])
    try:
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(
            query
        )
    except Exception:
        return await status.edit_text(lang["play_3"])

    if str(duration_min) == "None":
        return await status.edit_text(lang["song_3"])
    if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
        key = "play_4" if url else "play_6"
        return await status.edit_text(
            lang[key].format(SONG_DOWNLOAD_DURATION, duration_min)
        )

    buttons = song_markup(lang, vidid)
    await status.delete()
    await message.reply_photo(
        thumbnail,
        caption=lang["song_4"].format(title),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# Go back to song format selection
@app.on_callback_query(filters.regex("song_back") & ~BANNED_USERS)
@languageCB
async def song_back_cb(client, callback_query, lang):
    try:
        _, data = callback_query.data.strip().split(None, 1)
        stype, vidid = data.split("|")
    except ValueError:
        return

    buttons = song_markup(lang, vidid)
    await callback_query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# Show format options
@app.on_callback_query(filters.regex("song_helper") & ~BANNED_USERS)
@languageCB
async def song_helper_cb(client, callback_query, lang):
    try:
        await callback_query.answer(lang["song_6"], show_alert=True)
    except Exception:
        pass

    try:
        _, data = callback_query.data.strip().split(None, 1)
        stype, vidid = data.split("|")
    except ValueError:
        return await callback_query.edit_message_text("Invalid callback data.")

    try:
        formats, link = await YouTube.formats(vidid, True)
    except Exception:
        return await callback_query.edit_message_text(lang["song_7"])

    keyboard = InlineKeyboard()
    done = []

    for fmt in formats:
        if not fmt.get("filesize"):
            continue

        if stype == "audio":
            if "audio" not in fmt.get("format", ""):
                continue
            form = fmt.get("format_note", "").title()
            if not form or form in done:
                continue
            done.append(form)
            label = f"{form} Quality Audio = {convert_bytes(fmt['filesize'])}"
        else:
            allowed_ids = [160, 133, 134, 135, 136, 137, 298, 299, 264, 304, 266]
            if int(fmt.get("format_id", 0)) not in allowed_ids:
                continue
            label = f"{fmt['format'].split('-')[1].strip()} = {convert_bytes(fmt['filesize'])}"

        keyboard.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"song_download {stype}|{fmt['format_id']}|{vidid}",
            )
        )

    keyboard.row(
        InlineKeyboardButton(
            text=lang["BACK_BUTTON"], callback_data=f"song_back {stype}|{vidid}"
        ),
        InlineKeyboardButton(text=lang["CLOSE_BUTTON"], callback_data="close"),
    )

    await callback_query.edit_message_reply_markup(reply_markup=keyboard)


# Download selected audio/video
@app.on_callback_query(filters.regex("song_download") & ~BANNED_USERS)
@languageCB
async def song_download_cb(client, callback_query, lang):
    try:
        await callback_query.answer("Downloading")
    except Exception:
        pass

    try:
        _, data = callback_query.data.strip().split(None, 1)
        stype, format_id, vidid = data.split("|")
    except ValueError:
        return

    mystic = await callback_query.edit_message_text(lang["song_8"])
    yt_url = f"https://www.youtube.com/watch?v={vidid}"

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "cookiefile": cookies_file}) as ytdl:
            info = ytdl.extract_info(yt_url, download=False)
    except Exception as e:
        return await mystic.edit_text(f"Failed to fetch info: {e}")

    title = re.sub(r"\W+", " ", info["title"].title())
    duration = info.get("duration", 0)
    uploader = info.get("uploader", "Unknown")
    thumb_path = await callback_query.message.download()

    if stype == "video":
        width = callback_query.message.photo.width
        height = callback_query.message.photo.height
        try:
            file_path = await YouTube.download(
                yt_url, mystic, songvideo=True, format_id=format_id, title=title
            )
        except Exception as e:
            return await mystic.edit_text(lang["song_9"].format(e))

        await mystic.edit_text(lang["song_11"])
        await app.send_chat_action(
            callback_query.message.chat.id, ChatAction.UPLOAD_VIDEO
        )
        try:
            await callback_query.edit_message_media(
                media=InputMediaVideo(
                    media=file_path,
                    duration=duration,
                    width=width,
                    height=height,
                    thumb=thumb_path,
                    caption=title,
                    supports_streaming=True,
                )
            )
        except Exception as e:
            return await mystic.edit_text(lang["song_10"])
        os.remove(file_path)

    else:  # audio
        try:
            file_path = await YouTube.download(
                yt_url, mystic, songaudio=True, format_id=format_id, title=title
            )
        except Exception as e:
            return await mystic.edit_text(lang["song_9"].format(e))

        await mystic.edit_text(lang["song_11"])
        await app.send_chat_action(
            callback_query.message.chat.id, ChatAction.UPLOAD_AUDIO
        )
        try:
            await callback_query.edit_message_media(
                media=InputMediaAudio(
                    media=file_path,
                    caption=title,
                    thumb=thumb_path,
                    title=title,
                    performer=uploader,
                )
            )
        except Exception as e:
            return await mystic.edit_text(lang["song_10"])
        os.remove(file_path)
