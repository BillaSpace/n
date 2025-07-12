import asyncio

from pyrogram import filters
from pyrogram.errors import FloodWait, UserNotParticipant, RPCError
from pyrogram.types import Message

from AnonXMusic import app
from AnonXMusic.misc import SUDOERS
from AnonXMusic.utils import get_readable_time
from AnonXMusic.utils.database import (
    add_banned_user,
    get_banned_count,
    get_banned_users,
    get_served_chats,
    is_banned_user,
    remove_banned_user,
)
from AnonXMusic.utils.decorators.language import language
from AnonXMusic.utils.extraction import extract_user
from config import BANNED_USERS


@app.on_message(filters.command(["gban", "globalban"]) & SUDOERS)
@language
async def global_ban(client, message: Message, _):
    user = await extract_user(message)
    if not user:
        return await message.reply_text(_["general_1"])
    
    if user.id == message.from_user.id:
        return await message.reply_text(_["gban_1"])
    elif user.id == app.id:
        return await message.reply_text(_["gban_2"])
    elif user.id in SUDOERS:
        return await message.reply_text(_["gban_3"])
    
    is_gbanned = await is_banned_user(user.id)
    if is_gbanned:
        return await message.reply_text(_["gban_4"].format(user.mention))

    if user.id not in BANNED_USERS:
        BANNED_USERS.add(user.id)

    chats_data = await get_served_chats()
    served_chats = [int(c.chat_id) if not isinstance(c, int) else int(c) for c in chats_data]

    time_expected = get_readable_time(len(served_chats))
    mystic = await message.reply_text(_["gban_5"].format(user.mention, time_expected))

    number_of_chats = 0
    for chat_id in served_chats:
        try:
            await app.ban_chat_member(chat_id, user.id)
            number_of_chats += 1
            try:
                async for msg in app.search_messages(chat_id, from_user=user.id):
                    try:
                        await app.delete_messages(chat_id, msg.id)
                        await asyncio.sleep(0.1)
                    except Exception:
                        continue
            except Exception:
                continue
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
        except Exception:
            continue

    await add_banned_user(user.id)
    await message.reply_text(
        _["gban_6"].format(
            app.mention,
            message.chat.title if message.chat else "Unknown",
            message.chat.id if message.chat else "N/A",
            user.mention,
            user.id,
            message.from_user.mention,
            number_of_chats,
        )
    )
    await mystic.delete()


@app.on_message(filters.command(["ungban"]) & SUDOERS)
@language
async def global_un(client, message: Message, _):
    user = await extract_user(message)
    if not user:
        return await message.reply_text(_["general_1"])

    is_gbanned = await is_banned_user(user.id)
    if not is_gbanned:
        return await message.reply_text(_["gban_7"].format(user.mention))

    if user.id in BANNED_USERS:
        BANNED_USERS.remove(user.id)

    chats_data = await get_served_chats()
    served_chats = [int(c.chat_id) if not isinstance(c, int) else int(c) for c in chats_data]

    time_expected = get_readable_time(len(served_chats))
    mystic = await message.reply_text(_["gban_8"].format(user.mention, time_expected))

    number_of_chats = 0
    for chat_id in served_chats:
        try:
            await app.unban_chat_member(chat_id, user.id)
            number_of_chats += 1
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
        except Exception:
            continue

    await remove_banned_user(user.id)
    await message.reply_text(_["gban_9"].format(user.mention, number_of_chats))
    await mystic.delete()


@app.on_message(filters.command(["gbannedusers", "gbanlist"]) & SUDOERS)
@language
async def gbanned_list(client, message: Message, _):
    counts = await get_banned_count()
    if counts == 0:
        return await message.reply_text(_["gban_10"])

    mystic = await message.reply_text(_["gban_11"])
    msg = _["gban_12"]
    count = 0
    users = await get_banned_users()
    for user_id in users:
        count += 1
        try:
            user = await app.get_users(user_id)
            name = user.first_name if not user.mention else user.mention
            msg += f"{count}➤ {name}\n"
        except Exception:
            msg += f"{count}➤ {user_id}\n"
            continue

    await mystic.edit_text(msg)
