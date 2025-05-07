from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.misc import SUDOERS
from Tune.utils.database import add_gban_user, remove_gban_user, add_banned_user, remove_banned_user
from Tune.utils.decorators.language import language
from Tune.utils.extraction import extract_user
from config import BANNED_USERS


@app.on_message(filters.command(["block"]) & SUDOERS)
@language
async def useradd(client, message: Message, _):
    if not message.reply_to_message and len(message.command) != 2:
        return await message.reply_text(_["general_1"])

    user = await extract_user(message)
    if user.id in BANNED_USERS:
        return await message.reply_text(_["block_1"].format(user.mention))

    await add_gban_user(user.id)
    await add_banned_user(user.id)
    BANNED_USERS.add(user.id)

    await message.reply_text(_["block_2"].format(user.mention))


@app.on_message(filters.command(["unblock"]) & SUDOERS)
@language
async def userdel(client, message: Message, _):
    if not message.reply_to_message and len(message.command) != 2:
        return await message.reply_text(_["general_1"])

    user = await extract_user(message)
    if user.id not in BANNED_USERS:
        return await message.reply_text(_["block_3"].format(user.mention))

    await remove_gban_user(user.id)
    await remove_banned_user(user.id)
    BANNED_USERS.remove(user.id)

    await message.reply_text(_["block_4"].format(user.mention))


@app.on_message(filters.command(["blocked", "blockedusers", "blusers"]) & SUDOERS)
@language
async def sudoers_list(client, message: Message, _):
    if not BANNED_USERS:
        return await message.reply_text(_["block_5"])

    mystic = await message.reply_text(_["block_6"])
    msg = _["block_7"]
    count = 0

    for user_id in BANNED_USERS:
        try:
            user = await app.get_users(user_id)
            mention = user.mention if user.mention else user.first_name
            count += 1
            msg += f"{count}➤ {mention}\n"
        except:
            continue

    return await mystic.edit_text(_["block_5"] if count == 0 else msg)
