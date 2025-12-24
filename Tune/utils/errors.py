# Authored By Certified Coders © 2025
import os
import sys
import traceback
from datetime import datetime
from functools import wraps

import aiofiles
from pyrogram.enums import ParseMode
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden

from Tune import app
from config import DEBUG_IGNORE_LOG, LOGGER_ID
from Tune.core.dir import LOGS_DIR
from Tune.utils.exceptions import (
    is_expected_error,
    is_graceful_error,
    is_ignored_error,
    is_silent_error,
)
from Tune.utils.pastebin import TuneBin

DEBUG_LOG_FILE = os.path.join(LOGS_DIR, "ignored_errors.log")


def _is_already_logged(err: BaseException) -> bool:
    return getattr(err, "_tune_logged", False)


def _mark_logged(err: BaseException) -> None:
    try:
        setattr(err, "_tune_logged", True)
    except Exception:
        pass


def _get_error_severity(err: Exception) -> str:
    if is_graceful_error(err):
        return "warning"
    if isinstance(err, (SystemError, RuntimeError, MemoryError)):
        return "critical"
    return "error"


def _should_skip_error(err: Exception) -> bool:
    return is_expected_error(err) or is_silent_error(err)


def _get_severity_emoji(severity: str) -> str:
    emoji_map = {
        "warning": "⚠️",
        "critical": "🔴",
        "error": "❌"
    }
    return emoji_map.get(severity.lower(), "❌")


def format_traceback(err, tb, label: str, extras: dict = None) -> str:
    exc_type = type(err).__name__
    severity = _get_error_severity(err)
    severity_emoji = _get_severity_emoji(severity)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    parts = [
        f"<b>{severity_emoji} {label}</b>",
        f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>",
        f"",
        f"<b>📋 Type:</b> <code>{exc_type}</code>",
        f"<b>⚡ Severity:</b> <code>{severity.upper()}</code>",
        f"<b>🕐 Time:</b> <code>{timestamp}</code>"
    ]
    
    if extras:
        parts.append("")
        for k, v in extras.items():
            icon = "👤" if "User" in k else "💬" if "Command" in k else "🆔" if "Chat ID" in k else "⚙️" if "Function" in k else "📌"
            parts.append(f"<b>{icon} {k}:</b> <code>{v}</code>")
    
    parts.extend([
        "",
        f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>",
        f"",
        f"<b>📜 Traceback:</b>",
        f"<pre>{tb}</pre>"
    ])
    
    return "\n".join(parts)


async def send_large_error(text: str, caption: str, filename: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        paste_url = await TuneBin(text)
        if paste_url:
            enhanced_caption = (
                f"{caption}\n\n"
                f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
                f"<b>📄 Full Traceback:</b> <a href='{paste_url}'>View on Pastebin</a>\n"
                f"<b>🕐 Time:</b> <code>{timestamp}</code>"
            )
            await app.send_message(LOGGER_ID, enhanced_caption, parse_mode=ParseMode.HTML)
            return
    except Exception:
        pass

    path = f"{filename}.txt"
    async with aiofiles.open(path, "w") as f:
        await f.write(text)
    
    fallback_caption = (
        f"<b>📎 Error Log File</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
        f"<b>🕐 Time:</b> <code>{timestamp}</code>\n"
        f"<b>📝 Filename:</b> <code>{filename}.txt</code>"
    )
    await app.send_document(LOGGER_ID, path, caption=fallback_caption, parse_mode=ParseMode.HTML)
    os.remove(path)


async def log_ignored_error(err, tb, label, extras=None):
    if not DEBUG_IGNORE_LOG:
        return

    os.makedirs(LOGS_DIR, exist_ok=True)
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
    caption = format_traceback(err, tb, label, extras)

    if len(caption) > 4096:
        header = f"<b>{_get_severity_emoji(severity)} {label} [{severity.upper()}]</b>"
        await send_large_error(tb, header, filename)
    else:
        await app.send_message(LOGGER_ID, caption, parse_mode=ParseMode.HTML)

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
