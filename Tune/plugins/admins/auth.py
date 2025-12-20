# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.utils import extract_user, int_to_alpha
from Tune.utils.database import (
    delete_authuser,
    get_authuser,
    get_authuser_names,
    save_authuser,
)
from Tune.utils.decorators import AdminActual, language
from Tune.utils.inline import close_markup
from config import BANNED_USERS, adminlist


def _update_adminlist(chat_id, user_id, add=True):
    chat_admins = adminlist.get(chat_id)
    if chat_admins:
        if add and user_id not in chat_admins:
            chat_admins.append(user_id)
        elif not add and user_id in chat_admins:
            chat_admins.remove(user_id)


def _validate_command(message):
    if not message.reply_to_message and len(message.command) != 2:
        return False
    return True


@app.on_message(filters.command("auth") & filters.group & ~BANNED_USERS)
@AdminActual
async def auth(client, message: Message, _):
    if not _validate_command(message):
        return await message.reply_text(_["general_1"])

    user = await extract_user(message)
    token = await int_to_alpha(user.id)
    auth_names = await get_authuser_names(message.chat.id)

    if len(auth_names) >= 25:
        return await message.reply_text(_["auth_1"])

    if token in auth_names:
        return await message.reply_text(_["auth_3"].format(user.mention))

    auth_data = {
        "auth_user_id": user.id,
        "auth_name": user.first_name,
        "admin_id": message.from_user.id,
        "admin_name": message.from_user.first_name,
    }

    _update_adminlist(message.chat.id, user.id, add=True)
    await save_authuser(message.chat.id, token, auth_data)
    return await message.reply_text(_["auth_2"].format(user.mention))


@app.on_message(filters.command("unauth") & filters.group & ~BANNED_USERS)
@AdminActual
async def unauthusers(client, message: Message, _):
    if not _validate_command(message):
        return await message.reply_text(_["general_1"])

    user = await extract_user(message)
    token = await int_to_alpha(user.id)
    deleted = await delete_authuser(message.chat.id, token)

    _update_adminlist(message.chat.id, user.id, add=False)

    if deleted:
        return await message.reply_text(_["auth_4"].format(user.mention))
    return await message.reply_text(_["auth_5"].format(user.mention))


@app.on_message(
    filters.command(["authlist", "authusers"]) & filters.group & ~BANNED_USERS
)
@language
async def authusers(client, message: Message, _):
    auth_tokens = await get_authuser_names(message.chat.id)
    if not auth_tokens:
        return await message.reply_text(_["setting_4"])

    mystic = await message.reply_text(_["auth_6"])
    text = _["auth_7"].format(message.chat.title)
    counter = 0

    for token in auth_tokens:
        auth_data = await get_authuser(message.chat.id, token)
        user_id = auth_data["auth_user_id"]
        admin_id = auth_data["admin_id"]
        admin_name = auth_data["admin_name"]

        try:
            user_name = (await app.get_users(user_id)).first_name
            counter += 1
        except:
            continue

        text += f"{counter}➤ {user_name}[<code>{user_id}</code>]\n"
        text += f"   {_['auth_8']} {admin_name}[<code>{admin_id}</code>]\n\n"

    await mystic.edit_text(text, reply_markup=close_markup(_))
