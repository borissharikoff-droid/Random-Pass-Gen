# Telegram Password Generator Bot

🔐 A Telegram bot for generating secure random passwords with customizable options.

## Features

- **⚡️ Fast Generation**: Instantly generate a secure 12-character password
- **👁 Detailed Generation**: Customize password length and character types
- **📖 Password History**: View all previously generated passwords with timestamps
- **🔑 Password Manager**: Save and manage your passwords with descriptions
- **➕ Add Passwords**: Manually add passwords from any source
- **💾 Save Generated**: Save generated passwords directly to Manager
- **📱 User-Friendly**: Interactive inline keyboards for easy navigation
- **📋 Copy-Ready**: Passwords formatted for easy copying in Telegram
- **🔒 Secure**: Passwords generated locally, all data stored in encrypted database

## Bot Commands

- `/start` - Start the bot and show main menu
- `/help` - Show help information and usage instructions
- `/debug` - Show debug information (history count, user data)
- `/stats` - Show global statistics
- `/delete_<id>` - Delete a password from Password Manager

## Main Menu Options

- **⚡️ Fast** - Generate instant secure password
- **👁 Detailed** - Customize password settings
- **📖 History** - View password generation history
- **🔑 Password Manager** - View and manage saved passwords
- **➕ Add Password** - Manually add a password to Manager

## Password Options

### Fast Generation
- Length: 12 characters
- Includes: lowercase, uppercase, digits, symbols

### Detailed Generation
- **Length**: 8, 12, 16, 20, 24, or 32 characters
- **Character Types**:
  - Lowercase letters (a-z)
  - Uppercase letters (A-Z)
  - Digits (0-9)
  - Symbols (!@#$%^&*()_+-=[]{}|;:,.<>?)

## Local Development

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the bot:
   ```bash
   python main.py
   ```

## Railway Deployment

This bot is configured for easy deployment on Railway:

1. Connect your GitHub repository to Railway
2. Railway will automatically detect the configuration files
3. The bot will start automatically using the webhook mode

### Configuration Files

- `Procfile` - Defines the web process
- `railway.json` - Railway-specific configuration
- `runtime.txt` - Python version specification
- `requirements.txt` - Python dependencies

## Bot Token

The bot token is currently hardcoded in `main.py`. For production deployment, it's recommended to use environment variables:

```python
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'your_default_token_here')
```

## Security Features

- Passwords are generated using Python's `random` module
- No password storage - generated on-demand
- No persistent user data storage
- All processing happens locally

## Usage Example

### Generate and Save Password

1. Start the bot with `/start`
2. Choose **⚡️ Fast** or **👁 Detailed**
3. Get your generated password
4. Click **💾 Save to Manager**
5. Enter service name (e.g., "Gmail")
6. Enter username (optional)
7. Add notes (optional)
8. Password saved! ✅

### Add Existing Password

1. Start the bot with `/start`
2. Click **➕ Add Password**
3. Enter service name
4. Enter username
5. Enter password
6. Add notes (optional)
7. Password added! ✅

### View and Manage

1. Click **🔑 Password Manager**
2. Browse your saved passwords
3. Tap password to copy
4. Use `/delete_<id>` to remove passwords

## Password History Features

- **Storage**: Keeps ALL generated passwords permanently in database
- **Timestamps**: Shows when each password was created
- **Types**: Displays whether password was Fast or Custom generated
- **Easy Access**: All passwords formatted for easy copying
- **Clear Option**: Ability to clear entire history
- **Pagination**: 10 passwords per page with navigation
- **Persistent**: History stored in database, never resets

## Password Manager Features

- **Save Generated**: Save any generated password with description
- **Add Manually**: Add passwords from any source
- **Service Names**: Organize passwords by service (Gmail, Facebook, etc.)
- **Usernames**: Store username/email for each password
- **Notes**: Add optional notes for each entry
- **View All**: Browse all saved passwords with pagination (5 per page)
- **Delete**: Remove passwords with `/delete_<id>` command
- **Secure**: Each user sees only their own passwords
- **Persistent**: All data stored in SQLite database

## Technical Details

- Built with `python-telegram-bot` library v21.7
- Uses inline keyboards for user interaction
- ConversationHandler for interactive password adding
- MessageHandler for text input processing
- SQLite database for persistent storage
- Two tables: `password_history` and `password_manager`
- Supports both polling (local) and webhook (Railway) modes
- Automatic environment detection for deployment mode
- Context7 documentation used for best practices

## Database Schema

### password_history
Stores all generated passwords with metadata

### password_manager
Stores user-saved passwords with descriptions:
- `id` - Unique identifier
- `user_id` - Telegram user ID
- `service_name` - Service name (required)
- `username` - Username/email (optional)
- `password` - Password (required)
- `notes` - Additional notes (optional)
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp
