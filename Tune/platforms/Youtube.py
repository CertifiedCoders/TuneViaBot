import asyncio
import os
import re
from typing import Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from Tune.utils.database import is_on_off
from Tune.utils.formatters import time_to_seconds

cookies_file = "Tune/cookies/cookies.txt"


async def shell_cmd(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, errorz = await proc.communicate()
    decoded_out = out.decode("utf-8")
    if errorz:
        decoded_err = errorz.decode("utf-8")
        if "unavailable videos are hidden" in decoded_err.lower():
            return decoded_out
        return decoded_err
    return decoded_out


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Optional[str]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset, length = None, None
        for msg in messages:
            if offset is not None:
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
        if offset is None:
            return None
        return text[offset : offset + length]

    async def details(
        self, link: str, videoid: Union[bool, str] = None
    ) -> Tuple[str, str, int, str, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        search = VideosSearch(link, limit=1)
        result = (await search.next()).get("result", [])
        if not result:
            return ("", "", 0, "", "")
        video = result[0]
        title = video.get("title", "Unknown Title")
        duration_min = video.get("duration")
        thumbnail = video.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
        vidid = video.get("id", "")
        duration_sec = (
            0 if str(duration_min) == "None" else int(time_to_seconds(duration_min))
        )
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        search = VideosSearch(link, limit=1)
        result = (await search.next()).get("result", [])
        if result:
            return result[0].get("title", "Unknown Title")
        return "Unknown Title"

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> int:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        search = VideosSearch(link, limit=1)
        result = (await search.next()).get("result", [])
        if result:
            return result[0].get("duration", 0)
        return 0

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        search = VideosSearch(link, limit=1)
        result = (await search.next()).get("result", [])
        if result:
            thumb = result[0].get("thumbnails", [{}])[0].get("url", "")
            return thumb.split("?")[0]
        return ""

    async def video(
        self, link: str, videoid: Union[bool, str] = None
    ) -> Tuple[int, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
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
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        return 0, stderr.decode()

    async def playlist(
        self, link: str, limit: int, user_id, videoid: Union[bool, str] = None
    ) -> list:
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist_data = await shell_cmd(
            f"yt-dlp --cookies {cookies_file} -i --get-id --flat-playlist --playlist-end {limit} --skip-download {link}"
        )
        return [item for item in playlist_data.split("\n") if item]

    async def track(
        self, link: str, videoid: Union[bool, str] = None
    ) -> Tuple[dict, Optional[str]]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        search = VideosSearch(link, limit=1)
        result = (await search.next()).get("result", [])
        if not result:
            return {}, None
        video = result[0]
        title = video.get("title", "Unknown Title")
        duration_min = video.get("duration")
        vidid = video.get("id", "")
        yturl = video.get("link", "")
        thumbnail = video.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(
        self, link: str, videoid: Union[bool, str] = None
    ) -> Tuple[list, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile": cookies_file}
        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            formats_available = []
            for fmt in info.get("formats", []):
                try:
                    _ = str(fmt["format"])
                except Exception:
                    continue
                if "dash" not in str(fmt["format"]).lower():
                    try:
                        _ = fmt["format"]
                        _ = fmt["filesize"]
                        _ = fmt["format_id"]
                        _ = fmt["ext"]
                        _ = fmt["format_note"]
                    except KeyError:
                        continue
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

    async def slider(
        self, link: str, query_type: int, videoid: Union[bool, str] = None
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        search = VideosSearch(link, limit=10)
        results = (await search.next()).get("result", [])
        if not results:
            return None, None, None, None
        query_type = query_type % len(results)
        video = results[query_type]
        title = video.get("title", "Unknown Title")
        duration_min = video.get("duration")
        vidid = video.get("id", "")
        thumbnail = video.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> Union[Tuple[str, bool], None]:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        def audio_dl() -> str:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookies_file,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl_instance:
                info = ydl_instance.extract_info(link, False)
                filepath = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(filepath):
                    return filepath
                ydl_instance.download([link])
                return filepath

        def video_dl() -> str:
            ydl_opts = {
                "format": "(best[height<=?720][width<=?1280])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookies_file,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl_instance:
                info = ydl_instance.extract_info(link, False)
                filepath = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(filepath):
                    return filepath
                ydl_instance.download([link])
                return filepath

        def song_video_dl():
            formats_str = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_opts = {
                "format": formats_str,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
                "cookiefile": cookies_file,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl_instance:
                ydl_instance.download([link])

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_opts = {
                "format": format_id,
                "outtmpl": fpath,
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
                "cookiefile": cookies_file,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl_instance:
                ydl_instance.download([link])

        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            fpath = f"downloads/{title}.mp4"
            return fpath
        elif songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            fpath = f"downloads/{title}.mp3"
            return fpath
        elif video:
            if await is_on_off(1):
                downloaded_file = await loop.run_in_executor(None, video_dl)
            else:
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
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode().split("\n")[0]
                else:
                    return None
        else:
            downloaded_file = await loop.run_in_executor(None, audio_dl)
        return downloaded_file, True
