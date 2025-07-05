import re
import time

from pyrogram import filters
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from AnonXMusic import app
from AnonXMusic.mongo.afkdb import add_afk, is_afk, remove_afk
from AnonXMusic.mongo.readable_time import get_readable_time


@app.on_message(filters.command(["afk"], prefixes=["/"]))
async def active_afk(_, message: Message):
    if message.sender_chat:
        return
    user_id = message.from_user.id
    verifier, reasondb = await is_afk(user_id)
    if verifier:
        await remove_afk(user_id)
        try:
            timeafk = reasondb["time"]
            reasonafk = reasondb["reason"]
            seenago = get_readable_time((int(time.time() - timeafk)))
            if reasonafk:
                await message.reply_text(
                    f"{message.from_user.first_name} ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ᴡᴀs ᴀᴡᴀʏ ғᴏʀ {seenago}\n\nʀᴇᴀsᴏɴ: {reasonafk}",
                    disable_web_page_preview=True,
                )
            else:
                await message.reply_text(
                    f"{message.from_user.first_name} ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ᴡᴀs ᴀᴡᴀʏ ғᴏʀ {seenago}",
                    disable_web_page_preview=True,
                )
        except Exception:
            await message.reply_text(
                f"{message.from_user.first_name} ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ",
                disable_web_page_preview=True,
            )
        return

    if len(message.command) == 1:
        details = {
            "type": "text",
            "time": time.time(),
            "data": None,
            "reason": None,
        }
    else:
        _reason = (message.text.split(None, 1)[1].strip())[:100]
        details = {
            "type": "text_reason",
            "time": time.time(),
            "data": None,
            "reason": _reason,
        }

    await add_afk(user_id, details)
    await message.reply_text(f"{message.from_user.first_name} ɪs ɴᴏᴡ ᴀғᴋ")


chat_watcher_group = 1


@app.on_message(
    ~filters.me & ~filters.bot & ~filters.via_bot,
    group=chat_watcher_group,
)
async def chat_watcher_func(_, message: Message):
    if message.sender_chat:
        return
    userid = message.from_user.id
    user_name = message.from_user.first_name
    if message.entities:
        possible = ["/afk", f"/afk@{app.username}"]
        message_text = message.text or message.caption
        for entity in message.entities:
            if entity.type == MessageEntityType.BOT_COMMAND:
                if (message_text[0 : 0 + entity.length]).lower() in possible:
                    return

    msg = ""
    replied_user_id = 0

    # Check if the user who sent the message is AFK
    verifier, reasondb = await is_afk(userid)
    if verifier:
        await remove_afk(userid)
        try:
            timeafk = reasondb["time"]
            reasonafk = reasondb["reason"]
            seenago = get_readable_time((int(time.time() - timeafk)))
            if reasonafk:
                msg += f"{user_name[:25]} ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ᴡᴀs ᴀᴡᴀʏ ғᴏʀ {seenago}\n\nʀᴇᴀsᴏɴ: {reasonafk}\n\n"
            else:
                msg += f"{user_name[:25]} ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ᴡᴀs ᴀᴡᴀʏ ғᴏʀ {seenago}\n\n"
        except:
            msg += f"{user_name[:25]} ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ\n\n"

    # Check if a replied-to user is AFK
    if message.reply_to_message:
        try:
            replied_first_name = message.reply_to_message.from_user.first_name
            replied_user_id = message.reply_to_message.from_user.id
            verifier, reasondb = await is_afk(replied_user_id)
            if verifier:
                try:
                    timeafk = reasondb["time"]
                    reasonafk = reasondb["reason"]
                    seenago = get_readable_time((int(time.time() - timeafk)))
                    if reasonafk:
                        msg += f"{replied_first_name[:25]} ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}\n\nʀᴇᴀsᴏɴ: {reasonafk}\n\n"
                    else:
                        msg += f"{replied_first_name[:25]} ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}\n\n"
                except:
                    msg += f"{replied_first_name[:25]} ɪs ᴀғᴋ\n\n"
        except:
            pass

    # Check if mentioned users are AFK
    if message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.MENTION:
                found = re.findall("@([_0-9a-zA-Z]+)", message.text)
                try:
                    get_user = found[0]
                    user = await app.get_users(get_user)
                    if user.id == replied_user_id:
                        continue
                    verifier, reasondb = await is_afk(user.id)
                    if verifier:
                        try:
                            timeafk = reasondb["time"]
                            reasonafk = reasondb["reason"]
                            seenago = get_readable_time((int(time.time() - timeafk)))
                            if reasonafk:
                                msg += f"{user.first_name[:25]} ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}\n\nʀᴇᴀsᴏɴ: {reasonafk}\n\n"
                            else:
                                msg += f"{user.first_name[:25]} ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}\n\n"
                        except:
                            msg += f"{user.first_name[:25]} ɪs ᴀғᴋ\n\n"
                except:
                    continue
            elif entity.type == MessageEntityType.TEXT_MENTION:
                try:
                    user_id = entity.user.id
                    if user_id == replied_user_id:
                        continue
                    first_name = entity.user.first_name
                    verifier, reasondb = await is_afk(user_id)
                    if verifier:
                        try:
                            timeafk = reasondb["time"]
                            reasonafk = reasondb["reason"]
                            seenago = get_readable_time((int(time.time() - timeafk)))
                            if reasonafk:
                                msg += f"{first_name[:25]} ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}\n\nʀᴇᴀsᴏɴ: {reasonafk}\n\n"
                            else:
                                msg += f"{first_name[:25]} ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}\n\n"
                        except:
                            msg += f"{first_name[:25]} ɪs ᴀғᴋ\n\n"
                except:
                    continue

    if msg:
        await message.reply_text(msg, disable_web_page_preview=True)
