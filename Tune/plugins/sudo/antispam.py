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
        status_text = "enabled" if status else "disabled"
        blocked_count = len(await get_spam_blocked_users())
        response = (
            f"🛡️ <b>Anti-Spam System</b>\n\n"
            f"📊 <b>Status:</b> {status_text.title()}\n"
            f"🚫 <b>Blocked Users:</b> {blocked_count}\n\n"
            f"<b>Usage:</b>\n"
            f"• <code>/antispam enable</code> - Enable anti-spam\n"
            f"• <code>/antispam disable</code> - Disable anti-spam\n"
            f"• <code>/antispam unblock [user]</code> - Unblock a user\n"
            f"• <code>/antispam list</code> - List blocked users"
        )
        return await message.reply_text(response)
    
    action = message.command[1].lower()
    
    if action == "enable":
        if await is_antispam_enabled():
            return await message.reply_text("✅ Anti-spam is already enabled.")
        await antispam_on()
        return await message.reply_text("✅ Anti-spam system enabled.")
    
    elif action == "disable":
        if not await is_antispam_enabled():
            return await message.reply_text("❌ Anti-spam is already disabled.")
        await antispam_off()
        return await message.reply_text("❌ Anti-spam system disabled.")
    
    elif action == "unblock":
        if len(message.command) < 3 and not message.reply_to_message:
            return await message.reply_text("Please reply to a user or provide a user ID/username.")
        
        user_id = None
        user_mention = None
        
        # Handle reply to message
        if message.reply_to_message and message.reply_to_message.from_user:
            user_id = int(message.reply_to_message.from_user.id)
            try:
                user = await app.get_users(user_id)
                user_mention = user.mention or user.first_name or f"User {user_id}"
            except:
                user_mention = f"User {user_id}"
        # Handle numeric user ID (direct ID)
        elif len(message.command) >= 3:
            cmd_arg = message.command[2].strip()
            # Check if it's a numeric ID (including negative numbers)
            if cmd_arg.lstrip('-').isdigit():
                user_id = int(cmd_arg)
                try:
                    user = await app.get_users(user_id)
                    user_mention = user.mention or user.first_name or f"User {user_id}"
                except:
                    user_mention = f"User {user_id}"
            else:
                # Handle username or mention (use extract_user)
                try:
                    user = await extract_user(message)
                    user_id = int(user.id)
                    user_mention = user.mention or user.first_name or f"User {user_id}"
                except Exception as e:
                    return await message.reply_text(f"❌ Failed to extract user: {str(e)}")
        # Handle username or mention when no command args (shouldn't happen, but safety check)
        else:
            try:
                user = await extract_user(message)
                user_id = int(user.id)
                user_mention = user.mention or user.first_name or f"User {user_id}"
            except Exception as e:
                return await message.reply_text(f"❌ Failed to extract user: {str(e)}")
        
        if user_id is None:
            return await message.reply_text("❌ Could not determine user ID. Please provide a valid user ID, username, or reply to a message.")
        
        # Check both cache and database
        cache = get_spam_blocked_cache()
        is_in_cache = user_id in cache
        is_in_db = await is_spam_blocked(user_id)
        
        if not is_in_cache and not is_in_db:
            return await message.reply_text(f"❌ User {user_mention} ({user_id}) is not blocked.")
        
        # Remove from database
        await remove_spam_blocked_user(user_id)
        
        # Remove from cache
        cache.discard(user_id)
        reset_user_tracking(user_id)
        clear_user_notification(user_id)
        
        return await message.reply_text(f"✅ Unblocked {user_mention} ({user_id}) from anti-spam system.")
    
    elif action == "list":
        blocked_users = await get_spam_blocked_users()
        if not blocked_users:
            return await message.reply_text("📭 No users are currently blocked.")
        
        response = f"🚫 <b>Blocked Users ({len(blocked_users)}):</b>\n\n"
        for idx, user_id in enumerate(blocked_users[:50], 1):
            try:
                user_info = await app.get_users(user_id)
                response += f"{idx}. {user_info.mention} (<code>{user_id}</code>)\n"
            except Exception:
                response += f"{idx}. <code>{user_id}</code>\n"
        
        if len(blocked_users) > 50:
            response += f"\n... and {len(blocked_users) - 50} more."
        
        return await message.reply_text(response)
    
    else:
        return await message.reply_text("❌ Invalid action. Use: enable, disable, unblock, or list")
