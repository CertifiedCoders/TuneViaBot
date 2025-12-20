# Authored By Certified Coders © 2025
import re
import os
import traceback
from collections import Counter
from datetime import datetime
from pyrogram import filters, StopPropagation
from pyrogram.types import Message

from Tune import app
from Tune.utils.antispam import track_command, reset_user_tracking, get_user_command_count, TIME_WINDOW_SECONDS
from Tune.utils.database import is_spam_blocked, is_antispam_enabled, get_lang
from config import SUPPORT_CHAT, OWNER_ID
from Tune.core.dir import LOGS_DIR
from Tune.logging import LOGGER
from strings import get_string

_spam_blocked_users_cache = set()
_user_notified_cache = set()
_support_notified_cache = set()
_debug_file_path = os.path.join(LOGS_DIR, "antispam_debug.txt")
_COMMAND_PREFIXES = ["/", "!", ".", "#", "?"]
_loaded_commands_cache = set()  # Cache of all loaded bot commands


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


def get_debug_file_path():
    return _debug_file_path


def clear_user_notification(user_id: int):
    _user_notified_cache.discard(user_id)
    _support_notified_cache.discard(user_id)


def _get_most_frequent_command(commands: list) -> str:
    if not commands:
        return "unknown"
    counter = Counter(commands)
    most_common = counter.most_common(1)[0]
    return f"/{most_common[0]}"


async def _notify_user_blocked(user_id: int):
    if user_id in _user_notified_cache:
        return
    
    try:
        try:
            lang_code = await get_lang(user_id)
            _ = get_string(lang_code)
        except:
            _ = get_string("en")
        
        await app.send_message(
            user_id,
            _["antispam_1"].format(SUPPORT_CHAT)
        )
        _user_notified_cache.add(user_id)
        _write_debug_log("NOTIFY_USER", {"user_id": user_id, "status": "sent"})
    except Exception as e:
        _write_debug_log("NOTIFY_USER", {"user_id": user_id, "status": "failed", "error": str(e)})


async def _notify_support_chat(user_id: int, user_name: str, username: str, chat_info: str, spammed_commands: list, timestamp: str, command_name: str, command_count: int):
    if user_id in _support_notified_cache:
        return
    
    try:
        _ = get_string("en")
        user_display = user_name or _["antispam_22"].format(user_id)
        if username:
            user_display += f" (@{username})"
        
        # Format command name with /
        cmd_display = f"/{command_name}" if command_name else _get_most_frequent_command(spammed_commands)
        
        spam_notification = _["antispam_2"].format(
            user_display,
            user_id,
            chat_info,
            cmd_display,
            command_count,
            TIME_WINDOW_SECONDS,
            timestamp
        )
        
        await app.send_message(SUPPORT_CHAT, spam_notification)
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
    """Extract all command names from source code files."""
    commands_set = set()
    try:
        # Try multiple possible plugin directory paths
        possible_dirs = [
            os.path.join(os.getcwd(), "Tune", "plugins"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "plugins"),
        ]
        
        plugins_dir = None
        for dir_path in possible_dirs:
            if os.path.exists(dir_path):
                plugins_dir = dir_path
                break
        
        if not plugins_dir:
            _write_debug_log("EXTRACT_COMMANDS_ERROR", {"error": "plugins directory not found"})
            return commands_set
        
        # Pattern to match filters.command(["cmd1", "cmd2"]) or filters.command("cmd")
        command_pattern = r'filters\.command\s*\(\s*(\[[^\]]+\]|["\'][^"\']+["\'])\s*\)'
        
        for root, dirs, files in os.walk(plugins_dir):
            for file in files:
                if not file.endswith(".py") or file.startswith("__"):
                    continue
                
                try:
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        
                        # Find all command filter patterns
                        matches = re.finditer(command_pattern, content, re.IGNORECASE | re.MULTILINE)
                        for match in matches:
                            cmd_arg = match.group(1).strip()
                            
                            # Check if it's a list of commands: ["cmd1", "cmd2"]
                            if cmd_arg.startswith('[') and cmd_arg.endswith(']'):
                                # Extract all commands from the list
                                list_content = cmd_arg[1:-1]
                                cmd_matches = re.findall(r'["\']([^"\']+)["\']', list_content)
                                for cmd in cmd_matches:
                                    if cmd and cmd.strip():
                                        commands_set.add(cmd.strip().lower())
                            # Single command: "cmd" or 'cmd'
                            elif (cmd_arg.startswith('"') and cmd_arg.endswith('"')) or \
                                 (cmd_arg.startswith("'") and cmd_arg.endswith("'")):
                                cmd = cmd_arg[1:-1].strip()
                                if cmd:
                                    commands_set.add(cmd.lower())
                except Exception as e:
                    _write_debug_log("EXTRACT_FILE_ERROR", {"file": file, "error": str(e)})
                    continue
    except Exception as e:
        _write_debug_log("EXTRACT_COMMANDS_ERROR", {"error": str(e)})
    
    return sorted(commands_set)


def _get_all_protected_commands():
    """Get all registered bot commands from Pyrogram dispatcher and source files."""
    commands_set = set()
    try:
        # Try to get commands from Pyrogram dispatcher (most reliable)
        dispatcher = app.dispatcher
        handler_groups = getattr(dispatcher, 'groups', None)
        
        if handler_groups and isinstance(handler_groups, dict):
            for group_id, handlers in handler_groups.items():
                if not isinstance(handlers, (list, tuple)):
                    continue
                for handler in handlers:
                    try:
                        filter_obj = getattr(handler, 'filters', None)
                        if not filter_obj:
                            continue
                        
                        # Check if filter is a command filter
                        filter_str = str(filter_obj)
                        
                        # Try to extract command from filter
                        # Pattern for single command: filters.command("cmd")
                        single_cmd = re.search(r'command\(["\']([^"\']+)["\']\)', filter_str, re.IGNORECASE)
                        if single_cmd:
                            commands_set.add(single_cmd.group(1).lower())
                        
                        # Pattern for multiple commands: filters.command(["cmd1", "cmd2"])
                        list_match = re.search(r'command\(\[([^\]]+)\]\)', filter_str, re.IGNORECASE)
                        if list_match:
                            for cmd in re.findall(r'["\']([^"\']+)["\']', list_match.group(1)):
                                commands_set.add(cmd.lower().strip())
                    except Exception:
                        continue
        
        # If dispatcher method didn't work, fall back to source code extraction
        if not commands_set:
            commands_set = _extract_commands_from_source()
    except Exception as e:
        _write_debug_log("GET_COMMANDS_ERROR", {"error": str(e)})
        # Fall back to source code extraction
        commands_set = _extract_commands_from_source()
    
    return sorted(commands_set) if commands_set else []


def _load_and_cache_commands():
    """Load all bot commands and cache them for fast lookup."""
    global _loaded_commands_cache
    try:
        commands_list = _get_all_protected_commands()
        _loaded_commands_cache = set(commands_list)
        
        # Write all loaded commands to debug file
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(_debug_file_path, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"[{timestamp}] LOADED_BOT_COMMANDS\n")
                f.write(f"{'='*60}\n")
                f.write(f"Total Commands: {len(commands_list)}\n")
                f.write(f"Commands List:\n")
                for cmd in commands_list:
                    f.write(f"  - /{cmd}\n")
                f.write(f"{'='*60}\n\n")
        except Exception as e:
            _write_debug_log("WRITE_COMMANDS_ERROR", {"error": str(e)})
        
        _write_debug_log("COMMANDS_CACHED", {
            "command_count": len(_loaded_commands_cache),
            "commands": list(_loaded_commands_cache)[:20]  # First 20 for debug
        })
        
        return _loaded_commands_cache
    except Exception as e:
        _write_debug_log("LOAD_COMMANDS_ERROR", {"error": str(e)})
        return set()


def _is_bot_command(command_name: str) -> bool:
    """Check if a command is actually loaded in the bot."""
    if not _loaded_commands_cache:
        # If cache is empty, try to load commands
        _load_and_cache_commands()
    return command_name.lower() in _loaded_commands_cache


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
        _ = get_string("en")
        chat_type_str = str(message.chat.type).lower()
        if "private" in chat_type_str:
            return _["antispam_19"]
        chat_title = getattr(message.chat, 'title', None) or "ɴ/ᴀ"
        return _["antispam_20"].format(chat_title, message.chat.id)
    except Exception:
        _ = get_string("en")
        return _["antispam_21"]


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
        
        # Check if this is actually a bot command (not just any text starting with /)
        if not _is_bot_command(command_name):
            _write_debug_log("HANDLER_EXIT", {
                "reason": "not_bot_command",
                "command": command_name,
                "loaded_commands_count": len(_loaded_commands_cache)
            })
            return  # Don't track commands that aren't in the bot
        
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
            await _notify_support_chat(user_id, user_name, username, chat_info, spammed_commands, timestamp, command_name, command_count)
            
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
    """Log antispam status and load/cache all bot commands."""
    try:
        enabled = await is_antispam_enabled()
        # Load and cache all commands on startup
        loaded_commands = _load_and_cache_commands()
        cmd_count = len(loaded_commands)
        
        _write_debug_log("STARTUP_STATUS", {
            "enabled": enabled,
            "command_count": cmd_count,
            "owner_id": OWNER_ID,
            "handler_registered": True,
            "handler_group": -1,
            "commands_cached": True
        })
        
        return enabled, cmd_count
    except Exception as e:
        _write_debug_log("STARTUP_ERROR", {"error": str(e)})
        return False, 0
