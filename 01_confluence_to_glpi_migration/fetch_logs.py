import requests
import re

import config

# Config from config.py
COOKIE_NAME = config.COOKIE_NAME
COOKIE_VALUE = config.COOKIE_VALUE

# Or better, just paste the RAW Cookie header string from your browser network tab for any request
# Example: "glpi_c23...=t0l7...; other_cookie=..."
RAW_COOKIE = f"{COOKIE_NAME}={COOKIE_VALUE}"

BASE_URL = config.GLPI_URL

# Log files to fetch
LOG_FILES = ["php-errors.log", "api.log", "access-errors.log", "event.log"]

def fetch_log(filename):
    print(f"Fetching {filename}...")
    list_url = f"{BASE_URL}/front/logs.php"
    
    headers = {
        "Cookie": RAW_COOKIE,
        "User-Agent": "your_user_agent"
    }

    try:
        # Use verify from config
        response = requests.get(list_url, headers=headers, verify=config.VERIFY_SSL)
        if resp.status_code != 200:
            print(f"Failed to access logs page. Status: {resp.status_code}")
            return

        if filename in resp.text:
            print(f"Found {filename} in page.")
            pass
        
    except Exception as e:
        print(f"Error: {e}")

pass
