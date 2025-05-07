import time
import html
from typing import Dict, List
from collections import defaultdict

from pyrogram import filters
from pyrogram.enums import ParseMode, ChatType
from pyrogram.types import Message

from config import BANNED_USERS, LOGGER_ID
from Tune import LOGGER, app
from Tune.utils.database import add_banned_user

__all__ = [
    "init_antispam",
    "antispam_filter",
    "toggle_antispam",
    "is_antispam_enabled",
    "global_antispam_handler",
]

# ─── Configuration ───────────────────────────────────────────────────────────

SPAM_THRESHOLD = 7  # Max commands allowed
BLOCK_TIME = 5      # Time window in seconds

user_records: Dict[str, List[float]] = defaultdict(list)
OWNER_ID: List[int] = []
ANTISPAM_ENABLED = True

# ─── Setup & Controls ────────────────────────────────────────────────────────

def init_antispam(owner_ids):
    global OWNER_ID
    OWNER_ID = (
        owner_ids
        if isinstance(owner_ids, list)
        else [owner_ids] if owner_ids else []
    )

def antispam_filter() -> filters.Filter:
    return filters.regex(r"^/") & (filters.private | filters.group)

def toggle_antispam(enable: bool) -> str:
    global ANTISPAM_ENABLED
    ANTISPAM_ENABLED = enable
    return "ᴇɴᴀʙʟᴇᴅ ✅" if enable else "ᴅɪsᴀʙʟᴇᴅ ❌"

def is_antispam_enabled() -> bool:
    return ANTISPAM_ENABLED

# ─── Helpers ────────────────────────────────────────────────────────────────

async def _get_invite_link(chat) -> str | None:
    if chat.username:
        return f"https://t.me/{chat.username}"
    try:
        return await app.export_chat_invite_link(chat.id)
    except Exception:
        return None

# ─── Core Handler ────────────────────────────────────────────────────────────

async def global_antispam_handler(_, message: Message):
    if not message.from_user:
        return

    user_id = message.from_user.id

    if not ANTISPAM_ENABLED or user_id in OWNER_ID:
        await message.continue_propagation()
        return

    # Already banned?
    if user_id in BANNED_USERS:
        return

    chat_id = message.chat.id if message.chat else user_id
    key = f"{chat_id}:{user_id}"
    now = time.time()
    timestamps = user_records[key]
    timestamps[:] = [t for t in timestamps if now - t < BLOCK_TIME]
    timestamps.append(now)

    # Spam detected
    if len(timestamps) > SPAM_THRESHOLD:
        BANNED_USERS.add(user_id)
        try:
            await add_banned_user(user_id)
        except Exception as e:
            LOGGER("AntiSpam").error(f"⚠️ Failed to save ban: {e}")

        notify = (
            f"🚫 <b>{message.from_user.mention}</b>, ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ <u>ʙʟᴏᴄᴋᴇᴅ</u> ʙʏ ᴛʜᴇ ʙᴏᴛ's 🛡️ ᴀɴᴛɪ‑sᴘᴀᴍ sʏsᴛᴇᴍ.\n\n"
            "❗ <b>Reason:</b> <i>You were sending too many commands in a short period.</i>\n"
            "🔒 <b>ᴛʜɪs ᴀᴄᴄᴏᴜɴᴛ ɪs ɴᴏ ʟᴏɴɢᴇʀ ᴀʟʟᴏᴡᴇᴅ ᴛᴏ ɪɴᴛᴇʀᴀᴄᴛ ᴡɪᴛʜ ᴛʜᴇ ʙᴏᴛ.</b>\n\n"
            "👥 If you believe this was a mistake or were simply testing, please visit our "
            "<a href='https://t.me/CertifiedCoders'>Support Group</a> to appeal.\n\n"
            "🧠 <b>Tip:</b> Use commands at a steady pace to avoid future blocks.\n\n"
            "<b>— ᴛʜᴀɴᴋ ʏᴏᴜ ғᴏʀ ᴜɴᴅᴇʀsᴛᴀɴᴅɪɴɢ 💖</b>"
        )

        await message.reply_text(notify, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


        if message.chat:
            chat = message.chat
            ct = chat.type
            chat_title = html.escape(getattr(chat, "title", "Private Chat"))
            lines = [f"📌 <b>Chat Type:</b> {ct.name.title()}"]
            if ct is ChatType.PRIVATE:
                user_name = html.escape(chat.first_name or "User")
                username = f"@{chat.username}" if chat.username else "N/A"
                lines.append(f"👤 <b>User:</b> <a href='tg://user?id={chat.id}'>{user_name}</a>")
                lines.append(f"🔗 <b>Username:</b> {username}")
            else:
                lines.append(f"🏷️ <b>Title:</b> {chat_title}")
                username_link = f"<a href='https://t.me/{chat.username}'>@{chat.username}</a>" if chat.username else None
                if username_link:
                    lines.append(f"🔗 <b>Username:</b> {username_link}")
                invite = await _get_invite_link(chat)
                if invite:
                    lines.append(f"📩 <b>Invite:</b> <a href='{invite}'>Link</a>")
            lines.append(f"🆔 <b>ID:</b> <code>{chat.id}</code>")
            chat_info = "\n".join(lines) + "\n"
        else:
            chat_info = "⚠️ <b>Chat info unavailable</b>\n"

        log = (
            "🚨 <b>SPAMMER DETECTED</b>\n\n"
            f"👤 <b>User:</b> <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a> "
            f"(<code>{user_id}</code>)\n"
            f"🔗 <b>Username:</b> @{message.from_user.username or 'N/A'}\n"
            f"🗨️ <b>Command:</b> <code>{html.escape(message.text or '')[:50]}</code>\n"
            f"{chat_info}"
        )
        await app.send_message(LOGGER_ID, log, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        return

    await message.continue_propagation()
