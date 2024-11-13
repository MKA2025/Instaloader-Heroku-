import os
import zipfile
import instaloader
import telegram
from flask import Flask, jsonify, request
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

class InstagramDownloader:
    def __init__(self, bot_token):
        # Telegram Bot Setup
        self.bot = telegram.Bot(token=bot_token)
        self.updater = Updater(token=bot_token, use_context=True)
        self.dispatcher = self.updater.dispatcher

        # Instaloader Setup
        self.L = instaloader.Instaloader(
            download_pictures=True,
            download_videos=True,
            download_comments=False,
            save_metadata=False
        )

        # Register Handlers
        self.register_handlers()

    def register_handlers(self):
        # Command Handlers
        start_handler = CommandHandler('start', self.start_command)
        download_handler = MessageHandler(Filters.text & ~Filters.command, self.download_instagram_post)
        zip_handler = CommandHandler('zip', self.download_zip)

        self.dispatcher.add_handler(start_handler)
        self.dispatcher.add_handler(download_handler)
        self.dispatcher.add_handler(zip_handler)

    def start_command(self, update, context):
        welcome_message = """
        🤖 Instagram Media Downloader Bot 🤖
        
        Commands:
        - Send Instagram post link to download media
        - /zip [post_link] - Download media as ZIP
        
        Supported Links:
        - Single Post URL
        - Profile Picture URL
        """
        update.message.reply_text(welcome_message)

    def create_zip_file(self, download_dir, chat_id):
        # Create ZIP file
        zip_filename = f"downloads/instagram_media_{chat_id}.zip"
        
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(download_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, download_dir)
                    zipf.write(file_path, arcname=arcname)
        
        return zip_filename

    def download_instagram_post(self, update, context):
        url = update.message.text
        chat_id = update.effective_chat.id

        try:
            # Validate Instagram URL
            if "instagram.com" not in url:
                update.message.reply_text("❌ Invalid Instagram URL")
                return

            # Create a temporary download directory
            download_dir = f"downloads/{chat_id}"
            os.makedirs(download_dir, exist_ok=True)

            # Download Post
            post = instaloader.Post.from_shortcode(self.L.context, url.split("/")[-2])
            
            # Download all media from the post
            self.L.download_post(post, target=download_dir)

            # Send downloaded files
            media_files = []
            for filename in os.listdir(download_dir):
                file_path = os.path.join(download_dir, filename)
                
                # Determine file type and send accordingly
                if filename.endswith(('.jpg', '.jpeg', '.png')):
                    with open(file_path, 'rb') as photo:
                        sent_photo = update.message.reply_photo(photo=photo)
                        media_files.append(sent_photo)
                
                elif filename.endswith(('.mp4', '.mov')):
                    with open(file_path, 'rb') as video:
                        sent_video = update.message.reply_video(video=video)
                        media_files.append(sent_video)

            # Provide ZIP download option
            zip_keyboard = [
                [telegram.InlineKeyboardButton(
                    "📦 Download as ZIP", 
                    callback_data=f"zip_{url}"
                )]
            ]
            reply_markup = telegram.InlineKeyboardMarkup(zip_keyboard)
            update.message.reply_text(
                "Would you like to download all media as a ZIP file?", 
                reply_markup=reply_markup
            )

        except Exception as e:
            update.message.reply_text(f"❌ Error downloading: {str(e)}")

    def download_zip(self, update, context):
        # Check if URL is provided
        if len(context.args) == 0:
            update.message.reply_text("Please provide an Instagram post URL")
            return

        url = context.args[0]
        chat_id = update.effective_chat.id

        try:
            # Create download directory
            download_dir = f"downloads/{chat_id}"
            os.makedirs(download_dir, exist_ok=True)

            # Download Post
            post = instaloader.Post.from_shortcode(self.L.context, url.split("/")[-2])
            self.L.download_post(post, target=download_dir)

            # Create ZIP file
            zip_filename = self.create_zip_file(download_dir, chat_id)

            # Send ZIP file
            with open(zip_filename, 'rb') as zip_file:
                update.message.reply_document(
                    document=zip_file, 
                    filename=f"instagram_media_{chat_id}.zip"
                )

            # Clean up
            os.remove(zip_filename)
            for filename in os.listdir(download_dir):
                os.remove(os.path.join(download_dir, filename))
            os.rmdir(download_dir)

        except Exception as e:
            update.message.reply_text(f"❌ Error creating ZIP: {str(e)}")

    def handle_callback_query(self, update, context):
        query = update.callback_query
        query.answer()

        # Extract URL from callback data
        if query.data.startswith('zip_'):
            url = query.data.split('_', 1)[1]
            
            # Temporary chat ID
            chat_id = query.message.chat_id

            try:
                # Create download directory
                download_dir = f"downloads/{chat_id}"
                os.makedirs(download_dir, exist_ok=True)

                # Download Post
                post = instaloader.Post.from_shortcode(self.L.context, url.split("/")[-2])
                self.L.download_post(post, target=download_dir)

                # Create ZIP file
                zip_filename = self.create_zip_file(download_dir, chat_id)

                # Send ZIP file
                with open(zip_filename, 'rb') as zip_file:
                    query.message.reply_document(
                        document=zip_file, 
                        filename=f"instagram_media_{chat_id}.zip"
                    )

                # Clean up
                os.remove(zip_filename)
                for filename in os.listdir(download_dir):
                    os.remove(os.path.join(download_dir, filename))
                os.rmdir(download_dir)

            except Exception as e:
                query.message.reply_text(f"❌ Error creating ZIP: {str(e)}")

    def start_bot(self):
        # Add Callback Query Handler
        self.dispatcher.add_handler(
            telegram.ext.CallbackQueryHandler(self.handle_callback_query)
        )

        # Start the Bot
        self.updater.start_polling()
        self.updater.idle()

# Flask Web Application
app = Flask(__name__)

# Global Bot Instance
global_bot = None

@app.route('/')
def home():
    return jsonify({
        "status": "Running",
        "bot": "Instagram Downloader Telegram Bot"
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        # Process incoming Telegram update
        update = telegram.Update.de_json(request.get_json(force=True), global_bot.bot)
        global_bot.dispatcher.process_update(update)
        return 'ok', 200

def create_app():
    global global_bot
    BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    if BOT_TOKEN:
        global_bot = InstagramDownloader(BOT_TOKEN)
        # Start the bot in a separate thread if needed
        # from threading import Thread
        # bot_thread = Thread(target=global_bot.start_bot)
        # bot_thread.start()
    
    return app

# For Gunicorn
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
