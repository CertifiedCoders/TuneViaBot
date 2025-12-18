# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.utils.antispam import check_spam
from Tune.utils.database import is_spam_blocked

_spam_blocked_users_cache = set()


async def antispam_filter_func(_, __, message: Message):
    if not message.from_user:
        return True
    
    user_id = message.from_user.id
    
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
    
    is_spamming, _ = await check_spam(user_id, track_command=False)
    
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


def get_spam_blocked_cache():
    return _spam_blocked_users_cache


@app.on_message(COMMAND_ANTISPAM_FILTER, group=-10)
async def track_command_execution(client, message: Message):
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    try:
        bot_me = await app.get_me()
        if user_id == bot_me.id:
            return
    except Exception:
        pass
    
    await check_spam(user_id, track_command=True)
