import os
import asyncio
from Tune.utils.cookie_handler import COOKIE_PATH

CPU = os.cpu_count() or 4

MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", str(min(128, CPU * 16))))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", str(256 * 1024)))

YTDLP_TIMEOUT = int(os.getenv("YTDLP_TIMEOUT", "60"))
YOUTUBE_META_TTL = int(os.getenv("YOUTUBE_META_TTL", "300"))
YOUTUBE_META_MAX = int(os.getenv("YOUTUBE_META_MAX", "2048"))

HAS_COOKIE_FILE = bool(str(COOKIE_PATH) and os.path.exists(str(COOKIE_PATH)) and os.path.getsize(str(COOKIE_PATH)) > 0)

EXTRACTOR_ARGS_CLI = (
    "youtube:player_client=web"
    if HAS_COOKIE_FILE
    else "youtube:player_client=tvhtml5"
)
EXTRACTOR_ARGS_PY = {
    "youtube": {
        "player_client": ["web"] if HAS_COOKIE_FILE else ["tvhtml5"]
    }
}

SEM = asyncio.Semaphore(MAX_CONCURRENT)
