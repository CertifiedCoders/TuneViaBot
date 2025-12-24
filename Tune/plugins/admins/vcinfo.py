# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS
from Tune import app
from Tune.core.call import StreamController
from Tune.utils.database import group_assistant
from Tune.utils.admin_filters import admin_filter


@app.on_message(filters.command(["vcinfo", "vcmembers"]) & filters.group & admin_filter & ~BANNED_USERS)
async def vc_info(client, message: Message):
    chat_id = message.chat.id
    try:
        assistant = await group_assistant(StreamController, chat_id)
        participants = await assistant.get_participants(chat_id)

        if not participants:
            return await message.reply_text("❌ No users found in the voice chat.")

        msg_lines = ["🎧 <b>VC Members Info:</b>\n"]
        muted_count = 0
        unmuted_count = 0
        
        for p in participants:
            try:
                user = await app.get_users(p.user_id)
                name = user.mention if user else f"<code>{p.user_id}</code>"
            except Exception:
                name = f"<code>{p.user_id}</code>"

            is_muted = getattr(p, "is_muted", getattr(p, "muted", False))
            if is_muted:
                muted_count += 1
                mute_status = "🔇"
            else:
                unmuted_count += 1
                mute_status = "🔊"
            
            screen_status = "🖥️" if getattr(p, "screen_sharing", False) or getattr(p, "video", False) else ""
            
            volume_level = getattr(p, "volume", None)
            if volume_level is not None and volume_level <= 200:
                volume_percent = round(volume_level / 2, 1)
                volume_display = f"{volume_percent}%"
            else:
                volume_display = "N/A"

            info = f"{mute_status} {name} | 🎚️ {volume_display}"
            if screen_status:
                info += f" | {screen_status}"
            msg_lines.append(info)

        msg_lines.append(f"\n📊 <b>Statistics:</b>")
        msg_lines.append(f"👥 Total: <b>{len(participants)}</b>")
        msg_lines.append(f"🔊 Unmuted: <b>{unmuted_count}</b>")
        msg_lines.append(f"🔇 Muted: <b>{muted_count}</b>")
        
        await message.reply_text("\n".join(msg_lines))
    except Exception as e:
        await message.reply_text(f"❌ Failed to fetch VC info.\n<b>Error:</b> {e}")