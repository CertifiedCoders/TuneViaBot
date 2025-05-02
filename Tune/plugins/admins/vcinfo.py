from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS
from Tune import app
from Tune.core.call import JARVIS
from Tune.utils.database import group_assistant
from Tune.utils.admin_filters import admin_filter


@app.on_message(filters.command("volume") & filters.group & admin_filter & ~BANNED_USERS)
async def set_volume(client, message: Message):
    chat_id = message.chat.id

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply_text("⚠️ Usage: <code>/volume 1-200</code>")
    
    try:
        volume_level = int(args[1])
    except ValueError:
        return await message.reply_text("❌ Invalid number. Please use <code>/volume 1-200</code>")
    
    if volume_level == 0:
        return await message.reply_text("🔇 Use <code>/mute</code> to mute the stream.")
    
    if not 1 <= volume_level <= 200:
        return await message.reply_text("⚠️ Volume must be between 1 and 200.")
    
    if chat_id >= 0:
        return await message.reply_text("❌ Volume control is not supported in basic groups.")
    
    try:
        await JARVIS.change_volume(chat_id, volume_level)
        await message.reply_text(
            f"<b>🔊 Stream volume set to {volume_level}</b>.\n\n└ Requested by: {message.from_user.mention} 🥀"
        )
    except Exception as e:
        await message.reply_text(f"❌ Failed to change volume.\n<b>Error:</b> {e}")


@app.on_message(filters.command(["vcinfo", "vcmembers"]) & filters.group & admin_filter & ~BANNED_USERS)
async def vc_info(client, message: Message):
    chat_id = message.chat.id
    try:
        assistant = await group_assistant(JARVIS, chat_id)
        participants = await assistant.get_participants(chat_id)

        if not participants:
            return await message.reply_text("❌ No users found in the voice chat.")

        msg_lines = ["🎧 <b>VC Members Info:</b>\n"]
        for p in participants:
            try:
                user = await app.get_users(p.user_id)
                name = user.mention if user else f"<code>{p.user_id}</code>"
            except Exception:
                name = f"<code>{p.user_id}</code>"

            mute_status = "🔇" if p.muted else "👤"
            screen_status = "🖥️" if getattr(p, "screen_sharing", False) else ""
            volume_level = getattr(p, "volume", "N/A")

            info = f"{mute_status} {name} | 🎚️ {volume_level}"
            if screen_status:
                info += f" | {screen_status}"
            msg_lines.append(info)

        msg_lines.append(f"\n👥 Total: <b>{len(participants)}</b>")
        await message.reply_text("\n".join(msg_lines))
    except Exception as e:
        await message.reply_text(f"❌ Failed to fetch VC info.\n<b>Error:</b> {e}")
