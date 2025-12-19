# Authored By Certified Coders © 2025
import re
import os
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.utils.antispam import check_spam
from Tune.utils.database import is_spam_blocked, is_antispam_enabled
from config import SUPPORT_CHAT, OWNER_ID, LOGGER_ID
from Tune.core.dir import LOGS_DIR
from Tune.logging import LOGGER

_spam_blocked_users_cache = set()
_user_notified_cache = set()
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


async def _notify_user_blocked(user_id: int):
    if user_id not in _user_notified_cache:
        try:
            await app.send_message(
                user_id,
                f"⚠️ You've been blocked for spamming.\n\n"
                f"If you want to be freed, contact support:\n{SUPPORT_CHAT}"
            )
            _user_notified_cache.add(user_id)
            _write_debug_log("NOTIFY_USER", {"user_id": user_id, "status": "sent"})
        except Exception as e:
            _write_debug_log("NOTIFY_USER", {"user_id": user_id, "status": "failed", "error": str(e)})


async def _notify_support_chat(user_id: int, username: str, command: str, chat_type: str, chat_title: str, command_count: int):
    try:
        user_mention = f"@{username}" if username else f"User {user_id}"
        location = f"Group: {chat_title}" if chat_type != "private" else "Bot DM"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        spam_notification = (
            f"🚫 <b>Spam Detected & Blocked</b>\n\n"
            f"👤 <b>User:</b> {user_mention}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"📍 <b>Location:</b> {location}\n"
            f"⚡ <b>Commands:</b> {command_count}/10\n"
            f"🔧 <b>Last Command:</b> <code>/{command}</code>\n"
            f"⏱ <b>Time:</b> {current_time}\n"
            f"🔒 <b>Status:</b> User blocked - all messages ignored"
        )
        
        await app.send_message(LOGGER_ID, spam_notification)
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
                                r'@app\.on_message\([^)]*filters\.command\(["\']([^"\']+)["\']',
                                r'@app\.on_message\([^)]*filters\.command\(\[([^\]]+)\]\)',
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
                    
                    handler_str = str(handler)
                    if 'command' in handler_str.lower():
                        single_cmd = re.search(r'command\(["\']([^"\']+)["\']\)', handler_str, re.IGNORECASE)
                        if single_cmd:
                            commands_set.add(single_cmd.group(1).lower())
                        list_match = re.search(r'command\(\[([^\]]+)\]\)', handler_str, re.IGNORECASE)
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


async def _is_command_message(_, __, message: Message):
    return bool(message.command)


COMMAND_FILTER = filters.create(_is_command_message)


@app.on_message(COMMAND_FILTER, group=0)
async def antispam_command_handler(client, message: Message):
    try:
        if not message.command:
            return
        
        if not message.from_user:
            return
        
        user_id = message.from_user.id
        
        if user_id == OWNER_ID:
            return
        
        try:
            bot_me = await app.get_me()
            if user_id == bot_me.id:
                return
        except Exception:
            pass
        
        if user_id in _spam_blocked_users_cache:
            await _notify_user_blocked(user_id)
            await message.stop_propagation()
            return
        
        is_blocked_db = await is_spam_blocked(user_id)
        if is_blocked_db:
            _spam_blocked_users_cache.add(user_id)
            await _notify_user_blocked(user_id)
            await message.stop_propagation()
            return
        
        antispam_enabled = await is_antispam_enabled()
        if not antispam_enabled:
            return
        
        command_name = message.command[0].lower() if message.command else None
        try:
            chat_type_str = str(message.chat.type)
            chat_type = "private" if "private" in chat_type_str.lower() else "group"
        except Exception:
            chat_type = "group"
        
        try:
            chat_title = message.chat.title if hasattr(message.chat, 'title') and message.chat.title else "N/A"
        except Exception:
            chat_title = "N/A"
        
        username = message.from_user.username if message.from_user.username else None
        
        is_spamming, command_count = await check_spam(user_id, track_command=True)
        
        if is_spamming:
            _spam_blocked_users_cache.add(user_id)
            await _notify_user_blocked(user_id)
            await _notify_support_chat(user_id, username, command_name, chat_type, chat_title, command_count)
            await message.stop_propagation()
            return
    except Exception as e:
        LOGGER(__name__).error(f"Error in antispam handler: {e}")


async def log_antispam_status():
    try:
        enabled = await is_antispam_enabled()
        protected_commands = _get_all_protected_commands()
        cmd_count = len(protected_commands)
        status = "enabled" if enabled else "disabled"
        
        if protected_commands:
            commands_list = ", ".join(protected_commands[:100])
            if cmd_count > 100:
                commands_list += f" ... and {cmd_count - 100} more"
            LOGGER("Tune").info(f"ᴀɴᴛɪ-sᴘᴀᴍ {status} ɪɴ ʙᴏᴛ ғᴏʀ {cmd_count} ᴄᴏᴍᴍᴀɴᴅs: {commands_list}")
        else:
            LOGGER("Tune").info(f"ᴀɴᴛɪ-sᴘᴀᴍ {status} ɪɴ ʙᴏᴛ - ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs ᴀʀᴇ ᴘʀᴏᴛᴇᴄᴛᴇᴅ")
    except Exception as e:
        LOGGER("Tune").warning(f"ғᴀɪʟᴇᴅ ᴛᴏ ʟᴏɢ ᴀɴᴛɪ-sᴘᴀᴍ sᴛᴀᴛᴜs: {e}")
