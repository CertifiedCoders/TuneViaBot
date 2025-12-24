# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.misc import SUDOERS
from Tune.utils.database import (
    get_lang,
    is_maintenance,
    maintenance_off,
    maintenance_on,
)
from strings import get_string


@app.on_message(filters.command(["maintenance"]) & SUDOERS)
async def maintenance(client, message: Message):
    try:
        language = await get_lang(message.chat.id)
        _ = get_string(language)
    except:
        _ = get_string("en")
    
    if len(message.command) != 2:
        return await message.reply_text(_["maint_1"])
    
    state = message.text.split(None, 1)[1].strip().lower()
    maintenance_active = await is_maintenance() is False
    
    if state == "enable":
        if maintenance_active:
            await message.reply_text(_["maint_4"])
        else:
            await maintenance_on()
            await message.reply_text(_["maint_2"].format(app.mention))
    elif state == "disable":
        if not maintenance_active:
            await message.reply_text(_["maint_5"])
        else:
            await maintenance_off()
            await message.reply_text(_["maint_3"].format(app.mention))
    else:
        await message.reply_text(_["maint_1"])
