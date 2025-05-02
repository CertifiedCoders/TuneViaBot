import asyncio
import aiohttp
import os
from config import API_URL, API_KEY

USE_API = bool(API_URL and API_KEY)
_logged_api_skip = False


def extract_video_id(link: str) -> str:
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    return link.split("/")[-1].split("?")[0]


async def api_download_song(link: str) -> str:
    global _logged_api_skip

    if not USE_API:
        if not _logged_api_skip:
            print("[SKIPPED] API config missing — using yt-dlp for all downloads.")
            _logged_api_skip = True
        return None

    video_id = extract_video_id(link)
    download_folder = "downloads"
    for ext in ["mp3", "m4a", "webm"]:
        file_path = f"{download_folder}/{video_id}.{ext}"
        if os.path.exists(file_path):
            return file_path

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

            file_format = data.get("format", "mp3")
            file_extension = file_format.lower()
            file_name = f"{video_id}.{file_extension}"
            file_path = os.path.join(download_folder, file_name)

            os.makedirs(download_folder, exist_ok=True)
            async with session.get(download_url) as file_response:
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = await file_response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            return file_path

    except Exception:
        return None
