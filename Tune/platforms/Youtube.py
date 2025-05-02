import asyncio
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from Tune.utils.database import is_on_off
from Tune.utils.downloader import api_download_song
from Tune.utils.errors import capture_internal_err
from Tune.utils.formatters import time_to_seconds

cookies_file = "Tune/assets/cookies.txt"

_cache = {}


@capture_internal_err
async def shell_cmd(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    return (out or err).decode()


@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    if query in _cache:
        return _cache[query]
    search = VideosSearch(query, limit=1)
    results = await search.next()
    _cache[query] = results.get("result", [])
    return _cache[query]


class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()

        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]

        return link.split("&")[0]

    @capture_internal_err
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = msg.entities or msg.caption_entities or []
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset : ent.offset + ent.length]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url
        return None

    @capture_internal_err
    async def _fetch_video_info(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
        if use_cache and not query.startswith("http"):
            result = await cached_youtube_search(query)
        else:
            search = VideosSearch(query, limit=1)
            result = (await search.next()).get("result", [])
        return result[0] if result else None

    @capture_internal_err
    async def is_live(self, link: str) -> bool:
        prepared = self._prepare_link(link)
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--cookies", cookies_file, "--dump-json", prepared,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if not stdout:
            return False
        try:
            info = json.loads(stdout.decode())
            return bool(info.get("is_live"))
        except json.JSONDecodeError:
            return False

    @capture_internal_err
    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Video not found")

        duration_text = info.get("duration")
        duration_sec = int(time_to_seconds(duration_text)) if duration_text else 0
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]

        try:
            views = info["viewCount"]["short"]
        except Exception:
            views = "Unknown Views"

        return (
            info.get("title", ""),
            duration_text,
            duration_sec,
            thumb,
            info.get("id", ""),
            views,
        )


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
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--cookies", cookies_file, "-g", "-f", "best[height<=?720][width<=?1280]",
            link, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    @capture_internal_err
    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        if videoid:
            link = self.playlist_url + str(videoid)
        link = link.split("&")[0]
        cmd = (
            f"yt-dlp --cookies {cookies_file} -i --get-id --flat-playlist "
            f"--playlist-end {limit} --skip-download {link}"
        )
        data = await shell_cmd(cmd)
        return [item for item in data.strip().split("\n") if item]

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        try:
            info = await self._fetch_video_info(self._prepare_link(link, videoid))
            if not info:
                raise ValueError("Track not found via API")
        except Exception:
            prepared = self._prepare_link(link, videoid)
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp", "--cookies", cookies_file, "--dump-json", prepared,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            if not stdout:
                raise ValueError("Track not found (yt-dlp fallback)")
            try:
                info = json.loads(stdout.decode())
            except json.JSONDecodeError:
                raise ValueError("Failed to parse yt-dlp output")

        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", self._prepare_link(link, videoid)),
            "vidid": info.get("id", ""),
            "duration_min": info.get("duration") if isinstance(info.get("duration"), str) else None,
            "thumb": thumb,
        }
        return details, info.get("id", "")

    @capture_internal_err
    async def formats(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        opts = {"quiet": True, "cookiefile": cookies_file}
        formats: List[Dict] = []
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            for fmt in info.get("formats", []):
                if "dash" in fmt.get("format", "").lower():
                    continue
                if all(k in fmt for k in ("format", "filesize", "format_id", "ext", "format_note")):
                    formats.append({
                        "format": fmt["format"],
                        "filesize": fmt["filesize"],
                        "format_id": fmt["format_id"],
                        "ext": fmt["ext"],
                        "format_note": fmt["format_note"],
                        "yturl": link,
                    })
        return formats, link

    @capture_internal_err
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], str, str]:
        search = VideosSearch(self._prepare_link(link, videoid), limit=10)
        results = (await search.next()).get("result", [])
        if not results or query_type >= len(results):
            raise IndexError("Query type index out of range")
        res = results[query_type]
        return (
            res.get("title", ""),
            res.get("duration"),
            res.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
            res.get("id", ""),
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
        link = self._prepare_link(link, videoid)
        loop = asyncio.get_running_loop()

        def audio_dl() -> str:
            opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookies_file,
                "noplaylist": True,
                "concurrent_fragment_downloads": 5,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                path = f"downloads/{info['id']}.{info['ext']}"
                if os.path.exists(path):
                    return path
                ydl.download([link])
                return path


        def video_dl() -> str:
            opts = {
                "format": "best[height<=?720][width<=?1280]",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookies_file,
                "noplaylist": True,
                "concurrent_fragment_downloads": 5,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                path = f"downloads/{info['id']}.{info['ext']}"
                if os.path.exists(path):
                    return path
                ydl.download([link])
                return path


        def song_video_dl() -> None:
            opts = {
                "format": f"{format_id}+140",
                "outtmpl": f"downloads/{title}",
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
                "cookiefile": cookies_file,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([link])

        def song_audio_dl() -> None:
            opts = {
                "format": format_id,
                "outtmpl": f"downloads/{title}.%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "cookiefile": cookies_file,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([link])

        # ---------------- decision tree ---------------- #

        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            return f"downloads/{title}.mp4", True

        if songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            return f"downloads/{title}.mp3", True

        if video:
            if await self.is_live(link):
                status, stream_url = await self.video(link)
                if status == 1:
                    return stream_url, None
                raise ValueError("Unable to fetch live stream link")

            if await is_on_off(1):
                path = await loop.run_in_executor(None, video_dl)
                return path, True

            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "--cookies",
                cookies_file,
                "-g",
                "-f",
                "best[height<=?720][width<=?1280]",
                link,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if stdout:
                return stdout.decode().split("\n")[0], None
            return None, None

        try:
            api_path = await asyncio.wait_for(api_download_song(link), timeout=3.0)
            if api_path:
                return api_path, True
        except:
            pass

        path = await loop.run_in_executor(None, audio_dl)
        return path, True
