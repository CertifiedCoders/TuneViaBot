import asyncio
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    InviteHashExpired,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from Tune import YouTube, app
from Tune.misc import SUDOERS
from Tune.utils.database import (
    get_assistant,
    get_cmode,
    get_lang,
    get_playmode,
    get_playtype,
    is_active_chat,
    is_maintenance,
)
from Tune.utils.inline import botplaylist_markup
from config import PLAYLIST_IMG_URL, SUPPORT_CHAT, adminlist
from strings import get_string

# Cache for chat invite links
INVITE_LINK_CACHE = {}


def PlayWrapper(play_command):
    async def wrapper(client, message: Message):
        # --------------------------------------------------
        # 1) Basic checks: Anonymous Admin, Maintenance
        # --------------------------------------------------
        lang = await get_lang(message.chat.id)
        _ = get_string(lang)

        if message.sender_chat:
            # User is anonymous admin
            fix_btn = InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="ʜᴏᴡ ᴛᴏ ғɪx ?", callback_data="AnonymousAdmin")]]
            )
            return await message.reply_text(_["general_3"], reply_markup=fix_btn)

        # Check maintenance
        if not await is_maintenance():
            if message.from_user.id not in SUDOERS:
                return await message.reply_text(
                    text=(
                        f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, "
                        f"ᴠɪsɪᴛ <a href='{SUPPORT_CHAT}'>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ."
                    ),
                    disable_web_page_preview=True,
                )

        # Attempt to remove user's command message
        try:
            await message.delete()
        except:
            pass

        # --------------------------------------------------
        # 2) Gather audio/video or link from message
        # --------------------------------------------------
        audio_telegram = (
            message.reply_to_message.audio or message.reply_to_message.voice
        ) if message.reply_to_message else None

        video_telegram = (
            message.reply_to_message.video or message.reply_to_message.document
        ) if message.reply_to_message else None

        url = await YouTube.url(message)  # possibly None

        # If we find none and also no /play <query>, show usage
        if not (audio_telegram or video_telegram or url):
            if len(message.command) < 2:
                # Possibly the user just typed /play with no query
                if "stream" in message.command:
                    return await message.reply_text(_["str_1"])
                # show the bot's playlist usage
                markup = botplaylist_markup(_)
                return await message.reply_photo(
                    photo=PLAYLIST_IMG_URL,
                    caption=_["play_18"],
                    reply_markup=InlineKeyboardMarkup(markup),
                )

        # --------------------------------------------------
        # 3) Identify channel/group mode
        # --------------------------------------------------
        if message.command[0][0] == "c":
            # cplay, cplayforce, etc.
            chat_id = await get_cmode(message.chat.id)
            if chat_id is None:
                return await message.reply_text(_["setting_7"])
            try:
                channel_info = await app.get_chat(chat_id)
                channel = channel_info.title
            except Exception:
                return await message.reply_text(_["cplay_4"])
        else:
            # normal group
            chat_id = message.chat.id
            channel = None

        # --------------------------------------------------
        # 4) Get play mode & check user permission if needed
        # --------------------------------------------------
        playmode = await get_playmode(chat_id)
        play_type = await get_playtype(chat_id)

        if play_type != "Everyone":
            # Non-everyone means admins or SUDO only
            if message.from_user.id not in SUDOERS:
                # fetch adminlist from cache
                admins = adminlist.get(chat_id)
                if not admins:
                    return await message.reply_text(_["admin_13"])
                if message.from_user.id not in admins:
                    return await message.reply_text(_["play_4"])

        # --------------------------------------------------
        # 5) Parse audio vs video, forced
        # --------------------------------------------------
        # vplay => video = True
        # otherwise if text has '-v', or if command is e.g. 'play', skip
        if message.command[0][0] == "v":
            video = True
        else:
            if "-v" in message.text:
                video = True
            else:
                # e.g. 'playforce', check second char
                video = True if message.command[0][1] == "v" else False

        # if command ends with 'e' => force
        if message.command[0][-1] == "e":
            # e.g. 'playforce', check active?
            if not await is_active_chat(chat_id):
                return await message.reply_text(_["play_16"])
            fplay = True
        else:
            fplay = False

        # --------------------------------------------------
        # 6) Ensure assistant is joined to chat
        # --------------------------------------------------
        if not await is_active_chat(chat_id):
            # Not streaming yet => let's join userbot if needed
            userbot = await get_assistant(chat_id)
            try:
                member = await app.get_chat_member(chat_id, userbot.id)
            except ChatAdminRequired:
                return await message.reply_text(_["call_1"])

            # If userbot is banned or restricted
            if member.status in (ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED):
                ban_btn = InlineKeyboardMarkup(
                    [[
                        InlineKeyboardButton(
                            text="๏ 𝗨ɴʙᴀɴ 𝗔ssɪsᴛᴀɴᴛ ๏",
                            callback_data="unban_assistant",
                        )
                    ]]
                )
                return await message.reply_text(
                    _["call_2"].format(
                        app.mention, userbot.id, userbot.name, userbot.username
                    ),
                    reply_markup=ban_btn,
                )

            # If userbot not participant => we must invite
            try:
                # check membership
                await app.get_chat_member(chat_id, userbot.id)
            except UserNotParticipant:
                invitelink = None
                # see if we have a cached link
                if chat_id in INVITE_LINK_CACHE:
                    invitelink = INVITE_LINK_CACHE[chat_id]
                else:
                    # if chat has username => skip export
                    if message.chat.username:
                        invitelink = f"https://t.me/{message.chat.username}"
                        try:
                            await userbot.resolve_peer(message.chat.username)
                        except:
                            pass
                    else:
                        # export link
                        try:
                            invitelink = await app.export_chat_invite_link(chat_id)
                        except ChatAdminRequired:
                            return await message.reply_text(_["call_1"])
                        except Exception as e:
                            return await message.reply_text(_["call_3"].format(app.mention, type(e).__name__))

                    # adjust link
                    if invitelink.startswith("https://t.me/+"):
                        invitelink = invitelink.replace("https://t.me/+", "https://t.me/joinchat/")
                    # store in cache
                    INVITE_LINK_CACHE[chat_id] = invitelink

                # try to join
                joining_msg = await message.reply_text(_["call_4"].format(app.mention))
                try:
                    await asyncio.sleep(1)
                    await userbot.join_chat(invitelink)
                except InviteHashExpired:
                    # remove from cache
                    if chat_id in INVITE_LINK_CACHE:
                        del INVITE_LINK_CACHE[chat_id]
                    # generate new link
                    try:
                        invitelink = await app.export_chat_invite_link(chat_id)
                    except ChatAdminRequired:
                        return await message.reply_text(_["call_1"])
                    except Exception as e:
                        return await message.reply_text(_["call_3"].format(app.mention, type(e).__name__))

                    if invitelink.startswith("https://t.me/+"):
                        invitelink = invitelink.replace("https://t.me/+", "https://t.me/joinchat/")
                    INVITE_LINK_CACHE[chat_id] = invitelink
                    await userbot.join_chat(invitelink)
                except InviteRequestSent:
                    try:
                        await app.approve_chat_join_request(chat_id, userbot.id)
                    except Exception as e:
                        return await message.reply_text(_["call_3"].format(app.mention, type(e).__name__))
                    await asyncio.sleep(3)
                    await joining_msg.edit(_["call_5"].format(app.mention))
                except UserAlreadyParticipant:
                    pass
                except Exception as e:
                    return await message.reply_text(_["call_3"].format(app.mention, type(e).__name__))

                # try to resolve peer
                try:
                    await userbot.resolve_peer(chat_id)
                except:
                    pass

        # --------------------------------------------------
        # 7) We pass all parameters to actual command logic
        # --------------------------------------------------
        return await play_command(
            client, message, _, chat_id, video, channel, playmode, url, fplay
        )

    return wrapper
