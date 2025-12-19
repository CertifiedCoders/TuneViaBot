# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.utils.antispam import check_spam
from Tune.utils.database import is_spam_blocked, is_antispam_enabled
from Tune.misc import SUDOERS
from config import SUPPORT_CHAT
from Tune.logging import LOGGER

_spam_blocked_users_cache = set()
_user_notified_cache = set()


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
        except Exception:
            pass


def _has_command_filter(filter_obj):
    if not filter_obj:
        return False
    
    filter_type_name = type(filter_obj).__name__
    filter_str = str(filter_obj).lower()
    
    if 'command' in filter_type_name.lower():
        return True
    
    if 'command' in filter_str:
        return True
    
    if hasattr(filter_obj, '__class__'):
        class_name = filter_obj.__class__.__name__
        if 'Command' in class_name:
            return True
    
    if hasattr(filter_obj, 'filters'):
        if isinstance(filter_obj.filters, (list, tuple)):
            for sub_filter in filter_obj.filters:
                if _has_command_filter(sub_filter):
                    return True
        elif filter_obj.filters:
            return _has_command_filter(filter_obj.filters)
    
    if hasattr(filter_obj, 'left') and hasattr(filter_obj, 'right'):
        return _has_command_filter(filter_obj.left) or _has_command_filter(filter_obj.right)
    
    return False


def _count_command_handlers():
    command_count = 0
    try:
        dispatcher = app.dispatcher
        handler_groups = getattr(dispatcher, 'groups', None) or getattr(dispatcher, 'handlers', {})
        
        for group_id, handlers in handler_groups.items():
            for handler in handlers:
                if hasattr(handler, 'filters'):
                    if _has_command_filter(handler.filters):
                        command_count += 1
    except Exception as e:
        LOGGER(__name__).warning(f"Failed to count command handlers: {e}")
    return command_count


async def _is_command_message(_, __, message: Message):
    return bool(message.command)


COMMAND_FILTER = filters.create(_is_command_message)


@app.on_message(COMMAND_FILTER, group=0)
async def antispam_command_handler(client, message: Message):
    if not message.command:
        return
    
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    if user_id in SUDOERS:
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
    
    if await is_spam_blocked(user_id):
        _spam_blocked_users_cache.add(user_id)
        await _notify_user_blocked(user_id)
        await message.stop_propagation()
        return
    
    is_spamming, command_count = await check_spam(user_id, track_command=True)
    
    if is_spamming:
        _spam_blocked_users_cache.add(user_id)
        await _notify_user_blocked(user_id)
        await message.stop_propagation()
        return


async def log_antispam_status():
    try:
        enabled = await is_antispam_enabled()
        cmd_count = _count_command_handlers()
        status = "enabled" if enabled else "disabled"
        LOGGER("Tune").info(f"ᴀɴᴛɪ-sᴘᴀᴍ {status} ɪɴ ʙᴏᴛ ғᴏʀ {cmd_count} ᴄᴏᴍᴍᴀɴᴅs")
    except Exception as e:
        LOGGER("Tune").warning(f"ғᴀɪʟᴇᴅ ᴛᴏ ʟᴏɢ ᴀɴᴛɪ-sᴘᴀᴍ sᴛᴀᴛᴜs: {e}")
