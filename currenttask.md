Goal: To securely deploy the bot to Heroku so it can run 24/7 without needing your PC to be on.
✅ Phase 1: Secure Configuration (No Secrets in Code)
Task 1.1: Create .gitignore file.
Action: Create the file and add entries for venv/, __pycache__/, .idea/, *.json, and .env.
Prompt: Use prompt 4.1 from CLAUDE.md.
Task 1.2: Switch to Environment Variables.
Action: Install python-dotenv. Create the .env file with your secrets. Modify bot.py and sheets_handler.py to load secrets using os.getenv() instead of config.py.
Prompt: Use prompts 4.2 and 4.3 from CLAUDE.md.
✅ Phase 2: Prepare Project for Heroku
Task 2.1: Create requirements.txt.
Action: Run pip freeze > requirements.txt in your terminal.
Prompt: Use prompt 5.1 from CLAUDE.md.
Task 2.2: Create Procfile.
Action: Create a file named Procfile and add the line: worker: python bot.py.
Prompt: Use prompt 5.2 from CLAUDE.md.
✅ Phase 3: Handle Google Credentials for Production
Task 3.1: Encode your Google Credentials.
Action: Create and run a temporary script to convert your .json file's content into a Base64 string. Copy the output string.
Prompt: Use prompt 5.3 from CLAUDE.md.
Task 3.2: Update sheets_handler.py for Dual-Mode Authentication.
Action: Modify the authentication logic to use the encoded string if it exists (on Heroku) or fall back to the local .json file (on your PC).
Prompt: Use prompt 5.4 from CLAUDE.md.
✅ Phase 4: Deploy and Run on Heroku
Task 4.1: Follow the Deployment Checklist.
Action: This is a manual process. Follow the checklist step-by-step to log in, create the app, set the environment variables (including the encoded string), push the code with Git, and start the bot.
Prompt: Use the checklist from prompt 5.5 in CLAUDE.md.
Critical Step: Remember to set TELEGRAM_TOKEN and GOOGLE_CREDS_ENCODED in the Heroku settings.