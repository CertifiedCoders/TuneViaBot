# Authored By Certified Coders © 2025

import asyncio
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Union

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import VideosSearch, Video, Playlist

from Tune.utils.cookie_handler import COOKIE_PATH
from Tune.utils.downloader import yt_dlp_download
from Tune.utils.errors import capture_internal_err
from Tune.utils.formatters import time_to_seconds, seconds_to_min
from Tune.utils.tuning import YTDLP_TIMEOUT, Track, LiveTrack

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def get_cookies_args() -> List[str]:
    try:
        path = str(COOKIE_PATH)
        return ["--cookies", path] if path and os.path.exists(path) and os.path.getsize(path) > 0 else []
    except Exception:
        return []


def _extract_thumbnail(data: dict) -> str:
    thumbs = data.get("thumbnails")
    if isinstance(thumbs, list) and thumbs:
        url = thumbs[-1].get("url")
        if url:
            return url.split("?")[0]
    thumb = data.get("thumbnail", "")
    return thumb.split("?")[0] if thumb else ""


async def _run_ytdlp_dump(url: str) -> Optional[Dict]:
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        *get_cookies_args(),
        "--dump-json",
        "--no-warnings",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
        return json.loads(stdout.decode()) if stdout else None
    except Exception:
        return None


class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(youtube\.com|youtu\.be|music\.youtube\.com)")
        self.regex = re.compile(r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?")
        self._cookies = get_cookies_args()

    @property
    def cookies(self) -> List[str]:
        return self._cookies

    def _validate_url(self, query: str) -> Tuple[str, Optional[str], Optional[str]]:
        query = query.strip()
        if not self._url_pattern.search(query):
            return ("unknown", None, None)
        
        if "/playlist?list=" in query.lower():
            match = self.regex.search(query)
            if match and (playlist_id := match.group(1)):
                return ("playlist", None, playlist_id)
        
        match = self.regex.search(query)
        if not match or not (id_match := match.group(1)):
            return ("unknown", None, None)
        
        if len(id_match) == 11 and YOUTUBE_ID_RE.match(id_match):
            return ("live", id_match, None) if "/live/" in query.lower() else ("video", id_match, None)
        
        return ("unknown", None, None)

    async def _fetch_raw_metadata(self, query: Optional[str], url_type: str, video_id: Optional[str] = None, playlist_id: Optional[str] = None) -> Optional[dict]:
        if url_type == "playlist":
            try:
                return await Playlist.get(f"{self.playlist_url}{playlist_id}")
            except Exception:
                return None
        
        if url_type == "live":
            if not video_id:
                return None
            info = await _run_ytdlp_dump(f"{self.base_url}{video_id}")
            return info if info and info.get("is_live") else None
        
        if url_type == "video":
            if not video_id:
                return None
            try:
                return await Video.get(f"{self.base_url}{video_id}")
            except Exception:
                return None
        
        if url_type == "unknown" and query:
            try:
                results = (await VideosSearch(query, limit=1).next()).get("result", [])
                if results and (video_id := results[0].get("id")):
                    try:
                        return await Video.get(f"{self.base_url}{video_id}")
                    except Exception:
                        return results[0]
            except Exception:
                pass
        
        return None

    @capture_internal_err
    async def get_metadata(self, link: str, videoid: Union[str, bool, None] = None) -> Union[Track, LiveTrack, None]:
        if isinstance(videoid, str) and videoid.strip():
            video_id = videoid.strip()
            info = await _run_ytdlp_dump(f"{self.base_url}{video_id}")
            if info:
                video_id = info.get("id") or video_id or ""
                title = info.get("title", "")
                url = info.get("webpage_url") or f"{self.base_url}{video_id}"
                thumbnail = _extract_thumbnail(info)
                if info.get("is_live"):
                    return LiveTrack(id=video_id, title=title, url=url, thumbnail=thumbnail)
                duration = info.get("duration")
                duration_str = duration if isinstance(duration, str) else (seconds_to_min(int(duration.get("secondsText"))) if isinstance(duration, dict) and duration.get("secondsText") else None)
                duration_sec = int(time_to_seconds(duration_str)) if duration_str and duration_str != "-" else 0
                return Track(id=video_id, title=title, url=url, duration_min=duration_str if duration_str and duration_str != "-" else None, duration_sec=duration_sec, thumbnail=thumbnail)
            try:
                info = await Video.get(f"{self.base_url}{video_id}")
                if info:
                    video_id = info.get("id") or video_id or ""
                    title = info.get("title", "")
                    url = info.get("webpage_url") or info.get("link") or f"{self.base_url}{video_id}"
                    thumbnail = _extract_thumbnail(info)
                    duration = info.get("duration")
                    duration_str = duration if isinstance(duration, str) else (seconds_to_min(int(duration.get("secondsText"))) if isinstance(duration, dict) and duration.get("secondsText") else None)
                    duration_sec = int(time_to_seconds(duration_str)) if duration_str and duration_str != "-" else 0
                    return Track(id=video_id, title=title, url=url, duration_min=duration_str if duration_str and duration_str != "-" else None, duration_sec=duration_sec, thumbnail=thumbnail)
            except Exception:
                pass
            return None
        
        url_type, video_id, playlist_id = self._validate_url(link)
        if url_type == "playlist":
            return None
        
        info = await self._fetch_raw_metadata(link if url_type == "unknown" else None, url_type, video_id)
        if not info:
            return None
        
        video_id = info.get("id") or video_id or ""
        title = info.get("title", "")
        url = info.get("webpage_url") or info.get("link") or f"{self.base_url}{video_id}"
        thumbnail = _extract_thumbnail(info)
        
        if url_type == "live" or info.get("is_live"):
            return LiveTrack(
                id=video_id,
                title=title,
                url=url,
                thumbnail=thumbnail,
            )
        
        duration = info.get("duration")
        duration_str = duration if isinstance(duration, str) else (seconds_to_min(int(duration.get("secondsText"))) if isinstance(duration, dict) and duration.get("secondsText") else None)
        duration_sec = int(time_to_seconds(duration_str)) if duration_str and duration_str != "-" else 0
        
        return Track(
            id=video_id,
            title=title,
            url=url,
            duration_min=duration_str if duration_str and duration_str != "-" else None,
            duration_sec=duration_sec,
            thumbnail=thumbnail,
        )

    @capture_internal_err
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        if videoid:
            return bool(YOUTUBE_ID_RE.match(str(videoid)))
        return bool(self._url_pattern.search(link))

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset : ent.offset + ent.length].split("&si")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url.split("&si")[0]
        return None

    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        url_type, video_id, _ = self._validate_url(link)
        if not video_id and isinstance(videoid, str) and videoid.strip():
            video_id = videoid.strip()
        
        url = f"{self.base_url}{video_id}" if video_id else link
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", *self.cookies, "-g", "-f", "best[height<=?720][width<=?1280]", url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
            return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())
        except Exception:
            return (0, "")

    @capture_internal_err
    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        if videoid:
            playlist_id = str(videoid)
        else:
            url_type, _, playlist_id = self._validate_url(link)
            if url_type != "playlist":
                raise ValueError("Not a valid playlist URL")
        
        url = f"{self.playlist_url}{playlist_id}"
        try:
            playlist_info = await Playlist.get(url)
            if playlist_info:
                items = [v.get("id") if isinstance(v, dict) else getattr(v, "id", None)
                        for v in playlist_info.get("videos", [])[:limit]]
                if items := [i for i in items if i]:
                    return items
        except Exception:
            pass
        
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", *self.cookies, "-i", "--get-id", "--flat-playlist",
            "--playlist-end", str(limit), "--skip-download", url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
            return [i for i in (stdout.decode().strip().split("\n") if stdout else []) if i]
        except Exception:
            return []

    @capture_internal_err
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], str, str]:
        if videoid:
            query = f"{self.base_url}{videoid}"
        else:
            url_type, video_id, _ = self._validate_url(link)
            query = f"{self.base_url}{video_id}" if video_id else link
        
        results = (await VideosSearch(query, limit=10).next()).get("result", [])
        if not results or query_type >= len(results):
            raise IndexError(f"Query type index {query_type} out of range (found {len(results)} results)")
        
        r = results[query_type]
        duration = r.get("duration")
        duration_str = duration if isinstance(duration, str) else (seconds_to_min(int(duration.get("secondsText"))) if isinstance(duration, dict) and duration.get("secondsText") else None)
        
        return (
            r.get("title", ""),
            duration_str if duration_str and duration_str != "-" else None,
            _extract_thumbnail(r),
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
        title: Optional[str] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        if isinstance(videoid, bool):
            videoid = None
        
        url_type, video_id, _ = self._validate_url(link)
        url = f"{self.base_url}{video_id}" if video_id else link
        
        if videoid and not video_id:
            url_type, video_id, _ = self._validate_url(str(videoid))
            url = f"{self.base_url}{video_id}" if video_id else url
        
        metadata = await self.get_metadata(url, videoid)
        if isinstance(metadata, LiveTrack) and video:
            status, stream_url = await self.video(url)
            return (stream_url, None) if status == 1 else (None, None)
        
        if not title:
            title = metadata.title if metadata else ""
        
        p = await yt_dlp_download(url, type="video" if video else "audio", title=title)
        return (p, True) if p else (None, None)


YouTube = YouTubeAPI()
