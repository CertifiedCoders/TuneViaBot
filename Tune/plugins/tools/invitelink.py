# Authored By Certified Coders © 2025
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChannelInvalid, ChannelPrivate
from Tune import app
from Tune.misc import SUDOERS
from Tune.utils.decorators.language import language_no_delete


@app.on_message(filters.command("givelink"))
@language_no_delete
async def give_link_command(client: Client, message: Message, _):
    try:
        link = await app.export_chat_invite_link(message.chat.id)
        await message.reply_text(_["invitelink_1"].format(message.chat.title, link))
    except Exception as e:
        await message.reply_text(_["invitelink_2"].format(str(e)))


@app.on_message(filters.command(["link", "invitelink"], prefixes=["/", "!", ".", "#", "?"]) & SUDOERS)
@language_no_delete
async def link_command_handler(client: Client, message: Message, _):
    if len(message.command) != 2:
        return await message.reply(_["invitelink_3"])

    group_id = message.command[1]
    file_name = f"group_info_{group_id}.txt"

    try:
        chat = await client.get_chat(int(group_id))
        if not chat:
            return await message.reply(_["invitelink_4"])

        try:
            invite_link = await client.export_chat_invite_link(chat.id)
        except (ChannelInvalid, ChannelPrivate):
            return await message.reply(_["invitelink_5"])
        except FloodWait as e:
            return await message.reply(_["invitelink_6"].format(e.value))

        group_data = {
            "id": chat.id,
            "type": str(chat.type),
            "title": chat.title,
            "members_count": chat.members_count,
            "description": chat.description,
            "invite_link": invite_link,
            "is_verified": chat.is_verified,
            "is_restricted": chat.is_restricted,
            "is_creator": chat.is_creator,
            "is_scam": chat.is_scam,
            "is_fake": chat.is_fake,
            "dc_id": chat.dc_id,
            "has_protected_content": chat.has_protected_content,
        }

        with open(file_name, "w", encoding="utf-8") as file:
            for key, value in group_data.items():
                file.write(f"{key}: {value}\n")

        await client.send_document(
            chat_id=message.chat.id,
            document=file_name,
            caption=_["invitelink_7"].format(chat.title, app.username),
        )

    except ValueError:
        await message.reply(_["invitelink_8"])
    except Exception as e:
        await message.reply_text(_["invitelink_9"].format(str(e)))
    finally:
        if os.path.exists(file_name):
            os.remove(file_name)
