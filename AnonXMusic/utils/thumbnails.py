import os
import re
import textwrap
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.future import VideosSearch

from AnonXMusic import app
from config import YOUTUBE_IMG_URL

def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    ratio = min(widthRatio, heightRatio)
    newWidth = int(ratio * image.size[0])
    newHeight = int(ratio * image.size[1])
    return image.resize((newWidth, newHeight), Image.Resampling.LANCZOS)

def truncate_text(text, max_length, add_ellipsis=True):
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..." if add_ellipsis else text[:max_length]

async def get_thumb(videoid):
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"

    if not videoid or not re.match(r'^[a-zA-Z0-9_-]{11}$', videoid):
        return YOUTUBE_IMG_URL

    try:
        results = VideosSearch(videoid, limit=1)
        result = (await results.next())["result"]
        if not result:
            return YOUTUBE_IMG_URL

        for video in result:
            title = video.get("title", "Unsupported Title")
            title = re.sub("\W+", " ", title).title()
            duration = video.get("duration", "Unknown Mins")
            thumbnail = video.get("thumbnails", [{}])[0].get("url", "")
            views = video.get("viewCount", {}).get("short", "Unknown Views")
            channel = video.get("channel", {}).get("name", "Unknown Channel")

        if not thumbnail:
            return YOUTUBE_IMG_URL

        async with aiohttp.ClientSession() as session:
            for attempt in range(3):
                try:
                    async with session.get(thumbnail) as resp:
                        if resp.status == 200:
                            f = await aiofiles.open(f"cache/thumb{videoid}.png", mode="wb")
                            await f.write(await resp.read())
                            await f.close()
                            break
                        else:
                            if attempt == 2:
                                return YOUTUBE_IMG_URL
                except Exception:
                    if attempt == 2:
                        return YOUTUBE_IMG_URL

        youtube = Image.open(f"cache/thumb{videoid}.png")
        image1 = changeImageSize(1280, 720, youtube)
        image2 = image1.convert("RGBA")
        background = image2.filter(filter=ImageFilter.BoxBlur(10))
        enhancer = ImageEnhance.Brightness(background)
        background = enhancer.enhance(0.7)

        # Prepare square thumbnail with rounded corners
        thumb_size = 400
        Xcenter = youtube.width / 2
        Ycenter = youtube.height / 2
        x1 = Xcenter - 250
        y1 = Ycenter - 250
        x2 = Xcenter + 250
        y2 = Ycenter + 250
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

        draw = ImageDraw.Draw(background)
        font = ImageFont.truetype("AnonXMusic/assets/font3.ttf", 35)  # Title
        font2 = ImageFont.truetype("AnonXMusic/assets/font3.ttf", 45)  # Now Playing
        arial = ImageFont.truetype("AnonXMusic/assets/font4.ttf", 28)  # Views, Duration, Channel
        name_font = ImageFont.truetype("AnonXMusic/assets/font4.ttf", 28)  # App name

        # Text positions and gaps
        start_x = 50
        start_y = 60
        padding = 10
        box_gap = 15
        max_box_width = logo_pos_x - start_x - 60

        # Prepare text with dynamic truncation
        title = truncate_text(title, 50, add_ellipsis=True)
        views = truncate_text(views, 20, add_ellipsis=True)
        duration = truncate_text(duration, 20, add_ellipsis=True)
        channel = truncate_text(channel, 25, add_ellipsis=True)

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

        # Now Playing box
        now_playing_width = min(text_widths[0] + 2 * padding, max_box_width)
        now_playing_height = text_heights[0] + padding
        now_playing_box = Image.new("RGBA", (int(now_playing_width), int(now_playing_height)), (0, 0, 0, 0))
        now_playing_draw = ImageDraw.Draw(now_playing_box)
        now_playing_draw.rounded_rectangle(
            [(0, 0), (now_playing_width, now_playing_height)],
            radius=8,
            fill=(0, 0, 0, 180)
        )
        now_playing_box = now_playing_box.filter(ImageFilter.GaussianBlur(2))
        background.paste(now_playing_box, (start_x - padding, start_y - padding // 2), now_playing_box)

        # Title box
        title_lines = para[:2]
        title_width = min(max([text_widths[i] for i in [1, 2] if i < len(text_widths)]), max_box_width - 2 * padding)
        title_height = sum([text_heights[i] for i in [1, 2] if i < len(text_heights)]) + (len(title_lines) - 1) * 8 + padding
        title_box = Image.new("RGBA", (int(title_width + 2 * padding), int(title_height)), (0, 0, 0, 0))
        title_draw = ImageDraw.Draw(title_box)
        title_draw.rounded_rectangle(
            [(0, 0), (title_width + 2 * padding, title_height)],
            radius=8,
            fill=(0, 0, 0, 180)
        )
        title_box = title_box.filter(ImageFilter.GaussianBlur(2))
        title_y = start_y + now_playing_height + box_gap
        background.paste(title_box, (start_x - padding, int(title_y)), title_box)

        # Info box ( Insights, Duration, Channel)
        info_lines = text_lines[3:] if len(text_lines) > 3 else []
        info_width = min(max([text_widths[i] for i in range(3, len(text_widths))]), max_box_width - 2 * padding)
        info_height = sum([text_heights[i] for i in range(3, len(text_heights))]) + (len(info_lines) - 1) * 8 + padding
        info_box = Image.new("RGBA", (int(info_width + 2 * padding), int(info_height)), (0, 0, 0, 0))
        info_draw = ImageDraw.Draw(info_box)
        info_draw.rounded_rectangle(
            [(0, 0), (info_width + 2 * padding, info_height)],
            radius=8,
            fill=(0, 0, 0, 180)
        )
        info_box = info_box.filter(ImageFilter.GaussianBlur(2))
        info_y = title_y + title_height + box_gap
        background.paste(info_box, (start_x - padding, int(info_y)), info_box)

        # Draw text
        current_y = start_y
        draw.text(
            (start_x, current_y),
            "Now Playing",
            fill="white",
            stroke_width=1,
            stroke_fill="black",
            font=font2,
        )
        current_y = title_y + padding // 2
        for i, line in enumerate(title_lines):
            draw.text(
                (start_x, current_y),
                line,
                fill="white",
                stroke_width=1,
                stroke_fill="black",
                font=font,
            )
            current_y += text_heights[i + 1] + 8
        current_y = info_y + padding // 2
        for i, line in enumerate(info_lines):
            draw.text(
                (start_x, current_y),
                line,
                fill="white",
                stroke_width=1,
                stroke_fill="black",
                font=arial,
            )
            current_y += text_heights[i + 3] + 8

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

    except Exception:
        return YOUTUBE_IMG_URL
