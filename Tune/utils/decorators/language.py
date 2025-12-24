# Authored By Certified Coders © 2025
from Tune import app
from config import SUPPORT_CHAT
from pyrogram.types import CallbackQuery
from Tune.misc import SUDOERS
from Tune.utils.database import get_lang, is_maintenance
from strings import get_string


async def _get_language_strings(chat_id):
    try:
        language = await get_lang(chat_id)
        return get_string(language)
    except Exception:
        return get_string("en")


async def _check_maintenance_message(user_id):
    if not await is_maintenance():
        if user_id not in SUDOERS:
            return f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ <a href={SUPPORT_CHAT}>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ."
    return None


def language(mystic):
    async def wrapper(_, message, **kwargs):
        maintenance_msg = await _check_maintenance_message(message.from_user.id)
        if maintenance_msg:
            return await message.reply_text(
                text=maintenance_msg,
                disable_web_page_preview=True,
            )

        try:
            await message.delete()
        except Exception:
            pass

        language = await _get_language_strings(message.chat.id)
        return await mystic(_, message, language)

    return wrapper


def language_no_delete(mystic):
    async def wrapper(_, message, **kwargs):
        language = await _get_language_strings(message.chat.id)
        return await mystic(_, message, language)

    return wrapper


def languageCB(mystic):
    async def wrapper(_, CallbackQuery, **kwargs):
        maintenance_msg = await _check_maintenance_message(CallbackQuery.from_user.id)
        if maintenance_msg:
            return await CallbackQuery.answer(
                f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴄᴇ, ᴠɪsɪᴛ sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                show_alert=True,
            )

        language = await _get_language_strings(CallbackQuery.message.chat.id)
        return await mystic(_, CallbackQuery, language)

    return wrapper


def LanguageStart(mystic):
    async def wrapper(_, message, **kwargs):
        if isinstance(message, CallbackQuery):
            chat_id = message.message.chat.id
        else:
            chat_id = message.chat.id
        
        language = await _get_language_strings(chat_id)
        return await mystic(_, message, language)

    return wrapper
