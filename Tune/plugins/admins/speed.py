# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS, adminlist
from Tune import app
from Tune.core.call import StreamController
from Tune.misc import SUDOERS, db
from Tune.utils import AdminRightsCheck
from Tune.utils.database import is_active_chat, is_nonadmin_chat
from Tune.utils.decorators.language import languageCB
from Tune.utils.inline import close_markup, speed_markup

checker = []


def _validate_playing(chat_id):
    playing = db.get(chat_id)
    if not playing:
        return None, None
    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        return None, None
    file_path = playing[0]["file"]
    if "downloads" not in file_path:
        return None, None
    return playing, file_path


@app.on_message(
    filters.command(["cspeed", "speed", "cslow", "slow", "playback", "cplayback"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def playback(cli, message: Message, _, chat_id):
    playing, file_path = _validate_playing(chat_id)
    if not playing:
        return await message.reply_text(_["queue_2"])
    return await message.reply_text(
        text=_["admin_28"].format(app.mention),
        reply_markup=speed_markup(_, chat_id),
    )


def _check_admin_permission(user_id, chat_id, is_non_admin):
    if is_non_admin or user_id in SUDOERS:
        return True
    admins = adminlist.get(chat_id)
    if not admins or user_id not in admins:
        return False
    return True


@app.on_callback_query(filters.regex("SpeedUP") & ~BANNED_USERS)
@languageCB
async def manage_callback(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    chat, speed = callback_request.split("|")
    chat_id = int(chat)
    
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    
    is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
    if not _check_admin_permission(CallbackQuery.from_user.id, CallbackQuery.message.chat.id, is_non_admin):
        error_key = "admin_13" if not adminlist.get(CallbackQuery.message.chat.id) else "admin_14"
        return await CallbackQuery.answer(_[error_key], show_alert=True)
    
    playing, file_path = _validate_playing(chat_id)
    if not playing:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
    
    current_speed = playing[0].get("speed")
    # Block if the requested speed matches the current speed
    # For 1.0x, also treat None/unset as 1.0x (default normal speed)
    if str(speed) == "1.0":
        # Block only if already at normal speed (1.0x or unset/None)
        if not current_speed or str(current_speed) == "1.0":
            return await CallbackQuery.answer(_["admin_29"], show_alert=True)
    elif current_speed and str(current_speed) == str(speed):
        # For other speeds, block if already at that speed
        return await CallbackQuery.answer(_["admin_29"], show_alert=True)
    
    if chat_id in checker:
        return await CallbackQuery.answer(_["admin_30"], show_alert=True)
    
    checker.append(chat_id)
    try:
        try:
            await CallbackQuery.answer(_["admin_31"])
        except:
            pass
        
        mystic = await CallbackQuery.edit_message_text(
            text=_["admin_32"].format(CallbackQuery.from_user.mention),
        )
        
        try:
            await StreamController.speedup_stream(chat_id, file_path, speed, playing)
            await mystic.edit_text(
                text=_["admin_34"].format(speed, CallbackQuery.from_user.mention),
                reply_markup=close_markup(_),
            )
        except:
            await mystic.edit_text(_["admin_33"], reply_markup=close_markup(_))
    finally:
        if chat_id in checker:
            checker.remove(chat_id)
