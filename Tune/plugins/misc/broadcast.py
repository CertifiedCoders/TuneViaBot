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
from Tune.core.dir import LOGS_DIR
from config import adminlist

IS_BROADCASTING = False

CLEANUP_ERRORS = (
    PeerIdInvalid,
    ChannelPrivate,
    ChannelInvalid,
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
]


def _write_to_log_file(message: str):
    try:
        log_file = os.path.join(LOGS_DIR, "broadcast_actions.txt")
        timestamp = datetime.now().strftime("[%d-%b-%y %H:%M:%S]")
        log_entry = f"{timestamp} - {message}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass


def _should_cleanup_error(error: Exception) -> bool:
    if isinstance(error, CLEANUP_ERRORS):
        return True
    error_msg = str(error).lower()
    return any(keyword in error_msg for keyword in CLEANUP_KEYWORDS)


def _parse_broadcast_flags(text: str) -> tuple:
    flags = set()
    query = text
    
    flag_patterns = {
        "-pin": "pin",
        "-pinloud": "pinloud",
        "-nobot": "nobot",
        "-assistant": "assistant",
        "-user": "user",
    }
    
    for flag, key in flag_patterns.items():
        if flag in query:
            flags.add(key)
            query = query.replace(flag, "").strip()
    
    return flags, query


async def _send_with_retry(target_id: int, is_forward: bool, source_chat: int, msg_id: int, text: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            if is_forward:
                result = await app.forward_messages(target_id, source_chat, msg_id)
            else:
                result = await app.send_message(target_id, text=text)
            return result, None
        except FloodWait as fw:
            wait_time = int(fw.value)
            if wait_time > 200:
                return None, fw
            if attempt < max_retries - 1:
                await asyncio.sleep(wait_time)
            else:
                return None, fw
        except Exception as e:
            if attempt == max_retries - 1 or not isinstance(e, FloodWait):
                return None, e
    return None, None


async def _pin_message(result, pin_mode: str):
    try:
        if hasattr(result, 'pin'):
            await result.pin(disable_notification=(pin_mode == "pin"))
            return True
        elif isinstance(result, list) and result:
            await result[0].pin(disable_notification=(pin_mode == "pin"))
            return True
    except Exception:
        pass
    return False


async def _broadcast_to_targets(target_ids: list, is_forward: bool, source_chat: int, msg_id: int, text: str, pin_mode: str = None):
    sent = 0
    pinned = 0
    failed = 0
    to_remove = []
    
    for target_id in target_ids:
        if not isinstance(target_id, int) or target_id == 0:
            continue
            
        result, error = await _send_with_retry(target_id, is_forward, source_chat, msg_id, text)
        
        if result:
            sent += 1
            if pin_mode and await _pin_message(result, pin_mode):
                pinned += 1
            await asyncio.sleep(0.2)
        elif error and _should_cleanup_error(error):
            to_remove.append(target_id)
            failed += 1
            _write_to_log_file(f"Removed invalid target {target_id}: {type(error).__name__}")
        else:
            failed += 1
            if error:
                _write_to_log_file(f"Failed to send to {target_id}: {type(error).__name__}")
    
    return sent, pinned, failed, to_remove


async def _broadcast_to_chats(message, is_forward: bool, source_chat: int, msg_id: int, query: str, pin_mode: str, _):
    chats_data = await get_served_chats()
    chat_ids = [int(chat["chat_id"]) for chat in chats_data if chat.get("chat_id")]
    
    sent, pinned, failed, to_remove = await _broadcast_to_targets(
        chat_ids, is_forward, source_chat, msg_id, query, pin_mode
    )
    
    for chat_id in to_remove:
        try:
            await remove_served_chat(chat_id)
        except Exception as e:
            _write_to_log_file(f"Failed to remove chat {chat_id}: {e}")
    
    try:
        summary = _["broad_3"].format(sent, failed, pinned)
        await message.reply_text(summary)
    except Exception as e:
        _write_to_log_file(f"Failed to send chat broadcast summary: {e}")


async def _broadcast_to_users(message, is_forward: bool, source_chat: int, msg_id: int, query: str, _):
    users_data = await get_served_users()
    user_ids = [int(user["user_id"]) for user in users_data if user.get("user_id")]
    
    sent, _, failed, to_remove = await _broadcast_to_targets(
        user_ids, is_forward, source_chat, msg_id, query, None
    )
    
    for user_id in to_remove:
        try:
            await remove_served_user(user_id)
        except Exception as e:
            _write_to_log_file(f"Failed to remove user {user_id}: {e}")
    
    try:
        summary = _["broad_4"].format(sent, failed)
        await message.reply_text(summary)
    except Exception as e:
        _write_to_log_file(f"Failed to send user broadcast summary: {e}")


async def _broadcast_to_assistants(message, is_forward: bool, source_chat: int, msg_id: int, query: str, _):
    from Tune.core.userbot import assistants
    
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
                    wait_time = int(fw.value)
                    if wait_time <= 200:
                        await asyncio.sleep(wait_time)
                except Exception:
                    continue
        except Exception as e:
            _write_to_log_file(f"Assistant {num} broadcast failed: {e}")
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
        flags, query = _parse_broadcast_flags(message.text.split(None, 1)[1])
        if not query.strip():
            return await message.reply_text(_["broad_8"])
    else:
        flags, query = _parse_broadcast_flags(message.text or "")
    
    pin_mode = None
    if "pinloud" in flags:
        pin_mode = "pinloud"
    elif "pin" in flags:
        pin_mode = "pin"
    
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
    while not await asyncio.sleep(10):
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
    while not await asyncio.sleep(43200):
        try:
            cleaned_chats = 0
            cleaned_users = 0
            
            served_chats = await get_served_chats()
            for chat in served_chats:
                chat_id = int(chat.get("chat_id", 0))
                if chat_id >= 0:
                    continue
                try:
                    await app.get_chat(chat_id)
                except Exception as e:
                    if _should_cleanup_error(e):
                        await remove_served_chat(chat_id)
                        cleaned_chats += 1
                        _write_to_log_file(f"Removed invalid chat {chat_id} during periodic cleanup: {type(e).__name__}")
                await asyncio.sleep(0.1)
            
            served_users = await get_served_users()
            for user in served_users:
                user_id = int(user.get("user_id", 0))
                if user_id <= 0:
                    continue
                try:
                    await app.get_users(user_id)
                except Exception as e:
                    if _should_cleanup_error(e):
                        await remove_served_user(user_id)
                        cleaned_users += 1
                        _write_to_log_file(f"Removed invalid user {user_id} during periodic cleanup: {type(e).__name__}")
                await asyncio.sleep(0.1)
            
            if cleaned_chats > 0 or cleaned_users > 0:
                LOGGER(__name__).info(f"Periodic cleanup completed: {cleaned_chats} chats and {cleaned_users} users removed")
        except Exception as e:
            LOGGER(__name__).error(f"Error during periodic cleanup: {e}")

asyncio.create_task(auto_clean())
asyncio.create_task(periodic_cleanup())
