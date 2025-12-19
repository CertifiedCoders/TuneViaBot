# Authored By Certified Coders © 2025
import re
import os
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.utils.antispam import track_command, reset_user_tracking
from Tune.utils.database import is_spam_blocked, is_antispam_enabled
from config import SUPPORT_CHAT, OWNER_ID, LOGGER_ID
from Tune.core.dir import LOGS_DIR
from Tune.logging import LOGGER

_spam_blocked_users_cache = set()
_user_notified_cache = set()
_support_notified_cache = set()
_debug_file_path = os.path.join(LOGS_DIR, "antispam_debug.txt")


def _write_debug_log(event_type: str, data: dict):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{event_type}] {data}\n"
        with open(_debug_file_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass


def get_spam_blocked_cache():
    return _spam_blocked_users_cache


def clear_user_notification(user_id: int):
    if user_id in _user_notified_cache:
        _user_notified_cache.discard(user_id)
    if user_id in _support_notified_cache:
        _support_notified_cache.discard(user_id)


async def _notify_user_blocked(user_id: int):
    if user_id in _user_notified_cache:
        return
    
    try:
        await app.send_message(
            user_id,
            "⚠️ <b>You've been blocked for spamming</b>\n\n"
            "You were caught sending too many commands in a short time.\n"
            "You are now blocked from using this bot.\n\n"
            f"If you believe this is a mistake, contact support:\n{SUPPORT_CHAT}"
        )
        _user_notified_cache.add(user_id)
        _write_debug_log("NOTIFY_USER", {"user_id": user_id, "status": "sent"})
    except Exception as e:
        _write_debug_log("NOTIFY_USER", {"user_id": user_id, "status": "failed", "error": str(e)})


async def _notify_support_chat(user_id: int, user_name: str, username: str, chat_info: str, spammed_commands: list, timestamp: str):
    if user_id in _support_notified_cache:
        return
    
    try:
        user_display = f"{user_name}" if user_name else f"User {user_id}"
        if username:
            user_display += f" (@{username})"
        
        commands_list = ", ".join([f"/{cmd}" for cmd in spammed_commands[:20]])
        if len(spammed_commands) > 20:
            commands_list += f" ... and {len(spammed_commands) - 20} more"
        
        spam_notification = (
            f"🚫 <b>Spam Detected & Blocked</b>\n\n"
            f"👤 <b>User:</b> {user_display}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"📍 <b>Location:</b> {chat_info}\n"
            f"⚡ <b>Commands Spammed:</b> {len(spammed_commands)}/10\n"
            f"🔧 <b>Commands:</b> {commands_list}\n"
            f"⏱ <b>Time:</b> {timestamp}\n"
            f"🔒 <b>Status:</b> User blocked - all messages ignored"
        )
        
        await app.send_message(LOGGER_ID, spam_notification)
        _support_notified_cache.add(user_id)
        _write_debug_log("SUPPORT_NOTIFICATION", {"user_id": user_id, "status": "sent"})
    except Exception as e:
        _write_debug_log("SUPPORT_NOTIFICATION", {"user_id": user_id, "status": "failed", "error": str(e)})


def _extract_commands_from_source():
    commands_set = set()
    try:
        base_dir = os.getcwd()
        plugins_dir = os.path.join(base_dir, "Tune", "plugins")
        if not os.path.exists(plugins_dir):
            return commands_set
        
        for root, dirs, files in os.walk(plugins_dir):
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            
                            patterns = [
                                r'filters\.command\(["\']([^"\']+)["\']',
                                r'filters\.command\(\[([^\]]+)\]\)',
                            ]
                            
                            for pattern in patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
                                for match in matches:
                                    if isinstance(match, str):
                                        if match and not match.startswith('['):
                                            commands_set.add(match.lower())
                                    elif isinstance(match, tuple):
                                        for cmd in match:
                                            if cmd and not cmd.startswith('['):
                                                commands_set.add(cmd.lower())
                            
                            list_pattern = r'filters\.command\(\[([^\]]+)\]\)'
                            list_matches = re.findall(list_pattern, content, re.IGNORECASE | re.MULTILINE)
                            for match in list_matches:
                                cmd_list = re.findall(r'["\']([^"\']+)["\']', match)
                                for cmd in cmd_list:
                                    commands_set.add(cmd.lower())
                    except Exception:
                        continue
    except Exception as e:
        LOGGER(__name__).warning(f"Failed to extract commands from source: {e}")
    
    return sorted(commands_set)


def _get_all_protected_commands():
    commands_set = set()
    try:
        dispatcher = app.dispatcher
        handler_groups = getattr(dispatcher, 'groups', None) or getattr(dispatcher, 'handlers', {})
        
        if not handler_groups or not isinstance(handler_groups, dict):
            handler_groups = {}
            for attr_name in dir(dispatcher):
                if 'handler' in attr_name.lower() and not attr_name.startswith('_'):
                    try:
                        attr_value = getattr(dispatcher, attr_name, None)
                        if isinstance(attr_value, dict):
                            handler_groups.update(attr_value)
                    except Exception:
                        continue
        
        for group_id, handlers in handler_groups.items():
            if not isinstance(handlers, (list, tuple)):
                continue
            for handler in handlers:
                try:
                    if hasattr(handler, 'filters'):
                        filter_obj = handler.filters
                        if filter_obj:
                            filter_str = str(filter_obj)
                            if 'command' in filter_str.lower():
                                single_cmd = re.search(r'command\(["\']([^"\']+)["\']\)', filter_str, re.IGNORECASE)
                                if single_cmd:
                                    commands_set.add(single_cmd.group(1).lower())
                                list_match = re.search(r'command\(\[([^\]]+)\]\)', filter_str, re.IGNORECASE)
                                if list_match:
                                    for cmd in re.findall(r'["\']([^"\']+)["\']', list_match.group(1)):
                                        commands_set.add(cmd.lower())
                except Exception:
                    continue
        
        if not commands_set:
            commands_set = _extract_commands_from_source()
    except Exception as e:
        LOGGER(__name__).warning(f"Failed to extract commands: {e}")
        commands_set = _extract_commands_from_source()
    
    return sorted(commands_set) if commands_set else []


async def _check_is_command(_, __, message: Message):
    if not message or not hasattr(message, 'command'):
        return False
    return bool(message.command)


COMMAND_FILTER = filters.create(_check_is_command)


@app.on_message(COMMAND_FILTER, group=-1)
async def antispam_command_handler(client, message: Message):
    try:
        command_name = message.command[0] if message.command else None
        user_id = message.from_user.id if message.from_user else None
        
        _write_debug_log("HANDLER_CALLED", {
            "message_id": message.id,
            "chat_id": message.chat.id if message.chat else None,
            "has_command": bool(message.command),
            "command": command_name,
            "user_id": user_id
        })
        
        LOGGER(__name__).debug(f"Antispam handler called: user={user_id}, command={command_name}")
        
        if not message.command or not message.from_user:
            _write_debug_log("HANDLER_EXIT", {"reason": "no_command_or_user"})
            return
        
        user_id = message.from_user.id
        command_name = message.command[0].lower() if message.command else "unknown"
        
        _write_debug_log("USER_CHECK", {
            "user_id": user_id,
            "command": command_name,
            "is_owner": user_id == OWNER_ID
        })
        
        if user_id == OWNER_ID:
            _write_debug_log("HANDLER_EXIT", {"reason": "owner_exempt"})
            return
        
        try:
            bot_me = await app.get_me()
            if user_id == bot_me.id:
                _write_debug_log("HANDLER_EXIT", {"reason": "bot_self"})
                return
        except Exception as e:
            _write_debug_log("BOT_ME_ERROR", {"error": str(e)})
        
        if user_id in _spam_blocked_users_cache:
            _write_debug_log("ALREADY_BLOCKED_CACHE", {"user_id": user_id})
            await message.stop_propagation()
            return
        
        is_blocked_db = await is_spam_blocked(user_id)
        _write_debug_log("DB_BLOCK_CHECK", {"user_id": user_id, "is_blocked": is_blocked_db})
        
        if is_blocked_db:
            _spam_blocked_users_cache.add(user_id)
            _write_debug_log("ALREADY_BLOCKED_DB", {"user_id": user_id})
            await message.stop_propagation()
            return
        
        antispam_enabled = await is_antispam_enabled()
        _write_debug_log("ANTISPAM_ENABLED", {"enabled": antispam_enabled, "user_id": user_id})
        
        if not antispam_enabled:
            _write_debug_log("HANDLER_EXIT", {"reason": "antispam_disabled"})
            return
        
        is_spamming, command_count, spammed_commands = await track_command(user_id, command_name)
        
        _write_debug_log("SPAM_CHECK", {
            "user_id": user_id,
            "command": command_name,
            "is_spamming": is_spamming,
            "command_count": command_count,
            "spammed_commands_count": len(spammed_commands)
        })
        
        if is_spamming:
            _spam_blocked_users_cache.add(user_id)
            
            try:
                user_name = f"{message.from_user.first_name}"
                if message.from_user.last_name:
                    user_name += f" {message.from_user.last_name}"
            except Exception:
                user_name = None
            
            username = message.from_user.username if message.from_user.username else None
            
            try:
                chat_type_str = str(message.chat.type)
                is_private = "private" in chat_type_str.lower()
                
                if is_private:
                    chat_info = "Bot DM"
                else:
                    chat_title = getattr(message.chat, 'title', None) or "N/A"
                    chat_id = message.chat.id
                    chat_info = f"Group: {chat_title} (ID: {chat_id})"
            except Exception:
                chat_info = "Unknown Location"
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            _write_debug_log("SPAM_DETECTED", {
                "user_id": user_id,
                "command_count": command_count,
                "commands": spammed_commands[:10]
            })
            
            await _notify_user_blocked(user_id)
            await _notify_support_chat(user_id, user_name, username, chat_info, spammed_commands, timestamp)
            
            _write_debug_log("STOP_PROPAGATION", {"user_id": user_id, "command": command_name})
            await message.stop_propagation()
            return
        
        _write_debug_log("HANDLER_ALLOWED", {"user_id": user_id, "command": command_name, "count": command_count})
    except Exception as e:
        import traceback
        error_tb = traceback.format_exc()
        _write_debug_log("HANDLER_ERROR", {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": error_tb
        })
        LOGGER(__name__).error(f"Error in antispam handler: {e}")


async def log_antispam_status():
    try:
        enabled = await is_antispam_enabled()
        protected_commands = _get_all_protected_commands()
        cmd_count = len(protected_commands)
        status = "enabled" if enabled else "disabled"
        
        _write_debug_log("STARTUP_STATUS", {
            "enabled": enabled,
            "command_count": cmd_count,
            "owner_id": OWNER_ID
        })
        
        if protected_commands:
            commands_list = ", ".join(protected_commands[:100])
            if cmd_count > 100:
                commands_list += f" ... and {cmd_count - 100} more"
            LOGGER("Tune").info(f"ᴀɴᴛɪ-sᴘᴀᴍ {status} ɪɴ ʙᴏᴛ ғᴏʀ {cmd_count} ᴄᴏᴍᴍᴀɴᴅs: {commands_list}")
        else:
            LOGGER("Tune").info(f"ᴀɴᴛɪ-sᴘᴀᴍ {status} ɪɴ ʙᴏᴛ - ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs ᴀʀᴇ ᴘʀᴏᴛᴇᴄᴛᴇᴅ")
    except Exception as e:
        LOGGER("Tune").warning(f"ғᴀɪʟᴇᴅ ᴛᴏ ʟᴏɢ ᴀɴᴛɪ-sᴘᴀᴍ sᴛᴀᴛᴜs: {e}")
