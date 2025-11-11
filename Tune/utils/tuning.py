import os
import asyncio

CPU = os.cpu_count() or 4
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", str(min(128, CPU * 16))))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1048576"))  # 1MB
YTDLP_TIMEOUT = int(os.getenv("YTDLP_TIMEOUT", "30"))
YOUTUBE_META_TTL = int(os.getenv("YOUTUBE_META_TTL", "180"))
YOUTUBE_META_MAX = int(os.getenv("YOUTUBE_META_MAX", "1024"))

SEM = asyncio.Semaphore(MAX_CONCURRENT)