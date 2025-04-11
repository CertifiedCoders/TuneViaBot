import asyncio
import os
import re
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from Tune.utils.database import is_on_off

cookies_file = "Tune/cookies/cookies.txt"

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in errorz.decode("utf-8").lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def _search_info(self, query: str) -> dict:
        if not re.search(self.regex, query):
            search_query = f"ytsearch1:{query}"
        else:
            search_query = query

        loop = asyncio.get_running_loop()

        def get_info():
            opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(search_query, download=False)

        info = await loop.run_in_executor(None, get_info)
        if 'entries' in info and info['entries']:
            return info['entries'][0]
        return info

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset is not None:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset is None:
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        video_info = await self._search_info(link)
        title = video_info.get("title", "Unknown Title")
        duration_sec = video_info.get("duration", 0)
        minutes = duration_sec // 60
        seconds = duration_sec % 60
        duration_formatted = f"{minutes}:{seconds:02d}" if duration_sec else "Live"
        thumbnail = video_info.get("thumbnail")
        vidid = video_info.get("id")
        return title, duration_formatted, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        video_info = await self._search_info(link)
        return video_info.get("title", "Unknown Title")

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        video_info = await self._search_info(link)
        return video_info.get("duration", 0)

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        video_info = await self._search_info(link)
        return video_info.get("thumbnail")

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookies_file,
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
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp --cookies {cookies_file} -i --get-id --flat-playlist --playlist-end {limit} --skip-download {link}"
        )
        result = [item for item in playlist.split("\n") if item]
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        video_info = await self._search_info(link)
        title = video_info.get("title", "Unknown Title")
        duration_sec = video_info.get("duration", 0)
        minutes = duration_sec // 60
        seconds = duration_sec % 60
        duration_formatted = f"{minutes}:{seconds:02d}" if duration_sec else "Live"
        vidid = video_info.get("id")
        yturl = video_info.get("webpage_url")
        thumbnail = video_info.get("thumbnail")
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_formatted,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile": cookies_file}
        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
            r = ydl.extract_info(link, download=False)
            formats_available = []
            for fmt in r.get("formats", []):
                try:
                    str(fmt["format"])
                except:
                    continue
                if "dash" not in str(fmt["format"]).lower():
                    try:
                        fmt["format"]
                        fmt["filesize"]
                        fmt["format_id"]
                        fmt["ext"]
                        fmt["format_note"]
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

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if not re.search(self.regex, link):
            search_query = f"ytsearch10:{link}"
        else:
            search_query = link

        loop = asyncio.get_running_loop()

        def get_info():
            opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(search_query, download=False)

        info = await loop.run_in_executor(None, get_info)
        if 'entries' in info and info['entries']:
            results = info['entries']
            query_type = query_type % len(results)
            video_info = results[query_type]
            title = video_info.get("title", "Unknown Title")
            duration_sec = video_info.get("duration", 0)
            minutes = duration_sec // 60
            seconds = duration_sec % 60
            duration_formatted = f"{minutes}:{seconds:02d}" if duration_sec else "Live"
            vidid = video_info.get("id")
            thumbnail = video_info.get("thumbnail")
            return title, duration_formatted, thumbnail, vidid
        return None, None, None, None

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
    ) -> str:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookies_file,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as x:
                info = x.extract_info(link, False)
                filepath = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(filepath):
                    return filepath
                x.download([link])
                return filepath

        def video_dl():
            ydl_opts = {
                "format": "best[height<=?720][width<=?1280]",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookies_file,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as x:
                info = x.extract_info(link, False)
                filepath = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(filepath):
                    return filepath
                x.download([link])
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
            with yt_dlp.YoutubeDL(ydl_opts) as x:
                x.download([link])

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
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "cookiefile": cookies_file,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as x:
                x.download([link])

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
                    "--cookies", cookies_file,
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
                    return
        else:
            downloaded_file = await loop.run_in_executor(None, audio_dl)
        return downloaded_file, True
