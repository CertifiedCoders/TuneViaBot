# Authored By Certified Coders © 2025

import asyncio
import os

CPU = os.cpu_count() or 4
MAX_CONCURRENT = min(128, CPU * 16)
CHUNK_SIZE = 256 * 1024
YTDLP_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 300
JOIN_CALL_TIMEOUT = 30
YOUTUBE_META_TTL = 600
YOUTUBE_META_MAX = 4096
SEM = asyncio.Semaphore(MAX_CONCURRENT)
CHAT_SEMAPHORES = {}
CHAT_SEMAPHORE_LOCK = asyncio.Lock()

async def get_chat_semaphore(chat_id: int):
    async with CHAT_SEMAPHORE_LOCK:
        return CHAT_SEMAPHORES.setdefault(chat_id, asyncio.Semaphore(3))
