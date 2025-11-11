import os
import asyncio

CPU = os.cpu_count() or 4

MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", str(min(128, CPU * 16))))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", str(256 * 1024)))

YTDLP_TIMEOUT = int(os.getenv("YTDLP_TIMEOUT", "60"))
YOUTUBE_META_TTL = int(os.getenv("YOUTUBE_META_TTL", "300"))
YOUTUBE_META_MAX = int(os.getenv("YOUTUBE_META_MAX", "2048"))

EXTRACTOR_ARGS_CLI = os.getenv("EXTRACTOR_ARGS_CLI", "youtube:player_client=ios,android")
EXTRACTOR_ARGS_PY = {
    "youtube": {
        "player_client": ["ios", "android"]
    }
}

SEM = asyncio.Semaphore(MAX_CONCURRENT)