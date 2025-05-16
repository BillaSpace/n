from pyrogram import filters
from pyrogram.types import Message
from unidecode import unidecode

from AnonXMusic import app
from AnonXMusic.misc import SUDOERS
from AnonXMusic.utils.database import (
    get_active_chats,
    get_active_video_chats,
)


@app.on_message(filters.command(["ac"]) & SUDOERS)
async def active_chats(_, message: Message):
    mystic = await message.reply_text("» ɢᴇᴛᴛɪɴɢ ᴀᴄᴛɪᴠᴇ ᴄʜᴀᴛs ʟɪsᴛ...")
    
    # Get active audio and video chats
    audio_chats = await get_active_chats()
    video_chats = await get_active_video_chats()

    # Count active chats
    active_audio_count = len(audio_chats)
    active_video_count = len(video_chats)

    # Prepare the text to be sent
    text = f"<b>» ᴀᴄᴛɪᴠᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs:</b> {active_audio_count}\n"
    text += f"<b>» ᴀᴄᴛɪᴠᴇ ᴠɪᴅᴇᴏ ᴄʜᴀᴛs:</b> {active_video_count}\n"

    # If no active chats
    if active_audio_count == 0 and active_video_count == 0:
        await mystic.edit_text(f"» ɴᴏ ᴀᴄᴛɪᴠᴇ ᴄʜᴀᴛs ᴏɴ {app.mention}.")
    else:
        await mystic.edit_text(text, disable_web_page_preview=True)
