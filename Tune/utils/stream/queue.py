# Authored By Certified Coders © 2025
import asyncio
from typing import Union

from Tune.misc import db
from Tune.utils.formatters import check_duration, seconds_to_min
from config import autoclean, time_to_seconds

_queue_locks: dict[int, asyncio.Lock] = {}
_queue_locks_lock = asyncio.Lock()


async def _get_queue_lock(chat_id: int) -> asyncio.Lock:
    async with _queue_locks_lock:
        if chat_id not in _queue_locks:
            _queue_locks[chat_id] = asyncio.Lock()
        return _queue_locks[chat_id]


async def get_queue_lock(chat_id: int) -> asyncio.Lock:
    return await _get_queue_lock(chat_id)


def _validate_queue_state(chat_id: int) -> bool:
    if chat_id not in db:
        return True
    queue = db.get(chat_id)
    if queue is None:
        return True
    if not isinstance(queue, list):
        return False
    for item in queue:
        if not isinstance(item, dict):
            return False
        required_keys = {"title", "dur", "streamtype", "by", "chat_id", "file", "vidid", "seconds", "played"}
        if not all(key in item for key in required_keys):
            return False
    return True


async def put_queue(
    chat_id,
    original_chat_id,
    file,
    title,
    duration,
    user,
    vidid,
    user_id,
    stream,
    forceplay: Union[bool, str] = None,
):
    title = title.title()
    try:
        duration_in_seconds = time_to_seconds(duration) - 3
    except Exception:
        duration_in_seconds = 0
    put = {
        "title": title,
        "dur": duration,
        "streamtype": stream,
        "by": user,
        "user_id": user_id,
        "chat_id": original_chat_id,
        "file": file,
        "vidid": vidid,
        "seconds": duration_in_seconds,
        "played": 0,
    }
    lock = await _get_queue_lock(chat_id)
    async with lock:
        if forceplay:
            check = db.get(chat_id)
            if check:
                check.insert(0, put)
            else:
                db[chat_id] = [put]
        else:
            if chat_id not in db:
                db[chat_id] = []
            db[chat_id].append(put)
    autoclean.append(file)


async def put_queue_index(
    chat_id,
    original_chat_id,
    file,
    title,
    duration,
    user,
    vidid,
    stream,
    forceplay: Union[bool, str] = None,
):
    """Add an index/M3U8 stream to the playback queue for a chat."""
    if "20.212.146.162" in vidid:
        try:
            loop = asyncio.get_running_loop()
            dur = await loop.run_in_executor(
                None, check_duration, vidid
            )
            duration = seconds_to_min(dur)
        except Exception:
            duration = "ᴜʀʟ sᴛʀᴇᴀᴍ"
            dur = 0
    else:
        dur = 0
    put = {
        "title": title,
        "dur": duration,
        "streamtype": stream,
        "by": user,
        "chat_id": original_chat_id,
        "file": file,
        "vidid": vidid,
        "seconds": dur,
        "played": 0,
    }
    lock = await _get_queue_lock(chat_id)
    async with lock:
        if forceplay:
            check = db.get(chat_id)
            if check:
                check.insert(0, put)
            else:
                db[chat_id] = [put]
        else:
            if chat_id not in db:
                db[chat_id] = []
            db[chat_id].append(put)
