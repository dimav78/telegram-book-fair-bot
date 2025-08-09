Telegram Book Fair Cashier Bot
Project Description
This project is a Telegram bot designed to function as a simple and efficient cashier application for a book fair. The bot enables cashiers (or authors themselves) to quickly process sales, manage a shopping cart, and track daily earnings. It is built to handle a low volume of transactions (up to 50 per day) with a user-friendly, conversational interface, minimizing the need for specialized hardware or software. The UI language is Russian.
The primary features include:
Product selection by author or item.
A shopping cart system to handle multiple items in one transaction.
Separate processing for cash and cashless payments.
Display of a QR code for easy cashless transactions.
A reporting feature to view daily sales totals broken down by author.
Tech Stack
Frontend/User Interface: Telegram Bot API
Backend Logic: Python 3
Primary Libraries:
python-telegram-bot: For interacting with the Telegram Bot API.
gspread & google-auth: For connecting to and manipulating the Google Sheet.
Database: Google Sheets
Hosting Environment: PythonAnywhere (production deployment) - a cloud platform for Python web applications that provides persistent background tasks and easy deployment.
IDE: PyCharm
System Architecture
The application follows a simple and effective three-tier architecture, designed for low-volume use and easy maintenance.
Presentation Layer (Telegram): The user interacts exclusively through the Telegram app. All actions are triggered by commands (/start) and inline keyboard buttons ("Select Author", "Add to Cart", etc.). The bot's interface is responsible for displaying information and capturing user input.
Business Logic Layer (Python Application): A central Python script acts as the brain of the operation. It runs continuously on a server, listening for updates from Telegram. This layer manages user state (like the contents of a shopping cart), processes requests, fetches data from Google Sheets, formats responses, and sends them back to the user via the Telegram API.
Data Layer (Google Sheets): A single Google Sheet serves as the project's database. This choice is ideal for low transaction volumes as it is free, easily accessible, and allows for simple manual review, editing, and data export by non-technical users. The data is organized across multiple tabs (e.g., Authors, Products, Transactions) to act as a relational data store.
Component Breakdown
1. Telegram Bot Interface
Purpose: To provide a seamless and intuitive user experience.
Components:
Commands: The /start command to initialize the bot and display the main menu.
Inline Keyboards: Dynamic buttons that guide the user through a workflow without requiring them to type commands. Used for selecting authors, products, payment methods, and navigating menus.
Messages & Media: The bot sends formatted text, photos (book covers), and payment information (QR codes) to the user.
2. Python Backend Application
Purpose: To orchestrate the entire sales process.
Components:
bot.py: The main entry point of the application. It initializes the bot, registers command handlers, and manages the main event loop. It contains the logic for user interaction flows.
sheets_handler.py: A dedicated module responsible for all communication with the Google Sheets API. It abstracts the complexities of fetching and writing data, providing simple functions like get_authors() or record_transaction() to the main bot logic.
config.py: A configuration file to securely store sensitive information like the Telegram API token and Google Sheets credentials, keeping them separate from the main application code.
State Management: The backend uses the python-telegram-bot library's built-in user_data to manage each user's shopping cart temporarily.
3. Google Sheets Database
Purpose: To act as the single source of truth for all persistent data.
Components (Worksheets):
Authors: A sheet containing a list of all participating authors, their unique IDs, and their specific payment information (e.g., QR code URL).
Products: The complete catalog of all books available for sale. Each entry includes a title, description, price, photo URL, and is linked to an AuthorID.
Transactions: A log where every single completed sale is recorded as a new row. It captures the product sold, payment method (cash/cashless), amount, and a timestamp, providing a complete audit trail.