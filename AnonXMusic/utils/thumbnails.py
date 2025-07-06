import os
import re
import textwrap
import aiofiles
import aiohttp
import logging
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.__future__ import VideosSearch

from AnonXMusic import app
from config import YOUTUBE_IMG_URL

logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('thumb.log')]
)
logger = logging.getLogger(__name__)

def resize_image(image, max_width=1280, max_height=720):
    ratio = min(max_width / image.size[0], max_height / image.size[1])
    new_width, new_height = int(image.size[0] * ratio), int(image.size[1] * ratio)
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

def truncate_text(text, max_length, add_ellipsis=True):
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..." if add_ellipsis else text[:max_length]

async def fetch_video_metadata(videoid):
    try:
        results = VideosSearch(videoid, limit=1)
        result = await results.next()
        if not result or not result.get("result"):
            logger.error(f"No metadata found for video ID: {videoid}")
            return None
        video = result["result"][0]
        metadata = {
            "title": re.sub(r"\W+", " ", video.get("title", "Unsupported Title")).title(),
            "duration": video.get("duration", "Unknown Mins"),
            "thumbnail_url": video.get("thumbnails", [{}])[0].get("url", ""),
            "views": video.get("viewCount", {}).get("text", "Unknown"),
            "channel": video.get("channel", {}).get("name", "Unknown Channel")
        }
        return metadata
    except Exception as e:
        logger.error(f"Error fetching metadata for video ID {videoid}: {str(e)}")
        return None

async def download_thumbnail(videoid, thumbnail_url):
    async with aiohttp.ClientSession() as session:
        for attempt in range(2):
            try:
                async with session.get(thumbnail_url) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(f"cache/thumb{videoid}.png", mode="wb") as f:
                            await f.write(await resp.read())
                        return True
                    if attempt == 2:
                        logger.error(f"Failed to download thumbnail after 3 attempts for video ID: {videoid}")
                        return False
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Error downloading thumbnail for video ID {videoid}: {str(e)}")
                    return False
    return False

def prepare_background_image(videoid, thumbnail_path):
    try:
        base_image = Image.open(thumbnail_path)
    except Exception as e:
        logger.error(f"Error opening thumbnail for video ID {videoid}: {str(e)}")
        return None

    resized_image = resize_image(base_image)
    rgba_image = resized_image.convert("RGBA")
    background = rgba_image.filter(ImageFilter.BoxBlur(10))
    background = ImageEnhance.Brightness(background).enhance(0.7)

    thumb_size = 450
    x_center, y_center = base_image.width / 2, base_image.height / 2
    aspect_ratio = base_image.width / base_image.height
    crop_size = min(base_image.width, base_image.height)
    x1, y1 = x_center - crop_size / 2, y_center - crop_size / 2
    x2, y2 = x_center + crop_size / 2, y_center + crop_size / 2
    logo = base_image.crop((x1, y1, x2, y2))
    logo = ImageOps.fit(logo, (thumb_size, thumb_size), centering=(0.5, 0.5), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (thumb_size, thumb_size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (thumb_size, thumb_size)], radius=20, fill=255)
    logo.putalpha(mask)
    thumb_gap = 40
    logo_pos_x = rgba_image.width - thumb_size - thumb_gap
    logo_pos_y = (rgba_image.height - thumb_size) // 2
    background.paste(logo, (logo_pos_x, logo_pos_y), logo)
    return background

def load_fonts(videoid):
    try:
        now_playing_font = ImageFont.truetype("AnonXMusic/assets/font.ttf", 55)
        title_font = ImageFont.truetype("AnonXMusic/assets/font2.ttf", 42)
        info_font = ImageFont.truetype("AnonXMusic/assets/font2.ttf", 34)
        name_font = ImageFont.truetype("AnonXMusic/assets/font3.ttf", 28)
    except IOError as e:
        logger.error(f"Error loading fonts for video ID {videoid}: {str(e)}")
        now_playing_font = title_font = info_font = name_font = ImageFont.load_default()
    return now_playing_font, title_font, info_font, name_font

def prepare_text_lines(metadata, title_max_length=50):
    title = truncate_text(metadata["title"], title_max_length)
    views = truncate_text(metadata["views"], 15)
    duration = truncate_text(metadata["duration"], 15)
    channel = truncate_text(metadata["channel"], 20)
    return [
        "Now Playing :",
        f"Track   : {title}",
        f"Duration: {duration}",
        f"Views   : {views}",
        f"Channel : {channel}",
    ]

def calculate_text_dimensions(draw, text_lines, now_playing_font, title_font, info_font):
    heights = []
    widths = []
    for i, line in enumerate(text_lines):
        font = now_playing_font if i == 0 else title_font if i == 1 else info_font
        bbox = draw.textbbox((0, 0), line, font=font)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])
    return heights, widths

def draw_text_boxes(background, text_lines, heights, widths, now_playing_font, title_font, info_font, videoid):
    padding = 20
    box_gap = 25
    radius = 16
    box_width = int(max(widths) + 2 * padding)
    now_playing_height = heights[0] + 2 * padding
    detail_box_height = sum(heights[1:]) + (len(heights[1:]) - 1) * 10 + 2 * padding
    total_height = now_playing_height + detail_box_height + box_gap

    thumb_size = 450
    thumb_gap = 40
    start_x = (background.width - box_width - thumb_size - thumb_gap) // 2
    start_y = (background.height - total_height) // 2

    draw_img = ImageDraw.Draw(background)

    # Now Playing Box
    now_box = Image.new("RGBA", (box_width, now_playing_height), (0, 0, 0, 0))
    ImageDraw.Draw(now_box).rounded_rectangle([(0, 0), (box_width, now_playing_height)], radius=radius, fill=(0, 0, 0, 160))
    now_box = now_box.filter(ImageFilter.GaussianBlur(1))
    background.paste(now_box, (start_x, start_y), now_box)

    # Details Box
    detail_box = Image.new("RGBA", (box_width, detail_box_height), (0, 0, 0, 0))
    ImageDraw.Draw(detail_box).rounded_rectangle([(0, 0), (box_width, detail_box_height)], radius=radius, fill=(0, 0, 0, 160))
    detail_box = detail_box.filter(ImageFilter.GaussianBlur(1))
    detail_start_y = start_y + now_playing_height + box_gap
    background.paste(detail_box, (start_x, detail_start_y), detail_box)

    # Draw Text
    draw_img.text((start_x + padding, start_y + padding), text_lines[0], font=now_playing_font, fill="white", stroke_width=1, stroke_fill="black")
    current_y = detail_start_y + padding
    for i, line in enumerate(text_lines[1:], 1):
        font = title_font if i == 1 else info_font
        draw_img.text((start_x + padding, current_y), line, font=font, fill="white", stroke_width=1, stroke_fill="black")
        current_y += heights[i] + 10

    return background

async def get_thumb(videoid, title_max_length=50):
    cache_path = f"cache/{videoid}.png"
    if os.path.isfile(cache_path):
        return cache_path

    if not videoid or not re.match(r'^[a-zA-Z0-9_-]{11}$', videoid):
        logger.error(f"Invalid video ID: {videoid}")
        return YOUTUBE_IMG_URL

    try:
        metadata = await fetch_video_metadata(videoid)
        if not metadata:
            return YOUTUBE_IMG_URL

        if not await download_thumbnail(videoid, metadata["thumbnail_url"]):
            return YOUTUBE_IMG_URL

        background = prepare_background_image(videoid, f"cache/thumb{videoid}.png")
        if not background:
            return YOUTUBE_IMG_URL

        now_playing_font, title_font, info_font, name_font = load_fonts(videoid)
        text_lines = prepare_text_lines(metadata, title_max_length)

        draw = ImageDraw.Draw(background)
        heights, widths = calculate_text_dimensions(draw, text_lines, now_playing_font, title_font, info_font)

        background = draw_text_boxes(background, text_lines, heights, widths, now_playing_font, title_font, info_font, videoid)

        draw.text((5, 5), f"{app.name}", fill="white", font=name_font)

        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            logger.warning(f"Couldn't delete temporary thumbnail: {videoid}")

        background.save(cache_path)
        return cache_path

    except Exception as e:
        logger.error(f"Error in get_thumb for video ID {videoid}: {str(e)}")
        return YOUTUBE_IMG_URL
