from datetime import datetime

from pyrogram import filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import OWNER_ID
from Tune import app


def extract_bug_content(msg: Message) -> str:
    if msg.text and " " in msg.text:
        return msg.text.split(None, 1)[1]
    return None


@app.on_message(filters.command("bug"))
async def report_bug(_, msg: Message):
    if msg.chat.type == "private":
        await msg.reply_text("<b>ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ɪs ᴏɴʟʏ ғᴏʀ ɢʀᴏᴜᴘs.</b>")
        return

    bug_description = extract_bug_content(msg)
    if not bug_description:
        await msg.reply_text(
            "<b>ɴᴏ ʙᴜɢ ᴅᴇsᴄʀɪᴘᴛɪᴏɴ ᴘʀᴏᴠɪᴅᴇᴅ. ᴘʟᴇᴀsᴇ sᴘᴇᴄɪғʏ ᴛʜᴇ ʙᴜɢ.</b>"
        )
        return

    user_id = msg.from_user.id
    mention = f"[{msg.from_user.first_name}](tg://user?id={user_id})"
    chat_username = (
        f"@{msg.chat.username}/`{msg.chat.id}`"
        if msg.chat.username
        else f"ᴘʀɪᴠᴀᴛᴇ ɢʀᴏᴜᴘ/`{msg.chat.id}`"
    )
    current_date = datetime.utcnow().strftime("%d-%m-%Y")

    bug_report = (
        f"**#ʙᴜɢ ʀᴇᴘᴏʀᴛ**\n"
        f"**ʀᴇᴘᴏʀᴛᴇᴅ ʙʏ:** {mention}\n"
        f"**ᴜsᴇʀ ɪᴅ:** {user_id}\n"
        f"**ᴄʜᴀᴛ:** {chat_username}\n"
        f"**ʙᴜɢ ᴅᴇsᴄʀɪᴘᴛɪᴏɴ:** {bug_description}\n"
        f"**ᴅᴀᴛᴇ:** {current_date}"
    )

    if user_id == OWNER_ID:
        await msg.reply_text(
            "<b>ʏᴏᴜ ᴀʀᴇ ᴛʜᴇ ᴏᴡɴᴇʀ ᴏғ ᴛʜᴇ ʙᴏᴛ. ᴘʟᴇᴀsᴇ ᴀᴅᴅʀᴇss ᴛʜᴇ ʙᴜɢ ᴅɪʀᴇᴄᴛʟʏ.</b>"
        )
    else:
        await msg.reply_text(
            "<b>ʙᴜɢ ʀᴇᴘᴏʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close_data")]]
            ),
        )
        await app.send_message(
            -1002077986660,
            bug_report,
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("ᴠɪᴇᴡ ʙᴜɢ", url=msg.link)],
                    [InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close_send_photo")],
                ]
            ),
        )


@app.on_callback_query(filters.regex("close_send_photo"))
async def close_bug_report(_, query: CallbackQuery):
    is_admin = await app.get_chat_member(query.message.chat.id, query.from_user.id)
    if not is_admin.privileges.can_delete_messages:
        await query.answer("ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴛʜᴇ ʀɪɢʜᴛs ᴛᴏ ᴄʟᴏsᴇ ᴛʜɪs.", show_alert=True)
    else:
        await query.message.delete()
