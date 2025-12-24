# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import BANNED_USERS, OWNER_ID
from Tune import app
from Tune.misc import SUDOERS
from Tune.utils.database import add_sudo, remove_sudo
from Tune.utils.decorators.language import language_no_delete, languageCB
from Tune.utils.extraction import extract_user


@app.on_message(filters.command(["addsudo"], prefixes=["/", "!", "."]) & filters.user(OWNER_ID))
@language_no_delete
async def add_sudo_user(client, message: Message, _):
    if not message.reply_to_message and len(message.command) != 2:
        return await message.reply_text(_["general_1"])

    user = await extract_user(message)
    if user.id in SUDOERS:
        return await message.reply_text(_["sudo_1"].format(user.mention))

    if await add_sudo(user.id):
        SUDOERS.add(user.id)
        return await message.reply_text(_["sudo_2"].format(user.mention))

    await message.reply_text(_["sudo_8"])


@app.on_message(filters.command(["delsudo", "rmsudo"], prefixes=["/", "!", "."]) & filters.user(OWNER_ID))
@language_no_delete
async def remove_sudo_user(client, message: Message, _):
    if not message.reply_to_message and len(message.command) != 2:
        return await message.reply_text(_["general_1"])

    user = await extract_user(message)
    if user.id not in SUDOERS:
        return await message.reply_text(_["sudo_3"].format(user.mention))

    if await remove_sudo(user.id):
        SUDOERS.remove(user.id)
        return await message.reply_text(_["sudo_4"].format(user.mention))

    await message.reply_text(_["sudo_8"])


@app.on_message(filters.command(["sudolist", "listsudo", "sudoers"], prefixes=["/", "!", "."]) & ~BANNED_USERS)
@language_no_delete
async def sudoers_list(client, message: Message, _):
    keyboard = [[InlineKeyboardButton("๏ ᴠɪᴇᴡ sᴜᴅᴏʟɪsᴛ ๏", callback_data="sudo_list_view")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_video(
        video="https://files.catbox.moe/x7v3k6.mp4",
        caption=_["sudo_9"],
        reply_markup=reply_markup
    )


@app.on_callback_query(filters.regex("^sudo_list_view$"))
@languageCB
async def view_sudo_list_callback(client, callback_query: CallbackQuery, _):
    if callback_query.from_user.id not in SUDOERS:
        return await callback_query.answer(_["sudo_10"], show_alert=True)

    owner = await app.get_users(OWNER_ID)
    caption = _["sudo_11"].format(owner.mention)
    keyboard = [[InlineKeyboardButton("๏ ᴠɪᴇᴡ ᴏᴡɴᴇʀ ๏", url=f"tg://openmessage?user_id={OWNER_ID}")]]

    count = 0
    for user_id in SUDOERS:
        if user_id == OWNER_ID:
            continue
        try:
            user = await app.get_users(user_id)
            count += 1
            caption += _["sudo_12"].format(count, user.mention)
            keyboard.append([
                InlineKeyboardButton(f"๏ ᴠɪᴇᴡ sᴜᴅᴏ {count} ๏", url=f"tg://openmessage?user_id={user_id}")
            ])
        except Exception:
            continue

    if count == 0:
        caption += _["sudo_13"]

    keyboard.append([InlineKeyboardButton("๏ ʙᴀᴄᴋ ๏", callback_data="sudo_list_back")])
    await callback_query.message.edit_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))


@app.on_callback_query(filters.regex("^sudo_list_back$"))
@languageCB
async def back_to_sudo_list_menu(client, callback_query: CallbackQuery, _):
    keyboard = [[InlineKeyboardButton("๏ ᴠɪᴇᴡ sᴜᴅᴏʟɪsᴛ ๏", callback_data="sudo_list_view")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await callback_query.message.edit_caption(
        caption=_["sudo_9"],
        reply_markup=reply_markup
    )


@app.on_message(filters.command("delallsudo", prefixes=["/", "!", "%", ",", ".", "@", "#"]) & filters.user(OWNER_ID))
@language_no_delete
async def remove_all_sudo_users(client, message: Message, _):
    removed_count = 0
    for user_id in list(SUDOERS):
        if user_id != OWNER_ID:
            if await remove_sudo(user_id):
                SUDOERS.remove(user_id)
                removed_count += 1
    await message.reply_text(_["sudo_14"].format(removed_count))
