import os
import re
import textwrap
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.__future__ import VideosSearch

from AnonXMusic import app
from config import YOUTUBE_IMG_URL

def changeImageSize(maxWidth, maxHeight, image):
    """Resize image while maintaining aspect ratio."""
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    ratio = min(widthRatio, heightRatio)
    newWidth = int(ratio * image.size[0])
    newHeight = int(ratio * image.size[1])
    return image.resize((newWidth, newHeight), Image.Resampling.LANCZOS)

def truncate_text(text, max_length, add_ellipsis=True):
    """Truncate text to a specified length, optionally adding ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..." if add_ellipsis else text[:max_length]

async def get_thumb(videoid):
    """Generate a thumbnail for a YouTube video."""
    # Check if cached thumbnail exists
    cache_path = f"cache/{videoid}.png"
    if os.path.isfile(cache_path):
        return cache_path

    # Validate YouTube video ID
    if not videoid or not re.match(r'^[a-zA-Z0-9_-]{11}$', videoid):
        return YOUTUBE_IMG_URL

    try:
        # Fetch video metadata
        results = VideosSearch(videoid, limit=1)
        result = (await results.next())["result"]
        if not result:
            return YOUTUBE_IMG_URL

        video = result[0]
        title = video.get("title", "Unsupported Title")
        title = re.sub(r"\W+", " ", title).title()
        duration = video.get("duration", "Unknown Mins")
        thumbnail = video.get("thumbnails", [{}])[0].get("url", "")
        views = video.get("viewCount", {}).get("text", "Unknown Views")
        channel = video.get("channel", {}).get("name", "Unknown Channel")

        if not thumbnail:
            return YOUTUBE_IMG_URL

        # Download thumbnail
        async with aiohttp.ClientSession() as session:
            for attempt in range(3):
                try:
                    async with session.get(thumbnail) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(f"cache/thumb{videoid}.png", mode="wb") as f:
                                await f.write(await resp.read())
                            break
                        if attempt == 2:
                            return YOUTUBE_IMG_URL
                except Exception:
                    if attempt == 2:
                        return YOUTUBE_IMG_URL

        # Process image
        youtube = Image.open(f"cache/thumb{videoid}.png")
        image1 = changeImageSize(1280, 720, youtube)
        image2 = image1.convert("RGBA")
        background = image2.filter(filter=ImageFilter.BoxBlur(10))
        enhancer = ImageEnhance.Brightness(background)
        background = enhancer.enhance(0.7)

        # Prepare square thumbnail with rounded corners
        thumb_size = 450
        Xcenter = youtube.width / 2
        Ycenter = youtube.height / 2
        aspect_ratio = youtube.width / youtube.height

        # Dynamic thumbnail cropping based on aspect ratio
        if aspect_ratio > 1:  # Landscape
            crop_width = min(youtube.width, youtube.height * 1)
            crop_height = crop_width / 1
        else:  # Portrait or square
            crop_height = min(youtube.height, youtube.width * 1)
            crop_width = crop_height * 1

        x1 = Xcenter - crop_width / 2
        y1 = Ycenter - crop_height / 2
        x2 = Xcenter + crop_width / 2
        y2 = Ycenter + crop_height / 2
        logo = youtube.crop((x1, y1, x2, y2))
        logo = ImageOps.fit(logo, (thumb_size, thumb_size), centering=(0.5, 0.5), method=Image.Resampling.LANCZOS)
        mask = Image.new("L", (thumb_size, thumb_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), (thumb_size, thumb_size)], radius=20, fill=255)
        logo.putalpha(mask)
        thumb_gap = 40
        logo_pos_x = image2.width - thumb_size - thumb_gap
        logo_pos_y = (image2.height - thumb_size) // 2
        background.paste(logo, (logo_pos_x, logo_pos_y), logo)

        # Initialize drawing context and fonts
        draw = ImageDraw.Draw(background)
        try:
            font = ImageFont.truetype("AnonXMusic/assets/font3.ttf", 35)  # Title
            font2 = ImageFont.truetype("AnonXMusic/assets/font3.ttf", 45)  # Now Playing
            arial = ImageFont.truetype("AnonXMusic/assets/font3.ttf", 28)  # Views, Duration, Channel
            name_font = ImageFont.truetype("AnonXMusic/assets/font4.ttf", 28)  # App name
        except IOError:
            font = font2 = arial = name_font = ImageFont.load_default()

        # Text positions and gaps
        padding = 5  # Reduced padding for closer text-box fit
        box_gap = 10  # Reduced gap between boxes for tighter layout
        max_box_width = logo_pos_x - thumb_gap - 100  # Adjusted to maintain gap from thumbnail

        # Prepare text with dynamic truncation
        title = truncate_text(title, 20)
        views = truncate_text(views, 20)
        duration = truncate_text(duration, 15)
        channel = truncate_text(channel, 15)

        # Wrap title text
        para = textwrap.wrap(title, width=25)
        text_lines = ["Now Playing"] + para[:2] + [f"Views: {views}", f"Duration: {duration}", f"Channel: {channel}"]
        text_heights = []
        text_widths = []

        # Calculate text sizes
        for i, line in enumerate(text_lines):
            font_to_use = font2 if i == 0 else font if i in [1, 2] else arial
            bbox = draw.textbbox((0, 0), line, font=font_to_use)
            text_width = min(bbox[2] - bbox[0], max_box_width - 2 * padding)
            text_height = bbox[3] - bbox[1]
            text_heights.append(text_height)
            text_widths.append(text_width)

        # Calculate total text block height and width for centering
        total_text_height = sum(text_heights) + (len(text_lines) - 1) * box_gap + 2 * padding
        total_text_width = max(text_widths) + 2 * padding
        start_x = (image2.width - total_text_width - thumb_size - thumb_gap) // 2  # Center horizontally
        start_y = (image2.height - total_text_height) // 2  # Center vertically

        # Now Playing box
        now_playing_width = min(text_widths[0] + 2 * padding, max_box_width)
        now_playing_height = text_heights[0] + padding
        radius = min(now_playing_width, now_playing_height) // 4  # Dynamic radius
        now_playing_box = Image.new("RGBA", (int(now_playing_width), int(now_playing_height)), (0, 0, 0, 0))
        now_playing_draw = ImageDraw.Draw(now_playing_box)
        now_playing_draw.rounded_rectangle(
            [(0, 0), (now_playing_width, now_playing_height)], radius=radius, fill=(0, 0, 0, 180)
        )
        now_playing_box = now_playing_box.filter(ImageFilter.GaussianBlur(2))
        background.paste(now_playing_box, (start_x - padding, start_y - padding // 2), now_playing_box)

        # Title box
        title_lines = para[:2]
        title_width = min(max(text_widths[i] for i in [1, 2] if i < len(text_widths)), max_box_width - 2 * padding)
        title_height = sum(text_heights[i] for i in [1, 2] if i < len(text_heights)) + (len(title_lines) - 1) * box_gap + padding
        radius = min(title_width + 2 * padding, title_height) // 4  # Dynamic radius
        title_box = Image.new("RGBA", (int(title_width + 2 * padding), int(title_height)), (0, 0, 0, 0))
        title_draw = ImageDraw.Draw(title_box)
        title_draw.rounded_rectangle(
            [(0, 0), (title_width + 2 * padding, title_height)], radius=radius, fill=(0, 0, 0, 180)
        )
        title_box = title_box.filter(ImageFilter.GaussianBlur(2))
        title_y = start_y + now_playing_height + box_gap
        background.paste(title_box, (start_x - padding, int(title_y)), title_box)

        # Info box (Views, Duration, Channel)
        info_lines = text_lines[3:] if len(text_lines) > 3 else []
        info_width = min(max(text_widths[i] for i in range(3, len(text_widths))), max_box_width - 2 * padding)
        info_height = sum(text_heights[i] for i in range(3, len(text_heights))) + (len(info_lines) - 1) * box_gap + padding
        radius = min(info_width + 2 * padding, info_height) // 4  # Dynamic radius
        info_box = Image.new("RGBA", (int(info_width + 2 * padding), int(info_height)), (0, 0, 0, 0))
        info_draw = ImageDraw.Draw(info_box)
        info_draw.rounded_rectangle(
            [(0, 0), (info_width + 2 * padding, info_height)], radius=radius, fill=(0, 0, 0, 180)
        )
        info_box = info_box.filter(ImageFilter.GaussianBlur(2))
        info_y = title_y + title_height + box_gap
        background.paste(info_box, (start_x - padding, int(info_y)), info_box)

        # Draw text
        current_y = start_y
        draw.text(
            (start_x, current_y), "Now Playing", fill="black", stroke_width=1, stroke_fill="white", font=font2
        )
        current_y = title_y + padding // 2
        for i, line in enumerate(title_lines):
            draw.text(
                (start_x, current_y), line, fill="white", stroke_width=1, stroke_fill="black", font=font
            )
            current_y += text_heights[i + 1] + box_gap
        current_y = info_y + padding // 2
        for i, line in enumerate(info_lines):
            draw.text(
                (start_x, current_y), line, fill="black", stroke_width=1, stroke_fill="white", font=arial
            )
            current_y += text_heights[i + 3] + box_gap

        # Draw app name
        draw.text((5, 5), f"{app.name}", fill="white", font=name_font)

        # Clean up temporary file and save final thumbnail
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass
        background.save(cache_path)
        return cache_path

    except Exception as e:
        print(f"Error in get_thumb: {e}")
        return YOUTUBE_IMG_URL
