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

# Configure logging for critical errors only
logging.basicConfig(
    level=logging.CRITICAL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('thumb.log')]
)
logger = logging.getLogger(__name__)

def resize_image(max_width, max_height, image):
    """Resize image while maintaining aspect ratio."""
    width_ratio = max_width / image.size[0]
    height_ratio = max_height / image.size[1]
    ratio = min(width_ratio, height_ratio)
    new_width = int(ratio * image.size[0])
    new_height = int(ratio * image.size[1])
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

def truncate_text(text, max_length, add_ellipsis=True):
    """Truncate text to a specified length, optionally adding ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..." if add_ellipsis else text[:max_length]

async def get_thumb(videoid, title_max_length=30):
    """Generate a YouTube video thumbnail with text overlay."""
    cache_path = f"cache/{videoid}.png"
    if os.path.isfile(cache_path):
        return cache_path

    # Validate video ID
    if not videoid or not re.match(r'^[a-zA-Z0-9_-]{11}$', videoid):
        logger.critical(f"Invalid video ID: {videoid}")
        return YOUTUBE_IMG_URL

    try:
        # Fetch video metadata
        results = VideosSearch(videoid, limit=1)
        result = await results.next()
        if not result or not result.get("result"):
            logger.critical(f"No metadata found for video ID: {videoid}")
            return YOUTUBE_IMG_URL

        video = result["result"][0]
        title = re.sub(r"\W+", " ", video.get("title", "Unsupported Title")).title()
        duration = video.get("duration", "Unknown Mins")
        thumbnail_url = video.get("thumbnails", [{}])[0].get("url", "")
        views = video.get("viewCount", {}).get("text", "Unknown")
        channel = video.get("channel", {}).get("name", "Unknown Channel")

        if not thumbnail_url:
            logger.critical(f"No thumbnail URL found for video ID: {videoid}")
            return YOUTUBE_IMG_URL

        # Download thumbnail
        async with aiohttp.ClientSession() as session:
            for attempt in range(3):
                try:
                    async with session.get(thumbnail_url) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(f"cache/thumb{videoid}.png", mode="wb") as f:
                                await f.write(await resp.read())
                            break
                        if attempt == 2:
                            logger.critical(f"Failed to download thumbnail after 3 attempts for video ID: {videoid}")
                            return YOUTUBE_IMG_URL
                except Exception as e:
                    if attempt == 2:
                        logger.critical(f"Error downloading thumbnail for video ID {videoid}: {str(e)}")
                        return YOUTUBE_IMG_URL

        # Process base image
        try:
            base_image = Image.open(f"cache/thumb{videoid}.png")
        except Exception as e:
            logger.critical(f"Error opening thumbnail for video ID {videoid}: {str(e)}")
            return YOUTUBE_IMG_URL

        resized_image = resize_image(1280, 720, base_image)
        rgba_image = resized_image.convert("RGBA")
        background = rgba_image.filter(ImageFilter.BoxBlur(10))
        background = ImageEnhance.Brightness(background).enhance(0.7)

        # Create square thumbnail with rounded corners
        thumb_size = 450
        x_center, y_center = base_image.width / 2, base_image.height / 2
        aspect_ratio = base_image.width / base_image.height
        crop_width = min(base_image.width, base_image.height) if aspect_ratio > 1 else min(base_image.height, base_image.width)
        crop_height = crop_width if aspect_ratio > 1 else crop_width
        x1, y1 = x_center - crop_width / 2, y_center - crop_height / 2
        x2, y2 = x_center + crop_width / 2, y_center + crop_height / 2
        logo = base_image.crop((x1, y1, x2, y2))
        logo = ImageOps.fit(logo, (thumb_size, thumb_size), centering=(0.5, 0.5), method=Image.Resampling.LANCZOS)
        mask = Image.new("L", (thumb_size, thumb_size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (thumb_size, thumb_size)], radius=20, fill=255)
        logo.putalpha(mask)
        thumb_gap = 40
        logo_pos_x = rgba_image.width - thumb_size - thumb_gap
        logo_pos_y = (rgba_image.height - thumb_size) // 2
        background.paste(logo, (logo_pos_x, logo_pos_y), logo)

        # Load fonts
        draw = ImageDraw.Draw(background)
        try:
            title_font = ImageFont.truetype("AnonXMusic/assets/font.ttf", 40)  # Larger title
            now_playing_font = ImageFont.truetype("AnonXMusic/assets/font3.ttf", 45)  # Now Playing
            info_font = ImageFont.truetype("AnonXMusic/assets/font2.ttf", 30)  # Smaller views, duration, channel
            name_font = ImageFont.truetype("AnonXMusic/assets/font4.ttf", 28)  # App name
        except IOError as e:
            logger.critical(f"Error loading fonts for video ID {videoid}: {str(e)}")
            title_font = now_playing_font = info_font = name_font = ImageFont.load_default()

        # Prepare text
        padding = 17
        box_gap = 10
        max_box_width = logo_pos_x - thumb_gap - 100
        title = truncate_text(title, title_max_length)
        views = truncate_text(views, 20)
        duration = truncate_text(duration, 15)
        channel = truncate_text(channel, 15)

        # Wrap title and prepare text lines
        para = textwrap.wrap(title, width=25)
        text_lines = ["Now Playing"] + para[:2] + [f"Duration: {duration}", f"Views: {views}", f"Channel: {channel}"]
        text_heights = []
        text_widths = []
        max_label_width = 0

        # Calculate text sizes and label alignment
        for i, line in enumerate(text_lines):
            font = now_playing_font if i == 0 else title_font if i in [1, 2] else info_font
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = min(bbox[2] - bbox[0], max_box_width - 2 * padding)
            text_height = bbox[3] - bbox[1]
            text_heights.append(text_height)
            text_widths.append(text_width)
            if i >= 3:  # Align Views, Duration, Channel
                label = line.split(":")[0] + ":"
                label_bbox = draw.textbbox((0, 0), label, font=info_font)
                max_label_width = max(max_label_width, label_bbox[2] - label_bbox[0])

        # Calculate box dimensions
        scale_factor_now_playing = 0.9  # Unchanged for "Now Playing" box
        scale_factor_main = 0.85  # Slightly reduced for main box width
        height_scale_factor = 1.05  # Slightly increase main box height (5% taller)
        now_playing_width = int((text_widths[0] + 2 * padding + 35) * scale_factor_now_playing)
        now_playing_height = int((text_heights[0] + 2 * padding) * scale_factor_now_playing)
        radius = 15
        total_text_width = int((max(text_widths[1:]) + 2 * padding) * scale_factor_main)
        main_box_height = int((sum(text_heights[1:]) + (len(text_lines[1:]) - 1) * box_gap + 2 * padding) * scale_factor_main * height_scale_factor)
        main_box_width = int(max(now_playing_width - 10, total_text_width))

        # Center boxes
        start_x = (rgba_image.width - max(now_playing_width, main_box_width) - thumb_size - thumb_gap) // 2
        start_y = (rgba_image.height - (now_playing_height + main_box_height + box_gap)) // 2

        # Draw "Now Playing" box
        now_playing_box = Image.new("RGBA", (now_playing_width, now_playing_height), (0, 0, 0, 0))
        ImageDraw.Draw(now_playing_box).rounded_rectangle(
            [(0, 0), (now_playing_width, now_playing_height)], radius=radius, fill=(0, 0, 0, 160)
        )
        now_playing_box = now_playing_box.filter(ImageFilter.GaussianBlur(2))
        background.paste(now_playing_box, (start_x, start_y), now_playing_box)

        # Draw main text box
        main_box = Image.new("RGBA", (main_box_width, main_box_height), (0, 0, 0, 0))
        ImageDraw.Draw(main_box).rounded_rectangle(
            [(0, 0), (main_box_width, main_box_height)], radius=radius, fill=(0, 0, 0, 160)
        )
        main_box = main_box.filter(ImageFilter.GaussianBlur(1))
        main_y = start_y + now_playing_height + box_gap
        background.paste(main_box, (start_x + (now_playing_width - main_box_width) // 2, main_y), main_box)

        # Draw text
        current_y = start_y + (now_playing_height - text_heights[0]) // 2
        draw.text(
            (start_x + (now_playing_width - text_widths[0]) // 2, current_y),
            "Now Playing",
            fill="white",
            stroke_width=1,
            stroke_fill="white",
            font=now_playing_font
        )
        current_y = main_y + padding
        for i, line in enumerate(text_lines[1:], 1):
            font = title_font if i in [1, 2] else info_font
            text_width = min(text_widths[i], main_box_width - 2 * padding)  # Ensure text width doesn't exceed box
            if i >= 3:  # Align Views, Duration, Channel
                label, value = line.split(":", 1)
                label_x = start_x + (now_playing_width - main_box_width) // 2 + padding
                value_x = label_x + max_label_width + 5
                draw.text(
                    (label_x, current_y),
                    label + ":",
                    fill="white",
                    stroke_width=1,
                    stroke_fill="white",
                    font=font
                )
                draw.text(
                    (value_x, current_y),
                    value.strip(),
                    fill="white",
                    stroke_width=1,
                    stroke_fill="white",
                    font=font
                )
            else:  # Title text
                draw.text(
                    (start_x + (now_playing_width - main_box_width) // 2 + (main_box_width - text_width) // 2, current_y),
                    line,
                    fill="white",
                    stroke_width=1,
                    stroke_fill="black",
                    font=font
                )
            current_y += text_heights[i] + box_gap

        # Draw app name
        draw.text((5, 5), f"{app.name}", fill="white", font=name_font)

        # Clean up and save
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass
        background.save(cache_path)
        return cache_path

    except Exception as e:
        logger.critical(f"Error in get_thumb for video ID {videoid}: {str(e)}")
        if "WebpageMediaEmpty" in str(e):
            logger.critical(f"WebpageMediaEmpty: No valid media for video ID {videoid}")
        return YOUTUBE_IMG_URL
