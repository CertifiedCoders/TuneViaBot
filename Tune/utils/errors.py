import sys
import traceback
import os
from functools import wraps
from datetime import datetime

import aiohttp
import aiofiles
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden

from Tune import app
from config import LOGGER_ID


async def send_large_error(text: str, caption: str, filename: str):
    """
    Sends long error tracebacks to the log channel.
    - Tries Batbin first.
    - If it fails, uploads a .txt file as a fallback.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://batbin.me/api/v2/paste", json={"content": text}) as resp:
                if resp.status == 201:
                    res = await resp.json()
                    link = f"https://batbin.me/{res['paste_id']}"
                    return await app.send_message(LOGGER_ID, f"{caption}\n\n🔗 Batbin: {link}")
    except Exception:
        pass

    path = f"{filename}.txt"
    async with aiofiles.open(path, "w") as f:
        await f.write(text)

    await app.send_document(LOGGER_ID, path, caption="❌ Error Log (Fallback)")
    os.remove(path)


def capture_err(func):
    """
    Decorator for command handlers.
    Catches runtime errors, formats tracebacks,
    and reports them via Telegram.
    """
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        try:
            return await func(client, message, *args, **kwargs)
        except ChatWriteForbidden:
            await app.leave_chat(message.chat.id)
        except Exception as err:
            exc_type, _, exc_tb = sys.exc_info()
            full_trace = "".join(traceback.format_exception(exc_type, err, exc_tb))

            caption = (
                f"🚨 <b>Error Captured</b>\n"
                f"👤 <b>User:</b> {message.from_user.mention if message.from_user else 'N/A'}\n"
                f"💬 <b>Command:</b> <code>{message.text or message.caption}</code>\n"
                f"🆔 <b>Chat ID:</b> <code>{message.chat.id}</code>\n"
                f"📍 <b>Error Type:</b> <code>{exc_type.__name__}</code>"
            )

            final_message = f"{caption}\n\n<b>Traceback:</b>\n<pre>{full_trace}</pre>"

            if len(final_message) > 4096:
                filename = f"error_log_{message.chat.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                await send_large_error(full_trace, caption, filename)
            else:
                await app.send_message(LOGGER_ID, final_message)

            raise err
    return wrapper


def capture_callback_err(func):
    """
    Decorator for callback query handlers (e.g., Inline buttons).
    Logs any error raised during execution.
    """
    @wraps(func)
    async def wrapper(client, CallbackQuery, *args, **kwargs):
        try:
            return await func(client, CallbackQuery, *args, **kwargs)
        except Exception as err:
            exc_type, _, exc_tb = sys.exc_info()
            full_trace = "".join(traceback.format_exception(exc_type, err, exc_tb))

            caption = (
                f"🚨 <b>Callback Error Captured</b>\n"
                f"👤 <b>User:</b> {CallbackQuery.from_user.mention if CallbackQuery.from_user else 'N/A'}\n"
                f"🆔 <b>Chat ID:</b> <code>{CallbackQuery.message.chat.id}</code>\n"
                f"📍 <b>Error Type:</b> <code>{exc_type.__name__}</code>"
            )

            final_message = f"{caption}\n\n<b>Traceback:</b>\n<pre>{full_trace}</pre>"

            if len(final_message) > 4096:
                filename = f"cb_error_log_{CallbackQuery.message.chat.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                await send_large_error(full_trace, caption, filename)
            else:
                await app.send_message(LOGGER_ID, final_message)

            raise err
    return wrapper


def capture_internal_err(func):
    """
    General-purpose error capture for internal bot functions
    that don't receive Telegram messages or callback objects.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as err:
            exc_type, _, exc_tb = sys.exc_info()
            full_trace = "".join(traceback.format_exception(exc_type, err, exc_tb))

            caption = (
                f"🚨 <b>Internal Error Captured</b>\n"
                f"📍 <b>Function:</b> <code>{func.__name__}</code>\n"
                f"📍 <b>Error Type:</b> <code>{exc_type.__name__}</code>"
            )

            final_message = f"{caption}\n\n<b>Traceback:</b>\n<pre>{full_trace}</pre>"

            if len(final_message) > 4096:
                filename = f"internal_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                await send_large_error(full_trace, caption, filename)
            else:
                await app.send_message(LOGGER_ID, final_message)

            raise err
    return wrapper
