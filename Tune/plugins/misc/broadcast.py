# Authored By Certified Coders © 2025
import asyncio

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import (
    FloodWait,
    UserDeactivated,
    UserDeactivatedBan,
    ChatNotFound,
    PeerIdInvalid,
    ChannelPrivate,
    InputUserDeactivated,
)

from Tune import app
from Tune.misc import SUDOERS
from Tune.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_client,
    get_served_chats,
    get_served_users,
    remove_served_chat,
    remove_served_user,
)
from Tune.utils.decorators.language import language
from Tune.utils.formatters import alpha_to_int
from Tune.logging import LOGGER
from config import adminlist

IS_BROADCASTING = False

CLEANUP_ERRORS = (
    UserDeactivated,
    UserDeactivatedBan,
    ChatNotFound,
    PeerIdInvalid,
    ChannelPrivate,
    InputUserDeactivated,
)


@app.on_message(filters.command("broadcast") & SUDOERS)
@language
async def braodcast_message(client, message, _):
    global IS_BROADCASTING
    if message.reply_to_message:
        x = message.reply_to_message.id
        y = message.chat.id
    else:
        if len(message.command) < 2:
            return await message.reply_text(_["broad_2"])
        query = message.text.split(None, 1)[1]
        if "-pin" in query:
            query = query.replace("-pin", "")
        if "-nobot" in query:
            query = query.replace("-nobot", "")
        if "-pinloud" in query:
            query = query.replace("-pinloud", "")
        if "-assistant" in query:
            query = query.replace("-assistant", "")
        if "-user" in query:
            query = query.replace("-user", "")
        if query == "":
            return await message.reply_text(_["broad_8"])

    IS_BROADCASTING = True
    await message.reply_text(_["broad_1"])

    if "-nobot" not in message.text:
        sent = 0
        pin = 0
        failed = 0
        chats = []
        schats = await get_served_chats()
        for chat in schats:
            chats.append(int(chat["chat_id"]))
        for i in chats:
            try:
                m = (
                    await app.forward_messages(i, y, x)
                    if message.reply_to_message
                    else await app.send_message(i, text=query)
                )
                if "-pin" in message.text:
                    try:
                        await m.pin(disable_notification=True)
                        pin += 1
                    except Exception:
                        continue
                elif "-pinloud" in message.text:
                    try:
                        await m.pin(disable_notification=False)
                        pin += 1
                    except Exception:
                        continue
                sent += 1
                await asyncio.sleep(0.2)
            except FloodWait as fw:
                flood_time = int(fw.value)
                if flood_time > 200:
                    continue
                await asyncio.sleep(flood_time)
            except CLEANUP_ERRORS as e:
                failed += 1
                await remove_served_chat(i)
                LOGGER(__name__).info(f"Removed invalid chat {i} from database: {type(e).__name__}")
            except Exception as e:
                failed += 1
                LOGGER(__name__).warning(f"Failed to send to chat {i}: {type(e).__name__}")
                continue
        try:
            await message.reply_text(_["broad_3"].format(sent, pin))
            if failed > 0:
                await message.reply_text(f"⚠️ Failed to send to {failed} chat(s). Invalid entries removed from database.")
        except Exception:
            pass

    if "-user" in message.text:
        susr = 0
        failed = 0
        served_users = []
        susers = await get_served_users()
        for user in susers:
            served_users.append(int(user["user_id"]))
        for i in served_users:
            try:
                m = (
                    await app.forward_messages(i, y, x)
                    if message.reply_to_message
                    else await app.send_message(i, text=query)
                )
                susr += 1
                await asyncio.sleep(0.2)
            except FloodWait as fw:
                flood_time = int(fw.value)
                if flood_time > 200:
                    continue
                await asyncio.sleep(flood_time)
            except CLEANUP_ERRORS as e:
                failed += 1
                await remove_served_user(i)
                LOGGER(__name__).info(f"Removed invalid user {i} from database: {type(e).__name__}")
            except Exception as e:
                failed += 1
                LOGGER(__name__).warning(f"Failed to send to user {i}: {type(e).__name__}")
                pass
        try:
            await message.reply_text(_["broad_4"].format(susr))
            if failed > 0:
                await message.reply_text(f"⚠️ Failed to send to {failed} user(s). Invalid entries removed from database.")
        except Exception:
            pass

    if "-assistant" in message.text:
        aw = await message.reply_text(_["broad_5"])
        text = _["broad_6"]
        from Tune.core.userbot import assistants

        for num in assistants:
            sent = 0
            client = await get_client(num)
            async for dialog in client.get_dialogs():
                try:
                    await client.forward_messages(
                        dialog.chat.id, y, x
                    ) if message.reply_to_message else await client.send_message(
                        dialog.chat.id, text=query
                    )
                    sent += 1
                    await asyncio.sleep(3)
                except FloodWait as fw:
                    flood_time = int(fw.value)
                    if flood_time > 200:
                        continue
                    await asyncio.sleep(flood_time)
                except Exception:
                    continue
            text += _["broad_7"].format(num, sent)
        try:
            await aw.edit_text(text)
        except Exception:
            pass
    IS_BROADCASTING = False


async def auto_clean():
    while not await asyncio.sleep(10):
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    async for user in app.get_chat_members(
                        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                    ):
                        if getattr(user.privileges, 'can_manage_video_chats', False):
                            adminlist[chat_id].append(user.user.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        adminlist[chat_id].append(user_id)
        except Exception:
            continue


async def periodic_cleanup():
    while not await asyncio.sleep(43200):
        try:
            LOGGER(__name__).info("Starting periodic database cleanup...")
            cleaned_chats = 0
            cleaned_users = 0

            served_chats = await get_served_chats()
            for chat in served_chats:
                chat_id = int(chat["chat_id"])
                try:
                    await app.get_chat(chat_id)
                except CLEANUP_ERRORS:
                    await remove_served_chat(chat_id)
                    cleaned_chats += 1
                    LOGGER(__name__).info(f"Removed invalid chat {chat_id} during periodic cleanup")
                except Exception:
                    pass

            served_users = await get_served_users()
            for user in served_users:
                user_id = int(user["user_id"])
                try:
                    await app.get_users(user_id)
                except CLEANUP_ERRORS:
                    await remove_served_user(user_id)
                    cleaned_users += 1
                    LOGGER(__name__).info(f"Removed invalid user {user_id} during periodic cleanup")
                except Exception:
                    pass

            if cleaned_chats > 0 or cleaned_users > 0:
                LOGGER(__name__).info(f"Periodic cleanup completed: {cleaned_chats} chats and {cleaned_users} users removed")
        except Exception as e:
            LOGGER(__name__).error(f"Error during periodic cleanup: {e}")


asyncio.create_task(auto_clean())
asyncio.create_task(periodic_cleanup())
