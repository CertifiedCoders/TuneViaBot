# Authored By Certified Coders © 2025
import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatJoinRequest
from pyrogram.errors import (
    ChatAdminRequired,
    UserAlreadyParticipant,
    UserNotParticipant,
    ChannelPrivate,
    FloodWait,
    PeerIdInvalid,
    ChatWriteForbidden,
)

from Tune import app
from Tune.utils.admin_filters import dev_filter, admin_filter, sudo_filter
from Tune.utils.database import get_assistant, get_lang
from Tune.utils.decorators.language import language_no_delete
from strings import get_string

ACTIVE_STATUSES = {
    ChatMemberStatus.OWNER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED,
}


async def _get_lang_strings(chat_id):
    try:
        language = await get_lang(chat_id)
        return get_string(language)
    except Exception:
        return get_string("en")


async def _is_participant(client, chat_id, user_id) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ACTIVE_STATUSES
    except (UserNotParticipant, PeerIdInvalid):
        return False
    except Exception:
        return False


async def _handle_flood_wait(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await func(*args, **kwargs)


async def join_userbot(app, chat_id, chat_username=None, _=None):
    if _ is None:
        _ = await _get_lang_strings(chat_id)
    
    userbot = await get_assistant(chat_id)

    try:
        member = await app.get_chat_member(chat_id, userbot.id)
        if member.status == ChatMemberStatus.BANNED:
            try:
                await app.unban_chat_member(chat_id, userbot.id)
            except ChatAdminRequired:
                return _["assistant_1"]
        if member.status in ACTIVE_STATUSES:
            return _["assistant_2"]
    except UserNotParticipant:
        pass
    except PeerIdInvalid:
        return _["assistant_3"]

    if chat_username:
        invite = chat_username if chat_username.startswith("@") else f"@{chat_username}"
    else:
        try:
            link = await app.create_chat_invite_link(chat_id)
            invite = link.invite_link
        except ChatAdminRequired:
            return _["assistant_4"]

    try:
        await _handle_flood_wait(userbot.join_chat, invite)
        return _["assistant_5"]
    except UserAlreadyParticipant:
        return _["assistant_6"]
    except Exception as e:
        return _["assistant_8"].format(str(e))


@app.on_chat_join_request()
async def approve_join_request(client, chat_join_request: ChatJoinRequest):
    userbot = await get_assistant(chat_join_request.chat.id)
    if chat_join_request.from_user.id != userbot.id:
        return
    
    chat_id = chat_join_request.chat.id
    _ = await _get_lang_strings(chat_id)

    try:
        if await _is_participant(client, chat_id, userbot.id):
            return
        
        await _handle_flood_wait(client.approve_chat_join_request, chat_id, userbot.id)
        
        try:
            await client.send_message(chat_id, _["assistant_9"])
        except ChatWriteForbidden:
            pass
    except (UserAlreadyParticipant, ChatAdminRequired, PeerIdInvalid):
        return


@app.on_message(
    filters.command(["userbotjoin", "assistantjoin"], prefixes=[".", "/"])
    & (filters.group | filters.private)
    & admin_filter
    & sudo_filter
)
@language_no_delete
async def join_group(app, message, _):
    chat_id = message.chat.id
    status_message = await message.reply(_["assistant_10"])

    try:
        me = await app.get_me()
        chat_member = await app.get_chat_member(chat_id, me.id)
        if chat_member.status != ChatMemberStatus.ADMINISTRATOR:
            await status_message.edit_text(_["assistant_11"])
            return
    except ChatAdminRequired:
        await status_message.edit_text(_["assistant_12"])
        return
    except Exception as e:
        await status_message.edit_text(_["assistant_13"].format(str(e)))
        return

    chat_username = message.chat.username or None
    response = await join_userbot(app, chat_id, chat_username, _)
    try:
        await status_message.edit_text(response)
    except ChatWriteForbidden:
        pass


@app.on_message(
    filters.command("userbotleave", prefixes=[".", "/"])
    & filters.group
    & admin_filter
    & sudo_filter
)
@language_no_delete
async def leave_one(app, message, _):
    chat_id = message.chat.id
    try:
        userbot = await get_assistant(chat_id)
        
        if not await _is_participant(userbot, chat_id, userbot.id):
            await message.reply(_["assistant_14"])
            return

        await _handle_flood_wait(userbot.leave_chat, chat_id)
        try:
            await app.send_message(chat_id, _["assistant_15"])
        except ChatWriteForbidden:
            pass
    except ChannelPrivate:
        await message.reply(_["assistant_16"])
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await message.reply(_["assistant_17"])
    except Exception as e:
        await message.reply(_["assistant_18"].format(str(e)))


@app.on_message(filters.command("leaveall", prefixes=["."]) & dev_filter)
@language_no_delete
async def leave_all(app, message, _):
    left = 0
    failed = 0
    status_message = await message.reply(_["assistant_19"])

    try:
        userbot = await get_assistant(message.chat.id)
        async for dialog in userbot.get_dialogs():
            if dialog.chat.id == -1002014167331:
                continue
            
            try:
                await _handle_flood_wait(userbot.leave_chat, dialog.chat.id)
                left += 1
            except Exception:
                failed += 1

            try:
                await status_message.edit_text(_["assistant_20"].format(left, failed))
            except ChatWriteForbidden:
                pass
            await asyncio.sleep(1)
    except FloodWait as e:
        await asyncio.sleep(e.value)
    finally:
        try:
            await app.send_message(message.chat.id, _["assistant_21"].format(left, failed))
        except ChatWriteForbidden:
            pass
