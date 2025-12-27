# Authored By Certified Coders © 2025
import asyncio
import os
from datetime import datetime

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import (
    FloodWait,
    PeerIdInvalid,
    ChannelPrivate,
    ChannelInvalid,
    UserIsBlocked,
    InputUserDeactivated,
    UserDeactivated,
    UserDeactivatedBan,
)

from Tune import app
from Tune.misc import SUDOERS
from Tune.core.userbot import assistants
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
from Tune.core.dir import LOGS_DIR
from config import adminlist

IS_BROADCASTING = False

CLEANUP_ERRORS = (
    PeerIdInvalid,
    ChannelPrivate,
    ChannelInvalid,
    UserIsBlocked,
    InputUserDeactivated,
    UserDeactivated,
    UserDeactivatedBan,
)

CLEANUP_KEYWORDS = [
    "chat not found",
    "user deactivated",
    "user not found",
    "peer id invalid",
    "channel invalid",
    "channel private",
    "input user deactivated",
    "user is deactivated",
    "chat_id invalid",
    "user_id invalid",
    "user is blocked",
    "user blocked",
    "blocked by user",
]


def _log(message: str):
    try:
        log_file = os.path.join(LOGS_DIR, "broadcast_actions.txt")
        timestamp = datetime.now().strftime("[%d-%b-%y %H:%M:%S]")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} - {message}\n")
    except Exception:
        pass


def _should_cleanup(error: Exception) -> bool:
    if isinstance(error, CLEANUP_ERRORS):
        return True
    error_msg = str(error).lower()
    return any(keyword in error_msg for keyword in CLEANUP_KEYWORDS)


def _parse_flags(text: str) -> tuple:
    flags = set()
    query = text
    for flag, key in [("-pin", "pin"), ("-pinloud", "pinloud"), ("-nobot", "nobot"), 
                      ("-assistant", "assistant"), ("-user", "user")]:
        if flag in query:
            flags.add(key)
            query = query.replace(flag, "").strip()
    return flags, query


async def _send_message(target_id: int, is_forward: bool, source_chat: int, msg_id: int, text: str):
    for attempt in range(3):
        try:
            if is_forward:
                return await app.forward_messages(target_id, source_chat, msg_id), None
            return await app.send_message(target_id, text=text), None
        except FloodWait as fw:
            wait_time = int(fw.value)
            if wait_time > 200:
                return None, fw
            if attempt < 2:
                await asyncio.sleep(wait_time)
            else:
                return None, fw
        except Exception as e:
            if attempt == 2 or not isinstance(e, FloodWait):
                return None, e
    return None, None


async def _pin(result, pin_mode: str):
    try:
        msg = result[0] if isinstance(result, list) and result else result
        if hasattr(msg, 'pin'):
            await msg.pin(disable_notification=(pin_mode == "pin"))
            return True
    except Exception:
        pass
    return False


async def _broadcast_to_targets(target_ids: list, is_forward: bool, source_chat: int, 
                                 msg_id: int, text: str, pin_mode: str = None, 
                                 remove_func=None, verify_users: bool = False):
    sent = pinned = failed = 0
    to_remove = []
    failed_for_verify = []
    
    for target_id in target_ids:
        if not isinstance(target_id, int) or target_id == 0:
            continue
        
        result, error = await _send_message(target_id, is_forward, source_chat, msg_id, text)
        
        if result:
            sent += 1
            if pin_mode and await _pin(result, pin_mode):
                pinned += 1
            await asyncio.sleep(0.2)
        elif error:
            failed += 1
            if _should_cleanup(error):
                to_remove.append(target_id)
                _log(f"Removed invalid target {target_id}: {type(error).__name__}")
            elif verify_users:
                failed_for_verify.append((target_id, error))
            else:
                _log(f"Failed to send to {target_id}: {type(error).__name__}")
    
    removed = 0
    if to_remove and remove_func:
        for target_id in to_remove:
            try:
                await remove_func(target_id)
                removed += 1
            except Exception as e:
                _log(f"Failed to remove {target_id}: {e}")
    
    if verify_users and failed_for_verify:
        for user_id, _ in failed_for_verify[:100]:
            if user_id not in to_remove:
                try:
                    await app.get_users(user_id)
                except Exception as e:
                    if _should_cleanup(e):
                        try:
                            await remove_served_user(user_id)
                            removed += 1
                        except Exception:
                            pass
                await asyncio.sleep(0.05)
    
    return sent, pinned, failed, removed


async def _broadcast_to_chats(message, is_forward: bool, source_chat: int, msg_id: int, 
                              query: str, pin_mode: str, _):
    chats_data = await get_served_chats()
    chat_ids = [int(chat["chat_id"]) for chat in chats_data if chat.get("chat_id")]
    
    sent, pinned, failed, _ = await _broadcast_to_targets(
        chat_ids, is_forward, source_chat, msg_id, query, pin_mode, remove_served_chat
    )
    
    try:
        await message.reply_text(_["broad_3"].format(sent, failed, pinned))
    except Exception:
        pass


async def _broadcast_to_users(message, is_forward: bool, source_chat: int, msg_id: int, 
                              query: str, _):
    users_data = await get_served_users()
    user_ids = [int(user["user_id"]) for user in users_data if user.get("user_id")]
    
    sent, _, failed, removed = await _broadcast_to_targets(
        user_ids, is_forward, source_chat, msg_id, query, None, 
        remove_served_user, verify_users=True
    )
    
    if removed > 0:
        _log(f"Removed {removed} invalid users from database during broadcast")
    
    try:
        await message.reply_text(_["broad_4"].format(sent, failed))
    except Exception:
        pass


async def _broadcast_to_assistants(message, is_forward: bool, source_chat: int, msg_id: int, 
                                   query: str, _):
    aw = await message.reply_text(_["broad_5"])
    text = _["broad_6"]
    
    for num in assistants:
        sent = 0
        try:
            client = await get_client(num)
            async for dialog in client.get_dialogs():
                try:
                    if is_forward:
                        await client.forward_messages(dialog.chat.id, source_chat, msg_id)
                    else:
                        await client.send_message(dialog.chat.id, text=query)
                    sent += 1
                    await asyncio.sleep(3)
                except FloodWait as fw:
                    if int(fw.value) <= 200:
                        await asyncio.sleep(int(fw.value))
                except Exception:
                    continue
        except Exception as e:
            _log(f"Assistant {num} broadcast failed: {e}")
            continue
        text += _["broad_7"].format(num, sent)
    
    try:
        await aw.edit_text(text)
    except Exception:
        pass


@app.on_message(filters.command("broadcast") & SUDOERS)
@language
async def broadcast_message(client, message, _):
    global IS_BROADCASTING
    
    if IS_BROADCASTING:
        return await message.reply_text("Another broadcast is in progress. Please wait.")
    
    is_forward = bool(message.reply_to_message)
    source_chat = message.chat.id
    msg_id = message.reply_to_message.id if is_forward else None
    
    if not is_forward:
        if len(message.command) < 2:
            return await message.reply_text(_["broad_2"])
        flags, query = _parse_flags(message.text.split(None, 1)[1])
        if not query.strip():
            return await message.reply_text(_["broad_8"])
    else:
        flags, query = _parse_flags(message.text or "")
    
    pin_mode = "pinloud" if "pinloud" in flags else ("pin" if "pin" in flags else None)
    
    IS_BROADCASTING = True
    try:
        await message.reply_text(_["broad_1"])
        
        if "nobot" not in flags:
            await _broadcast_to_chats(message, is_forward, source_chat, msg_id, query, pin_mode, _)
        
        if "user" in flags:
            await _broadcast_to_users(message, is_forward, source_chat, msg_id, query, _)
        
        if "assistant" in flags:
            await _broadcast_to_assistants(message, is_forward, source_chat, msg_id, query, _)
    finally:
        IS_BROADCASTING = False


async def auto_clean():
    while True:
        await asyncio.sleep(10)
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    try:
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
        except Exception:
            continue


async def periodic_cleanup():
    while True:
        await asyncio.sleep(43200)
        try:
            cleaned_chats = cleaned_users = 0
            
            served_chats = await get_served_chats()
            for chat in served_chats:
                chat_id = int(chat.get("chat_id", 0))
                if chat_id >= 0:
                    continue
                try:
                    await app.get_chat(chat_id)
                except Exception as e:
                    if _should_cleanup(e):
                        try:
                            await remove_served_chat(chat_id)
                            cleaned_chats += 1
                            _log(f"Removed invalid chat {chat_id} during periodic cleanup: {type(e).__name__}")
                        except Exception:
                            pass
                await asyncio.sleep(0.1)
            
            served_users = await get_served_users()
            for user in served_users:
                user_id = int(user.get("user_id", 0))
                if user_id <= 0:
                    continue
                try:
                    await app.get_users(user_id)
                except Exception as e:
                    if _should_cleanup(e):
                        try:
                            await remove_served_user(user_id)
                            cleaned_users += 1
                            _log(f"Removed invalid user {user_id} during periodic cleanup: {type(e).__name__}")
                        except Exception:
                            pass
                await asyncio.sleep(0.1)
            
            if cleaned_chats > 0 or cleaned_users > 0:
                LOGGER(__name__).info(f"Periodic cleanup completed: {cleaned_chats} chats and {cleaned_users} users removed")
        except Exception as e:
            LOGGER(__name__).error(f"Error during periodic cleanup: {e}")

asyncio.create_task(auto_clean())
asyncio.create_task(periodic_cleanup())
