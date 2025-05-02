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

@app.on_callback_query(filters.regex(r"^settings_helper$") & ~BANNED_USERS)
@languageCB
async def settings_cb(client, callback: CallbackQuery, _):
    try:
        await callback.answer(_["set_cb_5"])
    except Exception:
        pass
    buttons = setting_markup(_)
    return await callback.edit_message_text(
        _["setting_1"].format(app.mention, callback.message.chat.id, callback.message.chat.title),
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ─── SETTINGS BACK (PRIVATE vs. GROUP) ──────────────────────────────

@app.on_callback_query(filters.regex(r"^settingsback_helper$") & ~BANNED_USERS)
@languageCB
async def settings_back_markup(client, callback: CallbackQuery, _):
    try:
        await callback.answer()
    except Exception:
        pass

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
        r"^(SEARCHANSWER|PLAYMODEANSWER|PLAYTYPEANSWER|AUTHANSWER|ANSWERVOMODE|VOTEANSWER|PM|AU|VM)$"
    ) & ~BANNED_USERS
)
@languageCB
async def without_admin_rights(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    if command == "SEARCHANSWER":
        try:
            return await callback.answer(_["setting_2"], show_alert=True)
        except Exception:
            return
    if command == "PLAYMODEANSWER":
        try:
            return await callback.answer(_["setting_5"], show_alert=True)
        except Exception:
            return
    if command == "PLAYTYPEANSWER":
        try:
            return await callback.answer(_["setting_6"], show_alert=True)
        except Exception:
            return
    if command == "AUTHANSWER":
        try:
            return await callback.answer(_["setting_3"], show_alert=True)
        except Exception:
            return
    if command == "VOTEANSWER":
        try:
            return await callback.answer(_["setting_8"], show_alert=True)
        except Exception:
            return
    if command == "ANSWERVOMODE":
        current = await get_upvote_count(callback.message.chat.id)
        try:
            return await callback.answer(_["setting_9"].format(current), show_alert=True)
        except Exception:
            return
    if command == "PM":
        try:
            await callback.answer(_["set_cb_2"], show_alert=True)
        except Exception:
            pass
        playmode = await get_playmode(callback.message.chat.id)
        Direct = True if playmode == "Direct" else None
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        Group = True if not is_non_admin else None
        playty = await get_playtype(callback.message.chat.id)
        Playtype = None if playty == "Everyone" else True
        buttons = playmode_users_markup(_, Direct, Group, Playtype)
    if command == "AU":
        try:
            await callback.answer(_["set_cb_1"], show_alert=True)
        except Exception:
            pass
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        buttons = auth_users_markup(_, True) if not is_non_admin else auth_users_markup(_)
    if command == "VM":
        mode = await is_skipmode(callback.message.chat.id)
        current = await get_upvote_count(callback.message.chat.id)
        buttons = vote_mode_markup(_, current, mode)
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return

# ─── NON-ADMIN ADDITION (FERRARIUDTI) ────────────────────────────────

@app.on_callback_query(filters.regex(r"^FERRARIUDTI$") & ~BANNED_USERS)
@ActualAdminCB
async def addition(client, callback: CallbackQuery, _):
    callback_data = callback.data.strip()
    mode = callback_data.split(None, 1)[1]
    if not await is_skipmode(callback.message.chat.id):
        return await callback.answer(_["setting_10"], show_alert=True)
    current = await get_upvote_count(callback.message.chat.id)
    if mode == "M":
        final = current - 2
        if final <= 2:
            final = 2
        if final == 0:
            return await callback.answer(_["setting_11"], show_alert=True)
        await set_upvotes(callback.message.chat.id, final)
    else:
        final = current + 2
        if final >= 15:
            final = 15
        if final == 17:
            return await callback.answer(_["setting_12"], show_alert=True)
        await set_upvotes(callback.message.chat.id, final)
    buttons = vote_mode_markup(_, final, True)
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return

# ─── PLAYMODE / PLAYTYPE CHANGE ─────────────────────────────────────

@app.on_callback_query(
    filters.regex(r"^(MODECHANGE|CHANNELMODECHANGE|PLAYTYPECHANGE)$") & ~BANNED_USERS
)
@ActualAdminCB
async def playmode_ans(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    if command == "CHANNELMODECHANGE":
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        if not is_non_admin:
            await add_nonadmin_chat(callback.message.chat.id)
            Group = None
        else:
            await remove_nonadmin_chat(callback.message.chat.id)
            Group = True
        playmode = await get_playmode(callback.message.chat.id)
        Direct = True if playmode == "Direct" else None
        playty = await get_playtype(callback.message.chat.id)
        Playtype = None if playty == "Everyone" else True
        buttons = playmode_users_markup(_, Direct, Group, Playtype)
    elif command == "MODECHANGE":
        try:
            await callback.answer(_["set_cb_3"], show_alert=True)
        except Exception:
            pass
        playmode = await get_playmode(callback.message.chat.id)
        if playmode == "Direct":
            await set_playmode(callback.message.chat.id, "Inline")
            Direct = None
        else:
            await set_playmode(callback.message.chat.id, "Direct")
            Direct = True
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        Group = True if not is_non_admin else None
        playty = await get_playtype(callback.message.chat.id)
        Playtype = False if playty == "Everyone" else True
        buttons = playmode_users_markup(_, Direct, Group, Playtype)
    elif command == "PLAYTYPECHANGE":
        try:
            await callback.answer(_["set_cb_3"], show_alert=True)
        except Exception:
            pass
        playty = await get_playtype(callback.message.chat.id)
        if playty == "Everyone":
            await set_playtype(callback.message.chat.id, "Admin")
            Playtype = False
        else:
            await set_playtype(callback.message.chat.id, "Everyone")
            Playtype = True
        playmode = await get_playmode(callback.message.chat.id)
        Direct = True if playmode == "Direct" else None
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        Group = True if not is_non_admin else None
        buttons = playmode_users_markup(_, Direct, Group, Playtype)
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return

# ─── AUTH USERS (AUTH / AUTHLIST) ─────────────────────────────────────

@app.on_callback_query(filters.regex(r"^(AUTH|AUTHLIST)$") & ~BANNED_USERS)
@ActualAdminCB
async def authusers_mar(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    if command == "AUTHLIST":
        _authusers = await get_authuser_names(callback.message.chat.id)
        if not _authusers:
            try:
                return await callback.answer(_["setting_4"], show_alert=True)
            except Exception:
                return
        else:
            try:
                await callback.answer(_["set_cb_4"], show_alert=True)
            except Exception:
                pass
            counter = 0
            await callback.edit_message_text(_["auth_6"])
            msg = _["auth_7"].format(callback.message.chat.title)
            for note in _authusers:
                _note = await get_authuser(callback.message.chat.id, note)
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
                    InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="AU"),
                    InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close")
                ]]
            )
            try:
                return await callback.edit_message_text(msg, reply_markup=upl)
            except MessageNotModified:
                return
    try:
        await callback.answer(_["set_cb_3"], show_alert=True)
    except Exception:
        pass
    if command == "AUTH":
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        if not is_non_admin:
            await add_nonadmin_chat(callback.message.chat.id)
            buttons = auth_users_markup(_)
        else:
            await remove_nonadmin_chat(callback.message.chat.id)
            buttons = auth_users_markup(_, True)
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return

# ─── VOTE MODE CHANGE ────────────────────────────────────────────────

@app.on_callback_query(filters.regex(r"^(VOMODECHANGE)$") & ~BANNED_USERS)
@ActualAdminCB
async def vote_change(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    try:
        await callback.answer(_["set_cb_3"], show_alert=True)
    except Exception:
        pass
    mod = None
    if await is_skipmode(callback.message.chat.id):
        await skip_off(callback.message.chat.id)
    else:
        mod = True
        await skip_on(callback.message.chat.id)
    current = await get_upvote_count(callback.message.chat.id)
    buttons = vote_mode_markup(_, current, mod)
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return
