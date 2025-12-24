# Authored By Certified Coders © 2025
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultPhoto,
)
from youtubesearchpython.aio import VideosSearch

from Tune.utils.inlinequery import answer
from config import BANNED_USERS
from Tune import app


@app.on_inline_query(~BANNED_USERS)
async def inline_query_handler(client, query):
    text = query.query.strip().lower()
    if not text:
        try:
            await client.answer_inline_query(query.id, results=answer, cache_time=10)
        except Exception:
            return
        return

    videos_search = VideosSearch(text, limit=20)
    search_result = await videos_search.next()
    results = search_result.get("result") if search_result else None

    if not results:
        return

    answers = []
    for video in results[:15]:
        try:
            title = video.get("title", "").title()
            duration = video.get("duration", "")
            views = video.get("viewCount", {}).get("short", "")
            thumbnails = video.get("thumbnails", [])
            thumbnail_url = thumbnails[0].get("url", "") if thumbnails else ""
            thumbnail = thumbnail_url.split("?")[0] if thumbnail_url else ""
            channel_info = video.get("channel", {})
            channellink = channel_info.get("link", "")
            channel = channel_info.get("name", "")
            link = video.get("link", "")
            published = video.get("publishedTime", "")

            if not all([title, link, thumbnail]):
                continue

            description = f"{views} | {duration} ᴍɪɴᴜᴛᴇs | {channel}  | {published}"
            buttons = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="ʏᴏᴜᴛᴜʙᴇ 🎄",
                            url=link,
                        )
                    ],
                ]
            )
            searched_text = f"""
❄ <b>ᴛɪᴛʟᴇ :</b> <a href={link}>{title}</a>

⏳ <b>ᴅᴜʀᴀᴛɪᴏɴ :</b> {duration} ᴍɪɴᴜᴛᴇs
👀 <b>ᴠɪᴇᴡs :</b> <code>{views}</code>
🎥 <b>ᴄʜᴀɴɴᴇʟ :</b> <a href={channellink}>{channel}</a>
⏰ <b>ᴘᴜʙʟɪsʜᴇᴅ ᴏɴ :</b> {published}


<u><b>➻ ɪɴʟɪɴᴇ sᴇᴀʀᴄʜ ᴍᴏᴅᴇ ʙʏ {app.name}</b></u>"""
            answers.append(
                InlineQueryResultPhoto(
                    photo_url=thumbnail,
                    title=title,
                    thumb_url=thumbnail,
                    description=description,
                    caption=searched_text,
                    reply_markup=buttons,
                )
            )
        except (KeyError, IndexError, TypeError):
            continue

    if answers:
        try:
            await client.answer_inline_query(query.id, results=answers)
        except Exception:
            return
