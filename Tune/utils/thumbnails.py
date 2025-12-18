# Authored By Certified Coders © 2025
import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL, SOUNCLOUD_IMG_URL
from Tune.core.dir import CACHE_DIR 


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


def _is_soundcloud_url(url_or_id: str) -> bool:
    """Check if the provided string is a SoundCloud URL."""
    return bool(url_or_id and (
        "soundcloud.com" in url_or_id or "on.soundcloud.com" in url_or_id
    ))


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
    """
    Create a decorated thumbnail with common styling logic.
    
    Args:
        title: Track/video title
        thumbnail_url: URL of the thumbnail image
        duration_text: Formatted duration string
        platform_text: Platform name (e.g., "YouTube", "SoundCloud")
        cache_path: Path to save the cached decorated thumbnail
        cache_id: Unique ID for temporary thumbnail download
        fallback_url: Fallback thumbnail URL if download fails
        is_live: Whether the content is live
        
    Returns:
        Path to the decorated thumbnail image
    """
    # Download thumbnail
    thumb_path = os.path.join(CACHE_DIR, f"thumb{cache_id}.png")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail_url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await resp.read())
                else:
                    raise Exception(f"HTTP {resp.status}")
    except Exception:
        try:
            # Try downloading fallback if original fails
            async with aiohttp.ClientSession() as session:
                async with session.get(fallback_url) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(thumb_path, "wb") as f:
                            await f.write(await resp.read())
                    else:
                        return fallback_url
        except Exception:
            return fallback_url

    try:
        # Create base image
        base = Image.open(thumb_path).resize((1280, 720)).convert("RGBA")
        bg = ImageEnhance.Brightness(base.filter(ImageFilter.BoxBlur(10))).enhance(0.6)

        # Frosted glass panel
        panel_area = bg.crop((PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
        overlay = Image.new("RGBA", (PANEL_W, PANEL_H), (255, 255, 255, TRANSPARENCY))
        frosted = Image.alpha_composite(panel_area, overlay)
        mask = Image.new("L", (PANEL_W, PANEL_H), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, PANEL_W, PANEL_H), 50, fill=255)
        bg.paste(frosted, (PANEL_X, PANEL_Y), mask)

        # Draw details
        draw = ImageDraw.Draw(bg)
        try:
            title_font = ImageFont.truetype("Tune/assets/thumb/font2.ttf", 32)
            regular_font = ImageFont.truetype("Tune/assets/thumb/font.ttf", 18)
        except OSError:
            title_font = regular_font = ImageFont.load_default()

        thumb = base.resize((THUMB_W, THUMB_H))
        tmask = Image.new("L", thumb.size, 0)
        ImageDraw.Draw(tmask).rounded_rectangle((0, 0, THUMB_W, THUMB_H), 20, fill=255)
        bg.paste(thumb, (THUMB_X, THUMB_Y), tmask)

        draw.text((TITLE_X, TITLE_Y), trim_to_width(title, title_font, MAX_TITLE_WIDTH), fill="black", font=title_font)
        draw.text((META_X, META_Y), platform_text, fill="black", font=regular_font)

        # Progress bar
        draw.line([(BAR_X, BAR_Y), (BAR_X + BAR_RED_LEN, BAR_Y)], fill="red", width=6)
        draw.line([(BAR_X + BAR_RED_LEN, BAR_Y), (BAR_X + BAR_TOTAL_LEN, BAR_Y)], fill="gray", width=5)
        draw.ellipse([(BAR_X + BAR_RED_LEN - 7, BAR_Y - 7), (BAR_X + BAR_RED_LEN + 7, BAR_Y + 7)], fill="red")

        draw.text((BAR_X, BAR_Y + 15), "00:00", fill="black", font=regular_font)
        end_text = "Live" if is_live else duration_text
        draw.text((BAR_X + BAR_TOTAL_LEN - (90 if is_live else 60), BAR_Y + 15), end_text, fill="red" if is_live else "black", font=regular_font)

        # Icons
        icons_path = "Tune/assets/thumb/play_icons.png"
        if os.path.isfile(icons_path):
            ic = Image.open(icons_path).resize((ICONS_W, ICONS_H)).convert("RGBA")
            r, g, b, a = ic.split()
            black_ic = Image.merge("RGBA", (r.point(lambda *_: 0), g.point(lambda *_: 0), b.point(lambda *_: 0), a))
            bg.paste(black_ic, (ICONS_X, ICONS_Y), black_ic)

        # Cleanup and save
        try:
            os.remove(thumb_path)
        except OSError:
            pass

        bg.save(cache_path)
        return cache_path
    except Exception:
        # If decoration fails, return fallback
        try:
            os.remove(thumb_path)
        except OSError:
            pass
        return fallback_url

async def get_soundcloud_thumb(url: str) -> str:
    """
    Get decorated thumbnail for a SoundCloud track URL.
    
    Args:
        url: SoundCloud track URL
        
    Returns:
        Path to cached decorated thumbnail, or fallback URL if extraction fails
    """
    # Import here to avoid circular dependency
    from Tune import SoundCloud
    import hashlib
    
    # Create a cache key from the URL (sanitize for filesystem)
    cache_id = hashlib.md5(url.encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"sc_{cache_id}_v4.png")
    
    if os.path.exists(cache_path):
        return cache_path

    try:
        # Extract track details using SoundCloud API
        title, duration_min, duration_sec, thumbnail, track_url = await SoundCloud.details(url)
    except Exception:
        # If extraction fails, return fallback
        return SOUNCLOUD_IMG_URL

    # Format title
    title = re.sub(r"\W+", " ", title).title()
    
    # Get uploader info for platform text
    try:
        info = await SoundCloud._extract_info(url)
        uploader = info.get("uploader", "SoundCloud") if info else "SoundCloud"
        platform_text = f"SoundCloud | {uploader}"
    except Exception:
        platform_text = "SoundCloud"

    # Format duration
    is_live = duration_sec == 0 or duration_min is None
    duration_text = "Live" if is_live else (duration_min or "Unknown Mins")
    
    # Use extracted thumbnail or fallback
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
    """
    Get decorated thumbnail for YouTube video ID or SoundCloud URL.
    Automatically detects the platform and routes to the appropriate function.
    
    Args:
        videoid: YouTube video ID or SoundCloud URL
        
    Returns:
        Path to cached decorated thumbnail, or fallback URL if extraction fails
    """
    # Check if it's a SoundCloud URL
    if _is_soundcloud_url(videoid):
        return await get_soundcloud_thumb(videoid)
    
    # If it's the string "soundcloud" without a URL, return fallback
    if videoid == "soundcloud":
        return SOUNCLOUD_IMG_URL
    
    # YouTube video data fetch
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
