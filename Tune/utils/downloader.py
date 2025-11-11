import asyncio
import contextlib
import os
import re
from typing import Dict, Optional, Union
from pathlib import Path

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL
from Tune.utils.cookie_handler import COOKIE_PATH
from Tune.core.dir import DOWNLOAD_DIR, CACHE_DIR
from Tune.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL


USE_API = bool(API_URL and API_KEY)

_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()

_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()

def extract_video_id(link: str) -> str:
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"shorts\/([0-9A-Za-z_-]{11})",
        r"live\/([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    raise ValueError("Invalid YouTube URL")

def _cookiefile_path() -> Optional[str]:
    try:
        if COOKIE_PATH.exists() and COOKIE_PATH.stat().st_size > 0:
            return str(COOKIE_PATH)
    except Exception:
        pass
    return None

def file_exists(video_id: str, ext_choices: tuple[str, ...] = ("mp3", "m4a", "webm", "mp4")) -> Optional[str]:
    for ext in ext_choices:
        path = DOWNLOAD_DIR / f"{video_id}.{ext}"
        if path.exists():
            return str(path)
    return None

def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]+', "_", (name or "").strip())[:200]

def _ytdlp_base_opts() -> Dict[str, Union[str, int, bool]]:
    opts: Dict[str, Union[str, int, bool]] = {
        "outtmpl": str(DOWNLOAD_DIR / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "overwrites": True,
        "continuedl": True,
        "noprogress": True,
        "concurrent_fragment_downloads": 16,  # Parallel fragments for speed
        "http_chunk_size": 1 << 20,  # 1MB chunks
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "cachedir": str(CACHE_DIR),
    }
    cookiefile = _cookiefile_path()
    if cookiefile:
        opts["cookiefile"] = cookiefile
    return opts

async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    async with _session_lock:
        if _session and not _session.closed:
            return _session
        timeout = aiohttp.ClientTimeout(total=600, sock_connect=20, sock_read=60)
        connector = TCPConnector(limit=0, ttl_dns_cache=300)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session

async def api_download(link: str, is_video: bool = False) -> Optional[str]:
    if not USE_API:
        return None
    try:
        vid = extract_video_id(link)
        endpoint = "/video/" if is_video else "/song/"
        poll_url = f"{API_URL}{endpoint}{vid}?api={API_KEY}"
        session = await _get_session()
        attempts = 0
        while attempts < 5:
            async with session.get(poll_url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                status = str(data.get("status", "")).lower()
                if status == "downloading":
                    await asyncio.sleep(1)
                    attempts += 1
                    continue
                if status != "done":
                    return None
                dl_link = data.get("link")
                fmt = str(data.get("format", "mp4" if is_video else "mp3")).lower()
                out_path = DOWNLOAD_DIR / f"{vid}.{fmt}"
                async with session.get(dl_link) as fr:
                    if fr.status != 200:
                        return None
                    async with aiofiles.open(out_path, "wb") as f:
                        async for chunk in fr.content.iter_chunked(CHUNK_SIZE):
                            if chunk:
                                await f.write(chunk)
                return str(out_path)
    except Exception as e:
        print(f"API download error: {e}")  # Basic logging
        return None

def _download_ytdlp(link: str, opts: Dict) -> Optional[str]:
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            vid = info.get("id")
            ext = info.get("ext") or ("mp4" if "video" in opts.get("format", "") else "webm")
            path = str(DOWNLOAD_DIR / f"{vid}.{ext}")
            if os.path.exists(path):
                return path
            ydl.download([link])
            return path
    except Exception as e:
        print(f"yt-dlp download error: {e}")
        return None

async def _with_sem(coro):
    async with SEM:
        return await coro

async def _dedup(key: str, runner):
    async with _inflight_lock:
        if key in _inflight:
            return await _inflight[key]
        fut = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
    try:
        res = await runner()
        fut.set_result(res)
        return res
    except Exception as e:
        fut.set_exception(e)
        return None
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)

async def yt_dlp_download(
    link: str,
    dl_type: str,
    format_id: Optional[str] = None,
    title: Optional[str] = None,
) -> Optional[str]:
    loop = asyncio.get_running_loop()
    base_opts = _ytdlp_base_opts()

    if dl_type == "audio":
        key = f"audio:{link}"
        async def run():
            opts = {**base_opts, "format": "bestaudio/best"}
            return await _with_sem(loop.run_in_executor(None, _download_ytdlp, link, opts))
        return await _dedup(key, run)

    if dl_type == "video":
        key = f"video:{link}"
        async def run():
            opts = {**base_opts, "format": "best[height<=?720][width<=?1280]"}
            return await _with_sem(loop.run_in_executor(None, _download_ytdlp, link, opts))
        return await _dedup(key, run)

    if dl_type == "song_video" and format_id and title:
        safe_title = _safe_filename(title)
        key = f"song_video:{link}:{format_id}:{safe_title}"
        async def run():
            opts = {
                **base_opts,
                "format": f"{format_id}+140",
                "outtmpl": str(DOWNLOAD_DIR / f"{safe_title}.mp4"),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            await _with_sem(loop.run_in_executor(None, lambda: YoutubeDL(opts).download([link])))
            return str(DOWNLOAD_DIR / f"{safe_title}.mp4")
        return await _dedup(key, run)

    if dl_type == "song_audio" and format_id and title:
        safe_title = _safe_filename(title)
        key = f"song_audio:{link}:{format_id}:{safe_title}"
        async def run():
            opts = {
                **base_opts,
                "format": format_id,
                "outtmpl": str(DOWNLOAD_DIR / f"{safe_title}.%(ext)s"),
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            await _with_sem(loop.run_in_executor(None, lambda: YoutubeDL(opts).download([link])))
            return str(DOWNLOAD_DIR / f"{safe_title}.mp3")
        return await _dedup(key, run)

    raise ValueError(f"Invalid download type: {dl_type}")

async def download_concurrent(link: str, is_video: bool = False) -> Optional[str]:
    try:
        vid = extract_video_id(link)
    except ValueError:
        return None
    cached = file_exists(vid, ("mp4",) if is_video else ("mp3", "m4a", "webm"))
    if cached:
        return cached

    dl_type = "video" if is_video else "audio"
    key = f"concurrent_{dl_type}:{link}"

    async def run():
        yt_task = asyncio.create_task(yt_dlp_download(link, dl_type))
        api_task = asyncio.create_task(api_download(link, is_video)) if USE_API else None

        tasks = {yt_task}
        if api_task:
            tasks.add(api_task)

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            with contextlib.suppress(Exception):
                res = t.result()
                if res:
                    for p in pending:
                        p.cancel()
                        with contextlib.suppress(Exception, asyncio.CancelledError):
                            await p
                    return res
        for t in pending:
            with contextlib.suppress(Exception, asyncio.CancelledError):
                res = await t
                if res:
                    return res
        return None

    return await _dedup(key, lambda: _with_sem(run()))