# Authored By Certified Coders © 2025
import time
import os
from collections import defaultdict, deque
from typing import Dict, Deque, Tuple
from datetime import datetime

from Tune.utils.database import (
    add_spam_blocked_user,
    is_antispam_enabled,
    is_spam_blocked,
)
from config import OWNER_ID
from Tune.core.dir import LOGS_DIR

COMMAND_RATE_LIMIT = 10
TIME_WINDOW_SECONDS = 20

_user_command_history: Dict[int, Deque[Tuple[float, str]]] = defaultdict(lambda: deque(maxlen=COMMAND_RATE_LIMIT + 5))
_debug_file_path = os.path.join(LOGS_DIR, "antispam_debug.txt")


def _write_debug_log(event_type: str, data: dict):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{event_type}] {data}\n"
        with open(_debug_file_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass


def _cleanup_old_entries(user_id: int, current_time: float, time_window: int):
    user_history = _user_command_history[user_id]
    cutoff_time = current_time - time_window
    removed = 0
    while user_history and user_history[0][0] < cutoff_time:
        user_history.popleft()
        removed += 1
    if removed > 0:
        _write_debug_log("CLEANUP_OLD", {"user_id": user_id, "removed": removed})


async def track_command(user_id: int, command_name: str) -> Tuple[bool, int, list]:
    _write_debug_log("TRACK_START", {"user_id": user_id, "command": command_name})
    
    if user_id == OWNER_ID:
        _write_debug_log("TRACK_EXIT", {"reason": "owner_exempt"})
        return False, 0, []
    
    antispam_enabled = await is_antispam_enabled()
    _write_debug_log("TRACK_ENABLED_CHECK", {"enabled": antispam_enabled, "user_id": user_id})
    
    if not antispam_enabled:
        _write_debug_log("TRACK_EXIT", {"reason": "antispam_disabled"})
        return False, 0, []
    
    is_blocked = await is_spam_blocked(user_id)
    _write_debug_log("TRACK_BLOCK_CHECK", {"user_id": user_id, "is_blocked": is_blocked})
    
    if is_blocked:
        _write_debug_log("TRACK_EXIT", {"reason": "already_blocked"})
        return True, 0, []
    
    current_time = time.time()
    user_history = _user_command_history[user_id]
    _cleanup_old_entries(user_id, current_time, TIME_WINDOW_SECONDS)
    
    user_history.append((current_time, command_name))
    
    command_count = len(user_history)
    is_spamming = command_count >= COMMAND_RATE_LIMIT
    
    _write_debug_log("TRACK_EVALUATION", {
        "user_id": user_id,
        "command": command_name,
        "command_count": command_count,
        "limit": COMMAND_RATE_LIMIT,
        "is_spamming": is_spamming,
        "history": [(t, cmd) for t, cmd in list(user_history)[-5:]]
    })
    
    if is_spamming:
        spammed_commands = [cmd for _, cmd in user_history]
        _write_debug_log("TRACK_SPAM_DETECTED", {
            "user_id": user_id,
            "command_count": command_count,
            "commands": spammed_commands
        })
        
        await add_spam_blocked_user(user_id, command_count, TIME_WINDOW_SECONDS)
        
        _write_debug_log("TRACK_RESULT", {
            "user_id": user_id,
            "is_spamming": True,
            "command_count": command_count,
            "action": "blocked"
        })
        return True, command_count, spammed_commands
    
    _write_debug_log("TRACK_RESULT", {
        "user_id": user_id,
        "is_spamming": False,
        "command_count": command_count,
        "action": "allowed"
    })
    return False, command_count, []


def reset_user_tracking(user_id: int):
    if user_id in _user_command_history:
        _user_command_history[user_id].clear()
        _write_debug_log("TRACKING_RESET", {"user_id": user_id})
