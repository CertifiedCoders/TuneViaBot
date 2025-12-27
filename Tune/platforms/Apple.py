# Authored By Certified Coders © 2025
import re
import json
from typing import List, Optional, Tuple, Union

import aiohttp
from bs4 import BeautifulSoup
from youtubesearchpython.aio import VideosSearch


class AppleAPI:
    _USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    _TITLE_CLEANUP_PATTERN = re.compile(r'\s*\|\s*Apple Music.*$', re.IGNORECASE)
    _SONG_URL_PATTERN = re.compile(r'/song/([^/]+)/')
    _URL_PATTERN = re.compile(r"^https://music\.apple\.com/.+")
    _BASE_URL = "https://music.apple.com/in/playlist/"

    async def valid(self, link: str) -> bool:
        return bool(self._URL_PATTERN.search(link or ""))

    def _extract_title(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        og_title = soup.find("meta", property="og:title")
        if og_title and (content := og_title.get("content")):
            return content

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                json_data = json.loads(script.string or script.get_text() or "")
                if isinstance(json_data, dict):
                    if json_data.get("@type") == "MusicRecording" and (name := json_data.get("name")):
                        return name
                    if name := json_data.get("name"):
                        return name
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue

        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return self._TITLE_CLEANUP_PATTERN.sub('', title_tag.string.strip())

        h1_tag = soup.find("h1")
        if h1_tag:
            return h1_tag.get_text(strip=True)

        if "/song/" in url:
            match = self._SONG_URL_PATTERN.search(url)
            if match:
                return match.group(1).replace("-", " ")

        return None

    async def _fetch_html(self, url: str) -> Optional[str]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"User-Agent": self._USER_AGENT}) as response:
                if response.status == 200:
                    return await response.text()
                return None

    async def track(self, url: str, playid: Union[bool, str] = None) -> Union[Tuple[dict, str], bool]:
        url = self._BASE_URL + url if playid else url
        html = await self._fetch_html(url)
        if not html:
            return False

        soup = BeautifulSoup(html, "html.parser")
        title_query = self._extract_title(soup, url)
        if not title_query or not (title_query := title_query.strip()):
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

    async def playlist(self, url: str, playid: Union[bool, str] = None) -> Union[Tuple[List[str], str], bool]:
        url = self._BASE_URL + url if playid else url
        try:
            playlist_id = url.split("playlist/")[1]
        except IndexError:
            return False

        html = await self._fetch_html(url)
        if not html:
            return False

        soup = BeautifulSoup(html, "html.parser")
        results: List[str] = []
        for item in soup.find_all("meta", attrs={"property": "music:song"}):
            try:
                slug = item["content"].split("album/")[1].split("/")[0]
                results.append(slug.replace("-", " "))
            except (KeyError, IndexError, AttributeError):
                continue

        return results, playlist_id
