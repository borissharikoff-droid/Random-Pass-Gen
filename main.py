import logging
import random
import string
import os
import aiosqlite
import asyncio
from datetime import datetime
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

# Database file path
DATABASE_PATH = "password_history.db"

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

def escape_markdown_v2(text):
    """Escape special characters for Markdown V2"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def init_database():
    """Initialize the database and create tables"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS password_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                password TEXT NOT NULL,
                generation_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
        logger.info("Database initialized successfully")

async def save_password_to_db(user_id, username, first_name, last_name, password, generation_type):
    """Save password to database"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("""
                INSERT INTO password_history (user_id, username, first_name, last_name, password, generation_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, password, generation_type))
            await db.commit()
            logger.info(f"Password saved to database for user {user_id} ({username})")
    except Exception as e:
        logger.error(f"Error saving password to database: {e}")

async def get_user_passwords_from_db(user_id, limit=20, offset=0):
    """Get user's passwords from database with pagination"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT password, generation_type, created_at 
                FROM password_history 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))
            rows = await cursor.fetchall()
            return rows
    except Exception as e:
        logger.error(f"Error getting passwords from database: {e}")
        return []

async def get_user_password_count(user_id):
    """Get total count of user's passwords"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM password_history WHERE user_id = ?
            """, (user_id,))
            count = await cursor.fetchone()
            return count[0] if count else 0
    except Exception as e:
        logger.error(f"Error getting password count: {e}")
        return 0

async def clear_user_passwords_from_db(user_id):
    """Clear all user's passwords from database"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("DELETE FROM password_history WHERE user_id = ?", (user_id,))
            await db.commit()
            logger.info(f"Cleared all passwords for user {user_id}")
    except Exception as e:
        logger.error(f"Error clearing passwords: {e}")

async def get_all_passwords_stats():
    """Get statistics about all passwords in database"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) as total_passwords,
                    COUNT(DISTINCT user_id) as unique_users,
                    generation_type,
                    COUNT(*) as count_by_type
                FROM password_history 
                GROUP BY generation_type
            """)
            stats = await cursor.fetchall()
            
            cursor = await db.execute("SELECT COUNT(*) FROM password_history")
            total = await cursor.fetchone()
            
            cursor = await db.execute("SELECT COUNT(DISTINCT user_id) FROM password_history")
            users = await cursor.fetchone()
            
            return {
                'total_passwords': total[0] if total else 0,
                'unique_users': users[0] if users else 0,
                'by_type': stats
            }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {'total_passwords': 0, 'unique_users': 0, 'by_type': []}

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
            
            # Save to history (memory)
            save_password_to_history(user_id, password, "Fast")
            
            # Save to database
            user = query.from_user
            await save_password_to_db(
                user_id=user_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                password=password,
                generation_type="Fast"
            )
            
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

async def handle_toggle(query, user_id):
    """Handle toggle button presses"""
    try:
        toggle_type = query.data.replace("toggle_", "")
        logger.info(f"Toggle {toggle_type} pressed by user {user_id}")
        
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
        logger.info(f"Toggled {toggle_type} to {user_settings[user_id][toggle_type]} for user {user_id}")
        
        # Refresh the detailed options menu
        await show_detailed_options(query, user_id)
        
    except Exception as e:
        logger.error(f"Error in handle_toggle: {e}")
        await query.answer("Произошла ошибка при переключении настройки.")

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
    logger.info(f"Generating custom password for user {user_id}")
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
    
    # Save to history (memory)
    save_password_to_history(user_id, password, "Custom")
    
    # Save to database
    user = query.from_user
    await save_password_to_db(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        password=password,
        generation_type="Custom"
    )
    
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
    
    try:
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        logger.info(f"Successfully generated custom password for user {user_id}")
    except Exception as e:
        logger.error(f"Error generating custom password: {e}")
        # Try with escaped characters
        try:
            escaped_features = []
            if settings['lowercase']:
                escaped_features.append("lowercase")
            if settings['uppercase']:
                escaped_features.append("UPPERCASE")
            if settings['digits']:
                escaped_features.append("123")
            if settings['symbols']:
                escaped_features.append("\\!\\@\\#")
            
            escaped_features_text = " \\+ ".join(escaped_features)
            
            fallback_text = f"""🔐 *Your custom password:*

`{password}`

📊 *Settings:* {escaped_features_text}
📏 *Length:* {settings['length']}

_Tap the password to copy_"""
            
            await query.edit_message_text(
                text=fallback_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e2:
            logger.error(f"Error in fallback: {e2}")
            # Final fallback - try with just monospace password
            try:
                simple_text = f"🔐 Your custom password:\n\n`{password}`\n\nLength: {settings['length']}\n\nTap the password to copy"
                await query.edit_message_text(
                    text=simple_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            except:
                # Last resort - plain text
                plain_text = f"🔐 Your custom password:\n\n{password}\n\nLength: {settings['length']}\n\nTap the password to copy"
                await query.edit_message_text(
                    text=plain_text,
                    reply_markup=reply_markup
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

async def show_password_history_page(query, user_id, page=1):
    """Show user's password history with pagination from database"""
    logger.info(f"Showing history page {page} for user {user_id}")
    
    # Get total count from database
    total_passwords = await get_user_password_count(user_id)
    
    if total_passwords == 0:
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
    total_pages = (total_passwords + passwords_per_page - 1) // passwords_per_page
    
    # Ensure page is within bounds
    page = max(1, min(page, total_pages))
    
    # Calculate offset for database query
    offset = (page - 1) * passwords_per_page
    
    # Get passwords from database
    passwords = await get_user_passwords_from_db(user_id, passwords_per_page, offset)
    
    # Build history text
    try:
        history_text = f"📖 *Password History* \\(Page {page}/{total_pages}\\)\n\n"
        
        for i, (password, generation_type, created_at) in enumerate(passwords, offset + 1):
            # Format the datetime
            try:
                # Parse SQLite datetime format
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                formatted_date = dt.strftime("%d.%m.%Y %H:%M")
            except:
                formatted_date = created_at
            
            # Use monospace for passwords to make them copyable
            history_text += f"{i}\\. `{password}`\n"
            history_text += f"   📅 {formatted_date} \\| 🔧 {generation_type}\n\n"
        
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
            for i, (password, generation_type, created_at) in enumerate(passwords, offset + 1):
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    formatted_date = dt.strftime("%d.%m.%Y %H:%M")
                except:
                    formatted_date = created_at
                    
                simple_history += f"{i}. `{password}`\n"
                simple_history += f"   📅 {formatted_date} | 🔧 {generation_type}\n\n"
            
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
            for i, (password, generation_type, created_at) in enumerate(passwords, offset + 1):
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    formatted_date = dt.strftime("%d.%m.%Y %H:%M")
                except:
                    formatted_date = created_at
                    
                plain_history += f"{i}. {password}\n"
                plain_history += f"   📅 {formatted_date} | 🔧 {generation_type}\n\n"
            
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

async def clear_password_history(query, user_id):
    """Clear user's password history from both memory and database"""
    # Clear from memory
    if user_id in user_password_history:
        user_password_history[user_id] = []
    
    # Clear from database
    await clear_user_passwords_from_db(user_id)
    
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
• /debug \\- Show debug information
• /stats \\- Show global statistics

*Features:*
• ⚡️ *Fast Generation* \\- Instantly generate a secure password
• 👁 *Detailed Generation* \\- Customize your password settings
• 📖 *History* \\- View all previously generated passwords
• 💾 *Database Storage* \\- All passwords saved permanently

*How to use:*
1\\. Use /start to begin
2\\. Choose Fast for instant password or Detailed for custom options
3\\. Tap on generated password to copy it
4\\. Use History to see all your previous passwords

*History Features:*
• Stores ALL passwords permanently in database
• Shows password type \\(Fast/Custom\\)
• Pagination \\- 10 passwords per page
• Clear history option available
• Includes username and timestamp

*Security:*
Passwords are generated locally\\. All data stored in secure database\\."""
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to check history and settings"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Get data from memory
    history_count_memory = len(user_password_history.get(user_id, []))
    settings = user_settings.get(user_id, "No settings")
    
    # Get data from database
    history_count_db = await get_user_password_count(user_id)
    recent_passwords = await get_user_passwords_from_db(user_id, limit=5)
    
    debug_text = f"""🔍 Debug Info:

👤 User Info:
• ID: {user_id}
• Username: @{user.username or 'None'}
• Name: {user.first_name or ''} {user.last_name or ''}

📊 Password Stats:
• In memory: {history_count_memory}
• In database: {history_count_db}

⚙️ Settings: {settings}

🔐 Recent passwords (DB):"""
    
    for i, (password, gen_type, created_at) in enumerate(recent_passwords[:3], 1):
        debug_text += f"\n{i}. {password} ({gen_type}) - {created_at}"
    
    await update.message.reply_text(debug_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show global statistics"""
    stats = await get_all_passwords_stats()
    
    stats_text = f"""📊 *Global Statistics*

🔐 Total passwords generated: {stats['total_passwords']}
👥 Unique users: {stats['unique_users']}

📈 By generation type:"""
    
    for _, _, gen_type, count in stats['by_type']:
        stats_text += f"\n• {gen_type}: {count}"
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN_V2)

async def main() -> None:
    """Start the bot"""
    # Initialize database first
    await init_database()
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("debug", debug_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Run the bot using polling (works better for Railway)
    logger.info("Starting bot with polling...")
    await application.run_polling(
        poll_interval=1.0,
        timeout=10,
        bootstrap_retries=5,
        read_timeout=10,
        write_timeout=10,
        connect_timeout=10,
        pool_timeout=10
    )

if __name__ == "__main__":
    asyncio.run(main())
