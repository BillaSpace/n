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

# Configure logging for errors only
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('thumb.log')]
)
logger = logging.getLogger(__name__)

def resize_image(image, max_width=1280, max_height=720):
    """Resize image while maintaining aspect ratio."""
    ratio = min(max_width / image.size[0], max_height / image.size[1])
    new_width, new_height = int(image.size[0] * ratio), int(image.size[1] * ratio)
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

def truncate_text(text, max_length, add_ellipsis=True):
    """Truncate text to a specified length with optional ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..." if add_ellipsis else text[:max_length]

async def fetch_video_metadata(videoid):
    """Fetch YouTube video metadata."""
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
    """Download thumbnail image with retries."""
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
    """Prepare blurred background with thumbnail logo."""
    try:
        base_image = Image.open(thumbnail_path)
    except Exception as e:
        logger.error(f"Error opening thumbnail for video ID {videoid}: {str(e)}")
        return None

    resized_image = resize_image(base_image)
    rgba_image = resized_image.convert("RGBA")
    background = rgba_image.filter(ImageFilter.BoxBlur(10))
    background = ImageEnhance.Brightness(background).enhance(0.7)

    # Create square thumbnail with rounded corners
    thumb_size = 450
    x_center, y_center = base_image.width / 2, base_image.height / 2
    aspect_ratio = base_image.width / base_image.height
    crop_width = min(base_image.width, base_image.height) if aspect_ratio > 1 else min(base_image.height, base_image.width)
    crop_height = crop_width
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
    return background

def load_fonts(videoid):
    """Load fonts with fallback to default."""
    try:
        now_playing_font = ImageFont.truetype("AnonXMusic/assets/font.ttf", 50)
        title_font = ImageFont.truetype("AnonXMusic/assets/font2.ttf", 40)
        info_font = ImageFont.truetype("AnonXMusic/assets/font2.ttf", 30)
        name_font = ImageFont.truetype("AnonXMusic/assets/font3.ttf", 28)
    except IOError as e:
        logger.error(f"Error loading fonts for video ID {videoid}: {str(e)}")
        now_playing_font = title_font = info_font = name_font = ImageFont.load_default()
    return now_playing_font, title_font, info_font, name_font

def prepare_text_lines(metadata, title_max_length=17):
    """Prepare and truncate text for thumbnail."""
    title = truncate_text(metadata["title"], title_max_length)
    views = truncate_text(metadata["views"], 20)
    duration = truncate_text(metadata["duration"], 15)
    channel = truncate_text(metadata["channel"], 20)
    return title, views, duration, channel

def calculate_text_dimensions(draw, text_lines, now_playing_font, title_font, info_font, max_box_width, padding=15):
    """Calculate text dimensions and alignment for captions."""
    text_heights = []
    text_widths = []
    max_label_width = 0
    for i, line in enumerate(text_lines):
        font = now_playing_font if i == 0 else title_font if i in [1, 2] else info_font
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = min(bbox[2] - bbox[0], max_box_width - 2 * padding)
        text_heights.append(bbox[3] - bbox[1])
        text_widths.append(text_width)
        if i >= 3:
            label = line.split(":")[0] + ":"
            label_bbox = draw.textbbox((0, 0), label, font=info_font)
            max_label_width = max(max_label_width, label_bbox[2] - label_bbox[0])
    return text_heights, text_widths, max_label_width

def draw_text_boxes(background, text_lines, text_heights, text_widths, max_label_width, now_playing_font, title_font, info_font, videoid):
    """Draw text boxes and text with proper alignment."""
    padding = 15
    box_gap = 10
    scale_factor = 0.9
    radius = 12

    # Calculate box dimensions
    now_playing_width = int((text_widths[0] + 2 * padding + 30) * scale_factor)
    now_playing_height = int((text_heights[0] + 2 * padding) * scale_factor)
    total_text_width = int((max(text_widths[1:]) + 2 * padding) * scale_factor)
    main_box_height = int((sum(text_heights[1:]) + (len(text_lines[1:]) - 1) * box_gap + 2 * padding) * scale_factor)
    main_box_width = int(max(now_playing_width - 10, total_text_width))

    # Center boxes
    thumb_size = 450
    thumb_gap = 40
    start_x = (background.width - max(now_playing_width, main_box_width) - thumb_size - thumb_gap) // 2
    start_y = (background.height - (now_playing_height + main_box_height + box_gap)) // 2

    # Draw "Now Playing" box
    now_playing_box = Image.new("RGBA", (now_playing_width, now_playing_height), (0, 0, 0, 0))
    ImageDraw.Draw(now_playing_box).rounded_rectangle(
        [(0, 0), (now_playing_width, now_playing_height)], radius=radius, fill=(0, 0, 0, 160)
    )
    now_playing_box = now_playing_box.filter(ImageFilter.GaussianBlur(1))
    background.paste(now_playing_box, (start_x, start_y), now_playing_box)

    # Draw main text box
    main_box = Image.new("RGBA", (main_box_width, main_box_height), (0, 0, 0, 0))
    ImageDraw.Draw(main_box).rounded_rectangle(
        [(0, 0), (main_box_width, main_box_height)], radius=radius, fill=(0, 0, 0, 160)
    )
    main_box = main_box.filter(ImageFilter.GaussianBlur(1))
    main_y = start_y + now_playing_height + box_gap
    background.paste(main_box, (start_x + (now_playing_width - main_box_width) // 2, main_y), main_box)

    # Draw text with aligned captions
    draw = ImageDraw.Draw(background)
    current_y = start_y + (now_playing_height - text_heights[0]) // 2
    draw.text(
        (start_x + (now_playing_width - text_widths[0]) // 2, current_y),
        "Now Playing",
        fill="black",
        stroke_width=1,
        stroke_fill="white",
        font=now_playing_font
    )
    current_y = main_y + padding
    for i, line in enumerate(text_lines[1:], 1):
        font = title_font if i in [1, 2] else info_font
        text_width = text_widths[i]
        if i >= 3:
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
        else:
            draw.text(
                (start_x + (now_playing_width - main_box_width) // 2 + padding + (main_box_width - 2 * padding - text_width) // 2, current_y),
                line,
                fill="white",
                stroke_width=1,
                stroke_fill="white",
                font=font
            )
        current_y += text_heights[i] + box_gap
    return background

async def get_thumb(videoid, title_max_length=17):
    """Generate a YouTube video thumbnail with text overlay."""
    cache_path = f"cache/{videoid}.png"
    if os.path.isfile(cache_path):
        return cache_path

    # Validate video ID
    if not videoid or not re.match(r'^[a-zA-Z0-9_-]{11}$', videoid):
        logger.error(f"Invalid video ID: {videoid}")
        return YOUTUBE_IMG_URL

    try:
        # Fetch metadata
        metadata = await fetch_video_metadata(videoid)
        if not metadata:
            return YOUTUBE_IMG_URL

        # Download thumbnail
        if not await download_thumbnail(videoid, metadata["thumbnail_url"]):
            return YOUTUBE_IMG_URL

        # Prepare background image
        background = prepare_background_image(videoid, f"cache/thumb{videoid}.png")
        if not background:
            return YOUTUBE_IMG_URL

        # Load fonts
        now_playing_font, title_font, info_font, name_font = load_fonts(videoid)

        # Prepare text
        title, views, duration, channel = prepare_text_lines(metadata, title_max_length)
        text_lines = ["Now Playing"] + [f"Track: {line}" for line in textwrap.wrap(title, width=20)[:2]] + [f"Views: {views}", f"Duration: {duration}", f"Channel: {channel}"]

        # Calculate text dimensions with constrained width
        draw = ImageDraw.Draw(background)
        max_box_width = background.width - 450 - 40 - 100
        text_heights, text_widths, max_label_width = calculate_text_dimensions(
            draw, text_lines, now_playing_font, title_font, info_font, max_box_width
        )

        # Draw text and boxes
        background = draw_text_boxes(
            background, text_lines, text_heights, text_widths, max_label_width,
            now_playing_font, title_font, info_font, videoid
        )

        # Draw app name
        draw.text((5, 5), f"{app.name}", fill="white", font=name_font)

        # Save thumbnail
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            logger.error(f"Failed to clean up temporary thumbnail file for video ID: {videoid}")
        background.save(cache_path)
        return cache_path

    except Exception as e:
        logger.error(f"Error in get_thumb for video ID {videoid}: {str(e)}")
        if "WebpageMediaEmpty" in str(e):
            logger.error(f"WebpageMediaEmpty: No valid media for video ID {videoid}")
        return YOUTUBE_IMG_URL
