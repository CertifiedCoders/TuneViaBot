import sys
import traceback
import os
from functools import wraps
from datetime import datetime

import aiohttp
import aiofiles
import html
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden

from Tune import app
from config import LOGGER_ID


_last_sent_trace = None


def current_timestamp() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


async def send_large_error(text: str, caption: str, filename_prefix: str):
    """
    Sends long error tracebacks to the log channel.
    Tries uploading to Batbin; falls back to sending as a .txt file.
    """
    if not LOGGER_ID:
        print("[ERROR] LOGGER_ID is not configured properly.")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://batbin.me/api/v2/paste", json={"content": text}) as resp:
                if resp.status == 201:
                    res = await resp.json()
                    link = f"https://batbin.me/{res['paste_id']}"
                    return await app.send_message(LOGGER_ID, f"{caption}\n\n🔗 Batbin: {link}")
                else:
                    print(f"[Batbin Failed] Status Code: {resp.status}")
    except Exception as batbin_err:
        print(f"[Batbin Exception] {batbin_err}")

    filename = f"{filename_prefix}.txt"
    try:
        async with aiofiles.open(filename, "w") as f:
            await f.write(text)

        await app.send_document(LOGGER_ID, filename, caption="❌ Error Log (Fallback)")
    except Exception as file_err:
        print(f"[File Upload Failed] {file_err}")
    finally:
        try:
            os.remove(filename)
        except Exception as e:
            print(f"[Cleanup Failed] Could not delete temp file {filename}: {e}")


def capture_err(func):
    """Decorator for command handler errors"""
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        global _last_sent_trace
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
                f"💬 <b>Command:</b> <code>{html.escape(message.text or message.caption or '')}</code>\n"
                f"🆔 <b>Chat ID:</b> <code>{message.chat.id}</code>\n"
                f"📍 <b>Error Type:</b> <code>{exc_type.__name__}</code>"
            )

            final_message = f"{caption}\n\n<b>Traceback:</b>\n<pre>{html.escape(full_trace)}</pre>"

            if final_message == _last_sent_trace:
                return

            if len(final_message) > 4096:
                filename = f"error_log_{message.chat.id}_{current_timestamp()}"
                await send_large_error(full_trace, caption, filename)
            else:
                await app.send_message(LOGGER_ID, final_message)

            _last_sent_trace = final_message
            raise err
    return wrapper


def capture_callback_err(func):
    """Decorator for inline callback errors"""
    @wraps(func)
    async def wrapper(client, CallbackQuery, *args, **kwargs):
        global _last_sent_trace
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

            final_message = f"{caption}\n\n<b>Traceback:</b>\n<pre>{html.escape(full_trace)}</pre>"

            if final_message == _last_sent_trace:
                return

            if len(final_message) > 4096:
                filename = f"cb_error_log_{CallbackQuery.message.chat.id}_{current_timestamp()}"
                await send_large_error(full_trace, caption, filename)
            else:
                await app.send_message(LOGGER_ID, final_message)

            _last_sent_trace = final_message
            raise err
    return wrapper


def capture_internal_err(func):
    """Decorator for internal error tracking"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        global _last_sent_trace
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

            final_message = f"{caption}\n\n<b>Traceback:</b>\n<pre>{html.escape(full_trace)}</pre>"

            if final_message == _last_sent_trace:
                return

            if len(final_message) > 4096:
                filename = f"internal_error_{current_timestamp()}"
                await send_large_error(full_trace, caption, filename)
            else:
                await app.send_message(LOGGER_ID, final_message)

            _last_sent_trace = final_message
            raise err
    return wrapper