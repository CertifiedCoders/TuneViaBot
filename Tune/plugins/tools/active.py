# Authored By Certified Coders © 2025
from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from unidecode import unidecode

from Tune import app
from Tune.misc import SUDOERS
from Tune.utils.database import (
    get_active_chats,
    get_active_video_chats,
    remove_active_chat,
    remove_active_video_chat,
)
from Tune.utils.decorators.language import language_no_delete


async def _format_active_chats(chat_ids, remove_func, include_id=False):
    text = ""
    for idx, chat_id in enumerate(chat_ids, 1):
        try:
            chat = await app.get_chat(chat_id)
            title = unidecode(chat.title).upper()
            link = f"<a href=https://t.me/{chat.username}>{title}</a>" if chat.username else title
            suffix = f" [<code>{chat_id}</code>]" if include_id else ""
            text += f"<b>{idx}.</b> {link}{suffix}\n"
        except Exception:
            await remove_func(chat_id)
    return text


@app.on_message(filters.command(["activevc", "activevoice", "vc"]) & SUDOERS)
@language_no_delete
async def activevc(client: Client, message: Message, _):
    mystic = await message.reply_text(_["active_1"])
    text = await _format_active_chats(await get_active_chats(), remove_active_chat)
    if not text:
        await mystic.edit_text(_["active_2"].format(app.mention))
    else:
        await mystic.edit_text(
            f"<b>{_['active_3']}</b>\n\n{text}",
            disable_web_page_preview=True,
        )


@app.on_message(filters.command(["activev", "activevideo", "avc"]) & SUDOERS)
@language_no_delete
async def activevideo(client: Client, message: Message, _):
    mystic = await message.reply_text(_["active_4"])
    text = await _format_active_chats(await get_active_video_chats(), remove_active_video_chat, include_id=True)
    if not text:
        await mystic.edit_text(_["active_5"].format(app.mention))
    else:
        await mystic.edit_text(
            f"<b>{_['active_6']}</b>\n\n{text}",
            disable_web_page_preview=True,
        )


@app.on_message(filters.command(["ac", "av"]) & SUDOERS)
@language_no_delete
async def active_count(client: Client, message: Message, _):
    ac_audio = str(len(await get_active_chats()))
    ac_video = str(len(await get_active_video_chats()))
    await message.reply_text(
        _["active_7"].format(ac_audio=ac_audio, ac_video=ac_video),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(_["active_8"], callback_data="close")]]
        )
    )
