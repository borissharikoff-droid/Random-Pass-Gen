import logging
import random
import string
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = "7534238170:AAG1nlQTip_pAPMrvDl8T3z7vHT0IaMY7TM"

# User settings storage (in production, use a database)
user_settings = {}
# Password history storage (in production, use a database)
user_password_history = {}

class PasswordGenerator:
    """Password generator class with customizable options"""
    
    def __init__(self):
        self.lowercase = string.ascii_lowercase
        self.uppercase = string.ascii_uppercase
        self.digits = string.digits
        self.symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    def generate_fast(self, length=12):
        """Generate a fast password with default settings"""
        chars = self.lowercase + self.uppercase + self.digits + self.symbols
        return ''.join(random.choice(chars) for _ in range(length))
    
    def generate_custom(self, length=12, use_lowercase=True, use_uppercase=True, 
                       use_digits=True, use_symbols=True):
        """Generate a custom password based on user preferences"""
        chars = ""
        
        if use_lowercase:
            chars += self.lowercase
        if use_uppercase:
            chars += self.uppercase
        if use_digits:
            chars += self.digits
        if use_symbols:
            chars += self.symbols
            
        if not chars:
            chars = self.lowercase + self.uppercase + self.digits
            
        return ''.join(random.choice(chars) for _ in range(length))

password_gen = PasswordGenerator()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send start message with inline keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("⚡️ Fast", callback_data="fast"),
            InlineKeyboardButton("👁 Detailed", callback_data="detailed")
        ],
        [
            InlineKeyboardButton("📖 History", callback_data="history")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """🔐 *Dox: Pass Gen*

1\\. Fast password generation
2\\. Detailed password generation
3\\. Password history

Choose your option:"""
    
    await update.message.reply_text(
        message_text, 
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        logger.info(f"Button pressed: '{query.data}' by user {user_id}")
        
        if query.data == "fast":
            # Generate fast password
            password = password_gen.generate_fast()
            
            # Save to history
            save_password_to_history(user_id, password, "Fast")
            
            # Format password in monospace for easy copying
            password_text = f"`{password}`"
            
            # Create keyboard with main menu buttons
            keyboard = [
                [
                    InlineKeyboardButton("⚡️ Fast", callback_data="fast"),
                    InlineKeyboardButton("👁 Detailed", callback_data="detailed")
                ],
                [
                    InlineKeyboardButton("📖 History", callback_data="history")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=f"🔐 *Your fast password:*\n\n{password_text}\n\n_Tap to copy_",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
        elif query.data == "detailed":
            # Show detailed options
            await show_detailed_options(query, user_id)
            
        elif query.data.startswith("toggle_"):
            # Handle toggle options
            await handle_toggle(query, user_id)
            
        elif query.data.startswith("length_"):
            # Handle length selection
            await handle_length_selection(query, user_id)
            
        elif query.data == "generate_custom":
            # Generate custom password
            await generate_custom_password(query, user_id)
            
        elif query.data == "back_to_main":
            # Go back to main menu
            await start_from_callback(query)
            
        elif query.data == "history":
            # Show password history
            logger.info(f"History button pressed by user {user_id}")
            await show_password_history(query, user_id)
            
        elif query.data == "clear_history":
            # Clear password history
            await clear_password_history(query, user_id)
            
    except Exception as e:
        logger.error(f"Error in button_handler: {e}")
        try:
            await query.answer("Произошла ошибка. Попробуйте еще раз.")
        except:
            pass

async def show_detailed_options(query, user_id):
    """Show detailed password generation options"""
    # Initialize user settings if not exists
    if user_id not in user_settings:
        user_settings[user_id] = {
            'length': 12,
            'lowercase': True,
            'uppercase': True,
            'digits': True,
            'symbols': True
        }
    
    settings = user_settings[user_id]
    
    # Create keyboard with current settings
    keyboard = [
        [InlineKeyboardButton(
            f"{'✅' if settings['lowercase'] else '❌'} Lowercase (a-z)", 
            callback_data="toggle_lowercase"
        )],
        [InlineKeyboardButton(
            f"{'✅' if settings['uppercase'] else '❌'} Uppercase (A-Z)", 
            callback_data="toggle_uppercase"
        )],
        [InlineKeyboardButton(
            f"{'✅' if settings['digits'] else '❌'} Digits (0-9)", 
            callback_data="toggle_digits"
        )],
        [InlineKeyboardButton(
            f"{'✅' if settings['symbols'] else '❌'} Symbols (!@#$...)", 
            callback_data="toggle_symbols"
        )],
        [InlineKeyboardButton(
            f"📏 Length: {settings['length']}", 
            callback_data="length_menu"
        )],
        [InlineKeyboardButton("🔐 Generate Password", callback_data="generate_custom")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """🔧 *Detailed Password Settings*

Configure your password options:"""
    
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def handle_toggle(query, user_id):
    """Handle toggle button presses"""
    toggle_type = query.data.replace("toggle_", "")
    
    if user_id not in user_settings:
        user_settings[user_id] = {
            'length': 12,
            'lowercase': True,
            'uppercase': True,
            'digits': True,
            'symbols': True
        }
    
    # Toggle the setting
    user_settings[user_id][toggle_type] = not user_settings[user_id][toggle_type]
    
    # Refresh the detailed options menu
    await show_detailed_options(query, user_id)

async def handle_length_selection(query, user_id):
    """Handle length selection"""
    if query.data == "length_menu":
        # Show length options
        keyboard = [
            [
                InlineKeyboardButton("8", callback_data="length_8"),
                InlineKeyboardButton("12", callback_data="length_12"),
                InlineKeyboardButton("16", callback_data="length_16")
            ],
            [
                InlineKeyboardButton("20", callback_data="length_20"),
                InlineKeyboardButton("24", callback_data="length_24"),
                InlineKeyboardButton("32", callback_data="length_32")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="detailed")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text="📏 *Select Password Length*",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        # Set specific length
        length = int(query.data.replace("length_", ""))
        user_settings[user_id]['length'] = length
        
        # Go back to detailed options
        await show_detailed_options(query, user_id)

async def generate_custom_password(query, user_id):
    """Generate custom password based on user settings"""
    if user_id not in user_settings:
        user_settings[user_id] = {
            'length': 12,
            'lowercase': True,
            'uppercase': True,
            'digits': True,
            'symbols': True
        }
    
    settings = user_settings[user_id]
    
    password = password_gen.generate_custom(
        length=settings['length'],
        use_lowercase=settings['lowercase'],
        use_uppercase=settings['uppercase'],
        use_digits=settings['digits'],
        use_symbols=settings['symbols']
    )
    
    # Save to history
    save_password_to_history(user_id, password, "Custom")
    
    # Format password in monospace for easy copying
    password_text = f"`{password}`"
    
    # Create keyboard with options
    keyboard = [
        [InlineKeyboardButton("🔄 Generate Another", callback_data="generate_custom")],
        [InlineKeyboardButton("⚙️ Change Settings", callback_data="detailed")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Create settings summary
    enabled_features = []
    if settings['lowercase']:
        enabled_features.append("lowercase")
    if settings['uppercase']:
        enabled_features.append("UPPERCASE")
    if settings['digits']:
        enabled_features.append("123")
    if settings['symbols']:
        enabled_features.append("!@#")
    
    features_text = " \\+ ".join(enabled_features)
    
    message_text = f"""🔐 *Your custom password:*

{password_text}

📊 *Settings:* {features_text}
📏 *Length:* {settings['length']}

_Tap the password to copy_"""
    
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def start_from_callback(query):
    """Start command from callback query"""
    keyboard = [
        [
            InlineKeyboardButton("⚡️ Fast", callback_data="fast"),
            InlineKeyboardButton("👁 Detailed", callback_data="detailed")
        ],
        [
            InlineKeyboardButton("📖 History", callback_data="history")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """🔐 *Dox: Pass Gen*

1\\. Fast password generation
2\\. Detailed password generation
3\\. Password history

Choose your option:"""
    
    await query.edit_message_text(
        text=message_text, 
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )

def save_password_to_history(user_id, password, password_type):
    """Save password to user's history"""
    import datetime
    
    if user_id not in user_password_history:
        user_password_history[user_id] = []
    
    # Add timestamp and password info
    history_entry = {
        'password': password,
        'type': password_type,
        'timestamp': datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    
    # Add to beginning of list (newest first)
    user_password_history[user_id].insert(0, history_entry)
    
    # Keep only last 20 passwords
    if len(user_password_history[user_id]) > 20:
        user_password_history[user_id] = user_password_history[user_id][:20]
    
    logger.info(f"Saved password to history for user {user_id}. Total passwords: {len(user_password_history[user_id])}")

async def show_password_history(query, user_id):
    """Show user's password history"""
    logger.info(f"Showing history for user {user_id}. History: {user_password_history.get(user_id, [])}")
    
    if user_id not in user_password_history or not user_password_history[user_id]:
        # No history
        logger.info(f"No history found for user {user_id}")
        keyboard = [
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text="📖 *Password History*\n\n❌ No passwords generated yet\\.\n\nStart generating passwords to see them here\\!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    
    # Build history text
    try:
        history_text = "📖 *Password History*\n\n"
        
        for i, entry in enumerate(user_password_history[user_id][:10], 1):  # Show last 10
            # Use simple formatting to avoid escaping issues
            history_text += f"{i}\\. `{entry['password']}`\n"
            history_text += f"   📅 {entry['timestamp']} \\| 🔧 {entry['type']}\n\n"
        
        if len(user_password_history[user_id]) > 10:
            history_text += f"_\\.\\.\\. and {len(user_password_history[user_id]) - 10} more passwords_\n\n"
        
        history_text += "_Tap any password to copy_"
        
        # Create keyboard
        keyboard = [
            [InlineKeyboardButton("🗑 Clear History", callback_data="clear_history")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=history_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
    except Exception as e:
        logger.error(f"Error showing history: {e}")
        # Fallback to simple text without markdown
        simple_history = "📖 Password History\n\n"
        for i, entry in enumerate(user_password_history[user_id][:10], 1):
            simple_history += f"{i}. {entry['password']}\n"
            simple_history += f"   📅 {entry['timestamp']} | 🔧 {entry['type']}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🗑 Clear History", callback_data="clear_history")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=simple_history,
            reply_markup=reply_markup
        )

async def clear_password_history(query, user_id):
    """Clear user's password history"""
    if user_id in user_password_history:
        user_password_history[user_id] = []
    
    keyboard = [
        [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text="📖 *Password History*\n\n✅ History cleared successfully\\!\n\nAll your saved passwords have been removed\\.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message"""
    help_text = """🔐 *Dox: Pass Gen Help*

*Commands:*
• /start \\- Start the bot
• /help \\- Show this help message

*Features:*
• ⚡️ *Fast Generation* \\- Instantly generate a secure password
• 👁 *Detailed Generation* \\- Customize your password settings
• 📖 *History* \\- View all previously generated passwords

*How to use:*
1\\. Use /start to begin
2\\. Choose Fast for instant password or Detailed for custom options
3\\. Tap on generated password to copy it
4\\. Use History to see all your previous passwords

*History Features:*
• Stores last 20 passwords with timestamps
• Shows password type \\(Fast/Custom\\)
• Clear history option available

*Security:*
Passwords are generated locally\\. History is stored temporarily during bot session\\."""
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to check history"""
    user_id = update.effective_user.id
    history_count = len(user_password_history.get(user_id, []))
    
    debug_text = f"🔍 Debug Info:\n\nUser ID: {user_id}\nPasswords in history: {history_count}\n\nHistory data:\n{user_password_history.get(user_id, [])}"
    
    await update.message.reply_text(debug_text)

def main() -> None:
    """Start the bot"""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("debug", debug_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Run the bot using polling (works better for Railway)
    logger.info("Starting bot with polling...")
    application.run_polling(
        poll_interval=1.0,
        timeout=10,
        bootstrap_retries=5,
        read_timeout=10,
        write_timeout=10,
        connect_timeout=10,
        pool_timeout=10
    )

if __name__ == "__main__":
    main()
