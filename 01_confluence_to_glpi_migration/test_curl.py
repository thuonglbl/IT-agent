import requests
import yaml
import os
import sys

print("Testing GLPI API Integration (Python requests)...")
print("-" * 50)

# 1. Load Configuration
current_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(current_dir, '../common', 'config.yaml')

try:
    with open(config_path, 'r', encoding='utf-8') as file:
        config_data = yaml.safe_load(file)
    glpi_conf = config_data['glpi']
    glpi_url = glpi_conf['url'].rstrip('/')
    app_token = glpi_conf['app_token']
    user_token = glpi_conf.get('user_token', '')
    verify_ssl = glpi_conf.get('verify_ssl', False)
    
    # Handle SSL mapping
    if str(verify_ssl).lower() == 'false':
        verify_ssl = False
    elif isinstance(verify_ssl, str) and str(verify_ssl).lower() != 'true':
        project_root = os.path.join(current_dir, '..')
        verify_ssl = os.path.abspath(os.path.join(project_root, verify_ssl))

except Exception as e:
    print(f"Error loading config: {e}")
    sys.exit(1)

if not user_token:
    print("Error: user_token is required in config.yaml for this script.")
    sys.exit(1)

# Global Headers for API
headers = {
    'App-Token': app_token,
    'Content-Type': 'application/json'
}

# ==========================================
# FUNCTION 1: Init Session
# ==========================================
def init_session():
    auth_headers = headers.copy()
    auth_headers['Authorization'] = f"user_token {user_token}"
    
    response = requests.get(f"{glpi_url}/initSession", headers=auth_headers, verify=verify_ssl)
    
    if response.status_code == 200:
        session_token = response.json().get('session_token')
        print(f"[+] Session Initialized: {session_token}")
        return session_token
    else:
        print(f"[-] Session Failed: {response.status_code} - {response.text}")
        sys.exit(1)

# ==========================================
# FUNCTION 2: Find User by Email Field
# ==========================================
def get_user_by_email(session_token, email):
    search_headers = headers.copy()
    search_headers['Session-Token'] = session_token
    
    params = {
        'criteria[0][field]': '5',
        'criteria[0][searchtype]': 'contains', 
        'criteria[0][value]': email,
        'forcedisplay[0]': '1', # Force display Login
        'forcedisplay[1]': '5', # Force display Email
        'forcedisplay[2]': '2'  # Force display ID (Field 2)
    }
    
    print(f"[*] Searching for user with email: {email}...")
    response = requests.get(f"{glpi_url}/search/User", headers=search_headers, params=params, verify=verify_ssl)
    
    if response.status_code == 200:
        data = response.json()
        total_count = data.get('totalcount', 0)
        
        if total_count == 0:
            print(f"[-] User mapping failed: No GLPI user found with email '{email}'.")
            return None
            
        user_data = data.get('data', [])[0]
        user_id = user_data.get('2')    # Get ID from field 2 instead of 'id'
        user_login = user_data.get('1') 
        
        print(f"[+] User Found! GLPI ID: {user_id} | Login: {user_login} | Email: {email}")
        return user_id
    else:
        print(f"[-] Search API Error: {response.status_code} - {response.text}")
        return None

# ==========================================
# EXECUTION FLOW
# ==========================================
if __name__ == "__main__":
    # 1. Get Session
    session_token = init_session()
    
    # 2. Test Mapping with target email
    # Replace this email with the actual email of the user you want to test or the Jira user you need to map
    target_email = glpi_conf.get('email', '') 
    
    glpi_user_id = get_user_by_email(session_token, target_email)
    
    print("-" * 50)
    if glpi_user_id:
        print("MAPPING SUCCESS: You can now use this ID to assign (assign) to a Ticket.")
    
    # Always kill session to free up GLPI server resources
    requests.get(f"{glpi_url}/killSession", headers={'Session-Token': session_token, 'App-Token': app_token}, verify=verify_ssl)