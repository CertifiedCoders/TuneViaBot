# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.misc import SUDOERS
from Tune.utils.database import autoend_off, autoend_on
from Tune.utils.decorators.language import language_no_delete


@app.on_message(filters.command("autoend") & SUDOERS)
@language_no_delete
async def auto_end_stream(client, message: Message, _):
    usage = _["autoend_1"]
    if len(message.command) != 2:
        return await message.reply_text(usage)
    state = message.text.split(None, 1)[1].strip().lower()
    if state == "enable":
        await autoend_on()
        await message.reply_text(_["autoend_2"])
    elif state == "disable":
        await autoend_off()
        await message.reply_text(_["autoend_3"])
    else:
        await message.reply_text(usage)
