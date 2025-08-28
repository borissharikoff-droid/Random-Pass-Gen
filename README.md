# Telegram Password Generator Bot

🔐 A Telegram bot for generating secure random passwords with customizable options.

## Features

- **⚡️ Fast Generation**: Instantly generate a secure 12-character password
- **👁 Detailed Generation**: Customize password length and character types
- **📖 Password History**: View all previously generated passwords with timestamps
- **📱 User-Friendly**: Interactive inline keyboards for easy navigation
- **📋 Copy-Ready**: Passwords formatted for easy copying in Telegram
- **🔒 Secure**: Passwords generated locally, history stored temporarily

## Bot Commands

- `/start` - Start the bot and show main menu
- `/help` - Show help information and usage instructions

## Main Menu Options

- **⚡️ Fast** - Generate instant secure password
- **👁 Detailed** - Customize password settings
- **📖 History** - View password history

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

1. Start the bot with `/start`
2. Choose between:
   - **⚡️ Fast** - Get an instant secure password
   - **👁 Detailed** - Customize your password settings
   - **📖 History** - View all your generated passwords
3. Tap on the generated password to copy it
4. Use the navigation buttons to generate more passwords or change settings

## Password History Features

- **Storage**: Keeps last 20 generated passwords
- **Timestamps**: Shows when each password was created
- **Types**: Displays whether password was Fast or Custom generated
- **Easy Access**: All passwords formatted for easy copying
- **Clear Option**: Ability to clear entire history
- **Session Based**: History is temporary and resets when bot restarts

## Technical Details

- Built with `python-telegram-bot` library
- Uses inline keyboards for user interaction
- Supports both polling (local) and webhook (Railway) modes
- Automatic environment detection for deployment mode
