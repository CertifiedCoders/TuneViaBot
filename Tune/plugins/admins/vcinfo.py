from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.core.call import Jarvis
from Tune.utils.decorators import AdminRightsCheck
from Tune.utils.database import group_assistant
from config import BANNED_USERS


@app.on_message(filters.command("volume") & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def set_volume(cli, message: Message, _, chat_id):
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

    try:
        await Jarvis.change_volume(chat_id, volume_level)
        await message.reply_text(
            f"<b>🔊 Stream volume set to {volume_level}</b>.\n\n└ Requested by: {message.from_user.mention} 🥀"
        )
    except Exception as e:
        await message.reply_text(f"❌ Failed to change volume.\n<b>Error:</b> {e}")


@app.on_message(filters.command(["vcinfo", "vcmembers"]) & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def vc_info(cli, message: Message, _, chat_id):
    try:
        assistant = await group_assistant(Jarvis, chat_id)
        participants = await assistant.get_participants(chat_id)

        if not participants:
            return await message.reply_text("❌ No users found in the voice chat.")

        msg_lines = ["🎧 <b>VC Members Info:</b>\n"]
        for p in participants:
            try:
                user = await app.get_users(p.user_id)
                name = user.mention if user else f"<code>{p.user_id}</code>"
            except:
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
