import gspread
from google.oauth2.service_account import Credentials

# --- Scopes for Google APIs ---
# Defines the permissions your bot needs.
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

# --- Import configuration from config.py ---
from config import GOOGLE_CREDENTIALS_FILE, GOOGLE_SHEET_NAME, GOOGLE_SHEET_ID

# --- Authenticate and Connect to Google Sheets ---
# This code authenticates using your service account file and opens the spreadsheet.
try:
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    
    # List all accessible spreadsheets
    print("Accessible spreadsheets:")
    try:
        all_sheets = client.openall()
        for sheet in all_sheets:
            print(f"  - {sheet.title} (ID: {sheet.id})")
    except Exception as e:
        print(f"Could not list spreadsheets: {e}")
    
    # Try to open existing sheet by ID (more reliable)
    try:
        print(f"Attempting to open sheet by ID: {GOOGLE_SHEET_ID}")
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
        print(f"SUCCESS: Connected to Google Sheet: {spreadsheet.title}")
    except Exception as e:
        print(f"ERROR: Could not open sheet by ID: {e}")
        print(f"Error type: {type(e)}")
        print("Please ensure:")
        print(f"  1. Sheet ID is correct: {GOOGLE_SHEET_ID}")
        print(f"  2. Sheet is shared with: bookcashierbot@bookfaircashierbot.iam.gserviceaccount.com")
        print(f"  3. Service account has 'Editor' permissions")
        spreadsheet = None
    
    if spreadsheet:
        print(f"Spreadsheet ID: {spreadsheet.id}")
        print(f"Available worksheets: {[ws.title for ws in spreadsheet.worksheets()]}")
    
except Exception as e:
    print(f"Error with Google Sheets: {e}")
    print(f"Error type: {type(e)}")
    spreadsheet = None

# --- Functions to interact with the sheet ---

def get_authors():
    """Fetches all authors from the 'Authors' worksheet."""
    if not spreadsheet:
        return []
    try:
        authors_sheet = spreadsheet.worksheet("Authors")
        return authors_sheet.get_all_records()
    except Exception as e:
        print(f"Error fetching authors: {e}")
        return []

def get_products_by_author(author_id):
    """Fetches all products for a specific author."""
    if not spreadsheet:
        return []
    try:
        products_sheet = spreadsheet.worksheet("Products")
        all_products = products_sheet.get_all_records()
        return [product for product in all_products if product.get('AuthorID') == author_id]
    except Exception as e:
        print(f"Error fetching products for author {author_id}: {e}")
        return []

def record_transaction(product_id, author_id, payment_method, amount):
    """Adds a new row to the 'Transactions' worksheet."""
    if not spreadsheet:
        return False
    try:
        from datetime import datetime
        transactions_sheet = spreadsheet.worksheet("Transactions")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Generate transaction ID (could be improved with proper ID generation)
        existing_transactions = transactions_sheet.get_all_records()
        transaction_id = len(existing_transactions) + 1
        
        transactions_sheet.append_row([transaction_id, product_id, author_id, payment_method, amount, timestamp])
        return True
    except Exception as e:
        print(f"Error recording transaction: {e}")
        return False

def setup_worksheets():
    """Creates the necessary worksheets and columns if they don't exist."""
    if not spreadsheet:
        print("No spreadsheet connection available")
        return False
    
    try:
        # Create Authors worksheet
        try:
            authors_sheet = spreadsheet.worksheet("Authors")
            print("Authors worksheet already exists")
        except gspread.WorksheetNotFound:
            authors_sheet = spreadsheet.add_worksheet(title="Authors", rows="100", cols="10")
            authors_sheet.append_row(["AuthorID", "Name", "QR_Code_URL", "Contact"])
            print("Created Authors worksheet")
        
        # Create Products worksheet
        try:
            products_sheet = spreadsheet.worksheet("Products")
            print("Products worksheet already exists")
        except gspread.WorksheetNotFound:
            products_sheet = spreadsheet.add_worksheet(title="Products", rows="100", cols="10")
            products_sheet.append_row(["ProductID", "Title", "Description", "Price", "Photo_URL", "AuthorID"])
            print("Created Products worksheet")
        
        # Create Transactions worksheet
        try:
            transactions_sheet = spreadsheet.worksheet("Transactions")
            print("Transactions worksheet already exists")
        except gspread.WorksheetNotFound:
            transactions_sheet = spreadsheet.add_worksheet(title="Transactions", rows="1000", cols="10")
            transactions_sheet.append_row(["TransactionID", "ProductID", "AuthorID", "Payment_Method", "Amount", "Timestamp"])
            print("Created Transactions worksheet")
        
        return True
    except Exception as e:
        print(f"Error setting up worksheets: {e}")
        return False
