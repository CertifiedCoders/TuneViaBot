# Authored By Certified Coders © 2025
import asyncio
import contextlib
import glob
import os
import re
from typing import Dict, List, Optional, Tuple

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

from Tune.core.dir import CACHE_DIR, DOWNLOAD_DIR
from Tune.utils.cookie_handler import COOKIE_PATH as _COOKIES_FILE
from Tune.utils.tuning import CHUNK_SIZE, SEM, extract_youtube_id
from config import API_KEY, API_URL, VIDEO_API_URL
from Tune.logging import LOGGER

LOGGER = LOGGER(__name__)

USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()
SOUNDCLOUD_RE = re.compile(r"^https?://(?:www\.)?(soundcloud\.com|on\.soundcloud\.com)/.+", re.I)


def log_download_source(media_type: str, title: str, source: str) -> None:
    LOGGER.info(f"[{media_type}] Track '{title}' - Downloaded by {source}")


def _get_cookie_file() -> Optional[str]:
    try:
        if _COOKIES_FILE and os.path.exists(_COOKIES_FILE) and os.path.getsize(_COOKIES_FILE) > 0:
            return _COOKIES_FILE
    except Exception:
        pass
    return None


def _get_ytdlp_opts(is_soundcloud: bool = False) -> Dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "overwrites": False,
        "continuedl": True,
        "noprogress": True,
        "cachedir": str(CACHE_DIR),
        "ignoreerrors": True,
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
    }
    
    if is_soundcloud:
        opts.update({
            "socket_timeout": 30,
            "retries": 3,
            "extractor_args": {"soundcloud": {"client_id": None}}
        })
    else:
        opts.update({
            "concurrent_fragment_downloads": 32,
            "http_chunk_size": 2 << 20,
            "socket_timeout": 10,
            "retries": 2,
            "fragment_retries": 2,
            "merge_output_format": "mp4"
        })
    
    if cookiefile := _get_cookie_file():
        opts["cookiefile"] = cookiefile
    return opts


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    async with _session_lock:
        if _session and not _session.closed:
            return _session
        timeout = aiohttp.ClientTimeout(total=600, sock_connect=10, sock_read=30)
        connector = TCPConnector(
            limit=200,
            limit_per_host=50,
            ttl_dns_cache=600,
            enable_cleanup_closed=True,
            keepalive_timeout=60,
            force_close=False
        )
        _session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        return _session


async def _download_file(url: str, out_path: str) -> Optional[str]:
    if not url:
        return None
    try:
        session = await _get_session()
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if chunk:
                        await f.write(chunk)
        return out_path if os.path.exists(out_path) else None
    except Exception:
        return None


async def _api_download(link: str, media_type: str) -> Optional[str]:
    if media_type == "audio" and not USE_AUDIO_API:
        return None
    if media_type == "video" and not USE_VIDEO_API:
        return None
    
    vid = extract_youtube_id(link)
    if not vid:
        return None
    
    base_url = API_URL if media_type == "audio" else VIDEO_API_URL
    endpoint = "song" if media_type == "audio" else "video"
    poll_url = f"{base_url}/{endpoint}/{vid}?api={API_KEY}"
    default_format = "webm" if media_type == "audio" else "mp4"
    
    try:
        session = await _get_session()
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
                if not dl_url:
                    return None
                fmt = data.get("format", default_format)
                out_path = f"{DOWNLOAD_DIR}/{vid}.{fmt}"
                return await _download_file(dl_url, out_path)
    except Exception:
        return None


def _get_downloaded_path(info: Dict) -> Optional[str]:
    vid = info.get("id")
    if not vid:
        return None
    ext = info.get("ext")
    if ext:
        p = f"{DOWNLOAD_DIR}/{vid}.{ext}"
        if os.path.exists(p):
            return p
    matches = sorted(glob.glob(f"{DOWNLOAD_DIR}/{vid}.*"), key=os.path.getmtime, reverse=True)
    return matches[0] if matches else None


def _download_with_ytdlp(link: str, fmt: str, is_soundcloud: bool = False) -> Optional[str]:
    try:
        opts = _get_ytdlp_opts(is_soundcloud=is_soundcloud)
        opts["format"] = fmt
        
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            if path := _get_downloaded_path(info):
                return path
            ydl.download([link])
            return _get_downloaded_path(info)
    except Exception as e:
        LOGGER.error(f"yt-dlp download failed for {link}: {e}")
        return None


async def _deduplicate_download(key: str, runner):
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


async def _race_downloads(yt_task, api_task, title: str, media_type: str):
    done, pending = await asyncio.wait({yt_task, api_task}, return_when=asyncio.FIRST_COMPLETED)
    
    for task in done:
        try:
            result = task.result()
            if result and os.path.exists(result):
                source = "yt-dlp" if task is yt_task else "API"
                log_download_source(media_type, title, source)
                for p in pending:
                    p.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await p
                return result
        except Exception:
            pass
    
    for task in pending:
        try:
            result = await task
            if result and os.path.exists(result):
                source = "yt-dlp" if task is yt_task else "API"
                log_download_source(media_type, title, source)
                return result
        except (asyncio.CancelledError, Exception):
            pass
    return None


async def _download_media(link: str, fmt: str, media_type: str, title: str, is_soundcloud: bool):
    loop = asyncio.get_running_loop()
    key = f"{media_type}:{link}"
    
    async def run():
        async def ytdlp_wrapper():
            async with SEM:
                return await loop.run_in_executor(None, _download_with_ytdlp, link, fmt, is_soundcloud)
        
        ytdlp_task = asyncio.create_task(ytdlp_wrapper())
        use_api = (USE_AUDIO_API if media_type == "audio" else USE_VIDEO_API) and not is_soundcloud
        api_task = asyncio.create_task(_api_download(link, media_type)) if use_api else None
        
        if api_task:
            return await _race_downloads(ytdlp_task, api_task, title or "Unknown", media_type.capitalize())
        
        result = await ytdlp_task
        if result and title:
            log_download_source(media_type.capitalize(), title, "yt-dlp")
        return result
    
    return await _deduplicate_download(key, run)


async def yt_dlp_download(link: str, type: str, title: str = "") -> Optional[str]:
    is_soundcloud = bool(SOUNDCLOUD_RE.match(link))
    
    if type == "audio":
        fmt = "bestaudio/best" if is_soundcloud else "bestaudio[ext=webm][acodec=opus]/bestaudio[ext=m4a][acodec=aac]/bestaudio/best"
        return await _download_media(link, fmt, "audio", title, is_soundcloud)
    elif type == "video":
        fmt = "(bestvideo[height<=?720][width<=?1280][ext=mp4][fps<=?30])+(bestaudio[acodec=opus]/bestaudio[acodec=aac]/bestaudio)"
        return await _download_media(link, fmt, "video", title, is_soundcloud)
    
    return None


async def yt_dlp_get_stream_url(link: str) -> Tuple[int, str]:
    try:
        opts = _get_ytdlp_opts(is_soundcloud=False)
        opts["format"] = "best[height<=?720][width<=?1280]"
        
        loop = asyncio.get_running_loop()
        
        def get_url():
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                if url := info.get("url"):
                    return (1, url)
                for fmt in info.get("formats", []):
                    if url := fmt.get("url"):
                        return (1, url)
                return (0, "")
        
        async with SEM:
            result = await loop.run_in_executor(None, get_url)
        return result if result else (0, "")
    except Exception as e:
        LOGGER.error(f"yt-dlp stream URL failed for {link}: {e}")
        return (0, "")


async def yt_dlp_get_playlist_ids(playlist_url: str, limit: int) -> List[str]:
    try:
        opts = _get_ytdlp_opts(is_soundcloud=False)
        opts["extract_flat"] = True
        opts["playlistend"] = limit
        
        loop = asyncio.get_running_loop()
        
        def get_ids():
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                entries = info.get("entries", [])
                return [entry.get("id", "") for entry in entries if entry.get("id")]
        
        async with SEM:
            ids = await loop.run_in_executor(None, get_ids)
        return ids if ids else []
    except Exception as e:
        LOGGER.error(f"yt-dlp playlist IDs failed for {playlist_url}: {e}")
        return []
