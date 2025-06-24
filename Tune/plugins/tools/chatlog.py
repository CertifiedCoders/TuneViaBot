
import asyncio
import random
import urllib.parse
from pyrogram import filters, errors
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from config import LOGGER_ID
from Tune import app

PHOTOS = "https://files.catbox.moe/j1d9dn.jpg"


def _is_valid_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urllib.parse.urlparse(url.strip())
    return parsed.scheme in ("http", "https", "tg") and (parsed.netloc or parsed.path)


async def _ensure_bot_info() -> None:
    global BOT_INFO, BOT_ID
    if BOT_INFO is None:
        BOT_INFO = await app.get_me()
        BOT_ID = BOT_INFO.id



@app.on_message(filters.new_chat_members)
async def join_watcher(_, message: Message):
    await _ensure_bot_info()
    chat = message.chat
    try:
        invite_link = await app.export_chat_invite_link(chat.id)
    except Exception:
        invite_link = None

    for member in message.new_chat_members:
        if member.id != BOT_ID:
            continue

        while True:
            try:
                member_count = await app.get_chat_members_count(chat.id)
                break
            except errors.FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
            except Exception:
                member_count = "?"
                break

        caption = (
            "📝 **ᴍᴜsɪᴄ ʙᴏᴛ ᴀᴅᴅᴇᴅ ɪɴ ᴀ ɴᴇᴡ ɢʀᴏᴜᴘ**\n\n"
            "❅─────✧❅✦❅✧─────❅\n\n"
            f"📌 **ᴄʜᴀᴛ ɴᴀᴍᴇ:** `{chat.title}`\n"
            f"🍂 **ᴄʜᴀᴛ ɪᴅ:** `{chat.id}`\n"
            f"🔐 **ᴄʜᴀᴛ ᴜsᴇʀɴᴀᴍᴇ:** @{chat.username if chat.username else 'Private'}\n"
            f"🛰 **ᴄʜᴀᴛ ʟɪɴᴋ:** [ᴄʟɪᴄᴋ ʜᴇʀᴇ]({invite_link or 'https://t.me/'})\n"
            f"📈 **ɢʀᴏᴜᴘ ᴍᴇᴍʙᴇʀs:** `{member_count}`\n"
            f"🤔 **ᴀᴅᴅᴇᴅ ʙʏ:** {message.from_user.mention if message.from_user else 'Unknown'}"
        )

        reply_markup = None
        if _is_valid_url(invite_link):
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("sᴇᴇ ɢʀᴏᴜᴘ 👀", url=invite_link.strip())]]
            )

        try:
            await app.send_photo(
                LOGGER_ID,
               photo=PHOTOS,
                caption=caption,
                reply_markup=reply_markup,
            )
        except errors.ButtonUrlInvalid:
            await app.send_photo(
                LOGGER_ID,
                photo=PHOTOS,
                caption=caption,
            )


@app.on_message(filters.left_chat_member)
async def on_left_chat_member(_, message: Message):
    await _ensure_bot_info()
    if message.left_chat_member.id != BOT_ID:
        return

    remover = message.from_user.mention if message.from_user else "**ᴜɴᴋɴᴏᴡɴ ᴜsᴇʀ**"
    chat = message.chat

    text = (
        "✫ **<u>#ʟᴇғᴛ_ɢʀᴏᴜᴘ</u>** ✫\n\n"
        f"📌 **ᴄʜᴀᴛ ɴᴀᴍᴇ:** `{chat.title}`\n"
        f"🆔 **ᴄʜᴀᴛ ɪᴅ:** `{chat.id}`\n"
        f"👤 **ʀᴇᴍᴏᴠᴇᴅ ʙʏ:** {remover}\n"
        f"🤖 **ʙᴏᴛ:** @{BOT_INFO.username}"
    )

    await app.send_message(LOGGER_ID, text)
