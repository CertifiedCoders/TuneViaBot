# Authored By Certified Coders © 2025

import asyncio
import contextlib
import json
import os
import re
import time
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import VideosSearch, Video, Playlist

from Tune.utils.cookie_handler import COOKIE_PATH
from Tune.utils.downloader import yt_dlp_download
from Tune.utils.errors import capture_internal_err
from Tune.utils.formatters import time_to_seconds
from Tune.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL

_query_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_query_cache_lock = asyncio.Lock()
_video_cache: Dict[str, Tuple[float, Dict]] = {}
_video_cache_lock = asyncio.Lock()
_playlist_cache: Dict[str, Tuple[float, Dict]] = {}
_playlist_cache_lock = asyncio.Lock()
_formats_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_formats_lock = asyncio.Lock()
_live_cache: Dict[str, Tuple[float, bool, Optional[Dict]]] = {}
_live_cache_lock = asyncio.Lock()
LIVE_CACHE_TTL = 300

YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
_PLAYLIST_ID_RE = re.compile(r"[&?]list=([a-zA-Z0-9_-]+)")
_VIDEO_ID_PATTERN = re.compile(r"(?:v=|\/)([a-zA-Z0-9_-]{11})")
_YOUTUBE_URL_PATTERN = re.compile(r"(?:youtube\.com|youtu\.be|music\.youtube\.com)")


def _extract_video_id_from_url(url: str) -> Optional[str]:
    url = url.strip()
    if "youtu.be" in url.lower():
        vid = url.split("/")[-1].split("?")[0].split("&")[0]
        if vid and YOUTUBE_ID_RE.match(vid):
            return vid
    match = _VIDEO_ID_PATTERN.search(url, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_playlist_id_from_url(url: str) -> Optional[str]:
    match = _PLAYLIST_ID_RE.search(url, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _normalize_duration(duration: Union[str, Dict, None]) -> Optional[str]:
    if duration is None:
        return None
    if isinstance(duration, str):
        return duration
    if isinstance(duration, dict):
        seconds = duration.get("secondsText")
        if seconds:
            try:
                secs = int(seconds)
                mins = secs // 60
                secs = secs % 60
                return f"{mins}:{secs:02d}"
            except (ValueError, TypeError):
                pass
    return None


def _cookiefile_path() -> Optional[str]:
    path = str(COOKIE_PATH)
    try:
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    except Exception:
        pass
    return None


def _cookies_args() -> List[str]:
    path = _cookiefile_path()
    return ["--cookies", path] if path else []


def _extract_thumbnail(info: Dict) -> str:
    thumb = info.get("thumbnail", "")
    if not thumb:
        thumbnails = info.get("thumbnails", [])
        if thumbnails:
            # Try to get the last thumbnail first (usually highest quality)
            if isinstance(thumbnails, list) and len(thumbnails) > 0:
                thumb = thumbnails[-1].get("url", "") if isinstance(thumbnails[-1], dict) else ""
            # If no thumbnail from last element, try first element
            if not thumb and len(thumbnails) > 0:
                thumb = thumbnails[0].get("url", "") if isinstance(thumbnails[0], dict) else ""
    return thumb.split("?")[0] if thumb else ""


async def _exec_ytdlp_command(*args: str) -> Tuple[bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return b"", b"timeout"


def _evict_oldest_cache(cache: Dict, max_size: int):
    if len(cache) >= max_size:
        if len(cache) == 0:
            return
        oldest_key = min(cache.keys(), key=lambda k: cache[k][0] if isinstance(cache[k], tuple) else float('inf'))
        cache.pop(oldest_key, None)


def _update_cache_access(cache: Dict, key: str, now: float):
    if key in cache and isinstance(cache[key], tuple):
        old_val = cache[key]
        if len(old_val) >= 2:
            cache[key] = (now, old_val[1]) + old_val[2:]


@capture_internal_err
async def _cached_query_search(query: str) -> List[Dict]:
    key = f"q:{query.lower().strip()}"
    now = time.time()

    async with _query_cache_lock:
        if key in _query_cache:
            ts, val = _query_cache[key]
            if now - ts < YOUTUBE_META_TTL:
                _query_cache[key] = (now, val)
                return val
            _query_cache.pop(key, None)
        if len(_query_cache) >= YOUTUBE_META_MAX:
            _evict_oldest_cache(_query_cache, YOUTUBE_META_MAX)

    try:
        search = VideosSearch(query, limit=1)
        data = await search.next()
        result = data.get("result", [])
    except Exception:
        result = []

    if result:
        async with _query_cache_lock:
            _query_cache[key] = (now, result)

    return result


@capture_internal_err
async def _cached_video_get(video_url: str) -> Optional[Dict]:
    key = f"v:{video_url}"
    now = time.time()

    async with _video_cache_lock:
        if key in _video_cache:
            ts, val = _video_cache[key]
            if now - ts < YOUTUBE_META_TTL:
                _video_cache[key] = (now, val)
                return val
            _video_cache.pop(key, None)
        if len(_video_cache) >= YOUTUBE_META_MAX:
            _evict_oldest_cache(_video_cache, YOUTUBE_META_MAX)

    try:
        video = await Video.get(video_url)
        if video:
            async with _video_cache_lock:
                _video_cache[key] = (now, video)
            return video
    except Exception:
        pass

    return None


@capture_internal_err
async def _cached_playlist_get(playlist_url: str) -> Optional[Dict]:
    key = f"p:{playlist_url}"
    now = time.time()

    async with _playlist_cache_lock:
        if key in _playlist_cache:
            ts, val = _playlist_cache[key]
            if now - ts < YOUTUBE_META_TTL:
                _playlist_cache[key] = (now, val)
                return val
            _playlist_cache.pop(key, None)
        if len(_playlist_cache) >= YOUTUBE_META_MAX:
            _evict_oldest_cache(_playlist_cache, YOUTUBE_META_MAX)

    try:
        playlist = await Playlist.get(playlist_url)
        if playlist:
            async with _playlist_cache_lock:
                _playlist_cache[key] = (now, playlist)
            return playlist
    except Exception:
        pass

    return None


@capture_internal_err
async def _get_live_video_info(link: str, video_id: str) -> Optional[Dict]:
    """
    Get live video info using VideosSearch and yt-dlp.
    This function is specifically for live YouTube videos as Video.get() doesn't work for them.
    """
    normalized_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Try VideosSearch first
    try:
        search = VideosSearch(normalized_url, limit=1)
        data = await search.next()
        results = data.get("result", [])
        if results:
            result = results[0]
            # Convert VideosSearch result to compatible format
            info = {
                "id": result.get("id", video_id),
                "title": result.get("title", ""),
                "duration": None,  # Live videos don't have duration
                "thumbnails": result.get("thumbnails", []),
                "thumbnail": result.get("thumbnails", [{}])[0].get("url", "") if result.get("thumbnails") else "",
                "link": normalized_url,
                "webpage_url": normalized_url,
                "viewCount": result.get("viewCount", {}),
            }
            # Verify it's actually live using yt-dlp and merge better data
            try:
                stdout, _ = await _exec_ytdlp_command(
                    "yt-dlp", *(_cookies_args()), "--dump-json", "--no-warnings", normalized_url
                )
                if stdout:
                    yt_dlp_info = json.loads(stdout.decode())
                    # Merge yt-dlp info for more complete data (even if not currently live)
                    info["title"] = yt_dlp_info.get("title", info["title"])
                    info["thumbnail"] = yt_dlp_info.get("thumbnail", info["thumbnail"])
                    info["thumbnails"] = yt_dlp_info.get("thumbnails", info["thumbnails"])
                    info["description"] = yt_dlp_info.get("description", "")
                    info["uploader"] = yt_dlp_info.get("uploader", "")
                    info["is_live"] = yt_dlp_info.get("is_live", False)
                    return info
            except Exception:
                pass
            # If VideosSearch found it, return it anyway (might be upcoming live or live URL)
            return info
    except Exception:
        pass
    
    # Fallback to yt-dlp only
    try:
        stdout, stderr = await _exec_ytdlp_command(
            "yt-dlp", *(_cookies_args()), "--dump-json", "--no-warnings", normalized_url
        )
        if stdout:
            info = json.loads(stdout.decode())
            # Return info if it's a live video or if the URL is a live URL pattern
            if info.get("is_live") or "/live/" in link.lower():
                return info
    except Exception:
        pass
    
    return None


class YouTubeAPI:
    def __init__(self) -> None:
        self.video_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self.live_url = "https://www.youtube.com/watch?v="
        self._url_pattern = _YOUTUBE_URL_PATTERN

    def _classify_url(self, url: str) -> Tuple[str, Optional[str], Optional[str]]:
        original_url = url.strip()
        url_lower = original_url.lower()

        playlist_id = _extract_playlist_id_from_url(original_url)
        if playlist_id:
            return ("playlist", None, playlist_id)

        if "/live/" in url_lower or "youtube.com/live/" in url_lower:
            video_id = _extract_video_id_from_url(original_url)
            if video_id:
                return ("live", video_id, None)

        video_id = _extract_video_id_from_url(original_url)
        if video_id:
            return ("video", video_id, None)

        return ("unknown", None, None)

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            return f"{self.video_url}{videoid.strip()}"

        link = link.strip()
        url_type, video_id, playlist_id = self._classify_url(link)

        if url_type == "video" and video_id:
            return f"{self.video_url}{video_id}"
        elif url_type == "playlist" and playlist_id:
            return f"{self.playlist_url}{playlist_id}"
        elif url_type == "live" and video_id:
            return f"{self.live_url}{video_id}"

        if "youtu.be" in link:
            vid = link.split("/")[-1].split("?")[0].split("&")[0]
            if vid:
                return f"{self.video_url}{vid}"
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            vid = link.split("/")[-1].split("?")[0]
            if vid:
                return f"{self.video_url}{vid}"

        return link.split("&")[0]

    def _convert_video_info_to_legacy_format(self, info: Dict) -> Dict:
        video_id = info.get("id") or ""
        duration = info.get("duration")

        duration_str = _normalize_duration(duration)
        if isinstance(duration, dict) and duration.get("secondsText"):
            try:
                duration_sec = int(duration["secondsText"])
            except (ValueError, TypeError):
                duration_sec = 0
        else:
            duration_sec = int(time_to_seconds(duration_str)) if duration_str else 0

        thumbnails = info.get("thumbnails", [])
        thumbnail = ""
        if thumbnails:
            thumbnail = thumbnails[0].get("url", "") if isinstance(thumbnails, list) else ""
        if not thumbnail:
            thumbnail = info.get("thumbnail", "")

        return {
            "id": video_id,
            "title": info.get("title", ""),
            "duration": duration_str,
            "duration_sec": duration_sec,
            "thumbnail": thumbnail.split("?")[0] if thumbnail else "",
            "thumbnails": thumbnails if thumbnails else [],
            "link": f"{self.video_url}{video_id}" if video_id else info.get("link", ""),
            "webpage_url": f"{self.video_url}{video_id}" if video_id else info.get("link", ""),
        }

    @capture_internal_err
    async def _get_video_info(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[Dict]:
        if isinstance(videoid, str) and videoid.strip():
            normalized_url = f"{self.video_url}{videoid.strip()}"
            return await _cached_video_get(normalized_url)

        url_type, video_id, playlist_id = self._classify_url(link)

        if url_type == "video" and video_id:
            normalized_url = f"{self.video_url}{video_id}"
            video_info = await _cached_video_get(normalized_url)
            if video_info:
                return video_info

        if url_type == "unknown" or not self._url_pattern.search(link):
            results = await _cached_query_search(link)
            if results:
                first_result = results[0]
                video_id = first_result.get("id")
                if video_id:
                    normalized_url = f"{self.video_url}{video_id}"
                    video_info = await _cached_video_get(normalized_url)
                    if video_info:
                        return video_info
                    return first_result
            return None

        video_id = _extract_video_id_from_url(link)
        if video_id:
            normalized_url = f"{self.video_url}{video_id}"
            return await _cached_video_get(normalized_url)

        return None

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
    async def is_live(self, link: str) -> bool:
        prepared = self._prepare_link(link)
        url_type, video_id, _ = self._classify_url(link)

        if url_type == "live":
            return True

        cache_key = f"live:{prepared}"
        now = time.time()

        async with _live_cache_lock:
            if cache_key in _live_cache:
                ts, val, cached_info = _live_cache[cache_key]
                if now - ts < LIVE_CACHE_TTL:
                    return val
                _live_cache.pop(cache_key, None)
            _evict_oldest_cache(_live_cache, YOUTUBE_META_MAX)

        try:
            stdout, stderr = await _exec_ytdlp_command("yt-dlp", *(_cookies_args()), "--dump-json", prepared)
            if not stdout or stdout == b"timeout":
                result = False
                info = None
            else:
                try:
                    info = json.loads(stdout.decode())
                    result = bool(info.get("is_live"))
                except json.JSONDecodeError:
                    result = False
                    info = None
        except Exception:
            result = False
            info = None

        async with _live_cache_lock:
            _live_cache[cache_key] = (now, result, info)

        return result

    @capture_internal_err
    async def details(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[str, Optional[str], int, str, str]:
        info = await self._get_video_info(link, videoid)
        if not info:
            raise ValueError("Video not found")

        if not info.get("duration_sec"):
            info = self._convert_video_info_to_legacy_format(info)

        title = info.get("title", "")
        duration_str = info.get("duration")
        duration_sec = info.get("duration_sec", 0)
        thumbnail = _extract_thumbnail(info)
        vidid = info.get("id", "")

        return title, duration_str, duration_sec, thumbnail, vidid

    @capture_internal_err
    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._get_video_info(link, videoid)
        return info.get("title", "") if info else ""

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._get_video_info(link, videoid)
        if not info:
            return None
        duration = info.get("duration")
        return _normalize_duration(duration)

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._get_video_info(link, videoid)
        return _extract_thumbnail(info) if info else ""

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        info = await self._get_video_info(link, videoid)

        if not info:
            prepared_link = self._prepare_link(link, videoid)
            stdout, stderr = await _exec_ytdlp_command(
                "yt-dlp", *(_cookies_args()), "--dump-json", "--no-warnings", prepared_link
            )

            if not stdout:
                stderr_msg = stderr.decode().strip() if stderr else "Empty response"
                raise ValueError(f"Failed to get video info: {stderr_msg}")

            try:
                info = json.loads(stdout.decode())
            except json.JSONDecodeError as json_err:
                raise ValueError(f"Failed to parse video info: {json_err}")

        if not info.get("duration_sec"):
            info = self._convert_video_info_to_legacy_format(info)

        thumb = _extract_thumbnail(info)
        vidid = info.get("id", "")

        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url") or info.get("link") or f"{self.video_url}{vidid}",
            "vidid": vidid,
            "duration_min": info.get("duration") or _normalize_duration(info.get("duration")) or None,
            "thumb": thumb,
        }

        return details, vidid

    @capture_internal_err
    async def live_track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        """
        Get track details specifically for live videos.
        This method uses _get_live_video_info() and ensures duration_min is None for live streams.
        Reuses cached info from is_live() if available to avoid redundant API calls.
        """
        # Extract video ID from link or videoid
        if isinstance(videoid, str) and videoid.strip():
            video_id = videoid.strip()
        else:
            url_type, video_id, _ = self._classify_url(link)
            if not video_id:
                video_id = _extract_video_id_from_url(link)
        
        if not video_id:
            raise ValueError("Could not extract video ID from live URL")

        prepared_link = self._prepare_link(link, videoid or video_id)
        cache_key = f"live:{prepared_link}"
        now = time.time()
        info = None

        async with _live_cache_lock:
            if cache_key in _live_cache:
                ts, is_live_val, cached_info = _live_cache[cache_key]
                if now - ts < LIVE_CACHE_TTL and cached_info:
                    info = cached_info.copy()

        if not info:
            info = await _get_live_video_info(link if link else f"{self.video_url}{video_id}", video_id)
            
            if not info:
                stdout, stderr = await _exec_ytdlp_command(
                    "yt-dlp", *(_cookies_args()), "--dump-json", "--no-warnings", prepared_link
                )

                if not stdout:
                    stderr_msg = stderr.decode().strip() if stderr else "Empty response"
                    raise ValueError(f"Failed to get live video info: {stderr_msg}")

                try:
                    info = json.loads(stdout.decode())
                except json.JSONDecodeError as json_err:
                    raise ValueError(f"Failed to parse live video info: {json_err}")

        # Ensure live video structure
        if not info.get("duration_sec"):
            info["duration_sec"] = 0
        info["duration"] = None

        thumb = _extract_thumbnail(info)
        vidid = info.get("id", video_id)

        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url") or info.get("link") or f"{self.video_url}{vidid}",
            "vidid": vidid,
            "duration_min": None,  # Explicitly None for live videos
            "thumb": thumb,
        }

        return details, vidid

    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        stdout, stderr = await _exec_ytdlp_command(
            "yt-dlp",
            *(_cookies_args()),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            link,
        )
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    @capture_internal_err
    async def playlist(
        self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None
    ) -> List[str]:
        if videoid:
            normalized_url = f"{self.playlist_url}{str(videoid)}"
        else:
            url_type, _, playlist_id = self._classify_url(link)
            if url_type == "playlist" and playlist_id:
                normalized_url = f"{self.playlist_url}{playlist_id}"
            else:
                normalized_url = self._prepare_link(link).split("&")[0]

        try:
            playlist_info = await _cached_playlist_get(normalized_url)
            if playlist_info:
                videos = playlist_info.get("videos", [])
                if videos:
                    items = []
                    for video in videos[:limit]:
                        vid_id = video.get("id") if isinstance(video, dict) else getattr(video, "id", None)
                        if vid_id:
                            items.append(vid_id)
                    if items:
                        return items
        except Exception:
            pass

        stdout, _ = await _exec_ytdlp_command(
            "yt-dlp",
            *(_cookies_args()),
            "-i",
            "--get-id",
            "--flat-playlist",
            "--playlist-end",
            str(limit),
            "--skip-download",
            normalized_url,
        )
        items = stdout.decode().strip().split("\n") if stdout else []
        return [i for i in items if i]

    @capture_internal_err
    async def formats(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        key = f"f:{link}"
        now = time.time()

        async with _formats_lock:
            cached = _formats_cache.get(key)
            if cached and now - cached[0] < YOUTUBE_META_TTL:
                return cached[1], cached[2]

        opts = {"quiet": True}
        if cf := _cookiefile_path():
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
    async def slider(
        self, link: str, query_type: int, videoid: Union[str, bool, None] = None
    ) -> Tuple[str, Optional[str], str, str]:
        if videoid:
            query = f"{self.video_url}{videoid}"
        else:
            url_type, video_id, _ = self._classify_url(link)
            if url_type in ("video", "live") and video_id:
                query = f"{self.video_url}{video_id}"
            else:
                query = link

        search = VideosSearch(query, limit=10)
        data = await search.next()
        results = data.get("result", [])

        if not results or query_type >= len(results):
            raise IndexError(
                f"Query type index {query_type} out of range (found {len(results)} results)"
            )

        r = results[query_type]
        duration = r.get("duration")
        duration_str = _normalize_duration(duration) if isinstance(duration, (str, dict)) else duration

        return (
            r.get("title", ""),
            duration_str,
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
        normalized_link = self._prepare_link(link, videoid)

        if video:
            if await self.is_live(normalized_link):
                status, stream_url = await self.video(normalized_link)
                if status == 1:
                    return stream_url, None
                return None, None

            if not title:
                info = await self._get_video_info(normalized_link)
                title = info.get("title", "") if info else ""

            p = await yt_dlp_download(normalized_link, type="video", title=title)
            return (p, True) if p else (None, None)

        if not title:
            info = await self._get_video_info(normalized_link)
            title = info.get("title", "") if info else ""

        p = await yt_dlp_download(normalized_link, type="audio", title=title)
        return (p, True) if p else (None, None)


YouTube = YouTubeAPI()
