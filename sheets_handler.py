import gspread
import os
import json
import base64
import time
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from functools import wraps

# --- Load environment variables ---
load_dotenv()

# --- Cache for reducing API calls ---
_cache = {}
CACHE_TTL = 300  # 5 minutes cache

def with_cache(ttl=CACHE_TTL):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}_{str(args)}_{str(kwargs)}"
            current_time = time.time()
            
            if cache_key in _cache:
                cached_result, cached_time = _cache[cache_key]
                if current_time - cached_time < ttl:
                    return cached_result
            
            result = func(*args, **kwargs)
            _cache[cache_key] = (result, current_time)
            return result
        return wrapper
    return decorator

def retry_with_backoff(max_retries=3, base_delay=1):
    """Decorator for exponential backoff retry on API errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "429" in str(e) or "Quota exceeded" in str(e):
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            print(f"Rate limit hit, retrying in {delay} seconds...")
                            time.sleep(delay)
                            continue
                    raise e
            return func(*args, **kwargs)
        return wrapper
    return decorator

# --- Scopes for Google APIs ---
# Defines the permissions your bot needs.
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

# --- Get configuration from environment ---
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE')
GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME')
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')

# --- Authenticate and Connect to Google Sheets ---
# This code supports dual authentication: Heroku (encoded) or local file
def get_google_credentials():
    """Get Google credentials either from encoded string (Heroku) or local file (development)."""
    
    # Check if we have encoded credentials (for Heroku production)
    encoded_creds = os.getenv('GOOGLE_CREDS_ENCODED')
    if encoded_creds:
        print("Using encoded Google credentials (production mode)")
        try:
            # Decode the Base64 string
            creds_json = base64.b64decode(encoded_creds).decode('utf-8')
            creds_dict = json.loads(creds_json)
            return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        except Exception as e:
            print(f"ERROR: Failed to decode Google credentials: {e}")
            return None
    
    # Fall back to local file (for development)
    elif GOOGLE_CREDENTIALS_FILE and os.path.exists(GOOGLE_CREDENTIALS_FILE):
        print(f"Using local Google credentials file: {GOOGLE_CREDENTIALS_FILE}")
        try:
            return Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        except Exception as e:
            print(f"ERROR: Failed to load credentials from file: {e}")
            return None
    
    else:
        print("ERROR: No Google credentials found!")
        print("Set GOOGLE_CREDS_ENCODED environment variable or ensure credentials file exists.")
        return None

try:
    creds = get_google_credentials()
    if not creds:
        raise Exception("Failed to obtain Google credentials")
        
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

# --- Cache management ---
def clear_all_caches():
    """Clears all caches to force fresh data retrieval"""
    global _cache, _all_products_cache, _all_products_cache_time
    _cache.clear()
    _all_products_cache = None
    _all_products_cache_time = 0
    print("All caches cleared")

# --- Batch operations ---
_all_products_cache = None
_all_products_cache_time = 0

def get_all_products():
    """Get all products at once to reduce API calls"""
    global _all_products_cache, _all_products_cache_time
    current_time = time.time()
    
    if _all_products_cache and current_time - _all_products_cache_time < 300:
        return _all_products_cache
    
    if not spreadsheet:
        return []
    try:
        products_sheet = spreadsheet.worksheet("Products")
        _all_products_cache = products_sheet.get_all_records()
        _all_products_cache_time = current_time
        return _all_products_cache
    except Exception as e:
        print(f"Error fetching all products: {e}")
        return []

# --- Functions to interact with the sheet ---

@with_cache(ttl=600)  # Cache for 10 minutes
@retry_with_backoff()
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
    """Fetches all products for a specific author using batch data."""
    all_products = get_all_products()
    return [product for product in all_products if product.get('AuthorID') == author_id]

def get_lottery_products():
    """Fetches all products eligible for lottery (where Lottery = Yes)."""
    all_products = get_all_products()
    return [product for product in all_products if product.get('Lottery', '').strip().lower() == 'yes']

@retry_with_backoff()
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

@retry_with_backoff()
def get_transactions_from_date(start_date=None):
    """Fetches transactions from a specific date onwards. If no date provided, gets all transactions."""
    if not spreadsheet:
        return []
    try:
        transactions_sheet = spreadsheet.worksheet("Transactions")
        all_transactions = transactions_sheet.get_all_records()
        
        if not start_date:
            return all_transactions
            
        from datetime import datetime
        # Filter transactions by date
        filtered_transactions = []
        for transaction in all_transactions:
            transaction_date_str = transaction.get('Timestamp', '')
            if transaction_date_str:
                try:
                    transaction_date = datetime.strptime(transaction_date_str.split(' ')[0], '%Y-%m-%d')
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                    if transaction_date >= start_date_obj:
                        filtered_transactions.append(transaction)
                except ValueError:
                    continue
        
        return filtered_transactions
    except Exception as e:
        print(f"Error fetching transactions: {e}")
        return []

def get_sales_summary_by_author(start_date=None):
    """Gets sales summary grouped by author with cash/cashless breakdown."""
    transactions = get_transactions_from_date(start_date)
    authors = get_authors()
    
    # Create author mapping
    author_map = {author.get('AuthorID'): author.get('Name', 'Неизвестный автор') for author in authors}
    
    # Group by author
    summary = {}
    for transaction in transactions:
        author_id = transaction.get('AuthorID')
        payment_method = transaction.get('Payment_Method', '').lower()
        amount = transaction.get('Amount', 0)
        
        if isinstance(amount, str):
            try:
                amount = float(amount)
            except ValueError:
                amount = 0
        
        author_name = author_map.get(author_id, f'Автор #{author_id}')
        
        if author_name not in summary:
            summary[author_name] = {
                'author_id': author_id,
                'cash': 0,
                'cashless': 0,
                'total': 0,
                'transactions': []
            }
        
        summary[author_name]['transactions'].append(transaction)
        summary[author_name]['total'] += amount
        
        if payment_method == 'cash':
            summary[author_name]['cash'] += amount
        elif payment_method == 'cashless':
            summary[author_name]['cashless'] += amount
    
    return summary

def get_author_transactions_detail(author_id, start_date=None):
    """Gets detailed transaction list for a specific author."""
    transactions = get_transactions_from_date(start_date)
    all_products = get_all_products()
    
    # Create product mapping
    product_map = {product.get('ProductID'): product for product in all_products}
    
    # Filter by author
    author_transactions = []
    for transaction in transactions:
        if transaction.get('AuthorID') == author_id:
            product_id = transaction.get('ProductID')
            product_info = product_map.get(product_id, {})
            
            transaction_detail = {
                'timestamp': transaction.get('Timestamp', ''),
                'product_title': product_info.get('Title', f'Продукт #{product_id}'),
                'amount': transaction.get('Amount', 0),
                'payment_method': transaction.get('Payment_Method', ''),
                'transaction_id': transaction.get('TransactionID', '')
            }
            author_transactions.append(transaction_detail)
    
    # Sort by timestamp (newest first)
    author_transactions.sort(key=lambda x: x['timestamp'], reverse=True)
    return author_transactions

# setup_worksheets() has been moved to local_admin.py (local-only file)
