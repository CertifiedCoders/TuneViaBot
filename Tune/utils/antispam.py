# Authored By Certified Coders © 2025
import time
import os
from collections import defaultdict, deque
from typing import Dict, Deque
from datetime import datetime

from Tune import app
from Tune.utils.database import (
    add_spam_blocked_user,
    is_antispam_enabled,
    is_spam_blocked,
)
from config import LOGGER_ID, OWNER_ID
from Tune.core.dir import LOGS_DIR
from Tune.logging import LOGGER

COMMAND_RATE_LIMIT = 10
TIME_WINDOW_SECONDS = 20

_user_command_times: Dict[int, Deque[float]] = defaultdict(lambda: deque(maxlen=COMMAND_RATE_LIMIT + 5))
_notified_users: set = set()
_debug_file_path = os.path.join(LOGS_DIR, "antispam_debug.txt")


def _write_debug_log(event_type: str, data: dict):
    try:
        if not _debug_file_path:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{event_type}] {data}\n"
        with open(_debug_file_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass


def _cleanup_old_entries(user_id: int, current_time: float, time_window: int):
    user_times = _user_command_times[user_id]
    cutoff_time = current_time - time_window
    removed_count = 0
    while user_times and user_times[0] < cutoff_time:
        user_times.popleft()
        removed_count += 1
    if removed_count > 0:
        _write_debug_log("CLEANUP_OLD", {"user_id": user_id, "removed": removed_count})


async def check_spam(user_id: int, track_command: bool = True) -> tuple:
    _write_debug_log("CHECK_SPAM_START", {
        "user_id": user_id,
        "track_command": track_command,
        "is_owner": user_id == OWNER_ID
    })
    
    if user_id == OWNER_ID:
        _write_debug_log("CHECK_SPAM_EXIT", {"reason": "owner_exempt", "user_id": user_id})
        return False, 0
    
    antispam_enabled = await is_antispam_enabled()
    _write_debug_log("ANTISPAM_ENABLED_CHECK", {"enabled": antispam_enabled, "user_id": user_id})
    
    if not antispam_enabled:
        if track_command:
            current_time = time.time()
            user_times = _user_command_times[user_id]
            _cleanup_old_entries(user_id, current_time, TIME_WINDOW_SECONDS)
            user_times.append(current_time)
            _write_debug_log("TRACKED_DISABLED", {
                "user_id": user_id,
                "count_after": len(user_times)
            })
        _write_debug_log("CHECK_SPAM_EXIT", {"reason": "antispam_disabled", "user_id": user_id})
        return False, 0
    
    is_blocked = await is_spam_blocked(user_id)
    _write_debug_log("DB_BLOCK_CHECK", {"user_id": user_id, "is_blocked": is_blocked})
    
    if is_blocked:
        _write_debug_log("CHECK_SPAM_EXIT", {"reason": "already_blocked", "user_id": user_id})
        return True, 0
    
    current_time = time.time()
    user_times = _user_command_times[user_id]
    _cleanup_old_entries(user_id, current_time, TIME_WINDOW_SECONDS)
    
    if track_command:
        user_times.append(current_time)
        _write_debug_log("COMMAND_TRACKED", {
            "user_id": user_id,
            "timestamp": current_time,
            "count": len(user_times)
        })
    
    command_count = len(user_times)
    is_spamming = command_count >= COMMAND_RATE_LIMIT
    
    _write_debug_log("SPAM_EVALUATION", {
        "user_id": user_id,
        "command_count": command_count,
        "limit": COMMAND_RATE_LIMIT,
        "is_spamming": is_spamming,
        "time_window": TIME_WINDOW_SECONDS
    })
    
    if is_spamming and user_id not in _notified_users:
        _write_debug_log("SPAM_DETECTED", {
            "user_id": user_id,
            "command_count": command_count,
            "limit": COMMAND_RATE_LIMIT
        })
        
        await add_spam_blocked_user(user_id, command_count, TIME_WINDOW_SECONDS)
        _notified_users.add(user_id)
        
        _write_debug_log("CHECK_SPAM_RESULT", {
            "user_id": user_id,
            "is_spamming": True,
            "command_count": command_count,
            "action": "blocked"
        })
        return True, command_count
    
    _write_debug_log("CHECK_SPAM_RESULT", {
        "user_id": user_id,
        "is_spamming": is_spamming,
        "command_count": command_count,
        "action": "allowed" if not is_spamming else "notified_already"
    })
    return is_spamming, command_count


def reset_user_tracking(user_id: int):
    if user_id in _user_command_times:
        _user_command_times[user_id].clear()
    if user_id in _notified_users:
        _notified_users.discard(user_id)
    _write_debug_log("TRACKING_RESET", {"user_id": user_id})
