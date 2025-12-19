# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.utils.antispam import check_spam
from Tune.utils.database import is_spam_blocked
from Tune.misc import SUDOERS
from config import SUPPORT_CHAT

_spam_blocked_users_cache = set()
_user_notified_cache = set()


def get_spam_blocked_cache():
    return _spam_blocked_users_cache


def clear_user_notification(user_id: int):
    if user_id in _user_notified_cache:
        _user_notified_cache.discard(user_id)


async def non_sudo_filter_func(_, __, message: Message):
    if not message.from_user:
        return False
    user_id = message.from_user.id
    return user_id not in SUDOERS


NON_SUDO_FILTER = filters.create(non_sudo_filter_func)


async def antispam_filter_func(_, __, message: Message):
    if not message.from_user:
        return True
    
    user_id = message.from_user.id
    
    if user_id in SUDOERS:
        return True
    
    try:
        bot_me = await app.get_me()
        if user_id == bot_me.id:
            return True
    except Exception:
        pass
    
    if user_id in _spam_blocked_users_cache:
        return False
    
    if await is_spam_blocked(user_id):
        _spam_blocked_users_cache.add(user_id)
        return False
    
    is_spamming, _ = await check_spam(user_id, track_command=True)
    
    if is_spamming:
        _spam_blocked_users_cache.add(user_id)
        return False
    
    return True


async def command_antispam_filter_func(_, __, message: Message):
    if not message.command:
        return False
    
    return await antispam_filter_func(_, __, message)


ANTISPAM_FILTER = filters.create(antispam_filter_func)
COMMAND_ANTISPAM_FILTER = filters.create(command_antispam_filter_func)


@app.on_message(filters.command & NON_SUDO_FILTER, group=0)
async def antispam_command_handler(client, message: Message):
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
        return
    
    if await is_spam_blocked(user_id):
        _spam_blocked_users_cache.add(user_id)
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
        return
    
    is_spamming, command_count = await check_spam(user_id, track_command=True)
    
    if is_spamming:
        _spam_blocked_users_cache.add(user_id)
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
        return
