from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.core.call import JARVIS

welcome = 20
close = 30


@app.on_message(filters.video_chat_started, group=welcome)
@app.on_message(filters.video_chat_ended, group=close)
async def welcome(_, message: Message):
    await JARVIS.force_stop_stream(message.chat.id)
