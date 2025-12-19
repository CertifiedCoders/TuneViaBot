# Authored By Certified Coders © 2025
import time
from collections import defaultdict, deque
from typing import Dict, Deque, Tuple

from Tune.utils.database import (
    add_spam_blocked_user,
    is_antispam_enabled,
    is_spam_blocked,
)
from config import OWNER_ID

COMMAND_RATE_LIMIT = 10
TIME_WINDOW_SECONDS = 20

_user_command_history: Dict[int, Deque[Tuple[float, str]]] = defaultdict(lambda: deque(maxlen=COMMAND_RATE_LIMIT + 5))


def _cleanup_old_entries(user_id: int, current_time: float, time_window: int):
    user_history = _user_command_history[user_id]
    cutoff_time = current_time - time_window
    while user_history and user_history[0][0] < cutoff_time:
        user_history.popleft()


async def track_command(user_id: int, command_name: str) -> Tuple[bool, int, list]:
    if user_id == OWNER_ID:
        return False, 0, []
    
    if not await is_antispam_enabled():
        return False, 0, []
    
    if await is_spam_blocked(user_id):
        return True, 0, []
    
    current_time = time.time()
    user_history = _user_command_history[user_id]
    _cleanup_old_entries(user_id, current_time, TIME_WINDOW_SECONDS)
    
    user_history.append((current_time, command_name))
    
    command_count = len(user_history)
    is_spamming = command_count >= COMMAND_RATE_LIMIT
    
    if is_spamming:
        spammed_commands = [cmd for _, cmd in user_history]
        await add_spam_blocked_user(user_id, command_count, TIME_WINDOW_SECONDS)
        return True, command_count, spammed_commands
    
    return False, command_count, []


def reset_user_tracking(user_id: int):
    if user_id in _user_command_history:
        _user_command_history[user_id].clear()
