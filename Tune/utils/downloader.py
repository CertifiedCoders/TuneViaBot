# Authored By Certified Coders © 2025

import asyncio
import contextlib
import glob
import os
import re
from typing import Dict, Optional

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

from Tune.core.dir import CACHE_DIR, DOWNLOAD_DIR
from Tune.utils.cookie_handler import COOKIE_PATH as _COOKIES_FILE
from Tune.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL, VIDEO_API_URL
from Tune.logging import LOGGER

LOGGER = LOGGER(__name__)

USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
SOUNDCLOUD_RE = re.compile(r"^https?://(?:www\.)?(soundcloud\.com|on\.soundcloud\.com)/.+", re.I)


def log_download_source(media_type: str, title: str, source: str) -> None:
    """
    Log which backend provided the downloaded media, with its type.
    media_type: "Audio" or "Video"
    source: e.g. "yt-dlp" or "API"
    """
    LOGGER.info(f"[{media_type}] Track '{title}' - Downloaded by {source}")


def extract_video_id(link: str) -> str:
    if not link:
        return ""
    s = link.strip()
    if YOUTUBE_ID_RE.match(s):
        return s
    if "v=" in s:
        return s.split("v=")[-1].split("&")[0]
    last = s.split("/")[-1].split("?")[0]
    if YOUTUBE_ID_RE.match(last):
        return last
    return ""


def get_cookie_file() -> Optional[str]:
    try:
        if _COOKIES_FILE and os.path.exists(_COOKIES_FILE) and os.path.getsize(_COOKIES_FILE) > 0:
            return _COOKIES_FILE
    except Exception:
        pass
    return None


def find_cached_file(video_id: str) -> Optional[str]:
    if not video_id:
        return None
    for ext in ("mp3", "m4a", "webm", "mp4", "mkv"):
        path = f"{DOWNLOAD_DIR}/{video_id}.{ext}"
        if os.path.exists(path):
            return path
    return None


def get_ytdlp_base_opts(is_soundcloud: bool = False) -> Dict[str, object]:
    """
    Get base yt-dlp options.
    
    Args:
        is_soundcloud: If True, optimize options for SoundCloud downloads
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "overwrites": False,
        "continuedl": True,
        "noprogress": True,
        "cachedir": str(CACHE_DIR),
        "ignoreerrors": True,
    }
    
    if is_soundcloud:
        # SoundCloud-specific optimizations
        # Use URL hash as output filename for consistent caching
        opts["outtmpl"] = f"{DOWNLOAD_DIR}/%(id)s.%(ext)s"
        # SoundCloud doesn't use fragments, so skip concurrent fragment settings
        opts["socket_timeout"] = 30  # Slightly longer timeout for SoundCloud
        opts["retries"] = 3  # More retries for SoundCloud (can be flaky)
        opts["extractor_args"] = {"soundcloud": {"client_id": None}}  # Use default client
    else:
        opts["outtmpl"] = f"{DOWNLOAD_DIR}/%(id)s.%(ext)s"
        opts["concurrent_fragment_downloads"] = 16
        opts["http_chunk_size"] = 1 << 20
        opts["socket_timeout"] = 15
        opts["retries"] = 1
        opts["fragment_retries"] = 1
        opts["merge_output_format"] = "mp4"
    
    if cookiefile := get_cookie_file():
        opts["cookiefile"] = cookiefile
    return opts


async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    async with _session_lock:
        if _session and not _session.closed:
            return _session
        timeout = aiohttp.ClientTimeout(total=600, sock_connect=20, sock_read=60)
        connector = TCPConnector(limit=0, ttl_dns_cache=300, enable_cleanup_closed=True)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session


async def close_http_session() -> None:
    global _session
    async with _session_lock:
        if _session and not _session.closed:
            await _session.close()
        _session = None


async def download_file(url: str, out_path: str) -> Optional[str]:
    if not url:
        return None
    try:
        session = await get_http_session()
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if not chunk:
                        break
                    await f.write(chunk)
        return out_path if os.path.exists(out_path) else None
    except Exception:
        return None


async def api_download_audio(link: str) -> Optional[str]:
    if not USE_AUDIO_API:
        return None
    vid = extract_video_id(link)
    if not vid:
        return None
    poll_url = f"{API_URL}/song/{vid}?api={API_KEY}"
    try:
        session = await get_http_session()
        while True:
            async with session.get(poll_url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                status = str(data.get("status", "")).lower()
                if status == "downloading":
                    await asyncio.sleep(1.0)
                    continue
                if status != "done":
                    return None
                dl_url = data.get("link")
                fmt = data.get("format", "webm")
                out_path = f"{DOWNLOAD_DIR}/{vid}.{fmt}"
                return await download_file(dl_url, out_path)
    except Exception:
        return None


async def api_download_video(link: str) -> Optional[str]:
    if not USE_VIDEO_API:
        return None
    vid = extract_video_id(link)
    if not vid:
        return None
    poll_url = f"{VIDEO_API_URL}/video/{vid}?api={API_KEY}"
    try:
        session = await get_http_session()
        while True:
            async with session.get(poll_url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                status = str(data.get("status", "")).lower()
                if status == "downloading":
                    await asyncio.sleep(1.0)
                    continue
                if status != "done":
                    return None
                dl_url = data.get("link")
                fmt = data.get("format", "mp4")
                out_path = f"{DOWNLOAD_DIR}/{vid}.{fmt}"
                return await download_file(dl_url, out_path)
    except Exception:
        return None


def get_final_path_from_info(info: Dict) -> Optional[str]:
    vid = info.get("id")
    if not vid:
        return None
    ext = info.get("ext")
    if ext:
        p = f"{DOWNLOAD_DIR}/{vid}.{ext}"
        if os.path.exists(p):
            return p
    matches = sorted(
        glob.glob(f"{DOWNLOAD_DIR}/{vid}.*"),
        key=os.path.getmtime,
        reverse=True,
    )
    return matches[0] if matches else None


def download_with_ytdlp_sync(link: str, fmt: str, is_soundcloud: bool = False, cache_id: Optional[str] = None) -> Optional[str]:
    """
    Synchronous yt-dlp download.
    
    Args:
        link: URL to download
        fmt: Format selector
        is_soundcloud: Whether this is a SoundCloud URL
        cache_id: Optional cache ID for SoundCloud (MD5 hash of URL) - used for pre-check only
    """
    try:
        opts = get_ytdlp_base_opts(is_soundcloud=is_soundcloud)
        opts["format"] = fmt
        
        with YoutubeDL(opts) as ydl:
            # Extract info first to check if file already exists
            info = ydl.extract_info(link, download=False)
            
            # Check if file already exists using yt-dlp's extracted ID
            if path := get_final_path_from_info(info):
                return path
            
            # Download the file
            ydl.download([link])
            
            # Return the path to the downloaded file
            return get_final_path_from_info(info)
    except Exception as e:
        # Log the actual error for debugging, but don't raise
        LOGGER.error(f"yt-dlp download failed for {link}: {e}")
        return None


async def run_with_semaphore(coro):
    async with SEM:
        return await coro


async def deduplicate_download(key: str, runner):
    async with _inflight_lock:
        if fut := _inflight.get(key):
            return await fut
        fut = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
    try:
        result = await runner()
        fut.set_result(result)
        return result
    except Exception as e:
        fut.set_exception(e)
        return None
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)


async def race_ytdlp_and_api(yt_task, api_task, title: str, media_type: str):
    done, pending = await asyncio.wait(
        {yt_task, api_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for task in done:
        result = task.result()
        if result and os.path.exists(result):
            source = "yt-dlp" if task is yt_task else "API"
            log_download_source(media_type, title, source)
            for p in pending:
                p.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await p
            return result
    for task in pending:
        try:
            result = await task
            if result and os.path.exists(result):
                source = "yt-dlp" if task is yt_task else "API"
                log_download_source(media_type, title, source)
                return result
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    return None


async def yt_dlp_download(link: str, type: str, title: str = "") -> Optional[str]:
    loop = asyncio.get_running_loop()
    is_soundcloud = bool(SOUNDCLOUD_RE.match(link))
    
    # Cache check is handled inside download_with_ytdlp_sync via get_final_path_from_info
    # which uses yt-dlp's extracted ID (works for both YouTube and SoundCloud)

    if type == "audio":
        key = f"audio:{link}"
        
        # Use flexible format for SoundCloud (they may not have webm/opus),
        # but prefer webm/opus for YouTube for better quality
        audio_format = "bestaudio/best" if is_soundcloud else "bestaudio[ext=webm][acodec=opus]/bestaudio/best"

        async def run():
            ytdlp_task = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(None, download_with_ytdlp_sync, link, audio_format, is_soundcloud, None)
                )
            )
            # Skip API for SoundCloud (API only supports YouTube)
            api_task = asyncio.create_task(api_download_audio(link)) if (USE_AUDIO_API and not is_soundcloud) else None
            if api_task:
                return await race_ytdlp_and_api(
                    ytdlp_task,
                    api_task,
                    title or "Unknown",
                    "Audio",
                )
            result = await ytdlp_task
            if result and title:
                log_download_source("Audio", title, "yt-dlp")
            return result

        return await deduplicate_download(key, run)

    elif type == "video":
        key = f"video:{link}"

        async def run():
            ytdlp_task = asyncio.create_task(
                run_with_semaphore(
                    loop.run_in_executor(None, download_with_ytdlp_sync, link, "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio)")
                )
            )
            api_task = asyncio.create_task(api_download_video(link)) if USE_VIDEO_API else None
            if api_task:
                return await race_ytdlp_and_api(
                    ytdlp_task,
                    api_task,
                    title or "Unknown",
                    "Video",
                )
            result = await ytdlp_task
            if result and title:
                log_download_source("Video", title, "yt-dlp")
            return result

        return await deduplicate_download(key, run)

    return None
