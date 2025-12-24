# Authored By Certified Coders © 2025
import asyncio

from Tune.misc import db
from Tune.utils.database import get_active_chats, is_music_playing


async def timer():
    while True:
        await asyncio.sleep(1)
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            try:
                if not await is_music_playing(chat_id):
                    continue
                playing = db.get(chat_id)
                if not playing:
                    continue
                duration = int(playing[0]["seconds"])
                if duration == 0:
                    continue
                if playing[0]["played"] >= duration:
                    continue
                playing[0]["played"] += 1
            except Exception:
                continue


asyncio.create_task(timer())
