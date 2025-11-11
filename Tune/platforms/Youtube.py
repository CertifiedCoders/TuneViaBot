import asyncio
import json
import os
import re
import time
from typing import Dict, List, Optional, Tuple

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from Tune.utils.cookie_handler import COOKIE_PATH
from Tune.utils.database import is_on_off
from Tune.utils.downloader import download_audio_concurrent, yt_dlp_download
from Tune.utils.formatters import time_to_seconds
from Tune.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL

_CACHE: Dict[str, Tuple[float, List[Dict]]] = {}
_CACHE_LOCK = asyncio.Lock()
_FORMATS_CACHE: Dict[str, Tuple[float, List[Dict], str]] = {}
_FORMATS_LOCK = asyncio.Lock()
_COOKIE_ARGS = ["--cookies", str(COOKIE_PATH)] if COOKIE_PATH and os.path.exists(COOKIE_PATH) and os.path.getsize(COOKIE_PATH) > 0 else []

URL_PATTERN = re.compile(r"(?:youtube\.com|youtu\.be)")
BASE_URL = "https://www.youtube.com/watch?v="
PLAYLIST_URL = "https://youtube.com/playlist?list="

async def exec_ytdlp(*args) -> Tuple[bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return b"", b""

async def cached_search(query: str) -> List[Dict]:
    key = f"q:{query.lower()}"
    now = time.time()
    async with _CACHE_LOCK:
        if key in _CACHE and now - _CACHE[key][0] < YOUTUBE_META_TTL:
            return _CACHE[key][1]
        if len(_CACHE) >= YOUTUBE_META_MAX:
            _CACHE.clear()
    try:
        data = (await VideosSearch(query, limit=1).next())["result"]
    except:
        data = []
    if data:
        async with _CACHE_LOCK:
            _CACHE[key] = (now, data)
    return data

class YouTubeAPI:
    def _prepare_link(self, link: str, videoid: Optional[str] = None) -> str:
        if videoid:
            return BASE_URL + videoid
        link = link.split("&")[0]
        if "youtu.be" in link:
            return BASE_URL + link.split("/")[-1].split("?")[0]
        if "/shorts/" in link or "/live/" in link:
            return BASE_URL + link.split("/")[-1].split("?")[0]
        return link

    async def exists(self, link: str, videoid: Optional[str] = None) -> bool:
        return bool(URL_PATTERN.search(self._prepare_link(link, videoid)))

    async def url(self, message: Message) -> Optional[str]:
        for msg in [message, message.reply_to_message]:
            if not msg:
                continue
            text = msg.text or msg.caption or ""
            entities = msg.entities or msg.caption_entities or []
            for e in entities:
                if e.type == MessageEntityType.URL:
                    return text[e.offset:e.offset + e.length]
                if e.type == MessageEntityType.TEXT_LINK:
                    return e.url
        return None

    async def _info(self, query: str) -> Optional[Dict]:
        q = self._prepare_link(query)
        if not q.startswith("http"):
            if res := await cached_search(q):
                return res[0]
        if res := (await VideosSearch(q, limit=1).next()).get("result"):
            return res[0]
        return None

    async def is_live(self, link: str) -> bool:
        stdout, _ = await exec_ytdlp("yt-dlp", *_COOKIE_ARGS, "--dump-json", self._prepare_link(link))
        return stdout and json.loads(stdout).get("is_live")

    async def details(self, link: str, videoid: Optional[str] = None) -> Tuple[str, Optional[str], int, str, str]:
        info = await self._info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Not found")
        dur = info.get("duration")
        secs = time_to_seconds(dur) if dur else 0
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        return info.get("title", ""), dur, secs, thumb, info.get("id", "")

    async def title(self, link: str, videoid: Optional[str] = None) -> str:
        return (await self._info(self._prepare_link(link, videoid)))["title"]

    async def duration(self, link: str, videoid: Optional[str] = None) -> Optional[str]:
        return (await self._info(self._prepare_link(link, videoid)))["duration"]

    async def thumbnail(self, link: str, videoid: Optional[str] = None) -> str:
        info = await self._info(self._prepare_link(link, videoid))
        return (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]

    async def video(self, link: str) -> Tuple[int, str]:
        stdout, _ = await exec_ytdlp("yt-dlp", *_COOKIE_ARGS, "-g", "-f", "best[height<=720][width<=1280]", self._prepare_link(link))
        return (1, stdout.decode().strip()) if stdout else (0, "")

    async def playlist(self, link: str, limit: int, user_id, videoid: Optional[str] = None) -> List[str]:
        link = PLAYLIST_URL + videoid if videoid else link.split("&")[0]
        stdout, _ = await exec_ytdlp("yt-dlp", *_COOKIE_ARGS, "-i", "--get-id", "--flat-playlist", "--playlist-end", str(limit), "--skip-download", link)
        return [x for x in stdout.decode().splitlines() if x]

    async def track(self, link: str, videoid: Optional[str] = None) -> Tuple[Dict, str]:
        try:
            info = await self._info(self._prepare_link(link, videoid))
        except:
            stdout, _ = await exec_ytdlp("yt-dlp", *_COOKIE_ARGS, "--dump-json", self._prepare_link(link, videoid))
            info = json.loads(stdout) if stdout else {}
        if not info:
            raise ValueError("Not found")
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        vid = info.get("id", "")
        return {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", BASE_URL + vid),
            "vidid": vid,
            "duration_min": info.get("duration"),
            "thumb": thumb,
        }, vid

    async def formats(self, link: str, videoid: Optional[str] = None) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        key = f"f:{link}"
        now = time.time()
        async with _FORMATS_LOCK:
            if key in _FORMATS_CACHE and now - _FORMATS_CACHE[key][0] < YOUTUBE_META_TTL:
                return _FORMATS_CACHE[key][1], _FORMATS_CACHE[key][2]
            if len(_FORMATS_CACHE) >= YOUTUBE_META_MAX:
                _FORMATS_CACHE.clear()

        opts = {"quiet": True}
        if _COOKIE_ARGS:
            opts["cookiefile"] = _COOKIE_ARGS[1]
        formats = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                for f in info.get("formats", []):
                    if "dash" in f.get("format", "").lower():
                        continue
                    size = f.get("filesize") or f.get("filesize_approx")
                    if not size or not all(k in f for k in ("format_id", "ext", "format_note")):
                        continue
                    formats.append({
                        "format": f["format"],
                        "filesize": size,
                        "format_id": f["format_id"],
                        "ext": f["ext"],
                        "format_note": f["format_note"],
                        "yturl": link,
                    })
        except:
            pass

        async with _FORMATS_LOCK:
            _FORMATS_CACHE[key] = (now, formats, link)
        return formats, link

    async def slider(self, link: str, idx: int, videoid: Optional[str] = None) -> Tuple[str, Optional[str], str, str]:
        results = (await VideosSearch(self._prepare_link(link, videoid), limit=10).next())["result"]
        if idx >= len(results):
            raise IndexError("Out of range")
        r = results[idx]
        return r.get("title", ""), r.get("duration"), (r.get("thumbnails", [{}])[0].get("url", "")).split("?")[0], r.get("id", "")

    async def download(self, link: str, mystic, *, video=None, videoid=None, songaudio=None, songvideo=None, format_id=None, title=None):
        link = self._prepare_link(link, videoid)

        if songvideo and format_id and title:
            path = await yt_dlp_download(link, "song_video", format_id, title)
            return (path, True) if path else (None, None)

        if songaudio and format_id and title:
            path = await yt_dlp_download(link, "song_audio", format_id, title)
            return (path, True) if path else (None, None)

        if video:
            if await self.is_live(link):
                status, url = await self.video(link)
                return (url, None) if status else (None, None)
            if await is_on_off(1):
                path = await yt_dlp_download(link, "video")
                return (path, True) if path else (None, None)
            stdout, _ = await exec_ytdlp("yt-dlp", *_COOKIE_ARGS, "-g", "-f", "best[height<=720][width<=1280]", link)
            return (stdout.decode().strip(), None) if stdout else (None, None)

        path = await download_audio_concurrent(link)
        return (path, True) if path else (None, None)