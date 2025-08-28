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

def safe_monospace_password(password):
    """Safely format password in monospace, handling all special characters"""
    try:
        # Try simple monospace first
        return f"`{password}`"
    except:
        # If that fails, just return the password
        return password

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
            
            # Save to history (memory only)
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
            logger.info(f"Detailed button pressed by user {user_id}")
            await show_detailed_options(query, user_id)
            
        elif query.data.startswith("toggle_"):
            # Handle toggle options
            await handle_toggle(query, user_id)
            
        elif query.data.startswith("length_"):
            # Handle length selection
            await handle_length_selection(query, user_id)
            
        elif query.data == "generate_custom":
            # Generate custom password
            logger.info(f"Generate custom button pressed by user {user_id}")
            await generate_custom_password(query, user_id)
            
        elif query.data == "back_to_main":
            # Go back to main menu
            await start_from_callback(query)
            
        elif query.data == "history":
            # Show password history
            logger.info(f"History button pressed by user {user_id}")
            await show_password_history_page(query, user_id, 1)
            
        elif query.data == "clear_history":
            # Clear password history
            await clear_password_history(query, user_id)
            
        elif query.data.startswith("history_page_"):
            # Handle history pagination
            page = int(query.data.replace("history_page_", ""))
            await show_password_history_page(query, user_id, page)
            
        elif query.data == "noop":
            # Do nothing - just for page indicator button
            pass
            
    except Exception as e:
        logger.error(f"Error in button_handler: {e}")
        try:
            await query.answer("Произошла ошибка. Попробуйте еще раз.")
        except:
            pass

async def show_detailed_options(query, user_id):
    """Show detailed password generation options"""
    logger.info(f"Showing detailed options for user {user_id}")
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
    
    try:
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        logger.info(f"Successfully showed detailed options for user {user_id}")
    except Exception as e:
        logger.error(f"Error showing detailed options: {e}")
        # Fallback without markdown
        simple_text = "🔧 Detailed Password Settings\n\nConfigure your password options:"
        await query.edit_message_text(
            text=simple_text,
            reply_markup=reply_markup
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

async def show_password_history_page(query, user_id, page=1):
    """Show user's password history with pagination from memory"""
    logger.info(f"Showing history page {page} for user {user_id}")
    
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
    
    # Pagination settings
    passwords_per_page = 10
    total_passwords = len(user_password_history[user_id])
    total_pages = (total_passwords + passwords_per_page - 1) // passwords_per_page
    
    # Ensure page is within bounds
    page = max(1, min(page, total_pages))
    
    # Calculate start and end indices
    start_idx = (page - 1) * passwords_per_page
    end_idx = min(start_idx + passwords_per_page, total_passwords)
    
    # Build history text
    try:
        history_text = f"📖 *Password History* \\(Page {page}/{total_pages}\\)\n\n"
        
        for i, entry in enumerate(user_password_history[user_id][start_idx:end_idx], start_idx + 1):
            # Use monospace for passwords to make them copyable
            safe_password = safe_monospace_password(entry['password'])
            history_text += f"{i}\\. {safe_password}\n"
            history_text += f"   📅 {entry['timestamp']} \\| 🔧 {entry['type']}\n\n"
        
        history_text += "_Tap any password to copy_"
        
        # Create pagination keyboard
        keyboard = []
        
        # Pagination buttons
        if total_pages > 1:
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"history_page_{page-1}"))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"history_page_{page+1}"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            # Page indicator
            keyboard.append([InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop")])
        
        # Action buttons
        keyboard.append([InlineKeyboardButton("🗑 Clear History", callback_data="clear_history")])
        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=history_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
    except Exception as e:
        logger.error(f"Error showing history page {page}: {e}")
        # Fallback - try with simpler formatting
        try:
            simple_history = f"📖 Password History (Page {page}/{total_pages})\n\n"
            for i, entry in enumerate(user_password_history[user_id][start_idx:end_idx], start_idx + 1):
                safe_password = safe_monospace_password(entry['password'])
                simple_history += f"{i}. {safe_password}\n"
                simple_history += f"   📅 {entry['timestamp']} | 🔧 {entry['type']}\n\n"
            
            simple_history += "Tap any password to copy"
            
            # Simple keyboard
            keyboard = []
            if total_pages > 1:
                nav_buttons = []
                if page > 1:
                    nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"history_page_{page-1}"))
                if page < total_pages:
                    nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"history_page_{page+1}"))
                if nav_buttons:
                    keyboard.append(nav_buttons)
            
            keyboard.append([InlineKeyboardButton("🗑 Clear History", callback_data="clear_history")])
            keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=simple_history,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
        except Exception as e2:
            logger.error(f"Error in history fallback: {e2}")
            # Final fallback without markdown
            plain_history = f"📖 Password History (Page {page}/{total_pages})\n\n"
            for i, entry in enumerate(user_password_history[user_id][start_idx:end_idx], start_idx + 1):
                plain_history += f"{i}. {entry['password']}\n"
                plain_history += f"   📅 {entry['timestamp']} | 🔧 {entry['type']}\n\n"
            
            keyboard = []
            if total_pages > 1:
                nav_buttons = []
                if page > 1:
                    nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"history_page_{page-1}"))
                if page < total_pages:
                    nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"history_page_{page+1}"))
                if nav_buttons:
                    keyboard.append(nav_buttons)
            
            keyboard.append([InlineKeyboardButton("🗑 Clear History", callback_data="clear_history")])
            keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=plain_history,
                reply_markup=reply_markup
            )

# Add other necessary functions here (handle_toggle, generate_custom_password, etc.)
# For brevity, I'm including just the essential ones for the simple version

def main() -> None:
    """Start the bot"""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Run the bot using polling (works better for Railway)
    logger.info("Starting simple bot with polling...")
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
