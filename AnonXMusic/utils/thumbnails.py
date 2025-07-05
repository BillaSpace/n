import os
import re
import textwrap
import aiofiles
import aiohttp
from AnonXMusic import app
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

async def fetch_thumbnail(videoid, cache_path):
    """Download and cache YouTube thumbnail."""
    thumbnail_url = await get_video_metadata(videoid)
    if not thumbnail_url:
        return None

    async with aiohttp.ClientSession() as session:
        for attempt in range(3):
            try:
                async with session.get(thumbnail_url) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(f"cache/thumb{videoid}.png", mode="wb") as f:
                            await f.write(await resp.read())
                        return f"cache/thumb{videoid}.png"
            except Exception as e:
                if attempt == 2:
                    print(f"Error downloading thumbnail for {videoid}: {e}")
                    return None
    return None

async def get_video_metadata(videoid):
    """Fetch YouTube video metadata."""
    if not re.match(r'^[a-zA-Z0-9_-]{11}$', videoid):
        print(f"Invalid video ID: {videoid}")
        return None
    results = VideosSearch(videoid, limit=1)
    result = await results.next()
    if not result or not result.get("result"):
        print(f"No results found for video ID: {videoid}")
        return None
    video = result["result"][0]
    return video.get("thumbnails", [{}])[0].get("url", "")

def resize_image(image, max_width=1280, max_height=720):
    """Resize image while maintaining aspect ratio."""
    ratio = min(max_width / image.size[0], max_height / image.size[1])
    new_size = (int(ratio * image.size[0]), int(ratio * image.size[1]))
    return image.resize(new_size, Image.Resampling.LANCZOS)

def create_rounded_thumbnail(image, thumb_size=450, radius=20):
    """Create a square thumbnail with rounded corners."""
    aspect_ratio = image.width / image.height
    if aspect_ratio > 1:
        crop_size = min(image.width, image.height)
    else:
        crop_size = min(image.height, image.width)
    
    x1 = (image.width - crop_size) / 2
    y1 = (image.height - crop_size) / 2
    logo = image.crop((x1, y1, x1 + crop_size, y1 + crop_size))
    logo = ImageOps.fit(logo, (thumb_size, thumb_size), centering=(0.5, 0.5), method=Image.Resampling.LANCZOS)
    
    mask = Image.new("L", (thumb_size, thumb_size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (thumb_size, thumb_size)], radius=radius, fill=255)
    logo.putalpha(mask)
    return logo

def load_fonts():
    """Load fonts with fallback to default."""
    try:
        return {
            "title": ImageFont.truetype("AnonXMusic/assets/font3.ttf", 50),
            "now_playing": ImageFont.truetype("AnonXMusic/assets/font3.ttf", 50),
            "info": ImageFont.truetype("AnonXMusic/assets/font3.ttf", 30),
            "name": ImageFont.truetype("AnonXMusic/assets/font4.ttf", 28)
        }
    except IOError as e:
        print(f"Error loading fonts: {e}")
        return {key: ImageFont.load_default() for key in ["title", "now_playing", "info", "name"]}

def truncate_text(text, max_length, add_ellipsis=True):
    """Truncate text with optional ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..." if add_ellipsis else text[:max_length]

def prepare_text_lines(video_data, title_max_length=20):
    """Prepare and truncate text lines for rendering."""
    title = re.sub(r"\W+", " ", video_data.get("title", "Unsupported Title")).title()
    title = truncate_text(title, title_max_length)
    views = truncate_text(video_data.get("viewCount", {}).get("text", "Unknown"), 20)
    duration = truncate_text(video_data.get("duration", "Unknown Mins"), 15)
    channel = truncate_text(video_data.get("channel", {}).get("name", "Unknown Channel"), 15)
    return ["Now Playing"] + textwrap.wrap(title, width=25)[:2] + [f"Views: {views}", f"Duration: {duration}", f"Channel: {channel}"]

def calculate_text_metrics(draw, text_lines, fonts, max_box_width):
    """Calculate text sizes and maximum label width."""
    text_heights, text_widths, max_label_width = [], [], 0
    for i, line in enumerate(text_lines):
        font = fonts["now_playing"] if i == 0 else fonts["title"] if i in [1, 2] else fonts["info"]
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = min(bbox[2] - bbox[0], max_box_width - 30)
        text_heights.append(bbox[3] - bbox[1])
        text_widths.append(text_width)
        if i >= 3:
            label = line.split(":")[0] + ":"
            label_bbox = draw.textbbox((0, 0), label, font=fonts["info"])
            max_label_width = max(max_label_width, label_bbox[2] - label_bbox[0])
    return text_heights, text_widths, max_label_width

def draw_text_boxes(background, draw, text_lines, text_heights, text_widths, max_label_width, fonts, box_params):
    """Draw text boxes and text on the background."""
    start_x, start_y, now_playing_width, now_playing_height, main_box_width, main_box_height, padding, box_gap, radius = box_params
    
    # Draw "Now Playing" box
    now_playing_box = Image.new("RGBA", (int(now_playing_width), int(now_playing_height)), (0, 0, 0, 0))
    ImageDraw.Draw(now_playing_box).rounded_rectangle(
        [(0, 0), (now_playing_width, now_playing_height)], radius=radius, fill=(0, 0, 0, 160)
    )
    now_playing_box = now_playing_box.filter(ImageFilter.GaussianBlur(1))
    background.paste(now_playing_box, (start_x, start_y), now_playing_box)

    # Draw main text box
    main_box = Image.new("RGBA", (int(main_box_width), int(main_box_height)), (0, 0, 0, 0))
    ImageDraw.Draw(main_box).rounded_rectangle(
        [(0, 0), (main_box_width, main_box_height)], radius=radius, fill=(0, 0, 0, 160)
    )
    main_box = main_box.filter(ImageFilter.GaussianBlur(2))
    main_y = start_y + now_playing_height + box_gap
    background.paste(main_box, (start_x + (now_playing_width - main_box_width) // 2, int(main_y)), main_box)

    # Draw text
    current_y = start_y + (now_playing_height - text_heights[0]) // 2
    draw.text(
        (start_x + (now_playing_width - text_widths[0]) // 2, current_y),
        "Now Playing",
        fill="black",
        stroke_width=1,
        stroke_fill="white",
        font=fonts["now_playing"]
    )
    
    current_y = main_y + padding
    for i, line in enumerate(text_lines[1:], 1):
        font = fonts["title"] if i in [1, 2] else fonts["info"]
        text_width = text_widths[i]
        if i >= 3:
            label, value = line.split(":", 1)
            label_x = start_x + (now_playing_width - main_box_width) // 2 + padding
            value_x = label_x + max_label_width + 5
            draw.text((label_x, current_y), label + ":", fill="white", stroke_width=1, stroke_fill="white", font=font)
            draw.text((value_x, current_y), value.strip(), fill="white", stroke_width=1, stroke_fill="white", font=font)
        else:
            draw.text(
                (start_x + (now_playing_width - main_box_width) // 2 + (main_box_width - text_width) // 2, current_y),
                line,
                fill="white",
                stroke_width=1,
                stroke_fill="white",
                font=font
            )
        current_y += text_heights[i] + box_gap

async def get_thumb(videoid, title_max_length=20):
    """Generate a thumbnail for a YouTube video."""
    cache_path = f"cache/{videoid}.png"
    if os.path.isfile(cache_path):
        return cache_path

    # Fetch video metadata and thumbnail
    results = VideosSearch(videoid, limit=1)
    result = await results.next()
    if not result or not result.get("result"):
        print(f"No results found for video ID: {videoid}")
        return YOUTUBE_IMG_URL
    video = result["result"][0]

    thumb_path = await fetch_thumbnail(videoid, cache_path)
    if not thumb_path:
        return YOUTUBE_IMG_URL

    try:
        # Process image
        with Image.open(thumb_path) as youtube:
            image = resize_image(youtube).convert("RGBA")
            background = ImageEnhance.Brightness(image.filter(ImageFilter.BoxBlur(10))).enhance(0.7)

        # Add rounded thumbnail
        thumb_size, thumb_gap = 450, 40
        logo = create_rounded_thumbnail(youtube)
        background.paste(logo, (image.width - thumb_size - thumb_gap, (image.height - thumb_size) // 2), logo)

        # Initialize drawing and fonts
        draw = ImageDraw.Draw(background)
        fonts = load_fonts()

        # Prepare text and calculate metrics
        text_lines = prepare_text_lines(video, title_max_length)
        max_box_width = image.width - thumb_size - thumb_gap - 100
        text_heights, text_widths, max_label_width = calculate_text_metrics(draw, text_lines, fonts, max_box_width)

        # Calculate box dimensions
        scale_factor, padding, box_gap, radius = 0.9, 15, 10, 12
        now_playing_width = (text_widths[0] + 2 * padding + 30) * scale_factor
        now_playing_height = (text_heights[0] + 2 * padding) * scale_factor
        main_box_width = max(now_playing_width - 10, (max(text_widths[1:]) + 2 * padding) * scale_factor)
        main_box_height = (sum(text_heights[1:]) + (len(text_lines[1:]) - 1) * box_gap + 2 * padding) * scale_factor
        start_x = (image.width - max(now_playing_width, main_box_width) - thumb_size - thumb_gap) // 2
        start_y = (image.height - (now_playing_height + main_box_height + box_gap)) // 2

        # Draw text boxes and text
        box_params = (start_x, start_y, now_playing_width, now_playing_height, main_box_width, main_box_height, padding, box_gap, radius)
        draw_text_boxes(background, draw, text_lines, text_heights, text_widths, max_label_width, fonts, box_params)

        # Draw app name
        draw.text((5, 5), f"{app.name}", fill="white", font=fonts["name"])

        # Save and clean up
        os.remove(thumb_path)
        background.save(cache_path)
        return cache_path

    except Exception as e:
        print(f"Error in get_thumb for video ID {videoid}: {e}")
        return YOUTUBE_IMG_URL
