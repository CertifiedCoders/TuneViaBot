# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from Tune import app
from Tune.utils.database import (
    add_nonadmin_chat,
    get_authuser,
    get_authuser_names,
    get_playmode,
    get_playtype,
    get_upvote_count,
    is_nonadmin_chat,
    is_skipmode,
    remove_nonadmin_chat,
    set_playmode,
    set_playtype,
    set_upvotes,
    skip_off,
    skip_on,
)
from Tune.utils.decorators.admins import ActualAdminCB
from Tune.utils.decorators.language import language, languageCB
from Tune.utils.inline.settings import (
    auth_users_markup,
    playmode_users_markup,
    setting_markup,
    vote_mode_markup,
)
from Tune.utils.inline.start import private_panel
from config import BANNED_USERS, OWNER_ID


async def safe_callback_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    try:
        if text:
            await callback.answer(text, show_alert=show_alert)
        else:
            await callback.answer()
    except Exception:
        pass


async def get_playmode_state(chat_id: int):
    playmode = await get_playmode(chat_id)
    is_non_admin = await is_nonadmin_chat(chat_id)
    playty = await get_playtype(chat_id)
    Direct = True if playmode == "Direct" else None
    Group = True if not is_non_admin else None
    Playtype = None if playty == "Everyone" else True
    return Direct, Group, Playtype

# ─── SETTINGS MESSAGE ──────────────────────────────────────────────

@app.on_message(filters.command(["settings", "setting"]) & filters.group & ~BANNED_USERS)
@language
async def settings_mar(client, message: Message, _):
    buttons = setting_markup(_)
    await message.reply_text(
        _["setting_1"].format(app.mention, message.chat.id, message.chat.title),
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ─── SETTINGS CALLBACK (HELPER) ─────────────────────────────────────

@app.on_callback_query(filters.regex(r"^SETTINGS_BACK$") & ~BANNED_USERS)
@languageCB
async def settings_cb(client, callback: CallbackQuery, _):
    await safe_callback_answer(callback, _["set_cb_5"])
    buttons = setting_markup(_)
    return await callback.edit_message_text(
        _["setting_1"].format(app.mention, callback.message.chat.id, callback.message.chat.title),
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ─── SETTINGS BACK (PRIVATE vs. GROUP) ──────────────────────────────

@app.on_callback_query(filters.regex(r"^SETTINGS_PRIVATE_BACK$") & ~BANNED_USERS)
@languageCB
async def settings_back_markup(client, callback: CallbackQuery, _):
    await safe_callback_answer(callback)

    if callback.message.chat.type == ChatType.PRIVATE:
        await app.resolve_peer(OWNER_ID)
        buttons = private_panel(_)
        return await callback.edit_message_text(
            _["start_2"].format(callback.from_user.mention, app.mention),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    else:
        buttons = setting_markup(_)
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# ─── CALLBACK WITHOUT ADMIN RIGHTS ──────────────────────────────────

@app.on_callback_query(
    filters.regex(
        r"^(SEARCH_MODE_INFO|PLAY_TYPE_INFO|CHANNEL_MODE_INFO|AUTH_USERS_INFO|CURRENT_VOTE_INFO|VOTE_MODE_INFO|PLAYBACK_SETTINGS|AUTH_SETTINGS|VOTE_SETTINGS)$"
    ) & ~BANNED_USERS
)
@languageCB
async def without_admin_rights(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    chat_id = callback.message.chat.id
    
    info_commands = {
        "SEARCH_MODE_INFO": _["setting_2"],
        "CHANNEL_MODE_INFO": _["setting_5"],
        "PLAY_TYPE_INFO": _["setting_6"],
        "AUTH_USERS_INFO": _["setting_3"],
        "VOTE_MODE_INFO": _["setting_8"],
    }
    
    if command in info_commands:
        try:
            return await callback.answer(info_commands[command], show_alert=True)
        except Exception:
            return
    
    if command == "CURRENT_VOTE_INFO":
        current = await get_upvote_count(chat_id)
        try:
            return await callback.answer(_["setting_9"].format(current), show_alert=True)
        except Exception:
            return
    
    buttons = None
    if command == "PLAYBACK_SETTINGS":
        await safe_callback_answer(callback, _["set_cb_2"], show_alert=True)
        Direct, Group, Playtype = await get_playmode_state(chat_id)
        buttons = playmode_users_markup(_, Direct, Group, Playtype)
    elif command == "AUTH_SETTINGS":
        await safe_callback_answer(callback, _["set_cb_1"], show_alert=True)
        is_non_admin = await is_nonadmin_chat(chat_id)
        buttons = auth_users_markup(_, True) if not is_non_admin else auth_users_markup(_)
    elif command == "VOTE_SETTINGS":
        mode = await is_skipmode(chat_id)
        current = await get_upvote_count(chat_id)
        buttons = vote_mode_markup(_, current, mode)
    
    if buttons:
        try:
            return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified:
            return

# ─── VOTE COUNT ADJUSTMENT ──────────────────────────────────────────

@app.on_callback_query(filters.regex(r"^(INCREASE_VOTE_COUNT|DECREASE_VOTE_COUNT)$") & ~BANNED_USERS)
@ActualAdminCB
async def vote_count_adjust(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    chat_id = callback.message.chat.id
    
    if not await is_skipmode(chat_id):
        return await callback.answer(_["setting_10"], show_alert=True)
    
    current = await get_upvote_count(chat_id)
    
    if command == "DECREASE_VOTE_COUNT":
        final = current - 2
        if final < 2:
            final = 2
            await callback.answer(_["setting_11"], show_alert=True)
        await set_upvotes(chat_id, final)
    else:  # INCREASE_VOTE_COUNT
        final = current + 2
        if final > 15:
            final = 15
            await callback.answer(_["setting_12"], show_alert=True)
        await set_upvotes(chat_id, final)
    
    buttons = vote_mode_markup(_, final, True)
    
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return

# ─── PLAYMODE / PLAYTYPE CHANGE ─────────────────────────────────────

@app.on_callback_query(
    filters.regex(r"^(TOGGLE_SEARCH_MODE|TOGGLE_CHANNEL_MODE|TOGGLE_PLAY_TYPE)$") & ~BANNED_USERS
)
@ActualAdminCB
async def playmode_ans(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    chat_id = callback.message.chat.id
    
    await safe_callback_answer(callback, _["set_cb_3"], show_alert=True)
    
    if command == "TOGGLE_CHANNEL_MODE":
        is_non_admin = await is_nonadmin_chat(chat_id)
        if not is_non_admin:
            await add_nonadmin_chat(chat_id)
            Group = None
        else:
            await remove_nonadmin_chat(chat_id)
            Group = True
        Direct, _group, Playtype = await get_playmode_state(chat_id)
        buttons = playmode_users_markup(_, Direct, Group, Playtype)
    
    elif command == "TOGGLE_SEARCH_MODE":
        playmode = await get_playmode(chat_id)
        if playmode == "Direct":
            await set_playmode(chat_id, "Inline")
            Direct = None
        else:
            await set_playmode(chat_id, "Direct")
            Direct = True
        is_non_admin = await is_nonadmin_chat(chat_id)
        Group = True if not is_non_admin else None
        playty = await get_playtype(chat_id)
        Playtype = False if playty == "Everyone" else True
        buttons = playmode_users_markup(_, Direct, Group, Playtype)
    
    elif command == "TOGGLE_PLAY_TYPE":
        playty = await get_playtype(chat_id)
        if playty == "Everyone":
            await set_playtype(chat_id, "Admin")
            Playtype = False
        else:
            await set_playtype(chat_id, "Everyone")
            Playtype = True
        Direct, Group, _playtype = await get_playmode_state(chat_id)
        buttons = playmode_users_markup(_, Direct, Group, Playtype)
    
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return

# ─── AUTH USERS (AUTH / AUTHLIST) ─────────────────────────────────────

@app.on_callback_query(filters.regex(r"^(TOGGLE_AUTH_MODE|VIEW_AUTH_USERS)$") & ~BANNED_USERS)
@ActualAdminCB
async def authusers_mar(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    chat_id = callback.message.chat.id
    
    if command == "VIEW_AUTH_USERS":
        _authusers = await get_authuser_names(chat_id)
        if not _authusers:
            try:
                return await callback.answer(_["setting_4"], show_alert=True)
            except Exception:
                return
        
        await safe_callback_answer(callback, _["set_cb_4"], show_alert=True)
        await callback.edit_message_text(_["auth_6"])
        msg = _["auth_7"].format(callback.message.chat.title)
        counter = 0
        
        for note in _authusers:
            _note = await get_authuser(chat_id, note)
            user_id = _note["auth_user_id"]
            admin_id = _note["admin_id"]
            admin_name = _note["admin_name"]
            try:
                user_obj = await app.get_users(user_id)
                user_name = user_obj.first_name
                counter += 1
            except Exception:
                continue
            msg += f"{counter}➤ {user_name}[<code>{user_id}</code>]\n"
            msg += f"   {_['auth_8']} {admin_name}[<code>{admin_id}</code>]\n\n"
        
        upl = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="AUTH_SETTINGS"),
                InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close")
            ]]
        )
        try:
            return await callback.edit_message_text(msg, reply_markup=upl)
        except MessageNotModified:
            return
    
    await safe_callback_answer(callback, _["set_cb_3"], show_alert=True)
    
    if command == "TOGGLE_AUTH_MODE":
        is_non_admin = await is_nonadmin_chat(chat_id)
        if not is_non_admin:
            await add_nonadmin_chat(chat_id)
            buttons = auth_users_markup(_)
        else:
            await remove_nonadmin_chat(chat_id)
            buttons = auth_users_markup(_, True)
    
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return

# ─── VOTE MODE CHANGE ────────────────────────────────────────────────

@app.on_callback_query(filters.regex(r"^TOGGLE_VOTE_MODE$") & ~BANNED_USERS)
@ActualAdminCB
async def vote_change(client, callback: CallbackQuery, _):
    await safe_callback_answer(callback, _["set_cb_3"], show_alert=True)
    
    chat_id = callback.message.chat.id
    mod = None
    if await is_skipmode(chat_id):
        await skip_off(chat_id)
    else:
        mod = True
        await skip_on(chat_id)
    
    current = await get_upvote_count(chat_id)
    buttons = vote_mode_markup(_, current, mod)
    
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return
