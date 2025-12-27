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
from Tune.utils.tuning import CHUNK_SIZE, SEM, YTDLP_TIMEOUT, extract_youtube_id
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




def get_cookie_file() -> Optional[str]:
    try:
        if _COOKIES_FILE and os.path.exists(_COOKIES_FILE) and os.path.getsize(_COOKIES_FILE) > 0:
            return _COOKIES_FILE
    except Exception:
        pass
    return None


def get_ytdlp_base_opts(is_soundcloud: bool = False) -> Dict[str, object]:
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
        opts["socket_timeout"] = 30
        opts["retries"] = 3
        opts["extractor_args"] = {"soundcloud": {"client_id": None}}
    else:
        opts["concurrent_fragment_downloads"] = 32
        opts["http_chunk_size"] = 2 << 20
        opts["socket_timeout"] = 10
        opts["retries"] = 2
        opts["fragment_retries"] = 2
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


async def _api_poll_and_download(poll_url: str, video_id: str, default_format: str) -> Optional[str]:
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
                fmt = data.get("format", default_format)
                out_path = f"{DOWNLOAD_DIR}/{video_id}.{fmt}"
                return await download_file(dl_url, out_path)
    except Exception:
        return None


async def api_download_audio(link: str) -> Optional[str]:
    if not USE_AUDIO_API:
        return None
    vid = extract_youtube_id(link)
    if not vid:
        return None
    poll_url = f"{API_URL}/song/{vid}?api={API_KEY}"
    return await _api_poll_and_download(poll_url, vid, "webm")


async def api_download_video(link: str) -> Optional[str]:
    if not USE_VIDEO_API:
        return None
    vid = extract_youtube_id(link)
    if not vid:
        return None
    poll_url = f"{VIDEO_API_URL}/video/{vid}?api={API_KEY}"
    return await _api_poll_and_download(poll_url, vid, "mp4")


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


def download_with_ytdlp_sync(link: str, fmt: str, is_soundcloud: bool = False) -> Optional[str]:
    try:
        opts = get_ytdlp_base_opts(is_soundcloud=is_soundcloud)
        opts["format"] = fmt
        
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            
            if path := get_final_path_from_info(info):
                return path
            
            ydl.download([link])
            
            return get_final_path_from_info(info)
    except Exception as e:
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
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    return None


async def _download_media(link: str, fmt: str, api_func, title: str, is_soundcloud: bool, media_type: str):
    loop = asyncio.get_running_loop()
    key = f"{media_type}:{link}"
    
    async def run():
        ytdlp_task = asyncio.create_task(
            run_with_semaphore(
                loop.run_in_executor(None, download_with_ytdlp_sync, link, fmt, is_soundcloud)
            )
        )
        use_api = (USE_AUDIO_API if media_type == "audio" else USE_VIDEO_API) and not is_soundcloud
        api_task = asyncio.create_task(api_func(link)) if use_api else None
        
        if api_task:
            return await race_ytdlp_and_api(
                ytdlp_task,
                api_task,
                title or "Unknown",
                media_type.capitalize(),
            )
        
        result = await ytdlp_task
        if result and title:
            log_download_source(media_type.capitalize(), title, "yt-dlp")
        return result

    return await deduplicate_download(key, run)


async def yt_dlp_download(link: str, type: str, title: str = "") -> Optional[str]:
    is_soundcloud = bool(SOUNDCLOUD_RE.match(link))
    
    if type == "audio":
        fmt = "bestaudio/best" if is_soundcloud else "bestaudio[ext=webm][acodec=opus]/bestaudio[ext=m4a][acodec=aac]/bestaudio/best"
        return await _download_media(link, fmt, api_download_audio, title, is_soundcloud, "audio")
    elif type == "video":
        fmt = "(bestvideo[height<=?720][width<=?1280][ext=mp4][fps<=?30])+(bestaudio[acodec=opus]/bestaudio[acodec=aac]/bestaudio)"
        return await _download_media(link, fmt, api_download_video, title, is_soundcloud, "video")
    
    return None


async def yt_dlp_get_stream_url(link: str) -> Tuple[int, str]:
    try:
        opts = get_ytdlp_base_opts(is_soundcloud=False)
        opts["format"] = "best[height<=?720][width<=?1280]"
        
        loop = asyncio.get_running_loop()
        
        def get_url():
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                url = info.get("url")
                if url:
                    return (1, url)
                formats = info.get("formats", [])
                if formats:
                    for fmt in formats:
                        if fmt.get("url"):
                            return (1, fmt.get("url"))
                return (0, "")
        
        result = await run_with_semaphore(loop.run_in_executor(None, get_url))
        return result if result else (0, "")
    except Exception as e:
        LOGGER.error(f"yt-dlp stream URL failed for {link}: {e}")
        return (0, "")


async def yt_dlp_get_playlist_ids(playlist_url: str, limit: int) -> List[str]:
    try:
        opts = get_ytdlp_base_opts(is_soundcloud=False)
        opts["extract_flat"] = True
        opts["playlistend"] = limit
        
        loop = asyncio.get_running_loop()
        
        def get_ids():
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                entries = info.get("entries", [])
                return [entry.get("id", "") for entry in entries if entry.get("id")]
        
        ids = await run_with_semaphore(loop.run_in_executor(None, get_ids))
        return ids if ids else []
    except Exception as e:
        LOGGER.error(f"yt-dlp playlist IDs failed for {playlist_url}: {e}")
        return []
