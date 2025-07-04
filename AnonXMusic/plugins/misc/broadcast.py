import asyncio
import logging
from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait, RPCError, ChatAdminRequired, ChannelPrivate

from AnonXMusic import app
from AnonXMusic.misc import SUDOERS
from AnonXMusic.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_client,
    get_served_chats,
    get_served_users,
)
from AnonXMusic.utils.decorators.language import language
from AnonXMusic.utils.formatters import alpha_to_int
from config import adminlist

# Configure logging
logging.basicConfig(filename='broadcast.log', level=logging.DEBUG)

IS_BROADCASTING = False

@app.on_message(filters.command("broadcast") & SUDOERS)
@language
async def braodcast_message(client, message, _):
    global IS_BROADCASTING

    if "-group" in message.text or "-user" in message.text:
        if not message.reply_to_message or not (message.reply_to_message.photo or message.reply_to_message.text):
            return await message.reply_text("Please reply to a text or image message for broadcasting.")

        # Extract data from the replied message
        if message.reply_to_message.photo:
            content_type = 'photo'
            file_id = message.reply_to_message.photo.file_id
        else:
            content_type = 'text'
            text_content = message.reply_to_message.text

        caption = message.reply_to_message.caption
        reply_markup = message.reply_to_message.reply_markup if hasattr(message.reply_to_message, 'reply_markup') else None

        IS_BROADCASTING = True
        await message.reply_text(_["broad_1"])

        if "-group" in message.text:
            # Broadcasting to chats
            sent_chats = 0
            chats = await get_served_chats()  # Returns list of integers
            logging.debug(f"get_served_chats returned: {chats}")
            if not chats:
                await message.reply_text("No served chats found in the database.")
                IS_BROADCASTING = False
                return
            for i in chats:
                try:
                    # Validate chat ID
                    if not isinstance(i, int) or i >= 0:
                        logging.warning(f"Invalid chat ID {i}, skipping.")
                        continue
                    # Check if bot is still a member of the chat
                    await app.get_chat(i)
                    if content_type == 'photo':
                        await app.send_photo(chat_id=i, photo=file_id, caption=caption, reply_markup=reply_markup)
                    else:
                        await app.send_message(chat_id=i, text=text_content, reply_markup=reply_markup)
                    sent_chats += 1
                    await asyncio.sleep(0.2)
                except FloodWait as fw:
                    logging.info(f"FloodWait for chat {i}: waiting {fw.x} seconds")
                    await asyncio.sleep(fw.x)
                except ChannelPrivate:
                    logging.error(f"Chat {i} is private or inaccessible, skipping.")
                    continue
                except RPCError as e:
                    logging.error(f"Error broadcasting to chat {i}: {e}")
                    continue
            await message.reply_text(f"Broadcast to chats completed! Sent to {sent_chats} chats.")

        if "-user" in message.text:
            # Broadcasting to users
            sent_users = 0
            users = await get_served_users()  # Returns list of integers
            logging.debug(f"get_served_users returned: {users}")
            if not users:
                await message.reply_text("No served users found in the database.")
                IS_BROADCASTING = False
                return
            for i in users:
                try:
                    # Validate user ID
                    if not isinstance(i, int) or i <= 0:
                        logging.warning(f"Invalid user ID {i}, skipping.")
                        continue
                    if content_type == 'photo':
                        await app.send_photo(chat_id=i, photo=file_id, caption=caption, reply_markup=reply_markup)
                    else:
                        await app.send_message(chat_id=i, text=text_content, reply_markup=reply_markup)
                    sent_users += 1
                    await asyncio.sleep(0.2)
                except FloodWait as fw:
                    logging.info(f"FloodWait for user {i}: waiting {fw.x} seconds")
                    await asyncio.sleep(fw.x)
                except RPCError as e:
                    logging.error(f"Error broadcasting to user {i}: {e}")
                    continue
            await message.reply_text(f"Broadcast to users completed! Sent to {sent_users} users.")

        IS_BROADCASTING = False
        return

    if message.reply_to_message:
        x = message.reply_to_message.id
        y = message.chat.id
        reply_markup = message.reply_to_message.reply_markup if message.reply_to_message.reply_markup else None
        content = None
    else:
        if len(message.command) < 2:
            return await message.reply_text(_["broad_2"])
        query = message.text.split(None, 1)[1]
        if "-pin" in query:
            query = query.replace("-pin", "")
        if "-nobot" in query:
            query = query.replace("-nobot", "")
        if "-pinloud" in query:
            query = query.replace("-pinloud", "")
        if "-assistant" in message.text:
            query = query.replace("-assistant", "")
        if "-user" in query:
            query = query.replace("-user", "")
        if query == "":
            return await message.reply_text(_["broad_8"])

    IS_BROADCASTING = True
    await message.reply_text(_["broad_1"])

    if "-nobot" not in message.text:
        sent = 0
        pin = 0
        chats = []
        schats = await get_served_chats()  # Returns list of integers
        logging.debug(f"get_served_chats (nobot) returned: {schats}")
        if not schats:
            await message.reply_text("No served chats found in the database.")
            IS_BROADCASTING = False
            return
        for chat in schats:
            if not isinstance(chat, int) or chat >= 0:
                logging.warning(f"Invalid chat ID {chat}, skipping.")
                continue
            chats.append(int(chat))  # Convert Int64 to int
        for i in chats:
            try:
                # Check if bot is still a member of the chat
                await app.get_chat(i)
                m = (
                    await app.copy_message(chat_id=i, from_chat_id=y, message_id=x, reply_markup=reply_markup)
                    if message.reply_to_message
                    else await app.send_message(i, text=query)
                )
                if "-pin" in message.text:
                    try:
                        await m.pin(disable_notification=True)
                        pin += 1
                    except (RPCError, ChatAdminRequired) as e:
                        logging.error(f"Error pinning in chat {i}: {e}")
                        continue
                elif "-pinloud" in message.text:
                    try:
                        await m.pin(disable_notification=False)
                        pin += 1
                    except (RPCError, ChatAdminRequired) as e:
                        logging.error(f"Error pinning in chat {i}: {e}")
                        continue
                sent += 1
                await asyncio.sleep(0.2)
            except FloodWait as fw:
                logging.info(f"FloodWait for chat {i}: waiting {fw.value} seconds")
                await asyncio.sleep(fw.value)
            except ChannelPrivate:
                logging.error(f"Chat {i} is private or inaccessible, skipping.")
                continue
            except RPCError as e:
                logging.error(f"Error broadcasting to chat {i}: {e}")
                continue
        try:
            await message.reply_text(_["broad_3"].format(sent, pin))
        except:
            pass

    if "-user" in message.text:
        susr = 0
        served_users = []
        susers = await get_served_users()  # Returns list of integers
        logging.debug(f"get_served_users (nobot) returned: {susers}")
        if not susers:
            await message.reply_text("No served users found in the database.")
            IS_BROADCASTING = False
            return
        for user in susers:
            if not isinstance(user, int) or user <= 0:
                logging.warning(f"Invalid user ID {user}, skipping.")
                continue
            served_users.append(int(user))  # Convert Int64 to int
        for i in served_users:
            try:
                m = (
                    await app.copy_message(chat_id=i, from_chat_id=y, message_id=x, reply_markup=reply_markup)
                    if message.reply_to_message
                    else await app.send_message(i, text=query)
                )
                susr += 1
                await asyncio.sleep(0.2)
            except FloodWait as fw:
                logging.info(f"FloodWait for user {i}: waiting {fw.value} seconds")
                await asyncio.sleep(fw.value)
            except RPCError as e:
                logging.error(f"Error broadcasting to user {i}: {e}")
                continue
        try:
            await message.reply_text(_["broad_4"].format(susr))
        except:
            pass

    if "-assistant" in message.text:
        aw = await message.reply_text(_["broad_5"])
        text = _["broad_6"]
        from AnonXMusic.core.userbot import assistants

        for num in assistants:
            sent = 0
            client = await get_client(num)
            async for dialog in client.get_dialogs():
                try:
                    await client.forward_messages(
                        dialog.chat.id, y, x
                    ) if message.reply_to_message else await client.send_message(
                        dialog.chat.id, text=query
                    )
                    sent += 1
                    await asyncio.sleep(3)
                except FloodWait as fw:
                    logging.info(f"FloodWait for assistant {num} in chat {dialog.chat.id}: waiting {fw.value} seconds")
                    await asyncio.sleep(fw.value)
                except ChannelPrivate:
                    logging.error(f"Chat {dialog.chat.id} is private or inaccessible for assistant {num}, skipping.")
                    continue
                except RPCError as e:
                    logging.error(f"Error broadcasting via assistant {num} to chat {dialog.chat.id}: {e}")
                    continue
            text += _["broad_7"].format(num, sent)
        try:
            await aw.edit_text(text)
        except:
            pass
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
        except ChannelPrivate:
            logging.error(f"Chat {chat_id} is private or inaccessible in auto_clean, skipping.")
            continue
        except Exception as e:
            logging.error(f"Error in auto_clean for chat {chat_id}: {e}")
            continue

asyncio.create_task(auto_clean())
