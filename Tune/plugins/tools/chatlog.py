from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode
from config import LOGGER_ID as LOG_GROUP_ID
from Tune import app

chatlog_img = "https://telegra.ph/file/7cc7183b82327933b7b04.jpg"

# ➤ Triggered when the bot is added to a new group
@app.on_message(filters.new_chat_members, group=2)
async def join_watcher(_, message: Message):
    chat = message.chat
    try:
        link = await app.export_chat_invite_link(chat.id)
    except Exception:
        link = "❌ ɴᴏ ʟɪɴᴋ ᴀᴠᴀɪʟᴀʙʟᴇ"

    for member in message.new_chat_members:
        if member.id == app.id:
            try:
                count = await app.get_chat_members_count(chat.id)
            except Exception:
                count = "❌ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ"

            msg = (
                "📝 ᴍᴜsɪᴄ ʙᴏᴛ ᴀᴅᴅᴇᴅ ɪɴ ᴀ ɴᴇᴡ ɢʀᴏᴜᴘ\n\n"
                "**❅─────✧❅✦❅✧─────❅**\n\n"
                f"📌 ᴄʜᴀᴛ ɴᴀᴍᴇ: {chat.title}\n"
                f"🍂 ᴄʜᴀᴛ ɪᴅ: `{chat.id}`\n"
                f"🔐 ᴄʜᴀᴛ ᴜsᴇʀɴᴀᴍᴇ: @{chat.username if chat.username else '𝐍ᴏɴᴇ'}\n"
                f"🛰 ᴄʜᴀᴛ ʟɪɴᴋ: <a href='{link}'>ᴄʟɪᴄᴋ</a>\n"
                f"📈 ɢʀᴏᴜᴘ ᴍᴇᴍʙᴇʀs: {count}\n"
                f"🤔 ᴀᴅᴅᴇᴅ ʙʏ: {message.from_user.mention if message.from_user else '𝐔ɴᴋɴᴏᴡɴ'}"
            )

            # Button only if link is valid
            buttons = []
            if link.startswith("http"):
                buttons.append([InlineKeyboardButton("sᴇᴇ ɢʀᴏᴜᴘ👀", url=link)])

            await app.send_photo(
                LOG_GROUP_ID,
                photo=chatlog_img,
                caption=msg,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
            )


# ➤ Triggered when the bot is removed from a group
@app.on_message(filters.left_chat_member)
async def on_left_chat_member(_, message: Message):
    bot_user = await app.get_me()

    if message.left_chat_member.id != bot_user.id:
        return

    chat = message.chat
    try:
        title = chat.title or "𝐔ɴᴋɴᴏᴡɴ"
        username = f"@{chat.username}" if chat.username else "𝐏ʀɪᴠᴀᴛᴇ 𝐂ʜᴀᴛ"
        members = await app.get_chat_members_count(chat.id)
        link = await app.export_chat_invite_link(chat.id)
    except Exception:
        title = chat.title or "𝐔ɴᴋɴᴏᴡɴ"
        username = f"@{chat.username}" if chat.username else "𝐏ʀɪᴠᴀᴛᴇ 𝐂ʜᴀᴛ"
        members = "❌"
        link = "❌"

    removed_by = message.from_user.mention if message.from_user else "𝐔ɴᴋɴᴏᴡɴ 𝐔sᴇʀ"

    left_msg = (
        "✫ <b><u>#𝐋ᴇғᴛ_𝐆ʀᴏᴜᴘ</u></b> ✫\n\n"
        f"𝐂ʜᴀᴛ 𝐓ɪᴛʟᴇ : <code>{title}</code>\n"
        f"𝐂ʜᴀᴛ 𝐈ᴅ : <code>{chat.id}</code>\n"
        f"𝐔sᴇʀɴᴀᴍᴇ : {username}\n"
        f"𝐌ᴇᴍʙᴇʀs : {members}\n"
        f"𝐂ʜᴀᴛ ʟɪɴᴋ : {link}\n"
        f"𝐑ᴇᴍᴏᴠᴇᴅ ʙʏ : {removed_by}\n"
        f"𝐁ᴏᴛ : @{bot_user.username}"
    )

    await app.send_message(
        LOG_GROUP_ID,
        text=left_msg,
        parse_mode=ParseMode.HTML
    )
