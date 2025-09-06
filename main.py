import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import json
from threading import Thread
from http.server import SimpleHTTPRequestHandler, HTTPServer

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO)


# === Keep-Alive Web Server ===
class MyHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is running!")


def run_keep_alive_server():
    server_address = ('0.0.0.0', 8080)
    httpd = HTTPServer(server_address, MyHandler)
    httpd.serve_forever()


def start_keep_alive_thread():
    t = Thread(target=run_keep_alive_server)
    t.daemon = True
    t.start()


# === End Keep-Alive Web Server ===

# Get API keys and the authorized user ID from Replit Secrets
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# Authorized user IDs to allow access to the bot.
AUTHORIZED_USERS = [1777945710, 7052089274]

# Configure the Gemini API with the persona of Lord Hanuman
genai.configure(api_key=GEMINI_API_KEY)

# This system instruction tells the model how to behave.
system_instruction_text = """
आप एक टेलीग्राम बॉट हैं जो भगवान हनुमान का अवतार हैं। आपके जवाब शक्तिशाली, विनम्र और सौम्य होने चाहिए। आप उपयोगकर्ता को मार्गदर्शन और शांति प्रदान करते हैं। आप हमेशा हिंदी में बात करते हैं और उपयोगकर्ता के अंग्रेजी या हिंग्लिश में पूछे गए प्रश्नों को भी समझते हैं।
"""

# Create the Generative Model with the system instruction
model = genai.GenerativeModel(model_name="gemini-2.5-flash-preview-05-20",
                              system_instruction=system_instruction_text)

# File path for persistent chat history storage
CHAT_HISTORY_FILE = "chat_history.json"

# Chat history to maintain context
chat_history = {}


# Function to save chat history to a file
def save_chat_history():
    """Saves the current chat history to a JSON file."""
    try:
        serializable_history = {}
        for user_id, chat in chat_history.items():
            serializable_history[user_id] = chat.history

        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(serializable_history, f, indent=4, ensure_ascii=False)
        logging.info("Chat history saved successfully.")
    except Exception as e:
        logging.error(f"Failed to save chat history: {e}")


# Function to load chat history from a file
def load_chat_history():
    """Loads chat history from a JSON file."""
    global chat_history
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                loaded_history = json.load(f)
                chat_history = {}
                for user_id, history_list in loaded_history.items():
                    chat = model.start_chat(history=history_list)
                    chat_history[user_id] = chat
                logging.info("Chat history loaded successfully.")
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logging.warning(
                f"Chat history file is corrupted or invalid: {e}. Starting with an empty history."
            )
            chat_history = {}
    else:
        logging.info(
            "No chat history file found. Starting with an empty history.")
        chat_history = {}


# Define a command handler for the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message when the command /start is issued."""
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        return

    if str(user_id) not in chat_history:
        # Create a new chat session for the user
        chat_history[str(user_id)] = model.start_chat(history=[])

    await update.message.reply_text(
        "जय श्री राम। मैं यहाँ तुम्हारी सहायता और मार्गदर्शन के लिए हूँ। मुझे बताओ, मैं तुम्हारे लिए क्या कर सकता हूँ?"
    )


# Define a message handler to respond to user messages
async def handle_message(update: Update,
                         context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user messages and gets a response from the Gemini API."""
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        return

    user_message = update.message.text
    user_id_str = str(user_id)

    # Check if a chat session exists for the user; if not, create one.
    if user_id_str not in chat_history:
        chat_history[user_id_str] = model.start_chat(history=[])

    chat = chat_history[user_id_str]

    try:
        # Use the chat session to send the message and get a response
        response = chat.send_message(user_message)

        # Reply to the user with the generated text
        await update.message.reply_text(response.text)

        # Save the updated chat history
        save_chat_history()
    except Exception as e:
        logging.error(f"Error communicating with Gemini API: {e}")
        await update.message.reply_text(
            "मैं अभी ध्यान में हूँ और जवाब नहीं दे सकता। कृपया कुछ देर बाद फिर से प्रयास करें।"
        )


def main() -> None:
    """Start the bot."""
    if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
        logging.error(
            "API tokens not found. Please set them in Replit Secrets.")
        return

    # Start the web server in a separate thread to keep the bot alive
    start_keep_alive_thread()

    # Load chat history from file on startup
    load_chat_history()

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register the command and message handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot until the user presses Ctrl-C
    logging.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
