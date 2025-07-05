from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from config import LOGGER_ID as LOG_ID
from AnonXMusic import app
from AnonXMusic.misc import SUDOERS
from AnonXMusic.utils.decorators.language import language

# Define the close button markup directly
def get_close_button():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="Close",
                    callback_data="close"
                )
            ]
        ]
    )

@app.on_message(filters.new_chat_members)
async def on_new_chat_members(_, message: Message):
    if app.id in [user.id for user in message.new_chat_members]:
        added_by = message.from_user.mention if message.from_user else "Unknown User"
        username = f"@{message.chat.username}" if message.chat.username else "None"
        log_message = (
            f"✫ <b><u>#New Group</u></b> :\n\n"
            f"Chat ID: {message.chat.id}\n"
            f"Chat Username: {username}\n"
            f"Chat Title: {message.chat.title}\n"
            f"Added By: {added_by}"
        )
        # Use close button as default
        button = get_close_button()
        # If user info is available, add user button
        if message.from_user:
            button = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=message.from_user.first_name,
                            user_id=message.from_user.id,
                        ),
                        InlineKeyboardButton(
                            text="Close",
                            callback_data="close"
                        )
                    ]
                ]
            )
        try:
            await app.send_message(chat_id=LOG_ID, text=log_message, reply_markup=button)
        except Exception as e:
            print(f"Failed to send new chat log: {e}")

@app.on_message(filters.left_chat_member)
async def on_left_chat_member(client: Client, message: Message):
    if app.id == message.left_chat_member.id:
        removed_by = message.from_user.mention if message.from_user else "Unknown User"
        username = f"@{message.chat.username}" if message.chat.username else "None"
        log_message = (
            f"✫ <b><u>#Left Group</u></b> :\n\n"
            f"Chat ID: {message.chat.id}\n"
            f"Chat Username: {username}\n"
            f"Chat Title: {message.chat.title}\n"
            f"Removed By: {removed_by}"
        )
        # Use close button as default
        button = get_close_button()
        # If user info is available, add user button
        if message.from_user:
            button = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=message.from_user.first_name,
                            user_id=message.from_user.id,
                        ),
                        InlineKeyboardButton(
                            text="Close",
                            callback_data="close"
                        )
                    ]
                ]
            )
        try:
            await app.send_message(chat_id=LOG_ID, text=log_message, reply_markup=button)
        except Exception as e:
            print(f"Failed to send left chat log: {e}")

# Optional: Handle the close button callback
@app.on_callback_query(filters.regex("close"))
async def close_button_handler(client: Client, callback_query):
    try:
        await callback_query.message.delete()
    except Exception as e:
        print(f"Failed to delete message: {e}")
