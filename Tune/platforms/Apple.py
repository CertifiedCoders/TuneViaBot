# Authored By Certified Coders © 2025
import re
import json
from typing import List, Union, Optional

import aiohttp
from bs4 import BeautifulSoup
from youtubesearchpython.aio import VideosSearch


class AppleAPI:
    def __init__(self):
        self.regex = r"^https:\/\/music\.apple\.com\/.+"
        self.base = "https://music.apple.com/in/playlist/"

    async def valid(self, link: str) -> bool:
        return bool(re.search(self.regex, link or ""))

    async def track(self, url: str, playid: Union[bool, str] = None):
        if playid:
            url = self.base + url

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return False
                html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        title_query: Optional[str] = None
        
        # Try multiple methods to extract the title
        # Method 1: Try og:title meta tag
        for tag in soup.find_all("meta"):
            if tag.get("property") == "og:title":
                title_query = tag.get("content")
                break
        
        # Method 2: Try JSON-LD structured data
        if not title_query:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    script_content = script.string or script.get_text()
                    if not script_content:
                        continue
                    json_data = json.loads(script_content)
                    if isinstance(json_data, dict):
                        if json_data.get("@type") == "MusicRecording" and json_data.get("name"):
                            title_query = json_data.get("name")
                            break
                        # Try nested structure
                        if "name" in json_data:
                            title_query = json_data.get("name")
                            break
                except (json.JSONDecodeError, AttributeError, TypeError):
                    continue
        
        # Method 3: Try title tag
        if not title_query:
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                title_query = title_tag.string.strip()
                # Clean up title (remove " | Apple Music" or similar suffixes)
                title_query = re.sub(r'\s*\|\s*Apple Music.*$', '', title_query, flags=re.IGNORECASE)
        
        # Method 4: Try to extract from h1 or other heading tags
        if not title_query:
            h1_tag = soup.find("h1")
            if h1_tag:
                title_query = h1_tag.get_text(strip=True)
        
        # Method 5: Try to extract from URL pattern if it contains song name
        if not title_query and "/song/" in url:
            try:
                # Extract song name from URL: /song/song-name/id
                match = re.search(r'/song/([^/]+)/', url)
                if match:
                    title_query = match.group(1).replace("-", " ")
            except Exception:
                pass

        if not title_query:
            return False

        # Clean up the title query
        title_query = title_query.strip()
        if not title_query:
            return False

        results = VideosSearch(title_query, limit=1)
        data = await results.next()
        if not data.get("result"):
            return False

        r = data["result"][0]
        track_details = {
            "title": r.get("title", ""),
            "link": r.get("link", ""),
            "vidid": r.get("id", ""),
            "duration_min": r.get("duration"),
            "thumb": r.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
        }
        return track_details, track_details["vidid"]

    async def playlist(self, url: str, playid: Union[bool, str] = None):
        if playid:
            url = self.base + url

        try:
            playlist_id = url.split("playlist/")[1]
        except Exception:
            return False

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return False
                html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        applelinks = soup.find_all("meta", attrs={"property": "music:song"})
        results: List[str] = []
        for item in applelinks:
            try:
                slug = item["content"].split("album/")[1].split("/")[0]
                results.append(slug.replace("-", " "))
            except Exception:
                continue

        return results, playlist_id
