# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.misc import SUDOERS
from Tune.utils.database import blacklist_chat, blacklisted_chats, whitelist_chat
from Tune.utils.decorators.language import language_no_delete
from config import BANNED_USERS


@app.on_message(filters.command(["blchat", "blacklistchat"]) & SUDOERS)
@language_no_delete
async def blacklist_chat_func(client, message: Message, _):
    if len(message.command) != 2:
        return await message.reply_text(_["black_1"])
    try:
        chat_id = int(message.command[1])
    except ValueError:
        return await message.reply_text(_["black_1"])
    if chat_id in await blacklisted_chats():
        return await message.reply_text(_["black_2"])
    blacklisted = await blacklist_chat(chat_id)
    if blacklisted:
        await message.reply_text(_["black_3"])
    else:
        await message.reply_text(_["black_9"])
    try:
        await app.leave_chat(chat_id)
    except Exception:
        pass


@app.on_message(
    filters.command(["whitelistchat", "unblacklistchat", "unblchat"]) & SUDOERS
)
@language_no_delete
async def whitelist_function(client, message: Message, _):
    if len(message.command) != 2:
        return await message.reply_text(_["black_4"])
    try:
        chat_id = int(message.command[1])
    except ValueError:
        return await message.reply_text(_["black_4"])
    if chat_id not in await blacklisted_chats():
        return await message.reply_text(_["black_5"])
    whitelisted = await whitelist_chat(chat_id)
    if whitelisted:
        return await message.reply_text(_["black_6"])
    await message.reply_text(_["black_9"])


@app.on_message(filters.command(["blchats", "blacklistedchats"]) & ~BANNED_USERS)
@language_no_delete
async def all_chats(client, message: Message, _):
    blacklisted = await blacklisted_chats()
    if not blacklisted:
        return await message.reply_text(_["black_8"].format(app.mention))
    text = _["black_7"]
    for count, chat_id in enumerate(blacklisted, 1):
        try:
            title = (await app.get_chat(chat_id)).title
        except Exception:
            title = "ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ"
        text += f"{count}. {title}[<code>{chat_id}</code>]\n"
    await message.reply_text(text)
