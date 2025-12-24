# Authored By Certified Coders © 2025
import asyncio
from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)

from Tune import app
from Tune.utils.database import get_lang, set_lang
from Tune.utils.decorators import ActualAdminCB, language, languageCB
from config import BANNED_USERS
from strings import get_string, languages_present


def languages_keyboard(_, back_button="SETTINGS_PRIVATE_BACK"):
    rows = []
    row = []

    for idx, code in enumerate(languages_present):
        row.append(
            InlineKeyboardButton(
                text=languages_present[code],
                callback_data=f"languages:{code}",
            )
        )
        if (idx + 1) % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data=back_button),
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close"),
        ]
    )

    return InlineKeyboardMarkup(rows)


async def _handle_flood_wait(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await func(*args, **kwargs)


async def _safe_callback_answer(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass


@app.on_message(filters.command(["lang", "setlang", "language"]) & ~BANNED_USERS)
@language
async def langs_command(client, message: Message, _):
    keyboard = languages_keyboard(_)
    await _handle_flood_wait(
        message.reply_text, _["lang_1"], reply_markup=keyboard
    )


@app.on_callback_query(filters.regex("LG") & ~BANNED_USERS)
@languageCB
async def languagecb(client, CallbackQuery: CallbackQuery, _):
    await _safe_callback_answer(CallbackQuery)
    keyboard = languages_keyboard(_)
    await _handle_flood_wait(
        CallbackQuery.edit_message_reply_markup, reply_markup=keyboard
    )


@app.on_callback_query(filters.regex(r"languages:(.*?)") & ~BANNED_USERS)
@ActualAdminCB
async def language_markup(client, CallbackQuery: CallbackQuery, _):
    lang_code = CallbackQuery.data.split(":")[1]
    old_lang = await get_lang(CallbackQuery.message.chat.id)
    if str(old_lang) == str(lang_code):
        return await CallbackQuery.answer(_["lang_4"], show_alert=True)

    try:
        new_lang_strings = get_string(lang_code)
        await CallbackQuery.answer(new_lang_strings["lang_2"], show_alert=True)
    except Exception:
        await CallbackQuery.answer(_["lang_3"], show_alert=True)
        return

    await set_lang(CallbackQuery.message.chat.id, lang_code)
    keyboard = languages_keyboard(new_lang_strings)
    await _handle_flood_wait(
        CallbackQuery.edit_message_reply_markup, reply_markup=keyboard
    )
