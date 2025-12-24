# Authored By Certified Coders © 2025
import asyncio
import urllib.parse
from pyrogram import filters, errors, types
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional

from config import LOGGER_ID
from Tune import app
from Tune.utils.database import remove_served_chat, get_lang
from strings import get_string

BOT_INFO: Optional[types.User] = None
BOT_ID: Optional[int] = None

IMG_URL = "https://files.catbox.moe/iq5t4i.jpg"

def _is_valid_url(url: Optional[str]) -> bool:
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url.strip())
        return parsed.scheme in ("http", "https", "tg") and (parsed.netloc or parsed.path)
    except Exception:
        return False

async def _ensure_bot_info() -> None:
    global BOT_INFO, BOT_ID
    if BOT_INFO is None:
        try:
            BOT_INFO = await app.get_me()
            BOT_ID = BOT_INFO.id
        except Exception:
            pass

async def _get_language(chat_id: int):
    try:
        lang = await get_lang(chat_id)
        return get_string(lang)
    except Exception:
        return get_string("en")

async def _safe_send_photo(chat_id: int, photo: str, caption: str, reply_markup=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await app.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup
            )
        except errors.FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except errors.ButtonUrlInvalid:
            for fallback_attempt in range(max_retries):
                try:
                    return await app.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=caption
                    )
                except errors.FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                except Exception:
                    if fallback_attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(1)
        except Exception:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1)

async def _safe_send_message(chat_id: int, text: str, max_retries=3):
    for attempt in range(max_retries):
        try:
            await app.send_message(chat_id, text)
            return
        except errors.FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1)

@app.on_message(filters.new_chat_members)
async def join_watcher(_, message: Message):
    try:
        await _ensure_bot_info()
        if BOT_INFO is None or BOT_ID is None:
            return

        chat = message.chat
        invite_link = None
        try:
            invite_link = await app.export_chat_invite_link(chat.id)
        except Exception:
            pass

        for member in message.new_chat_members:
            if member.id != BOT_ID:
                continue

            member_count = "?"
            try:
                member_count = await app.get_chat_members_count(chat.id)
            except errors.FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
                try:
                    member_count = await app.get_chat_members_count(chat.id)
                except Exception:
                    pass
            except Exception:
                pass

            _ = await _get_language(chat.id)
            username = chat.username if chat.username else _["chatlog_10"]
            added_by = message.from_user.mention if message.from_user else _["chatlog_11"]
            link = invite_link or "https://t.me/"

            caption = (
                _["chatlog_1"] +
                _["chatlog_2"] +
                _["chatlog_3"].format(chat.title) +
                _["chatlog_4"].format(chat.id) +
                _["chatlog_5"].format(username) +
                _["chatlog_6"].format(link) +
                _["chatlog_7"].format(member_count) +
                _["chatlog_8"].format(added_by)
            )

            reply_markup = None
            if _is_valid_url(invite_link):
                reply_markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(_["chatlog_9"], url=invite_link.strip())]]
                )

            await _safe_send_photo(
                LOGGER_ID,
                photo=IMG_URL,
                caption=caption,
                reply_markup=reply_markup
            )
    except Exception:
        pass

@app.on_message(filters.left_chat_member)
async def on_left_chat_member(_, message: Message):
    try:
        await _ensure_bot_info()
        if BOT_INFO is None or BOT_ID is None:
            return

        if message.left_chat_member.id != BOT_ID:
            return

        chat = message.chat
        _ = await _get_language(chat.id)
        remover = message.from_user.mention if message.from_user else _["chatlog_17"]

        await remove_served_chat(chat.id)

        text = (
            _["chatlog_12"] +
            _["chatlog_3"].format(chat.title) +
            _["chatlog_13"].format(chat.id) +
            _["chatlog_14"].format(remover) +
            _["chatlog_15"].format(BOT_INFO.username) +
            _["chatlog_16"]
        )

        await _safe_send_message(LOGGER_ID, text)
    except Exception:
        pass
