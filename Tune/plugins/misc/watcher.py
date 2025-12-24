# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.core.call import StreamController

GROUP_STARTED = 20
GROUP_ENDED = 30


@app.on_message(filters.video_chat_started, group=GROUP_STARTED)
@app.on_message(filters.video_chat_ended, group=GROUP_ENDED)
async def handle_video_chat_event(_, message: Message):
    await StreamController.force_stop_stream(message.chat.id)
