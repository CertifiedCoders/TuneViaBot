# Authored By Certified Coders © 2025
import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from yt_dlp import YoutubeDL

from Tune.utils.downloader import yt_dlp_download
from Tune.utils.formatters import seconds_to_min


_SC_RE = re.compile(r"^https?://(?:www\.)?(soundcloud\.com|on\.soundcloud\.com)/.+", re.I)


def is_soundcloud_url(url: str) -> bool:
    """Check if a string contains a SoundCloud URL (both soundcloud.com and on.soundcloud.com)."""
    return bool(url and "soundcloud.com" in str(url))


# Simple cache for extracted info to avoid redundant extractions
# Key: URL, Value: (info_dict, timestamp)
_info_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
_cache_max_age = 300  # Cache for 5 minutes


def _get_cached_info(url: str) -> Optional[Dict[str, Any]]:
    """Get cached info if still valid."""
    import time
    if url in _info_cache:
        info, timestamp = _info_cache[url]
        if time.time() - timestamp < _cache_max_age:
            return info
        else:
            del _info_cache[url]
    return None


def _cache_info(url: str, info: Dict[str, Any]) -> None:
    """Cache extracted info."""
    import time
    _info_cache[url] = (info, time.time())


class SoundAPI:
    async def valid(self, link: str) -> bool:
        return bool(link and _SC_RE.match(link))

    async def is_playlist(self, url: str) -> bool:
        """
        Check if the URL is a SoundCloud playlist.
        
        Uses caching to avoid redundant extractions if called before playlist() or download().
        """
        try:
            info = await self._extract_info(url, allow_playlist=True, use_cache=True)
            return info is not None and info.get("_type") == "playlist"
        except Exception:
            return False

    async def _extract_info(self, url: str, allow_playlist: bool = False, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Extract info from SoundCloud URL using yt-dlp.
        
        Args:
            url: SoundCloud URL
            allow_playlist: Whether to allow playlist extraction
            use_cache: Whether to use cached info if available
        
        Returns:
            Extracted info dict or None
        """
        # Check cache first
        if use_cache:
            if cached := _get_cached_info(url):
                # If cached info is a playlist and we need playlist, or vice versa, use it
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
                    # If extracting from URL fails, use original info
                    pass

            # Cache the result
            if use_cache and info:
                _cache_info(url, info)

            return info
        except Exception:
            return None

    async def download(self, url: str) -> Union[Tuple[Dict[str, Any], str], bool]:
        """
        Download a SoundCloud track.
        
        Optimized to use cached info if available, reducing redundant extractions.
        """
        try:
            # Try to use cached info first (from previous is_playlist or details calls)
            info = await self._extract_info(url, allow_playlist=False, use_cache=True)
            if not info:
                return False
        except Exception:
            return False

        if info.get("_type") == "playlist":
            return False

        title = (info.get("title") or "SoundCloud").strip()
        try:
            duration_sec = int(info.get("duration") or 0)
        except Exception:
            duration_sec = 0

        uploader = info.get("uploader") or ""
        thumb = (
            info.get("thumbnail")
            or (info.get("thumbnails") or [{}])[0].get("url")
            or ""
        )

        # Download the track - yt_dlp_download will use cache if file exists
        out_path: Optional[str] = await yt_dlp_download(url, type="audio", title=title)
        if not out_path:
            return False

        details = {
            "title": title,
            "duration_sec": duration_sec,
            "duration_min": seconds_to_min(max(duration_sec, 0)),
            "uploader": uploader,
            "thumb": thumb,
            "filepath": out_path,
            "link": url,  # Store original URL for thumbnail extraction
        }
        return details, out_path

    async def details(self, url: str) -> Tuple[str, Optional[str], int, str, str]:
        """
        Extract track details similar to YouTube.details() format.
        Returns: (title, duration_min, duration_sec, thumbnail, url)
        """
        try:
            info = await self._extract_info(url)
            if not info or info.get("_type") == "playlist":
                raise ValueError("Invalid track or playlist")
        except Exception as e:
            raise ValueError(f"Failed to extract SoundCloud track info: {e}") from e

        title = (info.get("title") or "SoundCloud Track").strip()
        try:
            duration_sec = int(info.get("duration") or 0)
        except Exception:
            duration_sec = 0
        
        duration_min = seconds_to_min(max(duration_sec, 0)) if duration_sec > 0 else None
        
        thumb = (
            info.get("thumbnail")
            or (info.get("thumbnails") or [{}])[0].get("url")
            or ""
        )

        # Use the URL as the ID for SoundCloud tracks
        track_url = info.get("webpage_url") or url

        return title, duration_min, duration_sec, thumb, track_url

    async def playlist(self, url: str, limit: int, user_id) -> List[str]:
        """
        Extract playlist track URLs from a SoundCloud playlist.
        Returns a list of track URLs.
        """
        try:
            info = await self._extract_info(url, allow_playlist=True)
            if not info:
                return []
            
            if info.get("_type") != "playlist":
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
