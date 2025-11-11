import asyncio
import re
from typing import Any, Dict, Optional, Tuple, Union

from yt_dlp import YoutubeDL

from Tune.utils.downloader import download_audio_concurrent
from Tune.utils.formatters import seconds_to_min


_SC_RE = re.compile(r"^https?://(soundcloud\.com|on\.soundcloud\.com)/.+", re.I)


class SoundAPI:
    async def valid(self, link: str) -> bool:
        return bool(link and _SC_RE.match(link))

    async def _extract_info(self, url: str) -> Dict[str, Any]:
        def _run():
            opts = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "skip_download": True,
            }
            with YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _run)

    async def download(self, url: str) -> Union[Tuple[Dict[str, Any], str], bool]:
        try:
            info = await self._extract_info(url)
        except Exception:
            return False

        if not info or info.get("_type") == "playlist":
            return False

        title = info.get("title") or "SoundCloud"
        duration_sec = int(info.get("duration") or 0)
        uploader = info.get("uploader") or ""

        out_path: Optional[str] = await download_audio_concurrent(url)
        if not out_path:
            return False

        details = {
            "title": title,
            "duration_sec": duration_sec,
            "duration_min": seconds_to_min(duration_sec),
            "uploader": uploader,
            "filepath": out_path,
        }
        return details, out_path