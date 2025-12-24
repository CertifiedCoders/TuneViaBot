# Authored By Certified Coders © 2025
import os
import re
import subprocess
import sys
import traceback
from io import StringIO
from time import time

from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import OWNER_ID
from Tune import app


async def aexec(code, client, message):
    exec(
        "async def __aexec(client, message): "
        + "".join(f"\n {a}" for a in code.split("\n"))
    )
    return await locals()["__aexec"](client, message)


async def edit_or_reply(msg: Message, **kwargs):
    func = msg.edit_text if msg.from_user.is_self else msg.reply
    await func(**kwargs)


@app.on_message(
    filters.command("eval")
    & filters.user(OWNER_ID)
    & ~filters.forwarded
    & ~filters.via_bot
)
async def executor(client: Client, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(message, text="<b>ᴡʜᴀᴛ ʏᴏᴜ ᴡᴀɴɴᴀ ᴇxᴇᴄᴜᴛᴇ ʙᴀʙʏ ?</b>")

    cmd = message.text.split(" ", maxsplit=1)[1]

    t1 = time()
    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = StringIO()
    redirected_error = StringIO()
    sys.stdout = redirected_output
    sys.stderr = redirected_error
    stdout, stderr, exc = None, None, None

    try:
        await aexec(cmd, client, message)
    except Exception:
        exc = traceback.format_exc()

    stdout = redirected_output.getvalue()
    stderr = redirected_error.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr

    evaluation = "\n"
    if exc:
        evaluation += exc
    elif stderr:
        evaluation += stderr
    elif stdout:
        evaluation += stdout
    else:
        evaluation += "Success"

    final_output = f"<b>⥤ ʀᴇsᴜʟᴛ :</b>\n<pre language='python'>{evaluation}</pre>"

    t2 = time()
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="⏳",
                    callback_data=f"runtime {round(t2 - t1, 3)} Seconds",
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data=f"forceclose abc|{message.from_user.id}",
                ),
            ]
        ]
    )

    if len(final_output) > 4096:
        filename = "output.txt"
        with open(filename, "w+", encoding="utf8") as out_file:
            out_file.write(str(evaluation))

        await message.reply_document(
            document=filename,
            caption=f"<b>⥤ ᴇᴠᴀʟ :</b>\n<code>{cmd[0:980]}</code>\n\n<b>⥤ ʀᴇsᴜʟᴛ :</b>\nAttached Document",
            quote=False,
            reply_markup=keyboard,
        )
        await message.delete()
        os.remove(filename)
    else:
        await edit_or_reply(message, text=final_output, reply_markup=keyboard)


@app.on_callback_query(filters.regex(r"runtime"))
async def runtime_func_cq(_, cq):
    try:
        runtime = cq.data.split(None, 1)[1]
        await cq.answer(runtime, show_alert=True)
    except (IndexError, Exception):
        pass


@app.on_callback_query(filters.regex("forceclose"))
async def forceclose_command(_, CallbackQuery):
    try:
        callback_data = CallbackQuery.data.strip()
        callback_request = callback_data.split(None, 1)[1]
        query, user_id = callback_request.split("|")
        if CallbackQuery.from_user.id != int(user_id):
            try:
                return await CallbackQuery.answer(
                    "» ɪᴛ'ʟʟ ʙᴇ ʙᴇᴛᴛᴇʀ ɪғ ʏᴏᴜ sᴛᴀʏ ɪɴ ʏᴏᴜʀ ʟɪᴍɪᴛs ʙᴀʙʏ.", show_alert=True
                )
            except Exception:
                return
        await CallbackQuery.message.delete()
        try:
            await CallbackQuery.answer()
        except Exception:
            pass
    except (IndexError, ValueError, Exception):
        pass


async def _run_shell_command(shell_cmd, multiline=False):
    shell = re.split(r""" (?=(?:[^'"]|'[^']*'|"[^"]*")*$)""", shell_cmd)
    if not multiline:
        shell = [arg.replace('"', "") for arg in shell]
    try:
        process = subprocess.Popen(
            shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate()
        return stdout.decode(), stderr.decode()
    except Exception as err:
        error_msg = traceback.format_exception(type(err), err, err.__traceback__)
        raise Exception(''.join(error_msg))


@app.on_message(
    filters.command("sh")
    & filters.user(OWNER_ID)
    & ~filters.forwarded
    & ~filters.via_bot
)
async def shellrunner(_, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(message, text="<b>ᴇxᴀᴍᴩʟᴇ :</b>\n/sh git pull")

    text = message.text.split(None, 1)[1]

    if "\n" in text:
        code = text.split("\n")
        output = ""
        for x in code:
            try:
                stdout, stderr = await _run_shell_command(x, multiline=True)
                output += f"<b>{x}</b>\n{stdout}\n{stderr}"
            except Exception as err:
                return await edit_or_reply(
                    message, text=f"<b>ERROR :</b>\n<pre>{err}</pre>"
                )
    else:
        try:
            stdout, stderr = await _run_shell_command(text, multiline=False)
            output = stdout + stderr
        except Exception as err:
            return await edit_or_reply(
                message, text=f"<b>ERROR :</b>\n<pre>{err}</pre>"
            )

    if not output.strip():
        output = "None"

    if len(output) > 4096:
        with open("output.txt", "w+", encoding="utf-8") as file:
            file.write(output)
        await app.send_document(
            message.chat.id,
            "output.txt",
            reply_to_message_id=message.id,
            caption="<code>Output</code>",
        )
        os.remove("output.txt")
    else:
        await edit_or_reply(message, text=f"<b>OUTPUT :</b>\n<pre>{output}</pre>")
