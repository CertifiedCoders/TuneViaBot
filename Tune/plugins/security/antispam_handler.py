# Authored By Certified Coders © 2025
import re
import os
import traceback
from datetime import datetime
from pyrogram import filters, StopPropagation
from pyrogram.types import Message

from Tune import app
from Tune.utils.antispam import track_command, reset_user_tracking, get_user_command_count
from Tune.utils.database import is_spam_blocked, is_antispam_enabled
from config import SUPPORT_CHAT, OWNER_ID, LOGGER_ID
from Tune.core.dir import LOGS_DIR
from Tune.logging import LOGGER

_spam_blocked_users_cache = set()
_user_notified_cache = set()
_support_notified_cache = set()
_debug_file_path = os.path.join(LOGS_DIR, "antispam_debug.txt")
_COMMAND_PREFIXES = ["/", "!", ".", "#", "?"]


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
    _user_notified_cache.discard(user_id)
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
        user_display = user_name or f"User {user_id}"
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


def _extract_command_from_text(text: str) -> str:
    text = text.strip()
    for prefix in _COMMAND_PREFIXES:
        if text.startswith(prefix):
            parts = text[1:].split(maxsplit=1)
            if parts and parts[0]:
                return parts[0].lower()
    return "unknown"


def _extract_commands_from_source():
    commands_set = set()
    try:
        plugins_dir = os.path.join(os.getcwd(), "Tune", "plugins")
        if not os.path.exists(plugins_dir):
            return commands_set
        
        patterns = [
            r'filters\.command\(["\']([^"\']+)["\']',
            r'filters\.command\(\[([^\]]+)\]\)',
        ]
        
        for root, dirs, files in os.walk(plugins_dir):
            for file in files:
                if not file.endswith(".py") or file.startswith("__"):
                    continue
                
                try:
                    with open(os.path.join(root, file), "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
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
                        
                        list_matches = re.findall(r'filters\.command\(\[([^\]]+)\]\)', content, re.IGNORECASE | re.MULTILINE)
                        for match in list_matches:
                            for cmd in re.findall(r'["\']([^"\']+)["\']', match):
                                commands_set.add(cmd.lower())
                except Exception:
                    continue
    except Exception as e:
        _write_debug_log("EXTRACT_COMMANDS_ERROR", {"error": str(e)})
    
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
                    filter_obj = getattr(handler, 'filters', None)
                    if not filter_obj:
                        continue
                    
                    filter_str = str(filter_obj).lower()
                    if 'command' not in filter_str:
                        continue
                    
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
        _write_debug_log("GET_COMMANDS_ERROR", {"error": str(e)})
        commands_set = _extract_commands_from_source()
    
    return sorted(commands_set) if commands_set else []


def _check_command(_, __, message: Message):
    if not message:
        return False
    if hasattr(message, 'command') and message.command:
        return True
    if message.text:
        text = message.text.strip()
        return any(text.startswith(prefix) for prefix in _COMMAND_PREFIXES) and len(text) > 1
    return False


def _get_command_name(message: Message) -> str:
    if hasattr(message, 'command') and message.command:
        return message.command[0].lower()
    return _extract_command_from_text(message.text) if message.text else "unknown"


def _get_user_info(message: Message):
    try:
        user_name = message.from_user.first_name or ""
        if message.from_user.last_name:
            user_name += f" {message.from_user.last_name}"
        user_name = user_name.strip() or None
    except Exception:
        user_name = None
    
    username = getattr(message.from_user, 'username', None)
    return user_name, username


def _get_chat_info(message: Message) -> str:
    try:
        chat_type_str = str(message.chat.type).lower()
        if "private" in chat_type_str:
            return "Bot DM"
        chat_title = getattr(message.chat, 'title', None) or "N/A"
        return f"Group: {chat_title} (ID: {message.chat.id})"
    except Exception:
        return "Unknown Location"


COMMAND_FILTER = filters.create(_check_command)


@app.on_message(COMMAND_FILTER, group=-1)
async def antispam_command_handler(client, message: Message):
    try:
        if not message or not message.from_user or not message.text:
            return
        
        user_id = message.from_user.id
        command_name = _get_command_name(message)
        
        _write_debug_log("HANDLER_CALLED", {
            "message_id": message.id,
            "chat_id": message.chat.id if message.chat else None,
            "user_id": user_id,
            "command": command_name,
            "text_preview": message.text[:50]
        })
        
        if user_id == OWNER_ID:
            _write_debug_log("HANDLER_EXIT", {"reason": "owner_exempt"})
            return
        
        try:
            bot_me = await app.get_me()
            if user_id == bot_me.id:
                _write_debug_log("HANDLER_EXIT", {"reason": "bot_self"})
                return
        except Exception:
            pass
        
        if user_id in _spam_blocked_users_cache:
            _write_debug_log("ALREADY_BLOCKED_CACHE", {"user_id": user_id})
            raise StopPropagation()
        
        is_blocked_db = await is_spam_blocked(user_id)
        if is_blocked_db:
            _spam_blocked_users_cache.add(user_id)
            _write_debug_log("ALREADY_BLOCKED_DB", {"user_id": user_id})
            raise StopPropagation()
        
        if not await is_antispam_enabled():
            _write_debug_log("HANDLER_EXIT", {"reason": "antispam_disabled"})
            return
        
        _write_debug_log("BEFORE_TRACK", {
            "user_id": user_id,
            "command": command_name,
            "current_count": get_user_command_count(user_id)
        })
        
        is_spamming, command_count, spammed_commands = await track_command(user_id, command_name)
        
        _write_debug_log("AFTER_TRACK", {
            "user_id": user_id,
            "command": command_name,
            "command_count": command_count,
            "is_spamming": is_spamming,
            "spammed_commands": spammed_commands[:10] if spammed_commands else []
        })
        
        if is_spamming:
            _spam_blocked_users_cache.add(user_id)
            
            user_name, username = _get_user_info(message)
            chat_info = _get_chat_info(message)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            _write_debug_log("SPAM_DETECTED", {
                "user_id": user_id,
                "command_count": command_count,
                "commands": spammed_commands[:10]
            })
            
            await _notify_user_blocked(user_id)
            await _notify_support_chat(user_id, user_name, username, chat_info, spammed_commands, timestamp)
            
            _write_debug_log("STOP_PROPAGATION", {"user_id": user_id, "command": command_name})
            raise StopPropagation()
        
        _write_debug_log("HANDLER_ALLOWED", {
            "user_id": user_id,
            "command": command_name,
            "count": command_count
        })
    except StopPropagation:
        raise
    except Exception as e:
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
        
        _write_debug_log("STARTUP_STATUS", {
            "enabled": enabled,
            "command_count": cmd_count,
            "owner_id": OWNER_ID,
            "handler_registered": True,
            "handler_group": -1
        })
        
        return enabled, cmd_count
    except Exception as e:
        _write_debug_log("STARTUP_ERROR", {"error": str(e)})
        return False, 0
