import asyncio
import contextlib
import glob
import os
import re
from typing import Dict, List, Optional, Union

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

from Tune.core.dir import CACHE_DIR
from Tune.core.dir import DOWNLOAD_DIR as _DOWNLOAD_DIR
from Tune.utils.cookie_handler import COOKIE_PATH
from Tune.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL

USE_API: bool = bool(API_URL and API_KEY)
_COOKIES_FILE = str(COOKIE_PATH)
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


class _YDLLogger:
    def debug(self, msg: str) -> None:
        return

    def info(self, msg: str) -> None:
        return

    def warning(self, msg: str) -> None:
        return

    def error(self, msg: str) -> None:
        return


_YDL_LOGGER = _YDLLogger()


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


def _cookiefile_path() -> Optional[str]:
    try:
        if _COOKIES_FILE and os.path.exists(_COOKIES_FILE) and os.path.getsize(_COOKIES_FILE) > 0:
            return _COOKIES_FILE
    except Exception:
        pass
    return None


def file_exists(video_id: str) -> Optional[str]:
    if not video_id:
        return None
    for ext in ("mp3", "m4a", "webm", "mp4", "mkv"):
        path = f"{_DOWNLOAD_DIR}/{video_id}.{ext}"
        if os.path.exists(path):
            return path
    return None


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]+', "_", (name or "").strip())[:200]


def _ytdlp_base_opts() -> Dict[str, Union[str, int, bool]]:
    opts: Dict[str, Union[str, int, bool]] = {
        "outtmpl": f"{_DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "overwrites": False,
        "continuedl": True,
        "noprogress": True,
        "concurrent_fragment_downloads": 16,
        "http_chunk_size": 1 << 20,
        "socket_timeout": 15,
        "retries": 1,
        "fragment_retries": 1,
        "cachedir": str(CACHE_DIR),
        "ignoreerrors": True,
        "logger": _YDL_LOGGER,
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
        connector = TCPConnector(limit=0, ttl_dns_cache=300, enable_cleanup_closed=True)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session


async def close_session() -> None:
    global _session
    async with _session_lock:
        if _session and not _session.closed:
            await _session.close()
        _session = None


async def api_download_song(link: str) -> Optional[str]:
    if not USE_API or not link:
        return None
    vid = extract_video_id(link)
    if not vid:
        return None
    poll_url = f"{API_URL}/song/{vid}?api={API_KEY}"
    try:
        session = await _get_session()
        while True:
            async with session.get(poll_url) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                s = str(data.get("status", "")).lower()
                if s == "downloading":
                    await asyncio.sleep(1.5)
                    continue
                if s != "done":
                    return None
                dl = data.get("link")
                fmt = str(data.get("format", "mp3")).lower()
                out_path = f"{_DOWNLOAD_DIR}/{vid}.{fmt}"
                async with session.get(dl) as fr:
                    if fr.status != 200:
                        return None
                    async with aiofiles.open(out_path, "wb") as f:
                        async for chunk in fr.content.iter_chunked(CHUNK_SIZE):
                            if not chunk:
                                break
                            await f.write(chunk)
                return out_path
    except Exception:
        return None


def _finalized_path_from_info(info: Dict) -> Optional[str]:
    vid = info.get("id")
    if not vid:
        return None
    ext = info.get("ext")
    if ext:
        p = f"{_DOWNLOAD_DIR}/{vid}.{ext}"
        if os.path.exists(p):
            return p
    matches = sorted(
        glob.glob(f"{_DOWNLOAD_DIR}/{vid}.*"),
        key=lambda p: os.path.getmtime(p),
        reverse=True,
    )
    return matches[0] if matches else None


def _download_ytdlp_once(
    link: str, fmt: str, extra_opts: Optional[Dict] = None
) -> Optional[str]:
    try:
        opts = _ytdlp_base_opts()
        opts.update({"format": fmt})
        if extra_opts:
            opts.update(extra_opts)
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            maybe = _finalized_path_from_info(info)
            if maybe:
                return maybe
            ydl.download([link])
            return _finalized_path_from_info(info) or maybe
    except Exception:
        return None


async def _with_sem(coro):
    async with SEM:
        return await coro


async def _dedup(key: str, runner):
    async with _inflight_lock:
        fut = _inflight.get(key)
        if fut:
            return await fut
        fut = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
    try:
        res = await runner()
        fut.set_result(res)
        return res
    except Exception:
        fut.set_result(None)
        return None
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)


async def yt_dlp_download(
    link: str, type: str, format_id: str = None, title: str = None
) -> Optional[str]:
    loop = asyncio.get_running_loop()

    if type == "audio":
        key = f"a:{link}"

        async def run():
            fmt = "bestaudio/best"
            return await _with_sem(
                loop.run_in_executor(None, _download_ytdlp_once, link, fmt, None)
            )

        return await _dedup(key, run)

    if type == "video":
        key = f"v:{link}"

        async def run():
            fmt = "best[height<=?720]/best"
            return await _with_sem(
                loop.run_in_executor(None, _download_ytdlp_once, link, fmt, None)
            )

        return await _dedup(key, run)

    if type == "song_video" and format_id and title:
        safe_title = _safe_filename(title)
        key = f"sv:{link}:{format_id}:{safe_title}"

        async def run():
            first = await _with_sem(
                loop.run_in_executor(
                    None,
                    _download_ytdlp_once,
                    link,
                    f"{format_id}+140",
                    {
                        "outtmpl": f"{_DOWNLOAD_DIR}/{safe_title}.mp4",
                        "prefer_ffmpeg": True,
                        "merge_output_format": "mp4",
                    },
                )
            )
            if first:
                return first
            return await _with_sem(
                loop.run_in_executor(
                    None,
                    _download_ytdlp_once,
                    link,
                    f"{format_id}+bestaudio/best",
                    {
                        "outtmpl": f"{_DOWNLOAD_DIR}/{safe_title}.mp4",
                        "prefer_ffmpeg": True,
                        "merge_output_format": "mp4",
                    },
                )
            )

        return await _dedup(key, run)

    if type == "song_audio" and format_id and title:
        safe_title = _safe_filename(title)
        key = f"sa:{link}:{format_id}:{safe_title}"

        async def run():
            return await _with_sem(
                loop.run_in_executor(
                    None,
                    _download_ytdlp_once,
                    link,
                    format_id,
                    {
                        "outtmpl": f"{_DOWNLOAD_DIR}/{safe_title}.%(ext)s",
                        "prefer_ffmpeg": True,
                        "postprocessors": [
                            {
                                "key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3",
                                "preferredquality": "192",
                            }
                        ],
                    },
                )
            )

        return await _dedup(key, run)

    return None


async def download_audio_concurrent(link: str) -> Optional[str]:
    vid = extract_video_id(link)
    cached = file_exists(vid)
    if cached:
        return cached
    if not USE_API:
        return await yt_dlp_download(link, type="audio")
    key = f"rac:{link}"

    async def run():
        yt_task = asyncio.create_task(yt_dlp_download(link, type="audio"))
        api_task = asyncio.create_task(api_download_song(link))
        done, pending = await asyncio.wait(
            {yt_task, api_task}, return_when=asyncio.FIRST_COMPLETED
        )
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
