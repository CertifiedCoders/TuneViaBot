# Authored By Certified Coders © 2025
import os
import sys
import traceback
from datetime import datetime
from functools import wraps

import aiofiles
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden

from Tune import app
from config import DEBUG_IGNORE_LOG, LOGGER_ID
from Tune.utils.exceptions import (
    is_expected_error,
    is_graceful_error,
    is_ignored_error,
    is_silent_error,
)
from Tune.utils.pastebin import TuneBin

DEBUG_LOG_FILE = "ignored_errors.log"


def _is_already_logged(err: BaseException) -> bool:
    return getattr(err, "_tune_logged", False)


def _mark_logged(err: BaseException) -> None:
    try:
        setattr(err, "_tune_logged", True)
    except Exception:
        pass


def _get_error_severity(err: Exception) -> str:
    if is_silent_error(err) or is_expected_error(err):
        return "info"
    if is_graceful_error(err):
        return "warning"
    if isinstance(err, (SystemError, RuntimeError, MemoryError)):
        return "critical"
    return "error"


def _should_skip_error(err: Exception) -> bool:
    return is_expected_error(err) or is_silent_error(err)


def format_traceback(err, tb, label: str, extras: dict = None) -> str:
    exc_type = type(err).__name__
    parts = [
        f"🚨 <b>{label} Captured</b>",
        f"📍 <b>Error Type:</b> <code>{exc_type}</code>"
    ]
    if extras:
        parts.extend([f"📌 <b>{k}:</b> <code>{v}</code>" for k, v in extras.items()])
    parts.append(f"\n<b>Traceback:</b>\n<pre>{tb}</pre>")
    return "\n".join(parts)


async def send_large_error(text: str, caption: str, filename: str):
    try:
        paste_url = await TuneBin(text)
        if paste_url:
            await app.send_message(LOGGER_ID, f"{caption}\n\n🔗 Paste: {paste_url}")
            return
    except Exception:
        pass

    path = f"{filename}.txt"
    async with aiofiles.open(path, "w") as f:
        await f.write(text)
    await app.send_document(LOGGER_ID, path, caption="❌ Error Log (Fallback)")
    os.remove(path)


async def log_ignored_error(err, tb, label, extras=None):
    if not DEBUG_IGNORE_LOG:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"\n--- Ignored Error | {label} @ {timestamp} ---",
        f"Type: {type(err).__name__}",
        *(f"{key}: {val}" for key, val in (extras or {}).items()),
        "Traceback:",
        tb.strip(),
        "------------------------------------------\n"
    ]
    async with aiofiles.open(DEBUG_LOG_FILE, "a") as log:
        await log.write("\n".join(lines))


async def handle_trace(err, tb, label, filename, extras=None):
    if _is_already_logged(err):
        return

    if is_ignored_error(err):
        await log_ignored_error(err, tb, label, extras)
        return

    severity = _get_error_severity(err)
    caption = format_traceback(err, tb, f"{label} [{severity.upper()}]", extras)

    if len(caption) > 4096:
        await send_large_error(tb, caption.split("\n\n")[0], filename)
    else:
        await app.send_message(LOGGER_ID, caption)

    _mark_logged(err)


def capture_err(func):
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        try:
            return await func(client, message, *args, **kwargs)
        except ChatWriteForbidden:
            await app.leave_chat(message.chat.id)
        except Exception as err:
            if _should_skip_error(err):
                raise

            tb = "".join(traceback.format_exception(*sys.exc_info()))
            extras = {
                "User": message.from_user.mention if message.from_user else "N/A",
                "Command": message.text or message.caption,
                "Chat ID": message.chat.id
            }
            filename = f"error_log_{message.chat.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await handle_trace(err, tb, "Command Error", filename, extras)
            raise err
    return wrapper


def capture_callback_err(func):
    @wraps(func)
    async def wrapper(client, callback_query, *args, **kwargs):
        try:
            return await func(client, callback_query, *args, **kwargs)
        except Exception as err:
            if _should_skip_error(err):
                raise

            tb = "".join(traceback.format_exception(*sys.exc_info()))
            extras = {
                "User": callback_query.from_user.mention if callback_query.from_user else "N/A",
                "Chat ID": callback_query.message.chat.id
            }
            filename = f"cb_error_log_{callback_query.message.chat.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await handle_trace(err, tb, "Callback Error", filename, extras)
            raise err
    return wrapper


def capture_internal_err(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as err:
            if _should_skip_error(err):
                raise

            tb = "".join(traceback.format_exception(*sys.exc_info()))
            extras = {"Function": func.__name__}
            filename = f"internal_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await handle_trace(err, tb, "Internal Error", filename, extras)
            raise err
    return wrapper
