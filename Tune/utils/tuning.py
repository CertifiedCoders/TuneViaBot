# Authored By Certified Coders © 2025

import asyncio
import os

CPU = os.cpu_count() or 4
MAX_CONCURRENT = min(128, CPU * 16)
CHUNK_SIZE = 256 * 1024
YTDLP_TIMEOUT = 30
YOUTUBE_META_TTL = 600
YOUTUBE_META_MAX = 4096
SEM = asyncio.Semaphore(MAX_CONCURRENT)
CHAT_SEMAPHORES = {}
CHAT_SEMAPHORE_LOCK = asyncio.Lock()

AUDIO_SAMPLE_RATE = 48000
AUDIO_BITRATE = "128k"
AUDIO_CHANNELS = 2

FFMPEG_AUDIO_FILTERS = (
    "loudnorm=I=-16:TP=-1.5:LRA=11,"
    "highpass=f=80,"
    "lowpass=f=15000,"
    "acompressor=threshold=0.89:ratio=9:attack=200:release=1000"
)

async def get_chat_semaphore(chat_id: int):
    async with CHAT_SEMAPHORE_LOCK:
        if chat_id not in CHAT_SEMAPHORES:
            CHAT_SEMAPHORES[chat_id] = asyncio.Semaphore(3)
        return CHAT_SEMAPHORES[chat_id]
