import asyncio
import os
import re
from typing import Dict, Optional

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

from Tune.core.dir import DOWNLOAD_DIR, CACHE_DIR
from Tune.utils.cookie_handler import COOKIE_PATH
from Tune.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL

USE_API = bool(API_URL and API_KEY)
COOKIES_FILE = str(COOKIE_PATH) if COOKIE_PATH and os.path.exists(COOKIE_PATH) and os.path.getsize(COOKIE_PATH) > 0 else None
_INFLIGHT: Dict[str, asyncio.Future] = {}
_INFLIGHT_LOCK = asyncio.Lock()
_SESSION: Optional[aiohttp.ClientSession] = None
_SESSION_LOCK = asyncio.Lock()

def extract_video_id(link: str) -> str:
    return (link.split("v=")[-1].split("&")[0] if "v=" in link else link.split("/")[-1].split("?")[0].split("&")[0])

def file_exists(video_id: str) -> Optional[str]:
    for ext in ("mp3", "m4a", "webm", "mp4"):
        path = f"{DOWNLOAD_DIR}/{video_id}.{ext}"
        if os.path.exists(path):
            return path
    return None

def safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", (name or "").strip())[:180]

def base_ytdlp_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "overwrites": True,
        "continuedl": True,
        "noprogress": True,
        "concurrent_fragment_downloads": 32,
        "http_chunk_size": 1 << 20,          # 1 MiB
        "retries": 10,
        "fragment_retries": 15,
        "socket_timeout": 8,
        "cachedir": str(CACHE_DIR),
        "external_downloader": "aria2c",
        # aria2c: max 16 connections per server, 64 total jobs
        "external_downloader_args": {"aria2c": ["-x", "16", "-s", "16", "-j", "64", "-k", "1M"]},
    }
    if COOKIES_FILE:
        opts["cookiefile"] = COOKIES_FILE
    return opts

async def get_session() -> aiohttp.ClientSession:
    global _SESSION
    async with _SESSION_LOCK:
        if _SESSION and not _SESSION.closed:
            return _SESSION
        timeout = aiohttp.ClientTimeout(total=300, connect=5, sock_read=15)
        connector = TCPConnector(limit=0, ttl_dns_cache=3600, use_dns_cache=True, enable_cleanup_closed=True)
        _SESSION = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _SESSION

async def api_download(link: str) -> Optional[str]:
    if not USE_API:
        return None
    vid = extract_video_id(link)
    url = f"{API_URL}/song/{vid}?api={API_KEY}"
    session = await get_session()
    try:
        async with session.get(url) as r:
            if r.status != 200:
                return None
            data = await r.json()
            status = data.get("status", "").lower()
            if status != "done":
                return None
            dl, fmt = data.get("link"), data.get("format", "mp3").lower()
            path = f"{DOWNLOAD_DIR}/{vid}.{fmt}"
            async with session.get(dl) as fr:
                if fr.status != 200:
                    return None
                async with aiofiles.open(path, "wb") as f:
                    async for chunk in fr.content.iter_chunked(CHUNK_SIZE):
                        await f.write(chunk)
            return path
    except:
        return None

def ytdlp_sync_download(link: str, opts: dict) -> Optional[str]:
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            vid, ext = info["id"], info.get("ext", "webm")
            path = f"{DOWNLOAD_DIR}/{vid}.{ext}"
            if os.path.exists(path):
                return path
            ydl.download([link])
            return path if os.path.exists(path) else None
    except:
        return None

async def dedup(key: str, runner):
    async with _INFLIGHT_LOCK:
        if key in _INFLIGHT:
            return await _INFLIGHT[key]
        fut = asyncio.get_event_loop().create_future()
        _INFLIGHT[key] = fut
    try:
        res = await runner()
        fut.set_result(res)
        return res
    except Exception as e:
        fut.set_exception(e)
        raise
    finally:
        async with _INFLIGHT_LOCK:
            _INFLIGHT.pop(key, None)

async def yt_dlp_download(link: str, type: str, format_id: str = None, title: str = None) -> Optional[str]:
    loop = asyncio.get_event_loop()
    if type == "audio":
        key = f"a:{link}"
        async def run():
            opts = base_ytdlp_opts() | {"format": "bestaudio/best"}
            return await loop.run_in_executor(None, ytdlp_sync_download, link, opts)
        return await dedup(key, lambda: asyncio.wait_for(run(), timeout=180))

    if type == "video":
        key = f"v:{link}"
        async def run():
            opts = base_ytdlp_opts() | {"format": "best[height<=720][width<=1280]"}
            return await loop.run_in_executor(None, ytdlp_sync_download, link, opts)
        return await dedup(key, lambda: asyncio.wait_for(run(), timeout=300))

    if type == "song_video" and format_id and title:
        safe_title = safe_filename(title)
        key = f"sv:{link}:{format_id}:{safe_title}"
        async def run():
            opts = base_ytdlp_opts() | {
                "format": f"{format_id}+bestaudio",
                "outtmpl": f"{DOWNLOAD_DIR}/{safe_title}.%(ext)s",
                "merge_output_format": "mp4",
            }
            await loop.run_in_executor(None, lambda: YoutubeDL(opts).download([link]))
            path = f"{DOWNLOAD_DIR}/{safe_title}.mp4"
            return path if os.path.exists(path) else None
        return await dedup(key, lambda: asyncio.wait_for(run(), timeout=300))

    if type == "song_audio" and format_id and title:
        safe_title = safe_filename(title)
        key = f"sa:{link}:{format_id}:{safe_title}"
        async def run():
            opts = base_ytdlp_opts() | {
                "format": format_id,
                "outtmpl": f"{DOWNLOAD_DIR}/{safe_title}.%(ext)s",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }],
            }
            await loop.run_in_executor(None, lambda: YoutubeDL(opts).download([link]))
            path = f"{DOWNLOAD_DIR}/{safe_title}.mp3"
            return path if os.path.exists(path) else None
        return await dedup(key, lambda: asyncio.wait_for(run(), timeout=300))

    return None

async def download_audio_concurrent(link: str) -> Optional[str]:
    vid = extract_video_id(link)
    if cached := file_exists(vid):
        return cached

    key = f"rac:{link}"
    async def run():
        async with SEM:
            yt_task = asyncio.create_task(yt_dlp_download(link, "audio"))
            api_task = asyncio.create_task(api_download(link)) if USE_API else None
            tasks = [t for t in (yt_task, api_task) if t]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                if res := t.result():
                    [p.cancel() for p in pending]
                    return res
            for t in pending:
                if res := await t:
                    return res
            return None
    return await dedup(key, run)