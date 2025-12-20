# Authored By Certified Coders © 2025
import os
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
from Tune.utils.decorators.language import language_no_delete
from Tune.utils.extraction import extract_user
from Tune.plugins.security.antispam_handler import get_spam_blocked_cache, clear_user_notification, get_debug_file_path
from Tune.utils.antispam import reset_user_tracking


@app.on_message(filters.command(["antispam"]) & SUDOERS)
@language_no_delete
async def antispam_command(client, message: Message, _):
    if len(message.command) < 2:
        status = await is_antispam_enabled()
        status_text = _["antispam_17"] if status else _["antispam_18"]
        blocked_count = len(await get_spam_blocked_users())
        response = _["antispam_3"].format(status_text.title(), blocked_count)
        return await message.reply_text(response)
    
    action = message.command[1].lower()
    
    if action == "enable":
        if await is_antispam_enabled():
            return await message.reply_text(_["antispam_4"])
        await antispam_on()
        return await message.reply_text(_["antispam_5"])
    
    elif action == "disable":
        if not await is_antispam_enabled():
            return await message.reply_text(_["antispam_6"])
        await antispam_off()
        return await message.reply_text(_["antispam_7"])
    
    elif action == "unblock":
        if len(message.command) < 3 and not message.reply_to_message:
            return await message.reply_text(_["antispam_8"])
        
        user_id = None
        user_mention = None
        
        if message.reply_to_message and message.reply_to_message.from_user:
            user_id = int(message.reply_to_message.from_user.id)
            try:
                user = await app.get_users(user_id)
                user_mention = user.mention or user.first_name or _["antispam_22"].format(user_id)
            except:
                user_mention = _["antispam_22"].format(user_id)
        elif len(message.command) >= 3:
            cmd_arg = message.command[2].strip()
            if cmd_arg.lstrip('-').isdigit():
                user_id = int(cmd_arg)
                try:
                    user = await app.get_users(user_id)
                    user_mention = user.mention or user.first_name or _["antispam_22"].format(user_id)
                except:
                    user_mention = _["antispam_22"].format(user_id)
            else:
                try:
                    user = await extract_user(message)
                    user_id = int(user.id)
                    user_mention = user.mention or user.first_name or _["antispam_22"].format(user_id)
                except Exception as e:
                    return await message.reply_text(_["antispam_9"].format(str(e)))
        else:
            try:
                user = await extract_user(message)
                user_id = int(user.id)
                user_mention = user.mention or user.first_name or _["antispam_22"].format(user_id)
            except Exception as e:
                return await message.reply_text(_["antispam_9"].format(str(e)))
        
        if user_id is None:
            return await message.reply_text(_["antispam_10"])
        
        cache = get_spam_blocked_cache()
        is_in_cache = user_id in cache
        is_in_db = await is_spam_blocked(user_id)
        
        if not is_in_cache and not is_in_db:
            return await message.reply_text(_["antispam_11"].format(user_mention, user_id))
        
        await remove_spam_blocked_user(user_id)
        cache.discard(user_id)
        reset_user_tracking(user_id)
        clear_user_notification(user_id)
        
        return await message.reply_text(_["antispam_12"].format(user_mention, user_id))
    
    elif action == "list":
        blocked_users = await get_spam_blocked_users()
        if not blocked_users:
            return await message.reply_text(_["antispam_13"])
        
        response = _["antispam_14"].format(len(blocked_users))
        for idx, user_id in enumerate(blocked_users[:50], 1):
            try:
                user_info = await app.get_users(user_id)
                response += f"{idx}. {user_info.mention} (<code>{user_id}</code>)\n"
            except Exception:
                response += f"{idx}. <code>{user_id}</code>\n"
        
        if len(blocked_users) > 50:
            response += _["antispam_15"].format(len(blocked_users) - 50)
        
        return await message.reply_text(response)
    
    elif action == "debug":
        debug_file_path = get_debug_file_path()
        try:
            if not os.path.exists(debug_file_path):
                return await message.reply_text(_["antispam_23"])
            
            file_size = os.path.getsize(debug_file_path)
            if file_size == 0:
                return await message.reply_text(_["antispam_24"])
            
            await message.reply_document(
                document=debug_file_path,
                caption=_["antispam_25"]
            )
        except Exception as e:
            return await message.reply_text(_["antispam_26"].format(str(e)))
    
    else:
        return await message.reply_text(_["antispam_16"])
