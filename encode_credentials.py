#!/usr/bin/env python3
"""
Script to encode Google service account credentials as Base64 string for Heroku deployment.
This script reads your JSON credentials file and outputs a Base64-encoded string
that you can set as an environment variable on Heroku.
"""

import json
import base64
import os
from dotenv import load_dotenv

def encode_credentials():
    # Load environment variables to get the credentials file path
    load_dotenv()
    
    credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE', 'bookfaircashierbot-e76ed9e4c8e3.json')
    
    try:
        # Read the JSON file
        with open(credentials_file, 'r') as f:
            credentials_json = json.load(f)
        
        # Convert to JSON string
        credentials_str = json.dumps(credentials_json)
        
        # Encode to Base64
        credentials_b64 = base64.b64encode(credentials_str.encode('utf-8')).decode('utf-8')
        
        print("=" * 80)
        print("SUCCESS: Google Credentials Encoded")
        print("=" * 80)
        print()
        print("Copy the following Base64 string and set it as GOOGLE_CREDS_ENCODED")
        print("environment variable on Heroku:")
        print()
        print("-" * 80)
        print(credentials_b64)
        print("-" * 80)
        print()
        print("Instructions:")
        print("1. Copy the entire string above (without the dashes)")
        print("2. In Heroku dashboard, go to Settings > Config Vars")
        print("3. Add new config var:")
        print("   Key: GOOGLE_CREDS_ENCODED")
        print("   Value: [paste the string here]")
        print()
        print("WARNING: Keep this encoded string secure - it contains your service account key!")
        
        return credentials_b64
        
    except FileNotFoundError:
        print(f"ERROR: Could not find credentials file: {credentials_file}")
        print("Make sure the file exists in the current directory.")
        return None
    except json.JSONDecodeError:
        print(f"ERROR: Invalid JSON in file: {credentials_file}")
        return None
    except Exception as e:
        print(f"ERROR: Failed to encode credentials: {e}")
        return None

if __name__ == "__main__":
    encode_credentials()