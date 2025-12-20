# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.misc import SUDOERS
from Tune.utils.database import (
    antispam_off,
    antispam_on,
    get_spam_blocked_users,
    is_antispam_enabled,
    is_spam_blocked,
    remove_spam_blocked_user,
)
from Tune.utils.decorators.language import language
from Tune.utils.extraction import extract_user
from Tune.plugins.security.antispam_handler import get_spam_blocked_cache, clear_user_notification
from Tune.utils.antispam import reset_user_tracking


@app.on_message(filters.command(["antispam"]) & SUDOERS)
@language
async def antispam_command(client, message: Message, _):
    if len(message.command) < 2:
        status = await is_antispam_enabled()
        status_text = "ᴇɴᴀʙʟᴇᴅ" if status else "ᴅɪsᴀʙʟᴇᴅ"
        blocked_count = len(await get_spam_blocked_users())
        response = (
            f"🛡️ <b>ᴀɴᴛɪ-sᴘᴀᴍ sʏsᴛᴇᴍ</b>\n\n"
            f"📊 <b>sᴛᴀᴛᴜs:</b> {status_text.title()}\n"
            f"🚫 <b>ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs:</b> {blocked_count}\n\n"
            f"<b>ᴜsᴀɢᴇ:</b>\n"
            f"• <code>/antispam enable</code> - ᴇɴᴀʙʟᴇ ᴀɴᴛɪ-sᴘᴀᴍ\n"
            f"• <code>/antispam disable</code> - ᴅɪsᴀʙʟᴇ ᴀɴᴛɪ-sᴘᴀᴍ\n"
            f"• <code>/antispam unblock [user]</code> - ᴜɴʙʟᴏᴄᴋ ᴀ ᴜsᴇʀ\n"
            f"• <code>/antispam list</code> - ʟɪsᴛ ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs"
        )
        return await message.reply_text(response)
    
    action = message.command[1].lower()
    
    if action == "enable":
        if await is_antispam_enabled():
            return await message.reply_text("✅ ᴀɴᴛɪ-sᴘᴀᴍ ɪs ᴀʟʀᴇᴀᴅʏ ᴇɴᴀʙʟᴇᴅ.")
        await antispam_on()
        return await message.reply_text("✅ ᴀɴᴛɪ-sᴘᴀᴍ sʏsᴛᴇᴍ ᴇɴᴀʙʟᴇᴅ.")
    
    elif action == "disable":
        if not await is_antispam_enabled():
            return await message.reply_text("❌ ᴀɴᴛɪ-sᴘᴀᴍ ɪs ᴀʟʀᴇᴀᴅʏ ᴅɪsᴀʙʟᴇᴅ.")
        await antispam_off()
        return await message.reply_text("❌ ᴀɴᴛɪ-sᴘᴀᴍ sʏsᴛᴇᴍ ᴅɪsᴀʙʟᴇᴅ.")
    
    elif action == "unblock":
        if len(message.command) < 3 and not message.reply_to_message:
            return await message.reply_text("ᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴜsᴇʀ ɪᴅ/ᴜsᴇʀɴᴀᴍᴇ.")
        
        user_id = None
        user_mention = None
        
        if message.reply_to_message and message.reply_to_message.from_user:
            user_id = int(message.reply_to_message.from_user.id)
            try:
                user = await app.get_users(user_id)
                user_mention = user.mention or user.first_name or f"ᴜsᴇʀ {user_id}"
            except:
                user_mention = f"ᴜsᴇʀ {user_id}"
        elif len(message.command) >= 3:
            cmd_arg = message.command[2].strip()
            if cmd_arg.lstrip('-').isdigit():
                user_id = int(cmd_arg)
                try:
                    user = await app.get_users(user_id)
                    user_mention = user.mention or user.first_name or f"ᴜsᴇʀ {user_id}"
                except:
                    user_mention = f"ᴜsᴇʀ {user_id}"
            else:
                try:
                    user = await extract_user(message)
                    user_id = int(user.id)
                    user_mention = user.mention or user.first_name or f"ᴜsᴇʀ {user_id}"
                except Exception as e:
                    return await message.reply_text(f"❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴇxᴛʀᴀᴄᴛ ᴜsᴇʀ: {str(e)}")
        else:
            try:
                user = await extract_user(message)
                user_id = int(user.id)
                user_mention = user.mention or user.first_name or f"ᴜsᴇʀ {user_id}"
            except Exception as e:
                return await message.reply_text(f"❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴇxᴛʀᴀᴄᴛ ᴜsᴇʀ: {str(e)}")
        
        if user_id is None:
            return await message.reply_text("❌ ᴄᴏᴜʟᴅ ɴᴏᴛ ᴅᴇᴛᴇʀᴍɪɴᴇ ᴜsᴇʀ ɪᴅ. ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ, ᴜsᴇʀɴᴀᴍᴇ, ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ.")
        
        cache = get_spam_blocked_cache()
        is_in_cache = user_id in cache
        is_in_db = await is_spam_blocked(user_id)
        
        if not is_in_cache and not is_in_db:
            return await message.reply_text(f"❌ ᴜsᴇʀ {user_mention} ({user_id}) ɪs ɴᴏᴛ ʙʟᴏᴄᴋᴇᴅ.")
        
        await remove_spam_blocked_user(user_id)
        cache.discard(user_id)
        reset_user_tracking(user_id)
        clear_user_notification(user_id)
        
        return await message.reply_text(f"✅ ᴜɴʙʟᴏᴄᴋᴇᴅ {user_mention} ({user_id}) ғʀᴏᴍ ᴀɴᴛɪ-sᴘᴀᴍ sʏsᴛᴇᴍ.")
    
    elif action == "list":
        blocked_users = await get_spam_blocked_users()
        if not blocked_users:
            return await message.reply_text("📭 ɴᴏ ᴜsᴇʀs ᴀʀᴇ ᴄᴜʀʀᴇɴᴛʟʏ ʙʟᴏᴄᴋᴇᴅ.")
        
        response = f"🚫 <b>ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs ({len(blocked_users)}):</b>\n\n"
        for idx, user_id in enumerate(blocked_users[:50], 1):
            try:
                user_info = await app.get_users(user_id)
                response += f"{idx}. {user_info.mention} (<code>{user_id}</code>)\n"
            except Exception:
                response += f"{idx}. <code>{user_id}</code>\n"
        
        if len(blocked_users) > 50:
            response += f"\n... ᴀɴᴅ {len(blocked_users) - 50} ᴍᴏʀᴇ."
        
        return await message.reply_text(response)
    
    else:
        return await message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ᴀᴄᴛɪᴏɴ. ᴜsᴇ: ᴇɴᴀʙʟᴇ, ᴅɪsᴀʙʟᴇ, ᴜɴʙʟᴏᴄᴋ, ᴏʀ ʟɪsᴛ")
