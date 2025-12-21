# Authored By Certified Coders © 2025
import os
import re
import hashlib
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.aio import VideosSearch
from config import YOUTUBE_IMG_URL, SOUNCLOUD_IMG_URL
from Tune.core.dir import CACHE_DIR
from Tune.platforms.Soundcloud import is_soundcloud_url

PANEL_W, PANEL_H = 763, 545
PANEL_X = (1280 - PANEL_W) // 2
PANEL_Y = 88
TRANSPARENCY = 170
INNER_OFFSET = 36

THUMB_W, THUMB_H = 542, 273
THUMB_X = PANEL_X + (PANEL_W - THUMB_W) // 2
THUMB_Y = PANEL_Y + INNER_OFFSET

TITLE_X = 377
META_X = 377
TITLE_Y = THUMB_Y + THUMB_H + 10
META_Y = TITLE_Y + 45

BAR_X, BAR_Y = 388, META_Y + 45
BAR_RED_LEN = 280
BAR_TOTAL_LEN = 480

ICONS_W, ICONS_H = 415, 45
ICONS_X = PANEL_X + (PANEL_W - ICONS_W) // 2
ICONS_Y = BAR_Y + 48

MAX_TITLE_WIDTH = 580


def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    ellipsis = "…"
    if font.getlength(text) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        if font.getlength(text[:i] + ellipsis) <= max_w:
            return text[:i] + ellipsis
    return ellipsis


def _load_fonts():
    try:
        title_font = ImageFont.truetype("Tune/assets/thumb/font2.ttf", 32)
        regular_font = ImageFont.truetype("Tune/assets/thumb/font.ttf", 18)
        return title_font, regular_font
    except OSError:
        default = ImageFont.load_default()
        return default, default


async def _download_thumbnail(url: str, path: str) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(path, "wb") as f:
                        await f.write(await resp.read())
                    return True
    except Exception:
        pass
    return False


async def _create_decorated_thumbnail(
    title: str,
    thumbnail_url: str,
    duration_text: str,
    platform_text: str,
    cache_path: str,
    cache_id: str,
    fallback_url: str,
    is_live: bool = False,
) -> str:
    thumb_path = os.path.join(CACHE_DIR, f"thumb{cache_id}.png")
    
    if not await _download_thumbnail(thumbnail_url, thumb_path):
        if not await _download_thumbnail(fallback_url, thumb_path):
            return fallback_url

    try:
        base = Image.open(thumb_path).resize((1280, 720)).convert("RGBA")
        bg = ImageEnhance.Brightness(base.filter(ImageFilter.BoxBlur(10))).enhance(0.6)

        panel_area = bg.crop((PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
        overlay = Image.new("RGBA", (PANEL_W, PANEL_H), (255, 255, 255, TRANSPARENCY))
        frosted = Image.alpha_composite(panel_area, overlay)
        mask = Image.new("L", (PANEL_W, PANEL_H), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, PANEL_W, PANEL_H), 50, fill=255)
        bg.paste(frosted, (PANEL_X, PANEL_Y), mask)

        draw = ImageDraw.Draw(bg)
        title_font, regular_font = _load_fonts()

        thumb = base.resize((THUMB_W, THUMB_H))
        tmask = Image.new("L", thumb.size, 0)
        ImageDraw.Draw(tmask).rounded_rectangle((0, 0, THUMB_W, THUMB_H), 20, fill=255)
        bg.paste(thumb, (THUMB_X, THUMB_Y), tmask)

        draw.text((TITLE_X, TITLE_Y), trim_to_width(title, title_font, MAX_TITLE_WIDTH), fill="black", font=title_font)
        draw.text((META_X, META_Y), platform_text, fill="black", font=regular_font)

        draw.line([(BAR_X, BAR_Y), (BAR_X + BAR_RED_LEN, BAR_Y)], fill="red", width=6)
        draw.line([(BAR_X + BAR_RED_LEN, BAR_Y), (BAR_X + BAR_TOTAL_LEN, BAR_Y)], fill="gray", width=5)
        draw.ellipse([(BAR_X + BAR_RED_LEN - 7, BAR_Y - 7), (BAR_X + BAR_RED_LEN + 7, BAR_Y + 7)], fill="red")

        draw.text((BAR_X, BAR_Y + 15), "00:00", fill="black", font=regular_font)
        end_text = "Live" if is_live else duration_text
        end_color = "red" if is_live else "black"
        end_x = BAR_X + BAR_TOTAL_LEN - (90 if is_live else 60)
        draw.text((end_x, BAR_Y + 15), end_text, fill=end_color, font=regular_font)

        icons_path = "Tune/assets/thumb/play_icons.png"
        if os.path.isfile(icons_path):
            ic = Image.open(icons_path).resize((ICONS_W, ICONS_H)).convert("RGBA")
            r, g, b, a = ic.split()
            black_ic = Image.merge("RGBA", (r.point(lambda *_: 0), g.point(lambda *_: 0), b.point(lambda *_: 0), a))
            bg.paste(black_ic, (ICONS_X, ICONS_Y), black_ic)

        bg.save(cache_path)
        return cache_path
    except Exception:
        return fallback_url
    finally:
        try:
            os.remove(thumb_path)
        except OSError:
            pass


async def get_soundcloud_thumb(url: str) -> str:
    from Tune import SoundCloud

    cache_id = hashlib.md5(url.encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"sc_{cache_id}_v4.png")

    if os.path.exists(cache_path):
        return cache_path

    try:
        title, duration_min, duration_sec, thumbnail, track_url = await SoundCloud.details(url)
    except Exception:
        return SOUNCLOUD_IMG_URL

    title = re.sub(r"\W+", " ", title).title()

    try:
        info = await SoundCloud._extract_info(url)
        uploader = info.get("uploader", "SoundCloud") if info else "SoundCloud"
        platform_text = f"SoundCloud | {uploader}"
    except Exception:
        platform_text = "SoundCloud"

    is_live = duration_sec == 0 or duration_min is None
    duration_text = "Live" if is_live else (duration_min or "Unknown Mins")
    thumbnail_url = thumbnail if thumbnail else SOUNCLOUD_IMG_URL

    return await _create_decorated_thumbnail(
        title=title,
        thumbnail_url=thumbnail_url,
        duration_text=duration_text,
        platform_text=platform_text,
        cache_path=cache_path,
        cache_id=cache_id,
        fallback_url=SOUNCLOUD_IMG_URL,
        is_live=is_live,
    )


async def get_thumb(videoid: str) -> str:
    if is_soundcloud_url(videoid):
        return await get_soundcloud_thumb(videoid)

    if videoid == "soundcloud":
        return SOUNCLOUD_IMG_URL

    cache_path = os.path.join(CACHE_DIR, f"{videoid}_v4.png")
    if os.path.exists(cache_path):
        return cache_path

    results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
    try:
        results_data = await results.next()
        result_items = results_data.get("result", [])
        if not result_items:
            raise ValueError("No results found.")
        data = result_items[0]
        title = re.sub(r"\W+", " ", data.get("title", "Unsupported Title")).title()
        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        duration = data.get("duration")
        views = data.get("viewCount", {}).get("short", "Unknown Views")
    except Exception:
        title, thumbnail, views = "Unsupported Title", YOUTUBE_IMG_URL, "Unknown Views"
        duration = None

    is_live = not duration or str(duration).strip().lower() in {"", "live", "live now"}
    duration_text = "Live" if is_live else duration or "Unknown Mins"
    platform_text = f"YouTube | {views}"

    return await _create_decorated_thumbnail(
        title=title,
        thumbnail_url=thumbnail,
        duration_text=duration_text,
        platform_text=platform_text,
        cache_path=cache_path,
        cache_id=videoid,
        fallback_url=YOUTUBE_IMG_URL,
        is_live=is_live,
    )
