import asyncio
from pykeyboard import InlineKeyboard
from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, Message

from Tune import app
from Tune.utils.database import get_lang, set_lang
from Tune.utils.decorators import ActualAdminCB, language, languageCB
from config import BANNED_USERS
from strings import get_string, languages_present


def languages_keyboard(_):
    keyboard = InlineKeyboard(row_width=2)
    keyboard.add(
        *[
            InlineKeyboardButton(
                text=languages_present[i],
                callback_data=f"languages:{i}",
            )
            for i in languages_present
        ]
    )
    keyboard.row(
        InlineKeyboardButton(
            text=_["BACK_BUTTON"],
            callback_data="settingsback_helper",
        ),
        InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close"),
    )
    return keyboard


@app.on_message(filters.command(["lang", "setlang", "language"]) & ~BANNED_USERS)
@language
async def langs_command(client, message: Message, _):
    keyboard = languages_keyboard(_)
    try:
        await message.reply_text(
            _["lang_1"],
            reply_markup=keyboard,
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await message.reply_text(
            _["lang_1"],
            reply_markup=keyboard,
        )


@app.on_callback_query(filters.regex("LG") & ~BANNED_USERS)
@languageCB
async def languagecb(client, CallbackQuery, _):
    try:
        await CallbackQuery.answer()
    except:
        pass
    keyboard = languages_keyboard(_)
    try:
        await CallbackQuery.edit_message_reply_markup(reply_markup=keyboard)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await CallbackQuery.edit_message_reply_markup(reply_markup=keyboard)


@app.on_callback_query(filters.regex(r"languages:(.*?)") & ~BANNED_USERS)
@ActualAdminCB
async def language_markup(client, CallbackQuery, _):
    lang_code = CallbackQuery.data.split(":")[1]
    old_lang = await get_lang(CallbackQuery.message.chat.id)
    if str(old_lang) == str(lang_code):
        return await CallbackQuery.answer(_["lang_4"], show_alert=True)

    try:
        _ = get_string(lang_code)
        await CallbackQuery.answer(_["lang_2"], show_alert=True)
    except:
        _ = get_string(old_lang)
        return await CallbackQuery.answer(_["lang_3"], show_alert=True)

    await set_lang(CallbackQuery.message.chat.id, lang_code)
    keyboard = languages_keyboard(_)
    try:
        await CallbackQuery.edit_message_reply_markup(reply_markup=keyboard)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await CallbackQuery.edit_message_reply_markup(reply_markup=keyboard)
