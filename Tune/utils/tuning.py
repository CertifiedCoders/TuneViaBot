# Tune/utils/tuning.py
# Hardcoded tuning knobs (no environment variables).
# Adjust here if you want different limits. The defaults are safe and fast.

import os
import asyncio

CPU = os.cpu_count() or 4

# Max number of concurrent heavy tasks (yt-dlp runs, API fetches, etc.).
# Derived from CPU to scale reasonably on the host, but NOT read from env.
MAX_CONCURRENT = min(64, CPU * 8)

# I/O chunk size for HTTP streaming (API downloads).
CHUNK_SIZE = 64 * 1024  # 64 KiB

# Timeouts and cache controls
YTDLP_TIMEOUT = 45               # seconds for yt-dlp subprocess calls
YOUTUBE_META_TTL = 300           # seconds for metadata/format cache
YOUTUBE_META_MAX = 2048          # max cached entries before flush

# Global concurrency limiter for heavy tasks
SEM = asyncio.Semaphore(MAX_CONCURRENT)
