# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
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
        # Get current voice chat members from Telegram's perspective.
        tg_participants = []
        async for member in app.get_chat_members(chat_id, filter=ChatMembersFilter.VOICE_CHAT):
            tg_participants.append(member)

        if not tg_participants:
            return await message.reply_text("❌ No active voice chat or no users in the voice chat.")

        # Try to fetch richer participant info from the assistant/ntgcalls,
        # but fall back gracefully if it fails.
        ntg_map = {}
        try:
            assistant = await group_assistant(StreamController, chat_id)
            ntg_participants = await assistant.get_participants(chat_id)
            ntg_map = {p.user_id: p for p in ntg_participants}
        except Exception:
            ntg_map = {}

        msg_lines = ["🎧 <b>VC Members Info:</b>\n"]
        for m in tg_participants:
            user = m.user
            uid = user.id if user else None
            try:
                name = user.mention if user else f"<code>{m.user.id}</code>"
            except Exception:
                name = f"<code>{uid or 'Unknown'}</code>"

            ntg = ntg_map.get(uid) if uid is not None else None
            muted = getattr(ntg, "muted", False)
            mute_status = "🔇" if muted else "👤"
            screen_status = "🖥️" if getattr(ntg, "screen_sharing", False) else ""
            volume_level = getattr(ntg, "volume", "N/A") if ntg else "N/A"

            info = f"{mute_status} {name} | 🎚️ {volume_level}"
            if screen_status:
                info += f" | {screen_status}"
            msg_lines.append(info)

        msg_lines.append(f"\n👥 Total: <b>{len(tg_participants)}</b>")
        await message.reply_text("\n".join(msg_lines))
    except Exception as e:
        await message.reply_text(f"❌ Failed to fetch VC info.\n<b>Error:</b> {e}")
