# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from Tune import app
from Tune.utils.decorators.language import language_no_delete


@app.on_message(filters.command("id"))
@language_no_delete
async def get_id(client, message: Message, _):
    chat, user, reply = message.chat, message.from_user, message.reply_to_message
    out = []

    out.append(_["id_1"].format(message.link, message.id) if message.link else _["id_2"].format(message.id))
    out.append(_["id_3"].format(user.id))

    if len(message.command) == 2:
        try:
            target = message.text.split(maxsplit=1)[1]
            tgt_user = await client.get_users(target)
            out.append(_["id_5"].format(tgt_user.id))
        except Exception:
            return await message.reply_text(_["id_4"], quote=True)

    if chat.username and chat.type != "private":
        out.append(_["id_6"].format(chat.username, chat.id))
    else:
        out.append(_["id_7"].format(chat.id))

    if reply:
        out.append(_["id_8"].format(reply.link, reply.id) if reply.link else _["id_9"].format(reply.id))

        if reply.from_user:
            out.append(_["id_10"].format(reply.from_user.id))

        if reply.forward_from_chat:
            out.append(_["id_11"].format(reply.forward_from_chat.title, reply.forward_from_chat.id))

        if reply.sender_chat:
            out.append(_["id_12"].format(reply.sender_chat.id))

    await message.reply_text(
        "\n".join(out),
        disable_web_page_preview=True,
        parse_mode=ParseMode.MARKDOWN,
    )
