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

    def __init__(self):
        self.regex = re.compile(r"^https://music\.apple\.com/.+")
        self.base = "https://music.apple.com/in/playlist/"

    async def valid(self, link: str) -> bool:
        return bool(self.regex.search(link or ""))

    def _build_url(self, url: str, playid: Union[bool, str]) -> str:
        return self.base + url if playid else url

    def _extract_title_from_soup(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title.get("content")

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                script_content = script.string or script.get_text()
                if not script_content:
                    continue
                json_data = json.loads(script_content)
                if isinstance(json_data, dict):
                    if json_data.get("@type") == "MusicRecording" and json_data.get("name"):
                        return json_data.get("name")
                    if "name" in json_data:
                        return json_data.get("name")
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue

        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.string.strip()
            return self._TITLE_CLEANUP_PATTERN.sub('', title)

        h1_tag = soup.find("h1")
        if h1_tag:
            return h1_tag.get_text(strip=True)

        if "/song/" in url:
            match = self._SONG_URL_PATTERN.search(url)
            if match:
                return match.group(1).replace("-", " ")

        return None

    async def _fetch_html(self, url: str, use_headers: bool = False) -> Optional[str]:
        headers = {"User-Agent": self._USER_AGENT} if use_headers else None
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return None
                return await response.text()

    async def track(self, url: str, playid: Union[bool, str] = None) -> Union[Tuple[dict, str], bool]:
        url = self._build_url(url, playid)
        html = await self._fetch_html(url, use_headers=True)
        if not html:
            return False

        soup = BeautifulSoup(html, "html.parser")
        title_query = self._extract_title_from_soup(soup, url)
        if not title_query:
            return False
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

    async def playlist(self, url: str, playid: Union[bool, str] = None) -> Union[Tuple[List[str], str], bool]:
        url = self._build_url(url, playid)
        try:
            playlist_id = url.split("playlist/")[1]
        except (IndexError, AttributeError):
            return False

        html = await self._fetch_html(url)
        if not html:
            return False

        soup = BeautifulSoup(html, "html.parser")
        applelinks = soup.find_all("meta", attrs={"property": "music:song"})
        results: List[str] = []
        for item in applelinks:
            try:
                slug = item["content"].split("album/")[1].split("/")[0]
                results.append(slug.replace("-", " "))
            except (KeyError, IndexError, AttributeError):
                continue

        return results, playlist_id
