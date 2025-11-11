import asyncio
import contextlib
import json
import os
import re
import time
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlparse

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from Tune.utils.cookie_handler import COOKIE_PATH
from Tune.utils.database import is_on_off
from Tune.utils.downloader import download_audio_concurrent, yt_dlp_download
from Tune.utils.errors import capture_internal_err
from Tune.utils.formatters import time_to_seconds
from Tune.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL

_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
_formats_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_formats_lock = asyncio.Lock()
_YT_HOST_RE = re.compile(r"(?:^|\.)((?:m|music|www)\.)?youtube\.com|youtu\.be", re.IGNORECASE)
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def _cookiefile_path() -> Optional[str]:
    path = str(COOKIE_PATH)
    try:
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    except Exception:
        pass
    return None


def _cookies_args() -> List[str]:
    p = _cookiefile_path()
    return ["--cookies", p] if p else []


async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return b"", b"timeout"


@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    key = f"q:{query}"
    now = time.time()
    async with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return val
            _cache.pop(key, None)
        if len(_cache) > YOUTUBE_META_MAX:
            _cache.clear()
    try:
        data = await VideosSearch(query, limit=1).next()
        result = data.get("result", [])
    except Exception:
        result = []
    if result:
        async with _cache_lock:
            _cache[key] = (now, result)
    return result


class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="

    def _is_url(self, s: str) -> bool:
        return bool(s and (s.startswith("http://") or s.startswith("https://")))

    def _normalize_id_or_none(self, s: str) -> Optional[str]:
        s = (s or "").strip()
        if YOUTUBE_ID_RE.match(s):
            return s
        return None

    def _is_playlist_url(self, s: str) -> bool:
        if not self._is_url(s):
            return False
        u = urlparse(s)
        if "youtu.be" in u.netloc:
            return False
        if u.path.startswith("/playlist"):
            return True
        qs = parse_qs(u.query or "")
        if "list" in qs and "v" not in qs:
            return True
        return False

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            return self.base_url + videoid.strip()
        s = (link or "").strip()
        raw = self._normalize_id_or_none(s)
        if raw:
            return self.base_url + raw
        if not self._is_url(s):
            return s
        try:
            if "youtu.be" in s:
                vid = s.split("/")[-1].split("?")[0]
                return self.base_url + vid
            if "youtube.com/shorts/" in s or "youtube.com/live/" in s or "youtube.com/embed/" in s:
                vid = s.split("/")[-1].split("?")[0]
                return self.base_url + vid
            if "youtube.com/watch" in s:
                return s.split("&")[0]
            return s
        except Exception:
            return s

    @capture_internal_err
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        s = self._prepare_link(link, videoid)
        return bool(YOUTUBE_ID_RE.search(s) or _YT_HOST_RE.search(s) or not self._is_url(s))

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset : ent.offset + ent.length]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url
        return None

    async def _ensure_watch_url(self, maybe_query_or_url: str) -> Optional[str]:
        prepared = self._prepare_link(maybe_query_or_url)
        if self._is_url(prepared) and not self._is_playlist_url(prepared):
            return prepared
        if self._is_playlist_url(prepared):
            return None
        data = await cached_youtube_search(prepared)
        if not data:
            return None
        vid = data[0].get("id")
        return self.base_url + vid if vid else None

    @capture_internal_err
    async def _fetch_video_info(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
        q = self._prepare_link(query)
        if use_cache and not self._is_url(q):
            res = await cached_youtube_search(q)
            return res[0] if res else None
        data = await VideosSearch(q, limit=1).next()
        result = data.get("result", [])
        return result[0] if result else None

    @capture_internal_err
    async def is_live(self, link: str) -> bool:
        prepared = await self._ensure_watch_url(link)
        if not prepared:
            return False
        stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", prepared)
        if not stdout:
            return False
        try:
            info = json.loads(stdout.decode())
            return bool(info.get("is_live"))
        except json.JSONDecodeError:
            return False

    @capture_internal_err
    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Video not found")
        dt = info.get("duration")
        ds = int(time_to_seconds(dt)) if dt else 0
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        return info.get("title", ""), dt, ds, thumb, info.get("id", "")

    @capture_internal_err
    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("duration") if info else None

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0] if info else ""

    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        if self._is_playlist_url(link):
            return 0, "playlist_link"
        link = await self._ensure_watch_url(link)
        if not link:
            return 0, "not_found"
        stdout, stderr = await _exec_proc(
            "yt-dlp", *(_cookies_args()), "-g", "-f", "best[height<=?720]/best", link
        )
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    @capture_internal_err
    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        if videoid:
            link = self.playlist_url + str(videoid)
        link = (link or "").split("&")[0]
        stdout, _ = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-i",
            "--get-id",
            "--flat-playlist",
            "--playlist-end",
            str(limit),
            "--skip-download",
            link,
        )
        items = stdout.decode().strip().split("\n") if stdout else []
        return [i for i in items if i]

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        try:
            info = await self._fetch_video_info(self._prepare_link(link, videoid))
            if not info:
                raise ValueError("Track not found via API")
        except Exception:
            prepared = self._prepare_link(link, videoid)
            if self._is_playlist_url(prepared):
                raise ValueError("Track not found (playlist link)")
            prepared = await self._ensure_watch_url(prepared)
            if not prepared:
                raise ValueError("Track not found (invalid input)")
            stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", prepared)
            if not stdout:
                raise ValueError("Track not found (yt-dlp fallback)")
            info = json.loads(stdout.decode())
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", await self._ensure_watch_url(link)),
            "vidid": info.get("id", ""),
            "duration_min": info.get("duration") if isinstance(info.get("duration"), str) else None,
            "thumb": thumb,
        }
        return details, info.get("id", "")

    @capture_internal_err
    async def formats(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        if self._is_playlist_url(link):
            return [], ""
        link = await self._ensure_watch_url(link)
        if not link:
            return [], ""
        key = f"f:{link}"
        now = time.time()
        async with _formats_lock:
            cached = _formats_cache.get(key)
            if cached and now - cached[0] < YOUTUBE_META_TTL:
                return cached[1], cached[2]
        opts = {"quiet": True}
        cf = _cookiefile_path()
        if cf:
            opts["cookiefile"] = cf
        out: List[Dict] = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                for fmt in info.get("formats", []):
                    if "dash" in str(fmt.get("format", "")).lower():
                        continue
                    if not any(k in fmt for k in ("filesize", "filesize_approx")):
                        continue
                    if not all(k in fmt for k in ("format", "format_id", "ext", "format_note")):
                        continue
                    size = fmt.get("filesize") or fmt.get("filesize_approx")
                    if not size:
                        continue
                    out.append(
                        {
                            "format": fmt["format"],
                            "filesize": size,
                            "format_id": fmt["format_id"],
                            "ext": fmt["ext"],
                            "format_note": fmt["format_note"],
                            "yturl": link,
                        }
                    )
        except Exception:
            pass
        async with _formats_lock:
            if len(_formats_cache) > YOUTUBE_META_MAX:
                _formats_cache.clear()
            _formats_cache[key] = (now, out, link)
        return out, link

    @capture_internal_err
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], str, str]:
        data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
        results = data.get("result", [])
        if not results or query_type >= len(results):
            raise IndexError(f"Query type index {query_type} out of range (found {len(results)} results)")
        r = results[query_type]
        return (
            r.get("title", ""),
            r.get("duration"),
            r.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
            r.get("id", ""),
        )

    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        songaudio: Union[bool, str, None] = None,
        songvideo: Union[bool, str, None] = None,
        format_id: Union[bool, str, None] = None,
        title: Union[bool, str, None] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        normalized = self._prepare_link(link, videoid)
        if self._is_playlist_url(normalized):
            return None, None
        if songvideo:
            p = await yt_dlp_download(
                normalized, type="song_video", format_id=str(format_id or ""), title=str(title or "video")
            )
            return (p, True) if p else (None, None)
        if songaudio:
            p = await yt_dlp_download(
                normalized, type="song_audio", format_id=str(format_id or ""), title=str(title or "audio")
            )
            return (p, True) if p else (None, None)
        if video:
            if await self.is_live(normalized):
                status, stream_url = await self.video(normalized)
                if status == 1:
                    return stream_url, None
                return None, None
            if await is_on_off(1):
                url = await self._ensure_watch_url(normalized)
                if not url:
                    return None, None
                p = await yt_dlp_download(url, type="video")
                return (p, True) if p else (None, None)
            url = await self._ensure_watch_url(normalized)
            if not url:
                return None, None
            status, stream_url = await self.video(url)
            if status == 1:
                return stream_url, None
            return None, None
        url = await self._ensure_watch_url(normalized)
        if not url:
            return None, None
        p = await download_audio_concurrent(url)
        return (p, True) if p else (None, None)
