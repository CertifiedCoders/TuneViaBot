# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.utils.database import get_loop, set_loop
from Tune.utils.decorators import AdminRightsCheck
from Tune.utils.inline import close_markup
from config import BANNED_USERS


@app.on_message(filters.command(["loop", "cloop"]) & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def admins(cli, message: Message, _, chat_id):
    usage = _["admin_17"]
    if len(message.command) != 2:
        return await message.reply_text(usage)
    state = message.text.split(None, 1)[1].strip()
    if state.isnumeric():
        loop_count = int(state)
        if 1 <= loop_count <= 10:
            current_loop = await get_loop(chat_id)
            if current_loop != 0:
                loop_count = current_loop + loop_count
            if loop_count > 10:
                loop_count = 10
            await set_loop(chat_id, loop_count)
            return await message.reply_text(
                text=_["admin_18"].format(loop_count, message.from_user.mention),
                reply_markup=close_markup(_),
            )
        else:
            return await message.reply_text(usage)
    elif state.lower() == "enable":
        await set_loop(chat_id, 10)
        return await message.reply_text(
            text=_["admin_18"].format(10, message.from_user.mention),
            reply_markup=close_markup(_),
        )
    elif state.lower() == "disable":
        await set_loop(chat_id, 0)
        return await message.reply_text(
            _["admin_19"].format(message.from_user.mention),
            reply_markup=close_markup(_),
        )
    else:
        return await message.reply_text(usage)
