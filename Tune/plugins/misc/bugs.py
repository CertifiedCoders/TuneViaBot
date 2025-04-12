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
        await msg.reply_text("<b>This command is only for groups.</b>")
        return

    bug_description = extract_bug_content(msg)
    if not bug_description:
        await msg.reply_text(
            "<b>No bug description provided. Please specify the bug.</b>"
        )
        return

    user_id = msg.from_user.id
    mention = f"[{msg.from_user.first_name}](tg://user?id={user_id})"
    chat_username = (
        f"@{msg.chat.username}/`{msg.chat.id}`"
        if msg.chat.username
        else f"Private Group/`{msg.chat.id}`"
    )
    current_date = datetime.utcnow().strftime("%d-%m-%Y")

    bug_report = (
        f"**#Bug Report**\n"
        f"**Reported by:** {mention}\n"
        f"**User ID:** {user_id}\n"
        f"**Chat:** {chat_username}\n"
        f"**Bug Description:** {bug_description}\n"
        f"**Date:** {current_date}"
    )

    if user_id == OWNER_ID:
        await msg.reply_text(
            "<b>You are the owner of the bot. Please address the bug directly.</b>"
        )
    else:
        await msg.reply_text(
            f"<b>Bug reported successfully!</b>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Close", callback_data="close_data")]]
            ),
        )
        await app.send_message(
            -1002014167331,
            bug_report,
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("View Bug", url=msg.link)],
                    [InlineKeyboardButton("Close", callback_data="close_send_photo")],
                ]
            ),
        )


@app.on_callback_query(filters.regex("close_send_photo"))
async def close_bug_report(_, query: CallbackQuery):
    is_admin = await app.get_chat_member(query.message.chat.id, query.from_user.id)
    if not is_admin.privileges.can_delete_messages:
        await query.answer("You don't have the rights to close this.", show_alert=True)
    else:
        await query.message.delete()
