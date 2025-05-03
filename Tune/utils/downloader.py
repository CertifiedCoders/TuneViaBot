import asyncio
import aiohttp
import os
import re
from typing import Optional, Union, Dict
from yt_dlp import YoutubeDL
from config import API_URL, API_KEY

USE_API = bool(API_URL and API_KEY)
_logged_api_skip = False
cookies_file = "Tune/assets/cookies.txt"
download_folder = "downloads"
os.makedirs(download_folder, exist_ok=True)


def extract_video_id(link: str) -> str:
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    return link.split("/")[-1].split("?")[0]


def safe_filename(name: str) -> str:
    return re.sub(r"[\\/*?\"<>|]", "_", name).strip()


def file_exists(video_id: str) -> Optional[str]:
    for ext in ["mp3", "m4a", "webm"]:
        path = f"{download_folder}/{video_id}.{ext}"
        if os.path.exists(path):
            return path
    return None


async def api_download_song(link: str) -> Optional[str]:
    global _logged_api_skip

    if not USE_API:
        if not _logged_api_skip:
            print("[SKIPPED] API config missing — using yt-dlp only.")
            _logged_api_skip = True
        return None

    video_id = extract_video_id(link)
    path = file_exists(video_id)
    if path:
        return path

    song_url = f"{API_URL}/song/{video_id}?api={API_KEY}"
    try:
        async with aiohttp.ClientSession() as session:
            while True:
                async with session.get(song_url) as response:
                    if response.status != 200:
                        return None
                    data = await response.json()
                    status = data.get("status", "").lower()
                    if status == "downloading":
                        await asyncio.sleep(2)
                        continue
                    elif status == "error":
                        return None
                    elif status == "done":
                        download_url = data.get("link")
                        break
                    else:
                        return None

            fmt = data.get("format", "mp3").lower()
            path = f"{download_folder}/{video_id}.{fmt}"
            async with session.get(download_url) as file_response:
                with open(path, 'wb') as f:
                    while True:
                        chunk = await file_response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            return path
    except Exception:
        return None


def _download_ytdlp(link: str, opts: Dict) -> Optional[str]:
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            ext = info.get("ext", "webm")
            vid = info.get("id")
            path = f"{download_folder}/{vid}.{ext}"
            if os.path.exists(path):
                return path
            ydl.download([link])
            return path
    except Exception:
        return None


async def yt_dlp_download(link: str, type: str, format_id: str = None, title: str = None) -> Optional[str]:
    loop = asyncio.get_running_loop()

    if type == "audio":
        opts = {
            "format": "bestaudio/best",
            "outtmpl": f"{download_folder}/%(id)s.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "cookiefile": cookies_file,
            "noplaylist": True,
            "concurrent_fragment_downloads": 5,
        }
        return await loop.run_in_executor(None, _download_ytdlp, link, opts)

    elif type == "video":
        opts = {
            "format": "best[height<=?720][width<=?1280]",
            "outtmpl": f"{download_folder}/%(id)s.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "cookiefile": cookies_file,
            "noplaylist": True,
            "concurrent_fragment_downloads": 5,
        }
        return await loop.run_in_executor(None, _download_ytdlp, link, opts)

    elif type == "song_video" and format_id and title:
        safe_title = safe_filename(title)
        opts = {
            "format": f"{format_id}+140",
            "outtmpl": f"{download_folder}/{safe_title}",
            "quiet": True,
            "no_warnings": True,
            "prefer_ffmpeg": True,
            "merge_output_format": "mp4",
            "cookiefile": cookies_file,
        }
        await loop.run_in_executor(None, lambda: YoutubeDL(opts).download([link]))
        return f"{download_folder}/{safe_title}.mp4"

    elif type == "song_audio" and format_id and title:
        safe_title = safe_filename(title)
        opts = {
            "format": format_id,
            "outtmpl": f"{download_folder}/{safe_title}.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "prefer_ffmpeg": True,
            "cookiefile": cookies_file,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
        await loop.run_in_executor(None, lambda: YoutubeDL(opts).download([link]))
        return f"{download_folder}/{safe_title}.mp3"

    return None


async def download_audio_concurrent(link: str) -> Optional[str]:
    video_id = extract_video_id(link)

    existing = file_exists(video_id)
    if existing:
        return existing

    if not USE_API:
        return await yt_dlp_download(link, type="audio")

    yt_task = asyncio.create_task(yt_dlp_download(link, type="audio"))
    api_task = asyncio.create_task(api_download_song(link))

    done, _ = await asyncio.wait([yt_task, api_task], return_when=asyncio.FIRST_COMPLETED)

    for task in done:
        result = task.result()
        if result:
            return result

    return await yt_task if not yt_task.done() else await api_task
