# Authored By Certified Coders © 2025
import sys
import traceback
import os
from functools import wraps
from datetime import datetime

import aiofiles
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden

from Tune import app
from config import LOGGER_ID, DEBUG_IGNORE_LOG
from Tune.utils.exceptions import is_ignored_error
from Tune.utils.pastebin import TuneBin


DEBUG_LOG_FILE = "ignored_errors.log"


# ========== Paste Fallback ==========

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


# ========== Formatting & Routing ==========

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

def _is_already_logged(err: BaseException) -> bool:
    """
    Check if this exception instance was already logged by one of our
    decorators. Prevents duplicate logs when the same error bubbles
    through multiple @capture_* wrappers (e.g. stream -> join_call).
    """
    return getattr(err, "_tune_logged", False)


def _mark_logged(err: BaseException) -> None:
    """
    Mark this exception instance as already logged.
    """
    try:
        setattr(err, "_tune_logged", True)
    except Exception:
        # In case someone raises a non-standard exception that forbids
        # setting attributes, just ignore – worst case we log twice.
        pass


def _get_error_severity(err: Exception) -> str:
    """
    Determine error severity level for better categorization in logs.
    
    Returns:
        "critical": System errors that need immediate attention
        "error": Operational errors that need investigation
        "warning": Expected issues that may need monitoring
        "info": Expected states that don't need action
    """
    from Tune.utils.exceptions import (
        is_expected_error,
        is_graceful_error,
        is_silent_error,
    )
    
    if is_silent_error(err):
        return "info"
    if is_expected_error(err):
        return "info"
    if is_graceful_error(err):
        return "warning"
    
    # Critical system errors
    if isinstance(err, (SystemError, RuntimeError, MemoryError)):
        return "critical"
    
    # Standard errors
    return "error"


async def handle_trace(err, tb, label, filename, extras=None):
    """
    Handle error logging with intelligent filtering based on error type.
    
    Expected errors (NoActiveGroupCall, AssistantErr, etc.) are logged only to debug log.
    Unexpected errors are logged to the error channel for investigation.
    """
    from Tune.utils.exceptions import is_ignored_error
    
    # Avoid double-logging the same exception instance
    if _is_already_logged(err):
        return
    
    # Check if error should be ignored (expected/silent errors)
    if is_ignored_error(err):
        # Log to debug file only (if DEBUG_IGNORE_LOG is enabled)
        await log_ignored_error(err, tb, label, extras)
        return

    # Log unexpected errors to error channel
    severity = _get_error_severity(err)
    caption = format_traceback(err, tb, f"{label} [{severity.upper()}]", extras)
    
    if len(caption) > 4096:
        await send_large_error(tb, caption.split("\n\n")[0], filename)
    else:
        await app.send_message(LOGGER_ID, caption)

    _mark_logged(err)

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



# ========== Decorators ==========


def capture_err(func):
    """
    Handles errors in command message handlers.
    
    Behavior:
    - ChatWriteForbidden: Leaves chat automatically
    - Expected errors (NoActiveGroupCall, etc.): Silently handled, not logged
    - AssistantErr: Propagates naturally (is_ignored_error prevents logging)
    - Other exceptions: Logged to error channel and re-raised
    """
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        from Tune.utils.exceptions import (
            is_expected_error,
            is_silent_error,
        )
        
        try:
            return await func(client, message, *args, **kwargs)
        except ChatWriteForbidden:
            # Bot cannot write - leave the chat
            await app.leave_chat(message.chat.id)
        except Exception as err:
            # Check if this is an expected/silent error (should not be logged)
            if is_expected_error(err) or is_silent_error(err):
                # Expected/silent errors: let them propagate naturally
                # They won't be logged due to is_ignored_error check
                raise
            
            # Unexpected error: log and re-raise
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
    """
    Handles errors in callback query handlers.
    
    Behavior:
    - Expected errors (NoActiveGroupCall, etc.): Silently handled, not logged
    - AssistantErr: Propagates naturally (is_ignored_error prevents logging)
    - Other exceptions: Logged to error channel and re-raised
    """
    @wraps(func)
    async def wrapper(client, callback_query, *args, **kwargs):
        from Tune.utils.exceptions import (
            is_expected_error,
            is_silent_error,
        )
        
        try:
            return await func(client, callback_query, *args, **kwargs)
        except Exception as err:
            # Check if this is an expected/silent error (should not be logged)
            if is_expected_error(err) or is_silent_error(err):
                # Expected/silent errors: let them propagate naturally
                # They won't be logged due to is_ignored_error check
                raise
            
            # Unexpected error: log and re-raise
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
    """
    Handles errors in background/internal async bot functions.
    
    Behavior:
    - Expected errors (NoActiveGroupCall, etc.): Silently handled, not logged
    - AssistantErr: Propagates naturally (is_ignored_error prevents logging)
    - Other exceptions: Logged to error channel and re-raised
    
    This is used for internal functions that may encounter expected states
    like "no active call" which are normal operational conditions.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        from Tune.utils.exceptions import (
            is_expected_error,
            is_silent_error,
        )
        
        try:
            return await func(*args, **kwargs)
        except Exception as err:
            # Check if this is an expected/silent error (should not be logged)
            if is_expected_error(err) or is_silent_error(err):
                # Expected/silent errors: let them propagate naturally
                # They won't be logged due to is_ignored_error check
                raise
            
            # Unexpected error: log and re-raise
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            extras = {"Function": func.__name__}
            filename = f"internal_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await handle_trace(err, tb, "Internal Error", filename, extras)
            raise err
    return wrapper
