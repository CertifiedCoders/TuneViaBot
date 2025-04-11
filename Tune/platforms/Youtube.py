import asyncio
import json
import os
import re
from typing import Union, Optional

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from Tune.utils.database import is_on_off
from Tune.utils.formatters import time_to_seconds


cookies_file = "Tune/cookies/cookies.txt"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
)


async def shell_cmd(cmd: list[str]) -> tuple[str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return out.decode("utf-8"), err.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.listbase = "https://youtube.com/playlist?list="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def fast_search(self, query: str) -> dict:
        cmd = [
            "yt-dlp",
            "--cookies", cookies_file,
            "--no-warnings",
            "--quiet",
            "-j",
            f"ytsearch1:{query}"
        ]
        stdout, stderr = await shell_cmd(cmd)
        if stderr and not stdout:
            raise ValueError(f"yt-dlp error: {stderr.strip()}")

        if not stdout.strip():
            raise ValueError(f"No results found for query: {query}")

        try:
            data = json.loads(stdout.strip())
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse yt-dlp JSON: {e}")

        title = data.get("title", "Unknown Title")
        duration = data.get("duration") or 0
        webpage_url = data.get("webpage_url")
        thumb = data.get("thumbnail") or ""

        if isinstance(duration, int) and duration > 0:
            duration_min = self._sec_to_min_str(duration)
        else:
            duration_min = None

        return {
            "title": title,
            "duration": duration,
            "url": webpage_url,
            "id": data.get("id"),
            "thumb": thumb,
            "duration_min": duration_min
        }

    def _sec_to_min_str(self, secs: int) -> str:
        if secs < 60:
            return f"0:{secs:02d}"
        elif secs < 3600:
            m, s = divmod(secs, 60)
            return f"{m}:{s:02d}"
        else:
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            return f"{h}:{m:02d}:{s:02d}"

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Optional[str]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        text = ""
        offset = None
        length = None

        for msg in messages:
            if offset:
                break
            if msg.entities:
                for entity in msg.entities:
                    if entity.type == MessageEntityType.URL:
                        text = msg.text or msg.caption
                        offset, length = entity.offset, entity.length
                        break
            elif msg.caption_entities:
                for entity in msg.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]



    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        vs = VideosSearch(link, limit=1)
        results = await vs.next()
        items = results.get("result") or []
        if not items:
            raise ValueError("No details found for this link/query.")

        item = items[0]
        title = item["title"]
        duration_min = item["duration"]
        thumbnail = item["thumbnails"][0]["url"].split("?")[0]
        vidid = item["id"]
        duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0

        return title, duration_min, duration_sec, thumbnail, vidid

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        vs = VideosSearch(link, limit=1)
        res = await vs.next()
        items = res.get("result") or []
        if not items:
            raise ValueError("No track result found.")
        item = items[0]

        track_details = {
            "title": item["title"],
            "link": item["link"],
            "vidid": item["id"],
            "duration_min": item["duration"],
            "thumb": item["thumbnails"][0]["url"].split("?")[0],
        }
        return track_details, item["id"]

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        vs = VideosSearch(link, limit=10)
        res = await vs.next()
        items = res.get("result") or []
        if not items:
            return ("Unknown", "0:00", "", "")
        if query_type >= len(items):
            query_type = 0

        it = items[query_type]
        return (
            it["title"],
            it["duration"] or "0:00",
            it["thumbnails"][0]["url"].split("?")[0],
            it["id"],
        )

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]

        cmd_str = (
            f'yt-dlp --cookies {cookies_file} '
            f'--http-header "User-Agent:{USER_AGENT}" '
            f"-i --get-id --flat-playlist --playlist-end {limit} --skip-download {link}"
        )
        proc = await asyncio.create_subprocess_shell(
            cmd_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        out_str = out.decode("utf-8")
        lines = [x.strip() for x in out_str.split("\n") if x.strip()]
        return lines


    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        cmd = [
            "yt-dlp",
            "--cookies", cookies_file,
            "--http-header", f"User-Agent:{USER_AGENT}",
            "-g",
            "-f", "best[height<=?720][width<=?1280]",
            link
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        return 0, stderr.decode()

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        ytdl_opts = {
            "quiet": True,
            "--cookies": cookies_file,
            "http_headers": {"User-Agent": USER_AGENT},
        }
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        info = ydl.extract_info(link, download=False)
        formats_available = []
        for fmt in info["formats"]:
            if "dash" in fmt.get("format", "").lower():
                continue
            if all(k in fmt for k in ("format", "filesize", "format_id", "ext", "format_note")):
                formats_available.append(
                    {
                        "format": fmt["format"],
                        "filesize": fmt["filesize"],
                        "format_id": fmt["format_id"],
                        "ext": fmt["ext"],
                        "format_note": fmt["format_note"],
                        "yturl": link,
                    }
                )
        return formats_available, link

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[str, None] = None,
        title: Union[str, None] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "--cookies": cookies_file,
                "http_headers": {"User-Agent": USER_AGENT},
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, download=False)
            file_path = f"downloads/{info['id']}.{info['ext']}"
            if not os.path.exists(file_path):
                x.download([link])
            return file_path

        def video_dl():
            ydl_optssx = {
                "format": "(best[height<=?720][width<=?1280])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "--cookies": cookies_file,
                "http_headers": {"User-Agent": USER_AGENT},
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, download=False)
            file_path = f"downloads/{info['id']}.{info['ext']}"
            if not os.path.exists(file_path):
                x.download([link])
            return file_path

        def song_video_dl():
            fmts = f"{format_id}+140"
            outtmpl = f"downloads/{title}"
            ydl_optssx = {
                "format": fmts,
                "outtmpl": outtmpl,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
                "--cookies": cookies_file,
                "http_headers": {"User-Agent": USER_AGENT},
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            outtmpl = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": outtmpl,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "--cookies": cookies_file,
                "http_headers": {"User-Agent": USER_AGENT},
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            return f"downloads/{title}.mp4"

        if songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            return f"downloads/{title}.mp3"

        direct = True
        if video:
            if await is_on_off(1):
                downloaded_file = await loop.run_in_executor(None, video_dl)
            else:
                cmd = [
                    "yt-dlp",
                    "--cookies", cookies_file,
                    "--http-header", f"User-Agent:{USER_AGENT}",
                    "-g",
                    "-f", "best[height<=?720][width<=?1280]",
                    link
                ]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode().split("\n")[0]
                    direct = None
                else:
                    return
        else:
            downloaded_file = await loop.run_in_executor(None, audio_dl)

        return downloaded_file, direct
