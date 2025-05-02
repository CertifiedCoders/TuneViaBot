import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from Tune.utils.errors import capture_internal_err
from Tune.platforms.Youtube import YouTubeAPI
from config import FAILED

os.makedirs("cache", exist_ok=True)

# --------------------------------------------------------------- Constants
CACHE_DIR = "cache"

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


@capture_internal_err
async def get_thumb(videoid):
    cache_path = f"{CACHE_DIR}/{videoid}_v4.png"
    if os.path.isfile(cache_path):
        return cache_path

    youtube = YouTubeAPI()
    try:
        title, duration, _, thumbnail, _, views = await youtube.details("", videoid=videoid)
    except Exception as e:
        raise ValueError(f"Could not fetch video details: {e}")

    title = re.sub(r"\W+", " ", title or "Unsupported Title").title()
    is_live = (duration is None) or (str(duration).strip().lower() in {"", "live", "live now"})
    duration = "Live" if is_live else duration or "Unknown Mins"
    thumbnail = thumbnail or FAILED
    views = views or "Unknown Views"

    thumb_path = f"{CACHE_DIR}/thumb{videoid}.png"
    async with aiohttp.ClientSession() as session:
        async with session.get(thumbnail) as resp:
            if resp.status == 200:
                async with aiofiles.open(thumb_path, mode="wb") as f:
                    await f.write(await resp.read())

    base = Image.open(thumb_path).resize((1280, 720)).convert("RGBA")
    bg = ImageEnhance.Brightness(base.filter(ImageFilter.BoxBlur(10))).enhance(0.6)

    panel_area = bg.crop((PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
    white_overlay = Image.new("RGBA", (PANEL_W, PANEL_H), (255, 255, 255, TRANSPARENCY))
    frosted = Image.alpha_composite(panel_area, white_overlay)
    mask = Image.new("L", (PANEL_W, PANEL_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PANEL_W, PANEL_H), 50, fill=255)
    bg.paste(frosted, (PANEL_X, PANEL_Y), mask)

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
    draw.text((META_X, META_Y), f"YouTube | {views}", fill="black", font=regular_font)

    draw.line([(BAR_X, BAR_Y), (BAR_X + BAR_RED_LEN, BAR_Y)], fill="red", width=6)
    draw.line([(BAR_X + BAR_RED_LEN, BAR_Y), (BAR_X + BAR_TOTAL_LEN, BAR_Y)], fill="gray", width=5)
    draw.ellipse([(BAR_X + BAR_RED_LEN - 7, BAR_Y - 7), (BAR_X + BAR_RED_LEN + 7, BAR_Y + 7)], fill="red")

    draw.text((BAR_X, BAR_Y + 15), "00:00", fill="black", font=regular_font)
    if is_live:
        draw.text((BAR_X + BAR_TOTAL_LEN - 90, BAR_Y + 15), "Live", fill="red", font=regular_font)
    else:
        draw.text((BAR_X + BAR_TOTAL_LEN - 60, BAR_Y + 15), duration, fill="black", font=regular_font)

    icons_path = "Tune/assets/thumb/play_icons.png"
    if os.path.isfile(icons_path):
        ic = Image.open(icons_path).resize((ICONS_W, ICONS_H)).convert("RGBA")
        r, g, b, a = ic.split()
        black_ic = Image.merge("RGBA", (r.point(lambda *_: 0), g.point(lambda *_: 0), b.point(lambda *_: 0), a))
        bg.paste(black_ic, (ICONS_X, ICONS_Y), black_ic)

    try:
        os.remove(thumb_path)
    except:
        pass

    bg.save(cache_path)
    return cache_path
