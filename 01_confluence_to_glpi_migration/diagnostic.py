import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Config
BASE_URL = "https://your-glpi-instance"
APP_TOKEN = "YOUR_APP_TOKEN"
USER_TOKEN = "YOUR_USER_TOKEN"

endpoints = [
    "/api.php/v2.1/initSession",
    "/api.php/v1/initSession",
    "/api.php/initSession",
    "/apirest.php/initSession"
]

headers = {
    "App-Token": APP_TOKEN,
    "Authorization": f"user_token {USER_TOKEN}",
    "Content-Type": "application/json"
}

print(f"Testing connection to {BASE_URL} with User-Token...")

for ep in endpoints:
    url = BASE_URL + ep
    print(f"\n--- Testing: {url} ---")
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
        
        try:
            json_resp = response.json()
            print(f"JSON Response: {json_resp}")
        except:
            preview = response.text[:200].replace('\n', ' ')
            print(f"Text Response: {preview}...")
            
    except Exception as e:
        print(f"Error: {e}")
