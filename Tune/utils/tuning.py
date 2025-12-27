# Authored By Certified Coders © 2025

import asyncio
import os
import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

from Tune.utils.formatters import time_to_seconds, seconds_to_min

CPU = os.cpu_count() or 4
MAX_CONCURRENT = min(128, CPU * 16)
CHUNK_SIZE = 256 * 1024
YTDLP_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 300
JOIN_CALL_TIMEOUT = 30
SEM = asyncio.Semaphore(MAX_CONCURRENT)
CHAT_SEMAPHORES = {}
CHAT_SEMAPHORE_LOCK = asyncio.Lock()

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_URL_PATTERN = re.compile(r"(youtube\.com|youtu\.be|music\.youtube\.com)")
YOUTUBE_ID_EXTRACT_RE = re.compile(r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?")

async def get_chat_semaphore(chat_id: int):
    async with CHAT_SEMAPHORE_LOCK:
        return CHAT_SEMAPHORES.setdefault(chat_id, asyncio.Semaphore(3))


def extract_youtube_id(link: str) -> str:
    if not link:
        return ""
    s = link.strip()
    if YOUTUBE_ID_RE.match(s):
        return s
    if "v=" in s:
        return s.split("v=")[-1].split("&")[0].split("?")[0]
    last = s.split("/")[-1].split("?")[0]
    return last if YOUTUBE_ID_RE.match(last) else ""


def validate_youtube_url(query: str) -> Tuple[str, Optional[str], Optional[str]]:
    query = query.strip()
    if not YOUTUBE_URL_PATTERN.search(query):
        return ("unknown", None, None)
    
    if "/playlist?list=" in query.lower():
        playlist_id = query.split("list=")[1].split("&")[0].split("?")[0]
        if playlist_id:
            return ("playlist", None, playlist_id)
    
    match = YOUTUBE_ID_EXTRACT_RE.search(query)
    if not match or not (id_match := match.group(1)):
        return ("unknown", None, None)
    
    if len(id_match) == 11 and YOUTUBE_ID_RE.match(id_match):
        return ("video", id_match, None)
    
    return ("unknown", None, None)


def extract_thumbnail(info: dict) -> str:
    thumbs = info.get("thumbnails")
    if not isinstance(thumbs, list) or not thumbs:
        return ""
    
    for thumb in reversed(thumbs):
        if not isinstance(thumb, dict):
            continue
        url = thumb.get("url", "")
        if url and ("maxresdefault" in url or "hq720" in url):
            return url.split("?")[0]
    
    last_thumb = thumbs[-1]
    if isinstance(last_thumb, dict):
        return last_thumb.get("url", "").split("?")[0]
    return ""


def parse_duration_from_metadata(duration) -> Tuple[Optional[str], int]:
    if isinstance(duration, str):
        if duration and duration != "-":
            return duration, int(time_to_seconds(duration))
        return None, 0
    
    if isinstance(duration, dict):
        duration_text = duration.get("text")
        duration_seconds = duration.get("seconds")
        
        if duration_text:
            if duration_seconds:
                return duration_text, int(duration_seconds)
            if duration_text != "-":
                return duration_text, int(time_to_seconds(duration_text))
            return None, 0
        
        seconds_text = duration.get("secondsText")
        if seconds_text:
            return seconds_to_min(int(seconds_text)), int(seconds_text)
        return None, 0
    
    if isinstance(duration, (int, float)) and duration > 0:
        return seconds_to_min(int(duration)), int(duration)
    
    return None, 0


def parse_view_count_from_metadata(info: dict) -> Optional[str]:
    view_count_data = info.get("viewCount") or info.get("view_count")
    
    if isinstance(view_count_data, dict):
        return view_count_data.get("short") or view_count_data.get("text")
    
    if isinstance(view_count_data, str):
        return view_count_data
    
    if isinstance(view_count_data, (int, float)) and view_count_data > 0:
        if view_count_data >= 1_000_000_000:
            return f"{view_count_data / 1_000_000_000:.1f}B views"
        if view_count_data >= 1_000_000:
            return f"{view_count_data / 1_000_000:.1f}M views"
        if view_count_data >= 1_000:
            return f"{view_count_data / 1_000:.1f}K views"
        return f"{int(view_count_data)} views"
    
    return None


def _extract_common_metadata(info: dict, video_id: Optional[str], base_url: str) -> Optional[Tuple[str, str, str, Optional[str], Optional[str], Optional[str]]]:
    video_id = info.get("id") or video_id or ""
    if not video_id:
        return None
    
    title = info.get("title", "")
    url = info.get("link") or f"{base_url}{video_id}"
    thumbnail = extract_thumbnail(info)
    view_count = parse_view_count_from_metadata(info)
    
    channel = info.get("channel", {})
    channel_name = channel.get("name") if isinstance(channel, dict) else None
    
    return video_id, title, url, thumbnail, view_count, channel_name


def create_track_from_youtube_metadata(info: dict, video_id: Optional[str] = None, base_url: str = "https://www.youtube.com/watch?v=") -> Optional[Union["Track", "LiveTrack"]]:
    if not info:
        return None
    
    if info.get("isLiveNow", False):
        return LiveTrack.from_youtube_metadata(info, video_id, base_url)
    return Track.from_youtube_metadata(info, video_id, base_url)


@dataclass
class Track:
    id: str
    title: str
    url: str
    duration_min: Optional[str] = None
    duration_sec: int = 0
    thumbnail: str = None
    file_path: str = None
    message_id: int = 0
    time: int = 0
    user: str = None
    video: bool = False
    channel_name: str = None
    view_count: str = None
    
    @classmethod
    def from_youtube_metadata(cls, info: dict, video_id: Optional[str] = None, base_url: str = "https://www.youtube.com/watch?v=") -> Optional["Track"]:
        metadata = _extract_common_metadata(info, video_id, base_url)
        if not metadata:
            return None
        
        video_id, title, url, thumbnail, view_count, channel_name = metadata
        duration_str, duration_sec = parse_duration_from_metadata(info.get("duration"))
        
        return cls(
            id=video_id,
            title=title,
            url=url,
            duration_min=duration_str,
            duration_sec=duration_sec,
            thumbnail=thumbnail,
            view_count=view_count,
            channel_name=channel_name,
        )
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "link": self.url,
            "vidid": self.id,
            "duration_min": self.duration_min,
            "thumb": self.thumbnail or "",
            "view_count": self.view_count,
        }


@dataclass
class LiveTrack:
    id: str
    title: str
    url: str
    thumbnail: str = None
    file_path: str = None
    message_id: int = 0
    time: int = 0
    user: str = None
    video: bool = False
    channel_name: str = None
    view_count: str = None
    
    @classmethod
    def from_youtube_metadata(cls, info: dict, video_id: Optional[str] = None, base_url: str = "https://www.youtube.com/watch?v=") -> Optional["LiveTrack"]:
        metadata = _extract_common_metadata(info, video_id, base_url)
        if not metadata:
            return None
        
        video_id, title, url, thumbnail, view_count, channel_name = metadata
        
        return cls(
            id=video_id,
            title=title,
            url=url,
            thumbnail=thumbnail,
            view_count=view_count,
            channel_name=channel_name,
        )
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "link": self.url,
            "vidid": self.id,
            "duration_min": None,
            "thumb": self.thumbnail or "",
            "view_count": self.view_count,
        }
