import os
import logging
import random
import string
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ParseMode,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler,
)
from pymongo import MongoClient

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB setup
MONGODB_URI = os.getenv("MONGODB_URI")
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client.telegram_bot_db
files_col = db.files
user_verifications_col = db.user_verifications

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Admin user ID(s) -- replace with your own Telegram user ID(s) for admin control
ADMIN_IDS = {123456789}  # Replace with your Telegram user ID for admin access


def generate_complex_parsing_link(file_name: str) -> str:
    """
    Generate a complex parsing link string including the file name.
    Example format:
    bhusufulfgjsthwtuchvysudtfywyftdisugydisugtausrfudug_6£5452524453637454yeyruejgyd463744hbskdveb647vfgoegwhfydisygudogygidih8rurtryeury5urur748&8&ug57&7=shdigtdidugifigifug"filename"b647vfgoegwhfydisygudogygidih8rurtryeury5urur748&8&ug57&7=shdigtdidugifigifug
    """
    random_part1 = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
    random_part2 = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
    random_number = random.randint(1015, 1016 - 1)
    return f'{random_part1}_6£{random_number}"{file_name}"{random_part2}'

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "👋 Welcome to the File Parsing Bot!\n\n"
        "📥 *Admin workflow:* Send a file with DropGalaxy link in the caption to generate parsing link.\n"
        "🔗 Then send the shortened link as a text message.\n\n"
        "👤 *User workflow:* Click the generated parsing link to start verification and download.\n\n"
        "Use /help to see commands.",
        parse_mode=ParseMode.MARKDOWN,
    )

def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "📚 *Bot Commands:* \n\n"
        "/start - Show welcome message\n"
        "Send a file + DropGalaxy link as caption (Admin only)\n"
        "Send shortlink text after parsing link generation (Admin only)\n\n"
        "User simply clicks the shared parsing link to follow verification and download flow."
    )
    update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

import secrets

def handle_file(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ You are not authorized to upload files.")
        return

    document = update.message.document
    caption = update.message.caption or ""

    # Extract DropGalaxy link from caption (simple heuristic: first http... string)
    dropgalaxy_link = None
    for word in caption.split():
        if word.startswith("http"):
            dropgalaxy_link = word
            break
    if not dropgalaxy_link:
        update.message.reply_text("⚠️ Please include DropGalaxy link in the caption.")
        return

    file_id = document.file_id
    file_name = document.file_name

    # Generate complex parsing link
    parsing_link = generate_complex_parsing_link(file_name)

    # Generate unique verification code
    verification_code = secrets.token_urlsafe(32)

    # Construct verification link (replace with your actual server URL)
    verification_link = f"https://yourserver.com/verify?uid={{user_id}}&file_id={file_id}&code={verification_code}"

    # Insert file metadata into DB
    files_col.insert_one({
        "file_id": file_id,
        "file_name": file_name,
        "storage_link": dropgalaxy_link,
        "parsing_link": parsing_link,
        "verification_code": verification_code,
        "shortlink": None,  # to be updated later when admin sends shortlink
    })

    context.user_data["last_file_id"] = file_id  # Save for linking shortlink

    update.message.reply_text(
        f"🔗 Parsing link generated:\nparsing link : {parsing_link}\n\n"
        f"🔐 Verification link generated:\nverification link : {verification_link}\n\n"
        "⚙️ Waiting for shortlink...",
        parse_mode=ParseMode.MARKDOWN,
    )

def handle_shortlink(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ You are not authorized to add shortlinks.")
        return
    
    text = update.message.text.strip()
    last_file_id = context.user_data.get("last_file_id")

    if not last_file_id:
        update.message.reply_text("⚠️ Please upload a file first to associate the shortlink with.")
        return

    file_doc = files_col.find_one({"file_id": last_file_id})
    if not file_doc:
        update.message.reply_text("❌ File information not found. Please upload again.")
        return

    # Update shortlink in DB
    files_col.update_one(
        {"file_id": last_file_id},
        {"$set": {"shortlink": text}}
    )

    update.message.reply_text(
        f"✅ File added successfully!\n\n📨 Share this link with users:\nhttps://t.me/Mahiraa3_bot?start={file_doc['parsing_link']}"
    )

def start_deep_link(update: Update, context: CallbackContext) -> None:
    """This handler deals with user clicking on link like /start <file_id>"""
    user_id = update.message.from_user.id
    args = context.args
    if not args:
        update.message.reply_text("👋 Please use the file-specific start link shared with you.")
        return

    file_parsing_link = args[0]

    # Find file by parsing_link
    file_doc = files_col.find_one({"parsing_link": file_parsing_link})
    if not file_doc:
        update.message.reply_text("❌ File not found or expired.")
        return

    file_id = file_doc['file_id']
    file_name = file_doc['file_name']
    storage_link = file_doc['storage_link']
    shortlink = file_doc.get('shortlink')

    if not shortlink:
        update.message.reply_text("⚠️ Shortlink not set yet by admin. Please try later.")
        return

    # Check user verification for this file
    now = datetime.utcnow()
    verification_doc = user_verifications_col.find_one({
        "user_id": user_id,
        "file_id": file_id,
        "expires_at": {"$gt": now}
    })

    if verification_doc:
        # User verified, show "retry" button only (which will redirect to dropgalaxy)
        keyboard = [
            [
                InlineKeyboardButton("🔁 Retry", callback_data=f"retry|{file_id}")
            ]
        ]
        update.message.reply_text(
            "🟢 You are already verified for this file.\n"
            "Click Retry to get your file download link.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        # User not verified, show both "verify" and "retry"
        keyboard = [
            [
                InlineKeyboardButton("✅ Verify", url=shortlink),
                InlineKeyboardButton("🔁 Retry", callback_data=f"retry|{file_id}")
            ]
        ]
        update.message.reply_text(
            "🔐 Please verify by clicking below:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    data = query.data
    user_id = query.from_user.id

    if data.startswith("retry|"):
        file_id = data.split("|")[1]

        # Check user verification
        now = datetime.utcnow()
        verification_doc = user_verifications_col.find_one({
            "user_id": user_id,
            "file_id": file_id,
            "expires_at": {"$gt": now}
        })

        if verification_doc:
            # Verified - Redirect users via inline keyboard with DropGalaxy URL
            file_doc = files_col.find_one({"file_id": file_id})
            if not file_doc:
                query.edit_message_text("❌ File info missing. Please try again later.")
                return

            storage_link = file_doc['storage_link']
            keyboard = [
                [InlineKeyboardButton("📥 Click here to download your file", url=storage_link)]
            ]
            query.edit_message_text(
                "📦 Here is your file download link:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            # Not verified - prompt user to verify again
            # We retrieve shortlink to provide verify button
            file_doc = files_col.find_one({"file_id": file_id})
            if not file_doc:
                query.edit_message_text("❌ File info missing. Please try again later.")
                return
            shortlink = file_doc.get('shortlink')
            if not shortlink:
                query.edit_message_text("⚠️ Verification link not set. Please contact admin.")
                return
            keyboard = [
                [
                    InlineKeyboardButton("✅ Verify", url=shortlink),
                    InlineKeyboardButton("🔁 Retry", callback_data=f"retry|{file_id}")
                ]
            ]
            query.edit_message_text(
                "⚠️ You need to verify again by clicking Verify below:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

def main() -> None:
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    # Handler for /start <parsing_link> deep links
    dispatcher.add_handler(CommandHandler("start", start_deep_link, pass_args=True))
    # Handler for receiving files (admin only)
    dispatcher.add_handler(MessageHandler(Filters.document & Filters.chat_type.private, handle_file))
    # Handler for receiving text messages for shortlinks (admin only)
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command & Filters.chat_type.private, handle_shortlink))
    # Callback query handler for button clicks
    dispatcher.add_handler(CallbackQueryHandler(button_callback))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
