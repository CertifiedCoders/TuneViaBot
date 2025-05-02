from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from Tune import app

@app.on_message(filters.command('id'))
async def get_id(client, message: Message):
    chat = message.chat
    user = message.from_user
    reply = message.reply_to_message

    text = f"**[ᴍᴇssᴀɢᴇ ɪᴅ:]({message.link})** `{message.id}`\n"
    text += f"**[ʏᴏᴜʀ ɪᴅ:](tg://user?id={user.id})** `{user.id}`\n"

    if len(message.command) == 2:
        try:
            target = message.text.split(None, 1)[1].strip()
            target_user = await client.get_users(target)
            text += f"**[ᴜsᴇʀ ɪᴅ:](tg://user?id={target_user.id})** `{target_user.id}`\n"
        except Exception:
            return await message.reply_text("**ᴛʜɪs ᴜsᴇʀ ᴅᴏᴇsɴ'ᴛ ᴇxɪsᴛ.**", quote=True)

    if chat.username:
        text += f"**[ᴄʜᴀᴛ ɪᴅ:](https://t.me/{chat.username})** `{chat.id}`\n\n"
    else:
        text += f"**ᴄʜᴀᴛ ɪᴅ:** `{chat.id}`\n\n"

    if reply:
        if reply.from_user:
            text += f"**[ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ ɪᴅ:]({reply.link})** `{reply.id}`\n"
            text += f"**[ʀᴇᴘʟɪᴇᴅ ᴜsᴇʀ ɪᴅ:](tg://user?id={reply.from_user.id})** `{reply.from_user.id}`\n\n"

        if reply.forward_from_chat:
            text += f"ᴛʜᴇ ғᴏʀᴡᴀʀᴅᴇᴅ ᴄʜᴀɴɴᴇʟ, {reply.forward_from_chat.title}, ʜᴀs ᴀɴ ɪᴅ ᴏғ `{reply.forward_from_chat.id}`\n\n"

        if reply.sender_chat:
            text += f"ɪᴅ ᴏғ ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴄʜᴀᴛ/ᴄʜᴀɴɴᴇʟ: `{reply.sender_chat.id}`"

    await message.reply_text(
        text,
        disable_web_page_preview=True,
        parse_mode=ParseMode.DEFAULT
    )
