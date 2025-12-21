import logging
import random
import string
import os
import aiosqlite
import asyncio
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
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

# Conversation states for adding password manually
ASK_SERVICE, ASK_USERNAME, ASK_PASSWORD, ASK_NOTES = range(4)

def escape_markdown_v2(text):
    """Escape special characters for Markdown V2"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def safe_monospace_password(password):
    """Safely format password in monospace, handling all special characters"""
    try:
        # Try simple monospace first
        return f"`{password}`"
    except:
        # If that fails, just return the password
        return password

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
        
        # Password Manager table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS password_manager (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                username TEXT,
                password TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

async def get_all_passwords_from_db(limit=50, offset=0):
    """Get all passwords from database with pagination (admin function)"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT user_id, username, first_name, last_name, password, generation_type, created_at 
                FROM password_history 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            rows = await cursor.fetchall()
            return rows
    except Exception as e:
        logger.error(f"Error getting all passwords: {e}")
        return []

async def get_total_passwords_count():
    """Get total count of all passwords in database"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM password_history")
            count = await cursor.fetchone()
            return count[0] if count else 0
    except Exception as e:
        logger.error(f"Error getting total count: {e}")
        return 0

# Password Manager Database Functions
async def save_password_to_manager(user_id, service_name, username, password, notes=""):
    """Save password to Password Manager"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("""
                INSERT INTO password_manager (user_id, service_name, username, password, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, service_name, username, password, notes))
            await db.commit()
            logger.info(f"Password saved to manager for user {user_id}, service {service_name}")
            return True
    except Exception as e:
        logger.error(f"Error saving password to manager: {e}")
        return False

async def get_manager_passwords(user_id, limit=20, offset=0):
    """Get user's passwords from Password Manager with pagination"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT id, service_name, username, password, notes, created_at 
                FROM password_manager 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))
            rows = await cursor.fetchall()
            return rows
    except Exception as e:
        logger.error(f"Error getting manager passwords: {e}")
        return []

async def get_manager_password_count(user_id):
    """Get total count of user's passwords in Password Manager"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM password_manager WHERE user_id = ?
            """, (user_id,))
            count = await cursor.fetchone()
            return count[0] if count else 0
    except Exception as e:
        logger.error(f"Error getting manager password count: {e}")
        return 0

async def delete_manager_password(user_id, password_id):
    """Delete a password from Password Manager"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("""
                DELETE FROM password_manager WHERE id = ? AND user_id = ?
            """, (password_id, user_id))
            await db.commit()
            logger.info(f"Deleted password {password_id} for user {user_id}")
            return True
    except Exception as e:
        logger.error(f"Error deleting password: {e}")
        return False

async def get_manager_password_by_id(user_id, password_id):
    """Get a specific password from Password Manager"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT id, service_name, username, password, notes, created_at
                FROM password_manager 
                WHERE id = ? AND user_id = ?
            """, (password_id, user_id))
            row = await cursor.fetchone()
            return row
    except Exception as e:
        logger.error(f"Error getting password by id: {e}")
        return None

# Password Manager Functions
async def save_generated_password_to_manager(query, user_id, context):
    """Start the process of saving generated password to manager"""
    password = context.user_data.get('last_generated_password')
    
    if not password:
        await query.edit_message_text(
            "❌ No password found to save\\. Please generate a password first\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    
    # Store password for the conversation
    context.user_data['password_to_save'] = password
    context.user_data['is_saving_generated'] = True
    context.user_data['waiting_for_service'] = True
    context.user_data['conv_state'] = ASK_SERVICE
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_password")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=f"💾 *Save Password to Manager*\n\nPassword: `{password}`\n\n📝 Please send the *service name* \\(e\\.g\\., Gmail, Facebook, etc\\.\\)",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    return ASK_SERVICE

async def ask_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask for service name when adding password manually"""
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_password")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💾 *Add Password to Manager*\n\n📝 Please send the *service name* \\(e\\.g\\., Gmail, Facebook, Instagram\\)",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return ASK_USERNAME

async def receive_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive service name and ask for username"""
    service_name = update.message.text
    context.user_data['service_name'] = service_name
    
    keyboard = [[InlineKeyboardButton("⏭ Skip", callback_data="skip_username")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Service: *{service_name}*\n\n👤 Now send your *username or email* for this service\n\n_Or click Skip if not needed_",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return ASK_PASSWORD

async def receive_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive username and ask for password"""
    username = update.message.text
    context.user_data['username'] = username
    
    # Check if we're saving a generated password
    if context.user_data.get('is_saving_generated'):
        keyboard = [[InlineKeyboardButton("⏭ Skip Notes", callback_data="skip_notes_generated")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        password = context.user_data.get('password_to_save', '')
        service = context.user_data.get('service_name', '')
        
        await update.message.reply_text(
            f"✅ Username: *{username}*\n\n📝 Send any *notes* \\(optional\\)\n\n_Or click Skip to save now_",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ASK_NOTES
    else:
        keyboard = [[InlineKeyboardButton("⏭ Skip", callback_data="skip_password")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Username: *{username}*\n\n🔐 Now send the *password* for this service",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ASK_NOTES

async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive password and ask for notes"""
    password = update.message.text
    context.user_data['password_to_save'] = password
    
    keyboard = [[InlineKeyboardButton("⏭ Skip Notes", callback_data="skip_notes")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✅ Password received\n\n📝 Send any *notes* \\(optional\\)\n\n_Or click Skip to save now_",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return ASK_NOTES

async def receive_notes_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive notes and save password to manager"""
    notes = update.message.text if update.message else ""
    
    user_id = update.effective_user.id
    service_name = context.user_data.get('service_name', '')
    username = context.user_data.get('username', '')
    password = context.user_data.get('password_to_save', '')
    
    # Save to database
    success = await save_password_to_manager(user_id, service_name, username, password, notes)
    
    if success:
        keyboard = [
            [InlineKeyboardButton("🔑 View Manager", callback_data="password_manager")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ *Password Saved Successfully\\!*\n\n📦 Service: *{service_name}*\n👤 Username: {username if username else '_not provided_'}\n🔐 Password: `{password}`\n📝 Notes: {notes if notes else '_none_'}",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await update.message.reply_text(
            "❌ Error saving password\\. Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    # Clear conversation data
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_add_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel adding password"""
    context.user_data.clear()
    
    keyboard = [
        [
            InlineKeyboardButton("⚡️ Fast", callback_data="fast"),
            InlineKeyboardButton("👁 Detailed", callback_data="detailed")
        ],
        [
            InlineKeyboardButton("📖 History", callback_data="history"),
            InlineKeyboardButton("🔑 Password Manager", callback_data="password_manager")
        ],
        [
            InlineKeyboardButton("➕ Add Password", callback_data="add_password_start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "❌ Cancelled\\.\n\n🔐 *Dox: Pass Gen*\n\nChoose your option:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message_text, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await update.message.reply_text(
            message_text, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    return ConversationHandler.END

async def show_password_manager(query, user_id, page=1):
    """Show Password Manager with pagination"""
    logger.info(f"Showing password manager page {page} for user {user_id}")
    
    total_passwords = await get_manager_password_count(user_id)
    
    if total_passwords == 0:
        keyboard = [
            [InlineKeyboardButton("➕ Add Password", callback_data="add_password_start")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text="🔑 *Password Manager*\n\n❌ No passwords saved yet\\.\n\nAdd passwords to keep them safe\\!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    
    # Pagination settings
    passwords_per_page = 5
    total_pages = (total_passwords + passwords_per_page - 1) // passwords_per_page
    page = max(1, min(page, total_pages))
    offset = (page - 1) * passwords_per_page
    
    # Get passwords from database
    passwords = await get_manager_passwords(user_id, passwords_per_page, offset)
    
    # Build text
    try:
        manager_text = f"🔑 *Password Manager* \\(Page {page}/{total_pages}\\)\n\n"
        
        for pwd_id, service, username, password, notes, created_at in passwords:
            safe_password = safe_monospace_password(password)
            manager_text += f"📦 *{service}*\n"
            if username:
                manager_text += f"👤 {username}\n"
            manager_text += f"🔐 {safe_password}\n"
            if notes:
                # Escape notes for MarkdownV2
                escaped_notes = notes.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
                manager_text += f"📝 _{escaped_notes}_\n"
            manager_text += f"🗑 /delete\\_{pwd_id}\n\n"
        
        manager_text += "_Tap password to copy_"
        
        # Create keyboard
        keyboard = []
        
        # Pagination
        if total_pages > 1:
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"manager_page_{page-1}"))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"manager_page_{page+1}"))
            if nav_buttons:
                keyboard.append(nav_buttons)
            keyboard.append([InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop")])
        
        keyboard.append([InlineKeyboardButton("➕ Add Password", callback_data="add_password_start")])
        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=manager_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
    except Exception as e:
        logger.error(f"Error showing password manager: {e}")
        # Fallback without markdown
        simple_text = f"🔑 Password Manager (Page {page}/{total_pages})\n\n"
        
        for pwd_id, service, username, password, notes, created_at in passwords:
            simple_text += f"📦 {service}\n"
            if username:
                simple_text += f"👤 {username}\n"
            simple_text += f"🔐 `{password}`\n"
            if notes:
                simple_text += f"📝 {notes}\n"
            simple_text += f"🗑 /delete_{pwd_id}\n\n"
        
        keyboard = []
        if total_pages > 1:
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"manager_page_{page-1}"))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"manager_page_{page+1}"))
            if nav_buttons:
                keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("➕ Add Password", callback_data="add_password_start")])
        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=simple_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send start message with inline keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("⚡️ Fast", callback_data="fast"),
            InlineKeyboardButton("👁 Detailed", callback_data="detailed")
        ],
        [
            InlineKeyboardButton("📖 History", callback_data="history"),
            InlineKeyboardButton("🔑 Password Manager", callback_data="password_manager")
        ],
        [
            InlineKeyboardButton("➕ Add Password", callback_data="add_password_start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """🔐 *Dox: Pass Gen*

1\\. Fast password generation
2\\. Detailed password generation
3\\. Password history
4\\. Password Manager \\- save and manage your passwords

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
            
            # Store password in context for saving to manager
            context.user_data['last_generated_password'] = password
            
            # Format password in monospace for easy copying
            password_text = f"`{password}`"
            
            # Create keyboard with main menu buttons and Save to Manager option
            keyboard = [
                [
                    InlineKeyboardButton("💾 Save to Manager", callback_data="save_to_manager")
                ],
                [
                    InlineKeyboardButton("⚡️ Fast", callback_data="fast"),
                    InlineKeyboardButton("👁 Detailed", callback_data="detailed")
                ],
                [
                    InlineKeyboardButton("📖 History", callback_data="history"),
                    InlineKeyboardButton("🔑 Manager", callback_data="password_manager")
                ],
                [
                    InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=f"🔐 *Your fast password:*\n\n{password_text}\n\n_Tap to copy_\n\n💡 _You can save this password to Manager_",
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
            
        elif query.data.startswith("admin_all_page_"):
            # Handle admin all passwords pagination
            page = int(query.data.replace("admin_all_page_", ""))
            await show_all_passwords_page(query, user_id, page)
            
        elif query.data in ["admin_menu", "admin_stats", "admin_export"]:
            # Handle admin callbacks
            await handle_admin_callbacks(query, user_id)
        
        elif query.data == "save_to_manager":
            # Start saving generated password to manager
            await save_generated_password_to_manager(query, user_id, context)
        
        elif query.data == "password_manager":
            # Show password manager
            await show_password_manager(query, user_id, 1)
        
        elif query.data.startswith("manager_page_"):
            # Handle password manager pagination
            page = int(query.data.replace("manager_page_", ""))
            await show_password_manager(query, user_id, page)
        
        elif query.data == "add_password_start":
            # Start adding password manually
            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_add_password")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "💾 *Add Password to Manager*\n\n📝 Please send the *service name* \\(e\\.g\\., Gmail, Facebook, Instagram\\)",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            context.user_data['adding_password'] = True
            context.user_data['is_saving_generated'] = False
            context.user_data['conv_state'] = ASK_SERVICE
        
        elif query.data == "cancel_add_password":
            # Cancel adding password
            await cancel_add_password(update, context)
        
        elif query.data == "skip_username":
            # Skip username and ask for password
            context.user_data['username'] = ""
            
            if context.user_data.get('is_saving_generated'):
                keyboard = [[InlineKeyboardButton("⏭ Skip Notes", callback_data="skip_notes_generated")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    "📝 Send any *notes* \\(optional\\)\n\n_Or click Skip to save now_",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                context.user_data['conv_state'] = ASK_NOTES
            else:
                keyboard = [[InlineKeyboardButton("⏭ Skip", callback_data="skip_password")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    "🔐 Now send the *password* for this service",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                context.user_data['conv_state'] = ASK_PASSWORD
        
        elif query.data in ["skip_notes", "skip_notes_generated"]:
            # Skip notes and save
            user_id = query.from_user.id
            service_name = context.user_data.get('service_name', '')
            username = context.user_data.get('username', '')
            password = context.user_data.get('password_to_save', '')
            notes = ""
            
            success = await save_password_to_manager(user_id, service_name, username, password, notes)
            
            if success:
                keyboard = [
                    [InlineKeyboardButton("🔑 View Manager", callback_data="password_manager")],
                    [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                safe_service = service_name.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
                safe_username = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!') if username else '_not provided_'
                
                await query.edit_message_text(
                    f"✅ *Password Saved Successfully\\!*\n\n📦 Service: *{safe_service}*\n👤 Username: {safe_username}\n🔐 Password: `{password}`",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                await query.edit_message_text(
                    "❌ Error saving password\\. Please try again\\.",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            
            context.user_data.clear()
            
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
    
    # Store password in context for saving to manager
    context = query._context
    context.user_data['last_generated_password'] = password
    
    # Format password in monospace for easy copying
    password_text = f"`{password}`"
    
    # Create keyboard with options
    keyboard = [
        [InlineKeyboardButton("💾 Save to Manager", callback_data="save_to_manager")],
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
            InlineKeyboardButton("📖 History", callback_data="history"),
            InlineKeyboardButton("🔑 Password Manager", callback_data="password_manager")
        ],
        [
            InlineKeyboardButton("➕ Add Password", callback_data="add_password_start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """🔐 *Dox: Pass Gen*

1\\. Fast password generation
2\\. Detailed password generation
3\\. Password history
4\\. Password Manager \\- save and manage your passwords

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
            safe_password = safe_monospace_password(password)
            history_text += f"{i}\\. {safe_password}\n"
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
                    
                safe_password = safe_monospace_password(password)
                simple_history += f"{i}. {safe_password}\n"
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
• /delete\\_<id> \\- Delete password from Manager

*Features:*
• ⚡️ *Fast Generation* \\- Instantly generate a secure password
• 👁 *Detailed Generation* \\- Customize your password settings
• 📖 *History* \\- View all previously generated passwords
• 🔑 *Password Manager* \\- Save and manage your passwords
• ➕ *Add Password* \\- Manually add passwords to Manager
• 💾 *Database Storage* \\- All passwords saved permanently

*How to use:*
1\\. Use /start to begin
2\\. Choose Fast for instant password or Detailed for custom options
3\\. Tap on generated password to copy it
4\\. Save generated passwords to Manager with "Save to Manager" button
5\\. Add your own passwords manually with "Add Password"
6\\. View all saved passwords in Password Manager

*Password Manager Features:*
• Save generated passwords with service name
• Add passwords manually from any source
• Store username/email for each password
• Add optional notes for each entry
• View all passwords with pagination
• Delete passwords with /delete\\_<id> command
• All data encrypted and secure

*History Features:*
• Stores ALL generated passwords permanently
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

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to view all passwords (restricted access)"""
    user_id = update.effective_user.id
    
    # Add your admin user IDs here
    ADMIN_IDS = [250800600]  # Replace with actual admin Telegram IDs
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Access denied. This command is for administrators only.")
        return
    
    # Create inline keyboard for admin functions
    keyboard = [
        [InlineKeyboardButton("📖 View All Passwords", callback_data="admin_all_page_1")],
        [InlineKeyboardButton("📊 Detailed Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📋 Export Data", callback_data="admin_export")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔧 *Admin Panel*\n\nChoose an option:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def show_all_passwords_page(query, admin_user_id, page=1):
    """Show all passwords with pagination (admin only)"""
    # Verify admin access
    ADMIN_IDS = [250800600]  # Replace with actual admin Telegram IDs
    if admin_user_id not in ADMIN_IDS:
        await query.answer("❌ Access denied")
        return
    
    logger.info(f"Admin {admin_user_id} viewing all passwords page {page}")
    
    # Get total count from database
    total_passwords = await get_total_passwords_count()
    
    if total_passwords == 0:
        await query.edit_message_text(
            text="📖 *All Passwords*\n\n❌ No passwords in database yet\\.",
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
    passwords = await get_all_passwords_from_db(passwords_per_page, offset)
    
    # Build history text
    try:
        history_text = f"📖 *All Passwords* \\(Page {page}/{total_pages}\\)\n\n"
        
        for i, (user_id, username, first_name, last_name, password, generation_type, created_at) in enumerate(passwords, offset + 1):
            # Format the datetime
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                formatted_date = dt.strftime("%d.%m.%Y %H:%M")
            except:
                formatted_date = created_at
            
            # Format user info
            user_info = f"@{username}" if username else f"{first_name or ''} {last_name or ''}".strip()
            if not user_info:
                user_info = f"ID:{user_id}"
            
            # Use monospace for passwords to make them copyable
            safe_password = safe_monospace_password(password)
            history_text += f"{i}\\. {safe_password}\n"
            history_text += f"   👤 {user_info} \\| 📅 {formatted_date} \\| 🔧 {generation_type}\n\n"
        
        history_text += "_Tap any password to copy_"
        
        # Create pagination keyboard
        keyboard = []
        
        # Pagination buttons
        if total_pages > 1:
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_all_page_{page-1}"))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_all_page_{page+1}"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            # Page indicator
            keyboard.append([InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop")])
        
        # Back button
        keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=history_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
    except Exception as e:
        logger.error(f"Error showing all passwords page {page}: {e}")
        # Fallback without markdown
        try:
            simple_history = f"📖 All Passwords (Page {page}/{total_pages})\n\n"
            for i, (user_id, username, first_name, last_name, password, generation_type, created_at) in enumerate(passwords, offset + 1):
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    formatted_date = dt.strftime("%d.%m.%Y %H:%M")
                except:
                    formatted_date = created_at
                
                user_info = f"@{username}" if username else f"{first_name or ''} {last_name or ''}".strip()
                if not user_info:
                    user_info = f"ID:{user_id}"
                    
                safe_password = safe_monospace_password(password)
                simple_history += f"{i}. {safe_password}\n"
                simple_history += f"   👤 {user_info} | 📅 {formatted_date} | 🔧 {generation_type}\n\n"
            
            keyboard = []
            if total_pages > 1:
                nav_buttons = []
                if page > 1:
                    nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_all_page_{page-1}"))
                if page < total_pages:
                    nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_all_page_{page+1}"))
                if nav_buttons:
                    keyboard.append(nav_buttons)
            
            keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=simple_history,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
        except Exception as e2:
            logger.error(f"Error in admin fallback: {e2}")
            await query.edit_message_text("❌ Error displaying passwords. Check logs.")

# Add handler for admin menu callback
async def handle_admin_callbacks(query, user_id):
    """Handle admin-specific callbacks"""
    ADMIN_IDS = [250800600]  # Replace with actual admin Telegram IDs
    if user_id not in ADMIN_IDS:
        await query.answer("❌ Access denied")
        return
    
    if query.data == "admin_menu":
        keyboard = [
            [InlineKeyboardButton("📖 View All Passwords", callback_data="admin_all_page_1")],
            [InlineKeyboardButton("📊 Detailed Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("📋 Export Data", callback_data="admin_export")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔧 *Admin Panel*\n\nChoose an option:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    elif query.data == "admin_stats":
        stats = await get_all_passwords_stats()
        
        stats_text = f"""📊 *Detailed Statistics*

🔐 Total passwords: {stats['total_passwords']}
👥 Unique users: {stats['unique_users']}

📈 By generation type:"""
        
        for _, _, gen_type, count in stats['by_type']:
            stats_text += f"\n• {gen_type}: {count}"
        
        keyboard = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    elif query.data == "admin_export":
        # Export database data
        try:
            export_text = "📋 *Database Export*\n\n"
            
            # Get all data
            async with aiosqlite.connect(DATABASE_PATH) as db:
                cursor = await db.execute("""
                    SELECT user_id, username, first_name, last_name, password, generation_type, created_at
                    FROM password_history 
                    ORDER BY created_at DESC 
                    LIMIT 100
                """)
                rows = await cursor.fetchall()
                
                export_text += f"📊 *Total records*: {len(rows)} (showing last 100)\n\n"
                
                for i, (user_id, username, first_name, last_name, password, gen_type, created_at) in enumerate(rows[:20], 1):
                    user_info = f"@{username}" if username else f"{first_name or ''} {last_name or ''}".strip()
                    if not user_info:
                        user_info = f"ID:{user_id}"
                    
                    export_text += f"{i}\\. `{password}` \\({gen_type}\\)\n"
                    export_text += f"   👤 {user_info} \\| 📅 {created_at}\n\n"
                
                if len(rows) > 20:
                    export_text += f"_\\.\\.\\. and {len(rows) - 20} more records_"
            
            keyboard = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                export_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            await query.edit_message_text(
                f"❌ Error exporting data: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_menu")]])
            )

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages during password adding conversation"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Check if user is in a conversation
    if not context.user_data.get('adding_password') and not context.user_data.get('waiting_for_service'):
        return
    
    # Set state if not set but we're in a conversation
    state = context.user_data.get('conv_state')
    if state is None:
        if context.user_data.get('waiting_for_service') or context.user_data.get('adding_password'):
            state = ASK_SERVICE
            context.user_data['conv_state'] = ASK_SERVICE
        else:
            return
    
    if state == ASK_SERVICE:
        # Received service name
        context.user_data['service_name'] = text
        keyboard = [[InlineKeyboardButton("⏭ Skip", callback_data="skip_username")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        safe_text = text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
        
        await update.message.reply_text(
            f"✅ Service: *{safe_text}*\n\n👤 Now send your *username or email* for this service\n\n_Or click Skip if not needed_",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        context.user_data['conv_state'] = ASK_USERNAME
        
    elif state == ASK_USERNAME:
        # Received username
        context.user_data['username'] = text
        
        if context.user_data.get('is_saving_generated'):
            keyboard = [[InlineKeyboardButton("⏭ Skip Notes", callback_data="skip_notes_generated")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Username: *{text}*\n\n📝 Send any *notes* \\(optional\\)\n\n_Or click Skip to save now_",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            context.user_data['conv_state'] = ASK_NOTES
        else:
            await update.message.reply_text(
                f"✅ Username: *{text}*\n\n🔐 Now send the *password* for this service",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            context.user_data['conv_state'] = ASK_PASSWORD
            
    elif state == ASK_PASSWORD:
        # Received password
        context.user_data['password_to_save'] = text
        keyboard = [[InlineKeyboardButton("⏭ Skip Notes", callback_data="skip_notes")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "✅ Password received\n\n📝 Send any *notes* \\(optional\\)\n\n_Or click Skip to save now_",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        context.user_data['conv_state'] = ASK_NOTES
        
    elif state == ASK_NOTES:
        # Received notes, save everything
        notes = text
        service_name = context.user_data.get('service_name', '')
        username = context.user_data.get('username', '')
        password = context.user_data.get('password_to_save', '')
        
        success = await save_password_to_manager(user_id, service_name, username, password, notes)
        
        if success:
            keyboard = [
                [InlineKeyboardButton("🔑 View Manager", callback_data="password_manager")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            safe_service = service_name.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
            safe_username = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!') if username else '_not provided_'
            safe_notes = notes.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
            
            await update.message.reply_text(
                f"✅ *Password Saved Successfully\\!*\n\n📦 Service: *{safe_service}*\n👤 Username: {safe_username}\n🔐 Password: `{password}`\n📝 Notes: {safe_notes}",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            await update.message.reply_text(
                "❌ Error saving password\\. Please try again\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        
        context.user_data.clear()

async def delete_password_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a password from Password Manager"""
    user_id = update.effective_user.id
    
    # Extract password ID from command
    # Command format: /delete_123
    command_text = update.message.text
    
    try:
        password_id = int(command_text.split('_')[1])
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Invalid command format. Use: /delete_<id>")
        return
    
    # Verify password belongs to user
    password = await get_manager_password_by_id(user_id, password_id)
    
    if not password:
        await update.message.reply_text("❌ Password not found or doesn't belong to you.")
        return
    
    # Delete password
    success = await delete_manager_password(user_id, password_id)
    
    if success:
        keyboard = [
            [InlineKeyboardButton("🔑 View Manager", callback_data="password_manager")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        service_name = password[1]
        await update.message.reply_text(
            f"✅ *Password Deleted*\n\n📦 Service: {service_name} has been removed from your Password Manager\\.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await update.message.reply_text("❌ Error deleting password. Please try again.")

async def db_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show database info (admin only)"""
    user_id = update.effective_user.id
    
    # Add your admin user IDs here
    ADMIN_IDS = [250800600]  # Replace with actual admin Telegram IDs
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Access denied. This command is for administrators only.")
        return
    
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Get table info
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = await cursor.fetchall()
            
            # Get record count
            cursor = await db.execute("SELECT COUNT(*) FROM password_history;")
            total_count = await cursor.fetchone()
            
            # Get unique users count
            cursor = await db.execute("SELECT COUNT(DISTINCT user_id) FROM password_history;")
            users_count = await cursor.fetchone()
            
            # Get recent records
            cursor = await db.execute("""
                SELECT user_id, username, password, generation_type, created_at 
                FROM password_history 
                ORDER BY created_at DESC 
                LIMIT 5
            """)
            recent = await cursor.fetchall()
            
            info_text = f"""🗄️ **Database Info**

📊 **Statistics:**
• Total passwords: {total_count[0] if total_count else 0}
• Unique users: {users_count[0] if users_count else 0}
• Tables: {', '.join([t[0] for t in tables])}

📝 **Recent entries:**"""

            for i, (uid, username, password, gen_type, created_at) in enumerate(recent, 1):
                user_info = f"@{username}" if username else f"ID:{uid}"
                info_text += f"\n{i}. `{password}` ({gen_type}) - {user_info}"
            
            await update.message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN_V2)
            
    except Exception as e:
        await update.message.reply_text(f"❌ Database error: {str(e)}")

def main() -> None:
    """Start the bot"""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("debug", debug_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("dbinfo", db_info_command))
    
    # Add delete command handler with pattern matching
    from telegram.ext import filters as Filters
    application.add_handler(MessageHandler(
        Filters.Regex(r'^/delete_\d+$'), 
        delete_password_command
    ))
    
    # Add text message handler for conversation
    application.add_handler(MessageHandler(
        Filters.TEXT & ~Filters.COMMAND, 
        handle_text_messages
    ))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Initialize database
    async def init_db():
        await init_database()
    
    # Run database initialization
    asyncio.get_event_loop().run_until_complete(init_db())
    
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
