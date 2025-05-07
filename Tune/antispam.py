import time
from typing import Dict, List
from collections import defaultdict

from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

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

# ─── Core Handler ────────────────────────────────────────────────────────────

async def global_antispam_handler(_, message: Message):
    if not message.from_user:
        return

    user_id = message.from_user.id

    if not ANTISPAM_ENABLED:
        await message.continue_propagation()
        return

    if user_id in OWNER_ID:
        await message.continue_propagation()
        return

    if user_id in BANNED_USERS:
        return

    chat_id = message.chat.id if message.chat else user_id
    key = f"{chat_id}:{user_id}"
    now = time.time()

    timestamps = user_records[key]
    timestamps[:] = [t for t in timestamps if now - t < BLOCK_TIME]
    timestamps.append(now)

    if len(timestamps) > SPAM_THRESHOLD:
        if user_id not in BANNED_USERS:
            BANNED_USERS.add(user_id)
            try:
                await add_banned_user(user_id)
            except Exception as e:
                LOGGER("AntiSpam").error(f"⚠️ Failed to save ban: {e}")

        notify_text = (
            f"🚫 <b>{message.from_user.mention}</b>, ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ <u>ʙʟᴏᴄᴋᴇᴅ</u> ʙʏ ᴛʜᴇ ʙᴏᴛ's 🛡️ ᴀɴᴛɪ‑sᴘᴀᴍ sʏsᴛᴇᴍ.\n\n"
            "❗ <b>Reason:</b> <i>You were sending too many commands in a short period.</i>\n"
            "🔒 <b>ᴛʜɪs ᴀᴄᴄᴏᴜɴᴛ ɪs ɴᴏ ʟᴏɴɢᴇʀ ᴀʟʟᴏᴡᴇᴅ ᴛᴏ ɪɴᴛᴇʀᴀᴄᴛ ᴡɪᴛʜ ᴛʜᴇ ʙᴏᴛ.</b>\n\n"
            "👥 If you believe this was a mistake or were simply testing, please visit our "
            "<a href='https://t.me/CertifiedCoders'>Support Group</a> to appeal.\n\n"
            "🧠 <b>Tip:</b> Use commands at a steady pace to avoid future blocks.\n\n"
            "<b>— ᴛʜᴀɴᴋ ʏᴏᴜ ғᴏʀ ᴜɴᴅᴇʀsᴛᴀɴᴅɪɴɢ 💖</b>"
        )

        try:
            await message.reply_text(
                notify_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            pass

        try:
            chat_info = "📥 <b>Chat:</b> Private Chat\n"
            if message.chat and message.chat.type in ("group", "supergroup"):
                try:
                    invite = await app.export_chat_invite_link(message.chat.id)
                except:
                    invite = "N/A"
                chat_info = (
                    f"👥 <b>Group:</b> {message.chat.title} (<code>{message.chat.id}</code>)\n"
                    f"🔗 <b>Invite:</b> {invite}\n"
                )

            log_text = (
                "🚨 <b>SPAMMER DETECTED</b>\n\n"
                f"👤 <b>User:</b> <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a> "
                f"(<code>{user_id}</code>)\n"
                f"🔗 <b>Username:</b> @{message.from_user.username or 'N/A'}\n"
                f"🗨️ <b>Command:</b> <code>{message.text[:50]}</code>\n"
                f"{chat_info}"
            )

            await app.send_message(
                LOGGER_ID,
                text=log_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            pass

        return

    await message.continue_propagation()
