# Authored By Certified Coders © 2025
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message, User

from Tune import app


async def extract_user(m: Message) -> User:
    if m.reply_to_message:
        return m.reply_to_message.from_user

    if m.entities:
        entity_index = 1 if m.text and m.text.startswith("/") else 0
        if entity_index < len(m.entities):
            entity = m.entities[entity_index]
            if entity.type == MessageEntityType.TEXT_MENTION:
                return await app.get_users(entity.user.id)

    user_arg = m.command[1]
    return await app.get_users(int(user_arg) if user_arg.isdecimal() else user_arg)
