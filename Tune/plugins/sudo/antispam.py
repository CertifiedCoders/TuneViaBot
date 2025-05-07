from pyrogram import filters
from pyrogram.types import Message

from config import OWNER_ID
from Tune import app
from Tune.antispam import toggle_antispam, is_antispam_enabled

@app.on_message(filters.command(["antispam", "aswitch", "spamlock"]) & filters.user(OWNER_ID))
async def toggle_antispam_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "💡 ᴜsᴀɢᴇ: `/antispam on` ᴏʀ `/antispam off`"
        )

    arg = message.command[1].lower().strip()
    if arg not in ["on", "off"]:
        return await message.reply_text(
            "❌ ɪɴᴠᴀʟɪᴅ ᴏᴘᴛɪᴏɴ.\nᴜsᴇ `/antispam on` ᴏʀ `/antispam off`"
        )

    state = toggle_antispam(arg == "on")
    emoji = "✅" if arg == "on" else "❌"

    await message.reply_text(
        f"{emoji} ᴀɴᴛɪ-sᴘᴀᴍ ᴘʀᴏᴛᴇᴄᴛɪᴏɴ ʜᴀs ʙᴇᴇɴ **{state}**."
    )


@app.on_message(filters.command("spamstatus") & filters.user(OWNER_ID))
async def antispam_status_cmd(_, message: Message):
    current = "ᴇɴᴀʙʟᴇᴅ ✅" if is_antispam_enabled() else "ᴅɪsᴀʙʟᴇᴅ ❌"
    await message.reply_text(
        f"🔎 ᴀɴᴛɪ-sᴘᴀᴍ sᴛᴀᴛᴜs: **{current}**"
    )
