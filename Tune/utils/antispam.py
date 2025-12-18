# Authored By Certified Coders © 2025
import time
from collections import defaultdict, deque
from typing import Dict, Deque

from Tune import app
from Tune.utils.database import (
    add_spam_blocked_user,
    is_antispam_enabled,
    is_spam_blocked,
)
from config import LOGGER_ID
from Tune.misc import SUDOERS
from Tune.logging import LOGGER

COMMAND_RATE_LIMIT = 10
TIME_WINDOW_SECONDS = 20

_user_command_times: Dict[int, Deque[float]] = defaultdict(lambda: deque(maxlen=COMMAND_RATE_LIMIT + 5))
_notified_users: set = set()


def _cleanup_old_entries(user_id: int, current_time: float, time_window: int):
    user_times = _user_command_times[user_id]
    cutoff_time = current_time - time_window
    while user_times and user_times[0] < cutoff_time:
        user_times.popleft()


async def check_spam(user_id: int, track_command: bool = True) -> tuple:
    if user_id in SUDOERS:
        return False, 0
    
    if not await is_antispam_enabled():
        if track_command:
            current_time = time.time()
            user_times = _user_command_times[user_id]
            _cleanup_old_entries(user_id, current_time, TIME_WINDOW_SECONDS)
            user_times.append(current_time)
        return False, 0
    
    if await is_spam_blocked(user_id):
        return True, 0
    
    current_time = time.time()
    user_times = _user_command_times[user_id]
    _cleanup_old_entries(user_id, current_time, TIME_WINDOW_SECONDS)
    
    if track_command:
        user_times.append(current_time)
    
    command_count = len(user_times)
    is_spamming = command_count >= COMMAND_RATE_LIMIT
    
    if is_spamming and user_id not in _notified_users:
        await add_spam_blocked_user(user_id, command_count, TIME_WINDOW_SECONDS)
        _notified_users.add(user_id)
        
        try:
            user_info = await app.get_users(user_id)
            user_mention = user_info.mention if user_info else f"User {user_id}"
            
            spam_details = (
                f"🚫 <b>Spam Detected</b>\n\n"
                f"👤 <b>User:</b> {user_mention}\n"
                f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                f"⚡ <b>Commands:</b> {command_count}/{COMMAND_RATE_LIMIT}\n"
                f"⏱ <b>Window:</b> {TIME_WINDOW_SECONDS}s\n"
                f"🔒 <b>Action:</b> Silently blocked - all messages ignored"
            )
            
            await app.send_message(LOGGER_ID, spam_details)
                
        except Exception as e:
            LOGGER(__name__).warning(f"Failed to send spam notification: {e}")
        
        return True, command_count
    
    return is_spamming, command_count


def reset_user_tracking(user_id: int):
    if user_id in _user_command_times:
        _user_command_times[user_id].clear()
    if user_id in _notified_users:
        _notified_users.discard(user_id)
