import os
import re
import textwrap
import logging

import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.__future__ import VideosSearch

from AnonXMusic import app
from config import YOUTUBE_IMG_URL

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage

async def get_thumb(videoid):
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"

    # Validate video ID
    if not videoid or not re.match(r'^[a-zA-Z0-9_-]{11}$', videoid):
        logger.error(f"Invalid video ID: {videoid}")
        return YOUTUBE_IMG_URL

    try:
        # Use video ID directly for search
        results = VideosSearch(videoid, limit=1)
        result = (await results.next())["result"]
        if not result:
            logger.error(f"No results found for video ID: {videoid}")
            return YOUTUBE_IMG_URL

        for video in result:
            try:
                title = video.get("title", "Unsupported Title")
                title = re.sub("\W+", " ", title).title()
            except:
                title = "Unsupported Title"
            duration = video.get("duration", "Unknown Mins")
            thumbnail = video.get("thumbnails", [{}])[0].get("url", "")
            views = video.get("viewCount", {}).get("short", "Unknown Views")
            channel = video.get("channel", {}).get("name", "Unknown Channel")

        if not thumbnail:
            logger.error(f"No thumbnail URL found for video ID: {videoid}")
            return YOUTUBE_IMG_URL

        # Fetch thumbnail with retry logic
        async with aiohttp.ClientSession() as session:
            for attempt in range(3):  # Retry up to 3 times
                try:
                    async with session.get(thumbnail) as resp:
                        if resp.status == 200:
                            f = await aiofiles.open(f"cache/thumb{videoid}.png", mode="wb")
                            await f.write(await resp.read())
                            await f.close()
                            break
                        else:
                            logger.warning(f"Thumbnail fetch failed with status {resp.status}, attempt {attempt + 1}")
                            if attempt == 2:
                                return YOUTUBE_IMG_URL
                except Exception as e:
                    logger.error(f"Thumbnail fetch error: {str(e)}, attempt {attempt + 1}")
                    if attempt == 2:
                        return YOUTUBE_IMG_URL

        youtube = Image.open(f"cache/thumb{videoid}.png")
        image1 = changeImageSize(1280, 720, youtube)
        image2 = image1.convert("RGBA")
        background = image2.filter(filter=ImageFilter.BoxBlur(10))
        enhancer = ImageEnhance.Brightness(background)
        background = enhancer.enhance(0.7)
        Xcenter = youtube.width / 2
        Ycenter = youtube.height / 2
        x1 = Xcenter - 250
        y1 = Ycenter - 250
        x2 = Xcenter + 250
        y2 = Ycenter + 250
        logo = youtube.crop((x1, y1, x2, y2))
        logo.thumbnail((520, 520), Image.Resampling.LANCZOS)
        logo = ImageOps.expand(logo, border=15, fill="white")
        background.paste(logo, (600, 100))  # Logo on right
        draw = ImageDraw.Draw(background)
        font = ImageFont.truetype("AnonXMusic/assets/font3.ttf", 40)  # Title
        font2 = ImageFont.truetype("AnonXMusic/assets/font4.ttf", 65)  # Now Playing
        arial = ImageFont.truetype("AnonXMusic/assets/font3.ttf", 30)  # Views, Duration, Channel
        name_font = ImageFont.truetype("AnonXMusic/assets/font3.ttf", 30)  # App name

        # Text positions and gaps
        start_x = 50
        start_y = 150
        gap = 20
        padding = 20

        # Wrap title text
        para = textwrap.wrap(title, width=32)
        text_lines = ["Now Playing"] + para[:2] + [f"Views: {views[:23]}", f"Duration: {duration[:23]} Mins", f"Channel: {channel}"]
        text_heights = []
        text_widths = []

        # Calculate text sizes
        for i, line in enumerate(text_lines):
            font_to_use = font2 if i == 0 else font if i in [1, 2] else arial
            bbox = draw.textbbox((0, 0), line, font=font_to_use)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_heights.append(text_height)
            text_widths.append(text_width)

        # Calculate blur box dimensions
        box_width = max(text_widths) + 2 * padding
        total_text_height = sum(text_heights) + (len(text_lines) - 1) * gap
        box_height = total_text_height + 2 * padding
        box_x = start_x - padding
        box_y = start_y - padding

        # Create a new image for the blur box
        blur_box = Image.new("RGBA", (int(box_width), int(box_height)), (0, 0, 0, 0))
        blur_draw = ImageDraw.Draw(blur_box)
        blur_draw.rounded_rectangle(
            [(0, 0), (box_width, box_height)],
            radius=20,
            fill=(0, 0, 0, 180)  # Semi-transparent black
        )
        blur_box = blur_box.filter(ImageFilter.GaussianBlur(5))
        background.paste(blur_box, (int(box_x), int(box_y)), blur_box)

        # Draw text
        current_y = start_y
        for i, line in enumerate(text_lines):
            font_to_use = font2 if i == 0 else font if i in [1, 2] else arial
            stroke_width = 2 if i == 0 else 1
            draw.text(
                (start_x, current_y),
                line,
                fill="white",
                stroke_width=stroke_width,
                stroke_fill="white",
                font=font_to_use,
            )
            current_y += text_heights[i] + gap

        # Draw app name
        draw.text(
            (5, 5), f"{app.name}", fill="white", font=name_font
        )

        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass
        background.save(f"cache/{videoid}.png")
        return f"cache/{videoid}.png"
    except Exception as e:
        logger.error(f"Error processing thumbnail for video ID {videoid}: {str(e)}")
        return YOUTUBE_IMG_URL
