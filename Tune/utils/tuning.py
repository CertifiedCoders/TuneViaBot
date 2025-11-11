import os
import asyncio

CPU = os.cpu_count() or 4

MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", str(min(64, CPU * 8))))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", str(64 * 1024)))

YTDLP_TIMEOUT = int(os.getenv("YTDLP_TIMEOUT", "45"))
YOUTUBE_META_TTL = int(os.getenv("YOUTUBE_META_TTL", "300"))
YOUTUBE_META_MAX = int(os.getenv("YOUTUBE_META_MAX", "2048"))

SEM = asyncio.Semaphore(MAX_CONCURRENT)
