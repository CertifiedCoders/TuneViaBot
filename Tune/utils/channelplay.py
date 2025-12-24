# Authored By Certified Coders © 2025
from Tune import app
from Tune.utils.database import get_cmode


async def get_channeplayCB(_, command, CallbackQuery):
    if command == "c":
        chat_id = await get_cmode(CallbackQuery.message.chat.id)
        if chat_id is None:
            try:
                await CallbackQuery.answer(_["setting_7"], show_alert=True)
            except Exception:
                pass
            return None
        
        try:
            channel = (await app.get_chat(chat_id)).title
        except Exception as e:
            try:
                await CallbackQuery.answer(_["cplay_4"].format(e), show_alert=True)
            except Exception:
                pass
            return None
    else:
        chat_id = CallbackQuery.message.chat.id
        channel = None
    
    return chat_id, channel
