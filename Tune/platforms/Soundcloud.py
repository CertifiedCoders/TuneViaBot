# Authored By Certified Coders © 2025
import asyncio
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from yt_dlp import YoutubeDL

from Tune.utils.downloader import yt_dlp_download
from Tune.utils.formatters import seconds_to_min

_SC_RE = re.compile(r"^https?://(?:www\.)?(soundcloud\.com|on\.soundcloud\.com)/.+", re.I)

_info_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
_cache_max_age = 300


def is_soundcloud_url(url: str) -> bool:
    return bool(url and "soundcloud.com" in str(url))


def _get_cached_info(url: str) -> Optional[Dict[str, Any]]:
    if url in _info_cache:
        info, timestamp = _info_cache[url]
        if time.time() - timestamp < _cache_max_age:
            return info
        del _info_cache[url]
    return None


def _cache_info(url: str, info: Dict[str, Any]) -> None:
    _info_cache[url] = (info, time.time())


def _extract_duration(info: Dict[str, Any]) -> int:
    try:
        return int(info.get("duration") or 0)
    except Exception:
        return 0


def _extract_thumbnail(info: Dict[str, Any]) -> str:
    return (
        info.get("thumbnail")
        or (info.get("thumbnails") or [{}])[0].get("url")
        or ""
    )


def _extract_title(info: Dict[str, Any], default: str = "SoundCloud") -> str:
    return (info.get("title") or default).strip()


class SoundAPI:
    async def valid(self, link: str) -> bool:
        return bool(link and _SC_RE.match(link))

    async def is_playlist(self, url: str) -> bool:
        try:
            info = await self._extract_info(url, allow_playlist=True, use_cache=True)
            return info is not None and info.get("_type") == "playlist"
        except Exception:
            return False

    async def _extract_info(self, url: str, allow_playlist: bool = False, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        if use_cache:
            if cached := _get_cached_info(url):
                if allow_playlist or cached.get("_type") != "playlist":
                    return cached
        
        def _run(u: str):
            opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
            }
            if not allow_playlist:
                opts["noplaylist"] = True
            with YoutubeDL(opts) as ydl:
                return ydl.extract_info(u, download=False)

        try:
            loop = asyncio.get_running_loop()
            info = await loop.run_in_executor(None, _run, url)
            
            if not info:
                return None

            _type = str(info.get("_type", ""))
            if _type in ("url", "url_transparent") and info.get("url"):
                try:
                    info = await loop.run_in_executor(None, _run, info["url"])
                except Exception:
                    pass

            if use_cache and info:
                _cache_info(url, info)

            return info
        except Exception:
            return None

    async def download(self, url: str) -> Union[Tuple[Dict[str, Any], str], bool]:
        try:
            info = await self._extract_info(url, allow_playlist=False, use_cache=True)
            if not info or info.get("_type") == "playlist":
                return False
        except Exception:
            return False

        title = _extract_title(info)
        duration_sec = _extract_duration(info)
        uploader = info.get("uploader") or ""
        thumb = _extract_thumbnail(info)

        out_path = await yt_dlp_download(url, type="audio", title=title)
        if not out_path:
            return False

        details = {
            "title": title,
            "duration_sec": duration_sec,
            "duration_min": seconds_to_min(max(duration_sec, 0)),
            "uploader": uploader,
            "thumb": thumb,
            "filepath": out_path,
            "link": url,
        }
        return details, out_path

    async def details(self, url: str) -> Tuple[str, Optional[str], int, str, str]:
        try:
            info = await self._extract_info(url)
            if not info or info.get("_type") == "playlist":
                raise ValueError("Invalid track or playlist")
        except Exception as e:
            raise ValueError(f"Failed to extract SoundCloud track info: {e}") from e

        title = _extract_title(info, "SoundCloud Track")
        duration_sec = _extract_duration(info)
        duration_min = seconds_to_min(max(duration_sec, 0)) if duration_sec > 0 else None
        thumb = _extract_thumbnail(info)
        track_url = info.get("webpage_url") or url

        return title, duration_min, duration_sec, thumb, track_url

    async def playlist(self, url: str, limit: int, user_id) -> List[str]:
        try:
            info = await self._extract_info(url, allow_playlist=True)
            if not info or info.get("_type") != "playlist":
                return []
            
            entries = info.get("entries", [])
            if not entries:
                return []

            track_urls = []
            for entry in entries[:limit]:
                if entry and entry.get("webpage_url"):
                    track_urls.append(entry["webpage_url"])
            
            return track_urls
        except Exception:
            return []


SoundCloud = SoundAPI()