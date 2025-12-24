# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

from Tune import app
from Tune.utils.database import get_playmode, get_playtype, is_nonadmin_chat
from Tune.utils.decorators import language
from Tune.utils.inline.settings import playmode_users_markup
from config import BANNED_USERS
from Tune.utils.errors import capture_err


@app.on_message(filters.command(["playmode", "mode"], prefixes=["/"]) & filters.group & ~BANNED_USERS)
@language
@capture_err
async def playmode_(client, message: Message, _):
    chat_id = message.chat.id
    playmode = await get_playmode(chat_id)
    is_non_admin = await is_nonadmin_chat(chat_id)
    playty = await get_playtype(chat_id)
    
    Direct = True if playmode == "Direct" else None
    Group = True if not is_non_admin else None
    Playtype = None if playty == "Everyone" else True
    
    buttons = playmode_users_markup(_, Direct, Group, Playtype)
    await message.reply_text(
        _["play_22"].format(message.chat.title),
        reply_markup=InlineKeyboardMarkup(buttons),
    )
