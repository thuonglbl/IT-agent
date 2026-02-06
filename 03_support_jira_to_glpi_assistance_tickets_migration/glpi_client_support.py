import requests
import json
import os
import mimetypes
import time

class GlpiClient:
    def __init__(self, url, app_token, user_token=None, verify_ssl=False):
        self.url = url
        self.app_token = app_token
        self.user_token = user_token
        self.verify_ssl = verify_ssl
        self.session_token = None
        self.headers = {
            "App-Token": self.app_token,
            "Content-Type": "application/json"
        }
        # User cache: login_name (lowercase) -> user_id
        self.user_cache = {}

    def init_session(self):
        """Initialize session using User Token."""
        endpoint = f"{self.url}/initSession"
        headers = {
            "App-Token": self.app_token,
            "Content-Type": "application/json"
        }
        
        if self.user_token:
             headers["Authorization"] = f"user_token {self.user_token}"
             print("Attempting authentication with User-Token...")
        
        try:
            response = requests.get(endpoint, headers=headers, verify=self.verify_ssl)
            if not response.ok:
                print(f"Failed to init session. Status: {response.status_code}")
                print(f"Response Body: {response.text}")
            response.raise_for_status()
            data = response.json()
            self.session_token = data.get("session_token")
            self.headers["Session-Token"] = self.session_token
            print(f"Session initialized: {self.session_token}")
        except Exception as e:
            print(f"Failed to init session: {e}")
            raise

    def kill_session(self):
        if not self.session_token: return
        endpoint = f"{self.url}/killSession"
        try:
            requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            print("Session killed.")
        except: pass

    # --- User Cache ---
    def load_user_cache(self, recursive=True):
        """
        Load ALL GLPI users into memory cache.
        recursive=True ensures we get users from sub-entities.
        """
        print("Loading GLPI User Cache (Recursive)...")
        endpoint = f"{self.url}/search/User"
        params = {
            "range": "0-10000",
            "forcedisplay[0]": "1",  # login
            "forcedisplay[1]": "2",  # id
            "is_deleted": "0"        # Only active users
        }
        if recursive:
            params["is_recursive"] = "1"
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            response.raise_for_status()
            
            result = response.json()
            data = result.get('data', [])
            
            if data:
                for item in data:
                    login = str(item.get('1', '')).lower().strip()
                    user_id = item.get('2')
                    if login and user_id:
                        self.user_cache[login] = user_id
                        
            print(f"-> Loaded {len(self.user_cache)} users into cache.")
            
        except Exception as e:
            print(f"[ERROR] Failed to load user cache: {e}")

    def get_user_id_by_name(self, username):
        if not username: return None
        return self.user_cache.get(username.lower())

    # --- Ticket Management ---
    def create_ticket(self, name, content, **kwargs):
        """Create a standard Assistance Ticket."""
        endpoint = f"{self.url}/Ticket"
        payload = {
            "input": {
                "name": name,
                "content": content,
                # Default values
                "status": 1, # New
                "urgency": 3, # Medium
            }
        }
        # Merge optional fields
        if kwargs:
            payload['input'].update(kwargs)

        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            result = response.json()
            print(f"Created Ticket '{name}': ID {result.get('id')}")
            return result.get('id')
        except Exception as e:
            print(f"Failed to create Ticket '{name}': {e}")
            if hasattr(e, 'response') and e.response:
                print(e.response.text)
            return None

    def add_ticket_followup(self, ticket_id, content, users_id=None, is_private=0, date=None):
        """Add a comment (Followup) to a ticket."""
        endpoint = f"{self.url}/ITILFollowup"
        payload = {
            "input": {
                "items_id": ticket_id,
                "itemtype": "Ticket",
                "content": content,
                "is_private": is_private
            }
        }
        if users_id: payload['input']['users_id'] = users_id
        if date: payload['input']['date'] = date

        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Failed to add followup to ticket {ticket_id}: {e}")
            return False

    # --- Document Management (Attachments) ---
    def upload_document(self, file_path, name=None):
        """Upload a file to GLPI as a Document."""
        if not name: name = os.path.basename(file_path)
        endpoint = f"{self.url}/Document"
        
        manifest = {"input": {"name": name, "_filename": [name]}}
        files = {
            'uploadManifest': (None, json.dumps(manifest), 'application/json'),
            'filename[0]': (name, open(file_path, 'rb'), mimetypes.guess_type(file_path)[0] or 'application/octet-stream')
        }
        upload_headers = self.headers.copy()
        upload_headers.pop("Content-Type", None)

        try:
            response = requests.post(endpoint, headers=upload_headers, files=files, verify=self.verify_ssl)
            response.raise_for_status()
            result = response.json()
            doc_id = result.get('id')
            return doc_id
        except Exception as e:
            print(f"Failed to upload {name}: {e}")
            return None
        finally:
            files['filename[0]'][1].close()

    def link_document_to_ticket(self, ticket_id, doc_id):
        """Link an uploaded Document to a Ticket."""
        endpoint = f"{self.url}/Document_Item"
        payload = {
            "input": {
                "documents_id": doc_id,
                "itemtype": "Ticket",
                "items_id": ticket_id
            }
        }
        try:
            requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
        except Exception as e:
            print(f"Failed to link doc {doc_id} to ticket {ticket_id}: {e}")
