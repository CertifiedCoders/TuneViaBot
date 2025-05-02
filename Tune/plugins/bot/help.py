import re
from typing import Union
from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, Message

from Tune import app
from Tune.utils.database import get_lang, get_served_users, get_served_chats
from Tune.utils.decorators.language import LanguageStart, languageCB
from Tune.utils.inline.help import help_keyboard, help_back_markup, private_help_panel
from Tune.utils.inline.start import private_panel
from config import BANNED_USERS, HELP_IMG_URL, SUPPORT_CHAT
from strings import get_string, helpers
from Tune.utils import bot_sys_stats

@app.on_message(filters.command(["help"]) & filters.private & ~BANNED_USERS)
@app.on_callback_query(filters.regex("open_help") & ~BANNED_USERS)
@LanguageStart
async def helper_private(client: Client, update: Union[Message, types.CallbackQuery], _):
    is_cb = isinstance(update, types.CallbackQuery)
    language = await get_lang(update.from_user.id)
    _ = get_string(language)

    keyboard = help_keyboard(_)
    caption = _["help_1"].format(SUPPORT_CHAT)

    if is_cb:
        await update.answer()
        await update.message.edit_caption(caption, reply_markup=keyboard)
    else:
        await update.delete()
        await update.reply_photo(
            photo=HELP_IMG_URL,
            caption=caption,
            reply_markup=keyboard
        )

@app.on_message(filters.command(["help"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def help_com_group(client: Client, message: Message, _):
    keyboard = private_help_panel(_)
    await message.reply_text(
        _["help_2"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

@app.on_callback_query(filters.regex(r"help_callback hb(\d+)") & ~BANNED_USERS)
@languageCB
async def helper_cb(client: Client, CallbackQuery: types.CallbackQuery, _):
    number = int(CallbackQuery.data.split("hb")[1])
    help_text = getattr(helpers, f"HELP_{number}", None)
    if not help_text:
        return await CallbackQuery.answer("Invalid help topic.", show_alert=True)

    await CallbackQuery.edit_message_text(
        help_text,
        reply_markup=help_back_markup(_),
        disable_web_page_preview=True
    )

@app.on_callback_query(filters.regex("back_to_main") & ~BANNED_USERS)
@languageCB
async def back_to_main_cb(client: Client, CallbackQuery: types.CallbackQuery, _):
    out = private_panel(_)
    UP, CPU, RAM, DISK = await bot_sys_stats()
    served_users = len(await get_served_users())
    served_chats = len(await get_served_chats())
    await CallbackQuery.edit_message_caption(
        _["start_2"].format(
            CallbackQuery.from_user.mention,
            app.mention,
            UP, DISK, CPU, RAM, served_users, served_chats
        ),
        reply_markup=InlineKeyboardMarkup(out)
    )
