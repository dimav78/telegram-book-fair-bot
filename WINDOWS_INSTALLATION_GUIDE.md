# BookFair Bot - Windows Server Installation Guide

This guide will help you install and run the Telegram BookFair Bot on a Windows server with automatic restart capabilities, installing directly from GitHub.

## Prerequisites
- Windows Server or Windows 10/11 with internet connection
- Administrator access
- Telegram Bot Token (from @BotFather)
- Google Sheets API credentials
- Git for Windows (optional, but recommended)

## Step 1: Install Required Software

### Install Python
1. Go to https://www.python.org/downloads/windows/
2. Download Python 3.11 or newer (64-bit recommended)
3. **IMPORTANT**: During installation, check "Add Python to PATH"
4. Choose "Install for all users" if installing on a server
5. Verify installation:
   ```cmd
   python --version
   pip --version
   ```

### Install Git (Optional but Recommended)
1. Download Git from https://git-scm.com/download/win
2. Install with default settings
3. Verify installation:
   ```cmd
   git --version
   ```

## Step 2: Download Bot from GitHub

### Option A: Using Git (Recommended)
1. Open Command Prompt as Administrator
2. Navigate to your desired installation directory:
   ```cmd
   cd C:\
   ```
3. Clone the repository:
   ```cmd
   git clone https://github.com/yourusername/bookfair-bot.git BookFairBot
   cd BookFairBot
   ```

### Option B: Download ZIP
1. Go to your GitHub repository
2. Click "Code" → "Download ZIP"
3. Extract to `C:\BookFairBot\`
4. Open Command Prompt and navigate:
   ```cmd
   cd C:\BookFairBot\
   ```

## Step 3: Install Dependencies

### Install Python Packages
```cmd
cd C:\BookFairBot\
pip install -r requirements.txt
```

## Step 4: Setup Configuration

### Create Environment File
1. In the bot directory, create a file named `.env`
2. Add your configuration:
   ```
   TELEGRAM_TOKEN=your_bot_token_here
   ```

### Add Google Sheets Credentials
1. Place your Google service account JSON file in the bot directory
2. Rename it to match what's referenced in your code (e.g., `bookfaircashierbot-e76ed9e4c8e3.json`)
3. Update your `.env` file:
   ```
   TELEGRAM_TOKEN=your_bot_token_here
   GOOGLE_APPLICATION_CREDENTIALS=C:\BookFairBot\bookfaircashierbot-e76ed9e4c8e3.json
   ```

### Test the Bot
1. Run the bot manually to ensure it works:
   ```cmd
   python bot.py
   ```
2. You should see "Bot is running..."
3. Test with your Telegram bot
4. Stop with Ctrl+C

## Step 5: Create Windows Service

### Install NSSM (Non-Sucking Service Manager)
1. Download NSSM from https://nssm.cc/download
2. Extract to `C:\nssm\`
3. Add `C:\nssm\win64\` to your system PATH:
   - Windows key + R → `sysdm.cpl` → Advanced → Environment Variables
   - Edit System PATH → Add `C:\nssm\win64\`

### Create the Service
1. Open Command Prompt as Administrator
2. Install the service:
   ```cmd
   nssm install BookFairBot
   ```
3. In the NSSM GUI:
   - **Path**: `C:\Python311\python.exe` (adjust path as needed)
   - **Startup directory**: `C:\BookFairBot\`
   - **Arguments**: `bot.py`
   
4. **Details** tab:
   - **Display name**: BookFair Telegram Bot
   - **Description**: Automated Telegram bot for book fair sales
   
5. **Log on** tab:
   - Select "This account" and enter Windows credentials
   
6. Click **Install service**

### Configure Service Recovery
1. Open Services (`services.msc`)
2. Find "BookFairBot" → Properties → Recovery
3. Set all failures to "Restart the service"
4. Set restart delay to 1 minute

## Step 6: Create Management Scripts

### Update Script (`update_bot.bat`)
```batch
@echo off
echo Updating BookFair Bot from GitHub...
cd C:\BookFairBot\

echo Stopping bot service...
net stop BookFairBot

echo Pulling latest changes...
git pull origin main

echo Installing/updating dependencies...
pip install -r requirements.txt

echo Starting bot service...
net start BookFairBot

if %errorlevel% == 0 (
    echo Bot updated and restarted successfully!
) else (
    echo Failed to start bot after update. Check logs.
)
pause
```

### Start Bot Script (`start_bot.bat`)
```batch
@echo off
echo Starting BookFair Bot...
net start BookFairBot
if %errorlevel% == 0 (
    echo Bot started successfully!
) else (
    echo Failed to start bot. Check Event Viewer.
)
pause
```

### Stop Bot Script (`stop_bot.bat`)
```batch
@echo off
echo Stopping BookFair Bot...
net stop BookFairBot
echo Bot stopped.
pause
```

### Status Check Script (`check_bot.bat`)
```batch
@echo off
echo BookFair Bot Status:
sc query BookFairBot
echo.
echo Recent GitHub commits:
cd C:\BookFairBot\
git log --oneline -5
pause
```

### View Logs Script (`view_logs.bat`)
```batch
@echo off
echo Opening Event Viewer...
echo Look for "BookFairBot" in Windows Logs → Application
eventvwr.msc
```

## Step 7: Start and Configure Service

### Start the Service
```cmd
net start BookFairBot
```

### Set Auto-Start
1. Open Services (`services.msc`)
2. Right-click "BookFairBot" → Properties
3. Set "Startup type" to "Automatic"

## Step 8: Setup Automatic Updates (Optional)

### Create Scheduled Update Task
1. Open Task Scheduler
2. Create Basic Task:
   - **Name**: Update BookFair Bot
   - **Trigger**: Weekly (choose your preferred time)
   - **Action**: Start a program
   - **Program**: `C:\BookFairBot\update_bot.bat`
3. Set to run with highest privileges

### Manual Updates
Run `update_bot.bat` anytime to update from GitHub.

## GitHub Repository Setup

### Required Files in Your Repository
```
your-repo/
├── bot.py
├── sheets_handler.py
├── config.py
├── requirements.txt
├── .gitignore
└── README.md
```

### Sample `.gitignore`
```
# Environment variables
.env

# Google credentials
*.json

# Python
__pycache__/
*.pyc
*.pyo

# Logs
*.log

# Windows
Thumbs.db
desktop.ini
```

**IMPORTANT**: Never commit your `.env` file or Google credentials to GitHub!

## Troubleshooting

### Update Issues
**Git pull fails:**
```cmd
cd C:\BookFairBot\
git stash
git pull origin main
git stash pop
```

**Dependencies fail to install:**
```cmd
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

### Service Issues
**Bot won't start after update:**
1. Check Python path in NSSM config
2. Verify all files downloaded correctly
3. Check Event Viewer for errors
4. Test manually: `python bot.py`

### Connection Issues
- Verify internet connectivity
- Check Windows Firewall settings
- Ensure HTTPS (port 443) outbound is allowed

## Security Best Practices

1. **Credentials**: Keep `.env` and credential files local only
2. **Repository**: Use private repository for sensitive projects
3. **Updates**: Review changes before running update script
4. **Backup**: Backup your `.env` and credentials before updates
5. **Access**: Limit who has access to the server and GitHub repo

## Maintenance Workflow

### Regular Updates
1. Check GitHub for new commits
2. Run `update_bot.bat` during maintenance windows
3. Monitor bot functionality after updates

### Before Events
1. Run manual update: `update_bot.bat`
2. Test bot functionality
3. Check system resources
4. Verify internet connection

The bot will now automatically stay updated from your GitHub repository with easy management scripts!