import asyncio
from pyrogram import filters
from pyrogram.errors import FloodWait
from AnonXMusic import app
from AnonXMusic.misc import SUDOERS
from AnonXMusic.utils.database import (
    get_served_chats,
    get_served_users,
    get_client,
    get_active_chats,
    get_authuser_names,
)
from AnonXMusic.utils.decorators.language import language
from pyrogram.enums import ChatMembersFilter
from AnonXMusic.utils.formatters import alpha_to_int
from config import adminlist


IS_BROADCASTING = False


@app.on_message(filters.command("broadcast") & SUDOERS)
@language
async def broadcast_message(client, message, _):
    global IS_BROADCASTING
    if IS_BROADCASTING:
        return await message.reply_text("A broadcast is already in progress.")
    
    IS_BROADCASTING = True

    # Determine message content
    if message.reply_to_message:
        msg_id = message.reply_to_message.id
        chat_id = message.chat.id
        query = None
    else:
        if len(message.command) < 2:
            return await message.reply_text(_["broad_2"])
        query = message.text.split(None, 1)[1].replace(
            "-pin", "").replace("-nobot", "").replace("-pinloud", "").replace("-assistant", "").replace("-user", "").strip()
        if not query:
            return await message.reply_text(_["broad_8"])

    await message.reply_text("Broadcasting started...")

    async def send_message(chat_list, is_user=False):
        """Sends messages concurrently to a list of chat/user IDs"""
        sent = 0
        pin = 0
        tasks = []

        async def send_single_message(chat_id):
            nonlocal sent, pin
            try:
                if message.reply_to_message:
                    m = await app.forward_messages(chat_id, chat_id, msg_id)
                else:
                    m = await app.send_message(chat_id, text=query)
                sent += 1

                if "-pin" in message.text:
                    await m.pin(disable_notification=True)
                    pin += 1
                elif "-pinloud" in message.text:
                    await m.pin(disable_notification=False)
                    pin += 1
            except FloodWait as fw:
                if fw.value > 200:
                    return
                await asyncio.sleep(fw.value)
            except Exception:
                pass

        for chat_id in chat_list:
            tasks.append(send_single_message(chat_id))

        await asyncio.gather(*tasks)
        return sent, pin

    # Broadcast to groups
    sent, pin = 0, 0
    if "-nobot" not in message.text:
        chats = [int(chat["chat_id"]) for chat in await get_served_chats()]
        sent, pin = await send_message(chats)
        await message.reply_text(_["broad_3"].format(sent, pin))

    # Broadcast to users
    if "-user" in message.text:
        users = [int(user["user_id"]) for user in await get_served_users()]
        user_sent, _ = await send_message(users, is_user=True)
        await message.reply_text(_["broad_4"].format(user_sent))

    # Broadcast via assistants
    if "-assistant" in message.text:
        aw = await message.reply_text(_["broad_5"])
        from AnonXMusic.core.userbot import assistants

        async def send_via_assistants():
            tasks = []
            for num in assistants:
                client = await get_client(num)

                async def send_for_client():
                    sent = 0
                    async for dialog in client.get_dialogs():
                        try:
                            if message.reply_to_message:
                                await client.forward_messages(dialog.chat.id, chat_id, msg_id)
                            else:
                                await client.send_message(dialog.chat.id, text=query)
                            sent += 1
                        except FloodWait as fw:
                            if fw.value > 200:
                                return
                            await asyncio.sleep(fw.value)
                        except:
                            pass
                    return f"Assistant {num}: {sent} messages sent\n"

                tasks.append(send_for_client())

            results = await asyncio.gather(*tasks)
            return "".join(filter(None, results))

        assist_msg = await send_via_assistants()
        await aw.edit_text(_["broad_6"] + assist_msg)

    IS_BROADCASTING = False

async def auto_clean():
    while not await asyncio.sleep(10):
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    async for user in app.get_chat_members(
                        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                    ):
                        if user.privileges.can_manage_video_chats:
                            adminlist[chat_id].append(user.user.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        adminlist[chat_id].append(user_id)
        except:
            continue


asyncio.create_task(auto_clean())
