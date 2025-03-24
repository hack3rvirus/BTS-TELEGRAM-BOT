# bot.py
import os
import time
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, BotCommandScopeChat
from telegram.error import NetworkError
import database
from datetime import datetime, timedelta


# Retrieve the bot token from environment variables
TOKEN = os.getenv("TOKEN")
PAYMENT_ADMIN = "@BTS_SUBSCRIPTION"  # First admin for payment
MAIN_ADMIN = "@BTSADMIN0"  # Second admin for main chat
ADMIN_IDS = [7104554772, 7105191693]  # List of admin IDs

def get_user_keyboard(telegram_id):
    # Base keyboard for all users
    keyboard = [["Subscribe"], ["Help"], ["Exit"]]
    # Add "Chat with Main Admin" button if the user has paid
    if database.has_paid(telegram_id):
        keyboard.insert(0, ["Chat with Your Favorite BTS Artist 🌟"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def set_user_commands(context, telegram_id):
    # Define commands for non-admins
    user_commands = [
        BotCommand("start", "Register with @BTS0BOT_BOT"),
        BotCommand("subscribe", "Subscribe to chat with your favorite BTS artist"),
        BotCommand("help", "Get support from BTS admins")
    ]
    # Define commands for admins
    admin_commands = [
        BotCommand("start", "Register with @BTS0BOT_BOT"),
        BotCommand("users", "(Admin) List all users"),
        BotCommand("chat", "(Admin) Chat with a user"),
        BotCommand("broadcast", "(Admin) Broadcast a message to all users"),
        BotCommand("remind", "(Admin) Send subscription reminders"),
        BotCommand("exit", "(Admin) Exit a chat session"),
        BotCommand("pending_payments", "(Admin) View pending payments"),
        BotCommand("confirm_payment", "(Admin) Confirm a payment")
    ]
    # Set commands based on user role
    commands = admin_commands if telegram_id in ADMIN_IDS else user_commands
    # Use BotCommandScopeChat for the scope
    scope = BotCommandScopeChat(chat_id=telegram_id)
    context.bot.set_my_commands(commands=commands, scope=scope)

def register_user(update, context):
    user = update.message.from_user
    chat_id = update.message.chat_id
    telegram_id = user.id
    username = user.username if user.username else "NoUsername"
    print(f"Registering user: {telegram_id}, Username: {username}, Chat ID: {chat_id}")  # Debug

    try:
        database.save_user(telegram_id, username, chat_id)
        database.log_interaction(telegram_id, "handshake")
        print("User saved to database")  # Debug
        return True
    except Exception as e:
        print(f"Database error: {e}")  # Debug
        return False

def start(update, context):
    print("Received /start command")  # Debug
    telegram_id = update.message.from_user.id
    username = update.message.from_user.username if update.message.from_user.username else "User"
    # Set commands based on user role
    set_user_commands(context, telegram_id)
    if register_user(update, context):
        greeting = f"Hello, {username}! Welcome to Big Hit Music with @BTS0BOT_BOT! 🎵\nI’m here to help you connect with your favorite BTS artist. 🌟\n\nPlease choose an option:"
        update.message.reply_text(greeting, reply_markup=get_user_keyboard(telegram_id))

def subscribe_command(update, context):
    telegram_id = update.message.from_user.id
    if telegram_id in ADMIN_IDS:
        update.message.reply_text("This option is not available for admins.")
        return
    subscribe(update, context)

def help_command(update, context):
    telegram_id = update.message.from_user.id
    if telegram_id in ADMIN_IDS:
        update.message.reply_text("This option is not available for admins.")
        return
    context.user_data['help_mode'] = True
    update.message.reply_text("Please type your message for the BTS admins, or type /cancel to stop:")

def handle_message(update, context):
    print("Received message")  # Debug
    telegram_id = update.message.from_user.id
    message_text = update.message.text

    # Set commands based on user role (in case they weren't set yet)
    set_user_commands(context, telegram_id)

    # Check if the admin is in a chat session
    if telegram_id in ADMIN_IDS and 'chat_with' in context.user_data:
        return handle_admin_chat_message(update, context)

    # Check if the admin is searching for a user
    if telegram_id in ADMIN_IDS and context.user_data.get('searching_users'):
        return handle_user_search(update, context)

    # Check if the user is in help mode
    if context.user_data.get('help_mode'):
        return handle_help_message(update, context)

    if not database.user_exists(telegram_id):
        if register_user(update, context):
            username = update.message.from_user.username if update.message.from_user.username else "User"
            greeting = f"Hello, {username}! Welcome to Big Hit Music with @BTS0BOT_BOT! 🎵\nI’m here to help you connect with your favorite BTS artist. 🌟\n\nPlease choose an option:"
            update.message.reply_text(greeting, reply_markup=get_user_keyboard(telegram_id))
        return

    # Handle button clicks
    if message_text == "Subscribe":
        if telegram_id in ADMIN_IDS:
            update.message.reply_text("This option is not available for admins.")
            return
        subscribe(update, context)
    elif message_text == "Help":
        if telegram_id in ADMIN_IDS:
            update.message.reply_text("This option is not available for admins.")
            return
        context.user_data['help_mode'] = True
        update.message.reply_text("Please type your message for the BTS admins, or type /cancel to stop:")
    elif message_text == "Exit":
        update.message.reply_text("Goodbye! To start again, type /start.", reply_markup=ReplyKeyboardRemove())
    elif message_text == "Chat with Your Favorite BTS Artist 🌟":
        if database.has_paid(telegram_id):
            update.message.reply_text(f"You can now chat with your favorite BTS artist at: {MAIN_ADMIN} 🎤🎶")
        else:
            update.message.reply_text("No access. Please complete your subscription payment to chat with your favorite BTS artist. 🎵")
    else:
        update.message.reply_text("Please choose an option:", reply_markup=get_user_keyboard(telegram_id))
        database.log_interaction(telegram_id, message_text)

def handle_help_message(update, context):
    telegram_id = update.message.from_user.id
    message = update.message.text

    if message == "/cancel":
        del context.user_data['help_mode']
        update.message.reply_text("Help request cancelled.", reply_markup=get_user_keyboard(telegram_id))
        return True

    # Send the user's message to all admins
    users = database.get_all_users()
    user_dict = {user['telegram_id']: user for user in users}
    user = user_dict.get(telegram_id)

    for admin_id in ADMIN_IDS:
        try:
            context.bot.send_message(
                chat_id=admin_id,
                text=f"Help request from {user['username']} (ID: {telegram_id}):\n{message}"
            )
        except Exception as e:
            print(f"Failed to send help request to admin {admin_id}: {e}")

    update.message.reply_text("Your message has been sent to the BTS admins. Please wait for a response. 💜", reply_markup=get_user_keyboard(telegram_id))
    del context.user_data['help_mode']
    return True

def subscribe(update, context):
    print("Received Subscribe button click")  # Debug
    telegram_id = update.message.from_user.id

    if not database.user_exists(telegram_id):
        if register_user(update, context):
            username = update.message.from_user.username if update.message.from_user.username else "User"
            greeting = f"Hello, {username}! Welcome to Big Hit Music with @BTS0BOT_BOT! 🎵\nI’m here to help you connect with your favorite BTS artist. 🌟\n\nPlease choose an option:"
            update.message.reply_text(greeting, reply_markup=get_user_keyboard(telegram_id))
        return

    start_date = datetime.now().date()
    end_date = start_date + timedelta(days=30)

    try:
        database.save_subscription(telegram_id, start_date, end_date)
        # Subscription message
        update.message.reply_text(
            f"Our monthly subscription costs $50. Please contact {PAYMENT_ADMIN} to complete your payment. 💸\n"
            f"Once payment is confirmed, you will gain access to chat 💬 with your favorite BTS artist! 🎼🎶",
            reply_markup=get_user_keyboard(telegram_id)
        )
        # Automatic message in case the payment admin is offline
        update.message.reply_text(
            f"If {PAYMENT_ADMIN} is not online, please wait for a response. In the meantime, you can prepare your payment of $50 to enjoy exclusive access to your favorite BTS artist with @BTS0BOT_BOT! 💜"
        )
        database.log_interaction(telegram_id, "subscribe")
    except Exception as e:
        print(f"Database error: {e}")  # Debug
        update.message.reply_text("Failed to process subscription. Please try again.", reply_markup=get_user_keyboard(telegram_id))

def pending_payments(update, context):
    print("Received /pending_payments command")  # Debug
    telegram_id = update.message.from_user.id

    if telegram_id not in ADMIN_IDS:
        update.message.reply_text("You are not authorized to use this command.")
        return

    pending = database.get_pending_payments()
    if not pending:
        update.message.reply_text("No pending payments found.")
        return

    buttons = [
        InlineKeyboardButton(f"{user['username']} (ID: {user['telegram_id']})", callback_data=f"confirm_{user['telegram_id']}")
        for user in pending
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Users with pending payments:", reply_markup=reply_markup)

def confirm_payment_callback(update, context):
    query = update.callback_query
    query.answer()
    telegram_id = query.from_user.id

    if telegram_id not in ADMIN_IDS:
        query.message.reply_text("You are not authorized to use this command.")
        return

    user_id = int(query.data.split("_")[1])
    database.confirm_payment(user_id)
    query.message.reply_text(f"Payment confirmed for user ID {user_id}.")

    # Notify the user
    users = database.get_all_users()
    user_dict = {user['telegram_id']: user for user in users}
    user = user_dict.get(user_id)
    if user:
        context.bot.send_message(
            chat_id=user['chat_id'],
            text="Your payment has been confirmed! You can now chat with your favorite BTS artist! 🌟🎤",
            reply_markup=get_user_keyboard(user_id)
        )

def confirm_payment(update, context):
    print("Received /confirm_payment command")  # Debug
    telegram_id = update.message.from_user.id

    if telegram_id not in ADMIN_IDS:
        update.message.reply_text("You are not authorized to use this command.")
        return

    if not context.args:
        update.message.reply_text("Please provide the Telegram ID of the user. Usage: /confirm_payment <telegram_id>")
        return

    try:
        user_id = int(context.args[0])
        database.confirm_payment(user_id)
        update.message.reply_text(f"Payment confirmed for user ID {user_id}.")

        # Notify the user
        users = database.get_all_users()
        user_dict = {user['telegram_id']: user for user in users}
        user = user_dict.get(user_id)
        if user:
            context.bot.send_message(
                chat_id=user['chat_id'],
                text="Your payment has been confirmed! You can now chat with your favorite BTS artist! 🌟🎤",
                reply_markup=get_user_keyboard(user_id)
            )
    except ValueError:
        update.message.reply_text("Invalid Telegram ID. Please provide a numeric ID.")
    except Exception as e:
        print(f"Error confirming payment: {e}")
        update.message.reply_text("Failed to confirm payment. Please try again.")

def list_users(update, context):
    print("Received /users command")  # Debug
    telegram_id = update.message.from_user.id

    if telegram_id not in ADMIN_IDS:
        update.message.reply_text("You are not authorized to use this command.")
        return

    users = database.get_all_users()
    if not users:
        update.message.reply_text("No users found.")
        return

    user_list = "\n".join([f"ID: {user['telegram_id']}, Username: {user['username']}" for user in users])
    update.message.reply_text(f"Registered users:\n{user_list}")

def chat(update, context):
    print("Received /chat command")  # Debug
    telegram_id = update.message.from_user.id

    if telegram_id not in ADMIN_IDS:
        update.message.reply_text("You are not authorized to use this command.")
        return

    users = database.get_all_users()
    if not users:
        update.message.reply_text("No users found to chat with.")
        return

    buttons = [
        InlineKeyboardButton(f"{user['username']} (ID: {user['telegram_id']})", callback_data=f"chat_{user['telegram_id']}")
        for user in users
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("Search for a user", callback_data="search_user")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Select a user to chat with:", reply_markup=reply_markup)

def chat_callback(update, context):
    query = update.callback_query
    query.answer()
    telegram_id = query.from_user.id

    if telegram_id not in ADMIN_IDS:
        query.message.reply_text("You are not authorized to use this command.")
        return

    if query.data == "search_user":
        context.user_data['searching_users'] = True
        query.message.reply_text("Please type the username or ID of the user you want to chat with (or type /cancel to stop):")
        return

    target_id = int(query.data.split("_")[1])
    users = database.get_all_users()
    user_dict = {user['telegram_id']: user for user in users}
    target_user = user_dict.get(target_id)

    if not target_user:
        query.message.reply_text(f"User with ID {target_id} not found.")
        return

    context.user_data['chat_with'] = target_id
    query.message.reply_text(
        f"--- Chat with {target_user['username']} (ID: {target_id}) ---\n"
        f"Send a message to them, or type /exit to stop chatting."
    )

def handle_user_search(update, context):
    telegram_id = update.message.from_user.id
    if telegram_id not in ADMIN_IDS or not context.user_data.get('searching_users'):
        return False

    search_query = update.message.text.lower()
    if search_query == "/cancel":
        del context.user_data['searching_users']
        update.message.reply_text("Search cancelled.")
        return True

    users = database.get_all_users()
    filtered_users = [
        user for user in users
        if search_query in str(user['telegram_id']) or (user['username'] and search_query in user['username'].lower())
    ]

    if not filtered_users:
        update.message.reply_text("No users found matching your search. Try again or type /cancel.")
        return True

    buttons = [
        InlineKeyboardButton(f"{user['username']} (ID: {user['telegram_id']})", callback_data=f"chat_{user['telegram_id']}")
        for user in filtered_users
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Select a user to chat with:", reply_markup=reply_markup)
    del context.user_data['searching_users']
    return True

def handle_admin_chat_message(update, context):
    telegram_id = update.message.from_user.id
    if telegram_id not in ADMIN_IDS or 'chat_with' not in context.user_data:
        return False

    target_id = context.user_data['chat_with']
    message = update.message.text

    if message == "/exit":
        del context.user_data['chat_with']
        update.message.reply_text("--- Chat session ended ---")
        return True

    users = database.get_all_users()
    user_dict = {user['telegram_id']: user for user in users}
    target_user = user_dict.get(target_id)

    if not target_user:
        update.message.reply_text(f"User with ID {target_id} not found.")
        del context.user_data['chat_with']
        return True

    chat_id = target_user['chat_id']
    try:
        context.bot.send_message(chat_id=chat_id, text=f"Message from BTS Admin: {message} 💜")
        print(f"Sent message to chat_id: {chat_id}")  # Debug
        update.message.reply_text(f"Message sent to {target_user['username']}: {message}")
    except Exception as e:
        print(f"Failed to send message to chat_id {chat_id}: {e}")  # Debug
        update.message.reply_text(f"Failed to send message to user {target_id}: {e}")
        del context.user_data['chat_with']
        return True

    return True

def broadcast(update, context):
    print("Received /broadcast command")  # Debug
    telegram_id = update.message.from_user.id

    if telegram_id not in ADMIN_IDS:
        update.message.reply_text("You are not authorized to use this command.")
        return

    if not context.args:
        update.message.reply_text("Please provide a message to broadcast. Usage: /broadcast <message>")
        return

    message = " ".join(context.args)
    print(f"Broadcasting message: {message}")  # Debug

    users = database.get_all_users()
    if not users:
        update.message.reply_text("No users found to broadcast to.")
        return

    successful_sends = 0
    for user in users:
        chat_id = user['chat_id']
        try:
            context.bot.send_message(chat_id=chat_id, text=f"📢 Message from @BTS0BOT_BOT: {message} 💜")
            print(f"Sent message to chat_id: {chat_id}")  # Debug
            successful_sends += 1
        except Exception as e:
            print(f"Failed to send message to chat_id {chat_id}: {e}")  # Debug

    update.message.reply_text(f"Broadcasted message to {successful_sends}/{len(users)} users successfully. 📢")

def remind(update, context):
    print("Received /remind command")  # Debug
    telegram_id = update.message.from_user.id

    if telegram_id not in ADMIN_IDS:
        update.message.reply_text("You are not authorized to use this command.")
        return

    today = datetime.now().date()
    subscriptions = database.get_subscriptions()
    if not subscriptions:
        update.message.reply_text("No subscriptions found.")
        return

    users = database.get_all_users()
    user_dict = {user['telegram_id']: user for user in users}

    for sub in subscriptions:
        telegram_id = sub['telegram_id']
        end_date = sub['end_date']
        days_left = (end_date - today).days

        if days_left <= 3:
            user = user_dict.get(telegram_id)
            if user:
                chat_id = user['chat_id']
                message = f"Reminder: Your subscription with @BTS0BOT_BOT ends on {end_date}. {days_left} days left! Please renew to continue chatting with your favorite BTS artist. 💜"
                try:
                    context.bot.send_message(chat_id=chat_id, text=message)
                    print(f"Sent reminder to chat_id: {chat_id}")  # Debug
                except Exception as e:
                    print(f"Failed to send reminder to chat_id {chat_id}: {e}")  # Debug

    update.message.reply_text("Reminders sent to users with upcoming or overdue subscriptions.")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("subscribe", subscribe_command))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("users", list_users))
    dp.add_handler(CommandHandler("chat", chat))
    dp.add_handler(CallbackQueryHandler(chat_callback, pattern="^(chat_|search_user)"))
    dp.add_handler(CallbackQueryHandler(confirm_payment_callback, pattern="^confirm_"))
    dp.add_handler(CommandHandler("broadcast", broadcast))
    dp.add_handler(CommandHandler("remind", remind))
    dp.add_handler(CommandHandler("pending_payments", pending_payments))
    dp.add_handler(CommandHandler("confirm_payment", confirm_payment))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    while True:
        try:
            print("Bot is running...")
            updater.start_polling(poll_interval=2.0)
            updater.idle()
            break
        except NetworkError as e:
            print(f"Network error: {e}. Retrying in 10 seconds...")
            time.sleep(10)

if __name__ == "__main__":
    main()
