import os
import re
from pyrogram import filters
from pyrogram.enums import ChatAction
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaAudio,
    InputMediaVideo,
    Message,
)

from Tune import app, YouTube
from config import (
    BANNED_USERS,
    SONG_DOWNLOAD_DURATION,
    SONG_DOWNLOAD_DURATION_LIMIT,
)
from Tune.utils.decorators.language import language, languageCB
from Tune.utils.errors import capture_err, capture_callback_err
from Tune.utils.formatters import convert_bytes, time_to_seconds
from Tune.utils.inline.song import song_markup

SONG_COMMAND = ["song"]


class InlineKeyboardBuilder(list):
    def row(self, *buttons):
        self.append(list(buttons))


# ───────────────────────────── COMMANDS ───────────────────────────── #
@app.on_message(filters.command(SONG_COMMAND) & filters.group & ~BANNED_USERS)
@capture_err
@language
async def song_command_group(client, message: Message, lang):
    await message.reply_text(
        lang["song_1"],
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(lang["SG_B_1"], url=f"https://t.me/{app.username}?start=song")]]
        ),
    )


@app.on_message(filters.command(SONG_COMMAND) & filters.private & ~BANNED_USERS)
@capture_err
@language
async def song_command_private(client, message: Message, lang):
    await message.delete()
    mystic = await message.reply_text(lang["play_1"])

    url = await YouTube.url(message)
    query = url or (message.text.split(None, 1)[1] if len(message.command) > 1 else None)
    if not query:
        return await mystic.edit_text(lang["song_2"])

    if url and not await YouTube.exists(url):
        return await mystic.edit_text(lang["song_5"])

    try:
        title, dur_min, dur_sec, thumb, vidid = await YouTube.details(query)
    except Exception:
        return await mystic.edit_text(lang["play_3"])

    if not dur_min:
        return await mystic.edit_text(lang["song_3"])
    if int(dur_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
        return await mystic.edit_text(lang["play_4"].format(SONG_DOWNLOAD_DURATION, dur_min))

    await mystic.delete()
    await message.reply_photo(
        thumb,
        caption=lang["song_4"].format(title),
        reply_markup=InlineKeyboardMarkup(song_markup(lang, vidid)),
    )


# ───────────────────────────── CALLBACKS ───────────────────────────── #
@app.on_callback_query(filters.regex(r"song_back") & ~BANNED_USERS)
@capture_callback_err
@languageCB
async def songs_back_helper(client, cq, lang):
    _ignored, req = cq.data.split(None, 1)
    stype, vidid = req.split("|")
    await cq.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup(song_markup(lang, vidid))
    )


@app.on_callback_query(filters.regex(r"song_helper") & ~BANNED_USERS)
@capture_callback_err
@languageCB
async def song_helper_cb(client, cq, lang):
    _ignored, req = cq.data.split(None, 1)
    stype, vidid = req.split("|")

    try:
        await cq.answer(lang["song_6"], show_alert=True)
    except Exception:
        pass

    try:
        formats, _ = await YouTube.formats(vidid)
    except Exception:
        return await cq.edit_message_text(lang["song_7"])

    kb = InlineKeyboardBuilder()
    seen = set()

    if stype == "audio":
        for f in formats:
            if "audio" not in f.get("format", "") or not f.get("filesize"):
                continue
            label = (f.get("format_note") or "").title() or "Audio"
            if label in seen:
                continue
            seen.add(label)
            kb.row(
                InlineKeyboardButton(
                    text=f"{label} • {convert_bytes(f['filesize'])}",
                    callback_data=f"song_download {stype}|{f['format_id']}|{vidid}",
                )
            )
    else:
        allowed = {160, 133, 134, 135, 136, 137, 298, 299, 264, 304, 266}
        for f in formats:
            try:
                fmt_id = int(f.get("format_id", 0))
            except Exception:
                continue
            if not f.get("filesize") or fmt_id not in allowed:
                continue
            note = (f.get("format_note") or "").strip()
            res = note or f.get("format", "").split("-")[-1].strip() or str(fmt_id)
            kb.row(
                InlineKeyboardButton(
                    text=f"{res} • {convert_bytes(f['filesize'])}",
                    callback_data=f"song_download {stype}|{f['format_id']}|{vidid}",
                )
            )

    kb.row(
        InlineKeyboardButton(lang["BACK_BUTTON"], callback_data=f"song_back {stype}|{vidid}"),
        InlineKeyboardButton(lang["CLOSE_BUTTON"], callback_data="close"),
    )
    await cq.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))


@app.on_callback_query(filters.regex(r"song_download") & ~BANNED_USERS)
@capture_callback_err
@languageCB
async def song_download_cb(client, cq, lang):
    try:
        await cq.answer("Downloading…")
    except Exception:
        pass

    _ignored, req = cq.data.split(None, 1)
    stype, fmt_id, vidid = req.split("|")
    yturl = f"https://www.youtube.com/watch?v={vidid}"

    mystic = await cq.edit_message_text(lang["song_8"])

    file_path = None
    try:
        info, _ = await YouTube.track(yturl)
        raw_title = info.get("title") or "Song"
        title = re.sub(r"\s+", " ", re.sub(r"[^\w\s\-\.\(\)\[\]]+", " ", raw_title)).strip()[:200]
        duration_sec = time_to_seconds(info.get("duration_min")) if info.get("duration_min") else None

        if stype == "audio":
            file_path, _ = await YouTube.download(
                yturl, mystic, songaudio=True, format_id=fmt_id, title=title
            )
            if not file_path:
                raise RuntimeError("no audio file")
            await app.send_chat_action(cq.message.chat.id, ChatAction.UPLOAD_AUDIO)
            await cq.edit_message_media(
                InputMediaAudio(
                    media=file_path,
                    caption=title,
                    title=title,
                    performer=info.get("uploader"),
                )
            )
        else:
            file_path, _ = await YouTube.download(
                yturl, mystic, songvideo=True, format_id=fmt_id, title=title
            )
            if not file_path:
                raise RuntimeError("no video file")
            await app.send_chat_action(cq.message.chat.id, ChatAction.UPLOAD_VIDEO)
            w = getattr(getattr(cq.message, "photo", None), "width", None)
            h = getattr(getattr(cq.message, "photo", None), "height", None)
            await cq.edit_message_media(
                InputMediaVideo(
                    media=file_path,
                    duration=duration_sec,
                    width=w,
                    height=h,
                    caption=title,
                    supports_streaming=True,
                )
            )

    except Exception:
        await mystic.edit_text(lang["song_10"])
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
