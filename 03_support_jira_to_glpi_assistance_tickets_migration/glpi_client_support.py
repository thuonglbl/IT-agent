import requests
import json
import os
import mimetypes
import time

class GlpiClient:
    def __init__(self, url, app_token, user_token=None, username=None, password=None, verify_ssl=False):
        self.url = url
        self.app_token = app_token
        self.user_token = user_token
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.session_token = None
        self.headers = {
            "App-Token": self.app_token,
            "Content-Type": "application/json"
        }
        # User cache: login_name (lowercase) -> user_id
        self.user_cache = {}
        # Group cache: name (lowercase) -> group_id
        self.group_cache = {}
        # Category cache: name (lowercase) -> category_id
        self.category_cache = {}

    def init_session(self):
        """Initialize session: Try User Token first, then Basic Auth."""
        endpoint = f"{self.url}/initSession"
        base_headers = {
            "App-Token": self.app_token,
            "Content-Type": "application/json"
        }
        
        # 1. Try User Token
        if self.user_token:
            print("Attempting authentication with User-Token...")
            headers = base_headers.copy()
            headers["Authorization"] = f"user_token {self.user_token}"
            
            try:
                response = requests.get(endpoint, headers=headers, verify=self.verify_ssl)
                if response.ok:
                    data = response.json()
                    self.session_token = data.get("session_token")
                    self.headers["Session-Token"] = self.session_token
                    print(f"Session initialized (User-Token): {self.session_token}")
                    return
                else:
                    print(f"User-Token failed (Status: {response.status_code}).")
            except Exception as e:
                print(f"User-Token connection error: {e}")
        
        # 2. Fallback to Basic Auth
        if self.username and self.password:
            print(f"Attempting fallback to Basic Auth (User: {self.username})...")
            import base64
            auth_str = f"{self.username}:{self.password}"
            b64_auth = base64.b64encode(auth_str.encode()).decode()
            
            headers = base_headers.copy()
            headers["Authorization"] = f"Basic {b64_auth}"
            
            try:
                response = requests.get(endpoint, headers=headers, verify=self.verify_ssl)
                if not response.ok:
                    print(f"Basic Auth failed. Status: {response.status_code}")
                    print(f"Response Body: {response.text}")
                response.raise_for_status()
                
                data = response.json()
                self.session_token = data.get("session_token")
                self.headers["Session-Token"] = self.session_token
                print(f"Session initialized (Basic Auth): {self.session_token}")
                return
            except Exception as e:
                print(f"Basic Auth connection error: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Response Body: {e.response.text}")
                raise
        
        # If here, failure
        print("Error: Could not initialize session with any credentials.")
        raise Exception("Authentication Failed")

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

    # --- Group Cache ---
    def load_group_cache(self, recursive=True):
        """
        Load ALL GLPI groups into memory cache.
        recursive=True ensures we get groups from sub-entities.
        """
        print("Loading GLPI Group Cache (Recursive)...")
        endpoint = f"{self.url}/search/Group"
        params = {
            "range": "0-10000",
            "forcedisplay[0]": "1",  # name
            "forcedisplay[1]": "2",  # id
            "forcedisplay[2]": "14", # completename (for hierarchical match)
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
                    name = str(item.get('1', '')).lower().strip()
                    # Also map completename if available for precise matching
                    completename = str(item.get('14', '')).lower().strip()
                    group_id = item.get('2')
                    
                    if name and group_id:
                        self.group_cache[name] = group_id
                    if completename and group_id:
                        self.group_cache[completename] = group_id
                        
            print(f"-> Loaded {len(self.group_cache)} groups into cache.")
            
        except Exception as e:
            print(f"[ERROR] Failed to load group cache: {e}")

    def get_group_id_by_name(self, group_name):
        if not group_name: return None
        return self.group_cache.get(group_name.lower())

    # --- Category Cache ---
    def load_category_cache(self, recursive=True):
        """
        Load ALL GLPI ITIL Categories into memory cache.
        """
        print("Loading GLPI ITIL Category Cache...")
        endpoint = f"{self.url}/search/ITILCategory"
        params = {
            "range": "0-10000",
            "forcedisplay[0]": "1",  # name
            "forcedisplay[1]": "2",  # id
            "forcedisplay[2]": "14", # completename
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
                    name = str(item.get('1', '')).lower().strip()
                    completename = str(item.get('14', '')).lower().strip()
                    cat_id = item.get('2')
                    
                    if name and cat_id:
                        self.category_cache[name] = cat_id
                    if completename and cat_id:
                        self.category_cache[completename] = cat_id
                        
            print(f"-> Loaded {len(self.category_cache)} categories into cache.")
            
        except Exception as e:
            print(f"[ERROR] Failed to load category cache: {e}")

    def get_or_create_category(self, category_name):
        """
        Get a category ID by name. If not found, create it.
        Created categories: is_incident=1, is_request=1, is_problem=0, is_change=0.
        Returns category_id or None.
        """
        if not category_name:
            return None
        
        # Check cache first
        cat_id = self.category_cache.get(category_name.lower())
        if cat_id:
            return cat_id
        
        # Create new category
        print(f"  [NEW] Creating ITIL Category '{category_name}'...")
        endpoint = f"{self.url}/ITILCategory"
        payload = {
            "input": {
                "name": category_name,
                "is_incident": 1,
                "is_request": 1,
                "is_problem": 0,
                "is_change": 0,
            }
        }
        
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            result = response.json()
            new_id = result.get('id')
            if new_id:
                self.category_cache[category_name.lower()] = new_id
                print(f"  [NEW] Created Category '{category_name}' -> GLPI ID {new_id}")
                return new_id
            else:
                print(f"  [ERROR] Category creation returned no ID: {result}")
                return None
        except Exception as e:
            print(f"  [ERROR] Failed to create category '{category_name}': {e}")
            if hasattr(e, 'response') and e.response:
                print(f"  Response: {e.response.text}")
            return None

    # --- Ticket Management ---
    def get_status_id_map(self):
        """
        Get valid Ticket Statuses from GLPI.
        Returns dict: {name_lower: id}
        Note: GLPI Ticket Statuses are usually fixed (1-6).
        """
        # Standard GLPI Statuses (Hardcoded fallback if API fails)
        # 1: New, 10:Approval, 2: Processing (Assigned), 3: Processing (Planned), 4: Pending, 5: Solved, 6: Closed
        standard_statuses = {
            "new": 1,
            "approval": 10,
            "processing (assigned)": 2,
            "assigned": 2,
            "processing (planned)": 3,
            "planned": 3,
            "pending": 4,
            "solved": 5,
            "closed": 6
        }
        
        # Try to fetch from API if possible (listSearchOptions)
        endpoint = f"{self.url}/listSearchOptions/Ticket"
        try:
            response = requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            if response.ok:
                data = response.json()
                # Field 12 is Status
                status_field = data.get('12', {})
                choices = status_field.get('k', {}) or status_field.get('choices', {})
                
                if choices:
                    api_map = {}
                    for k, v in choices.items():
                        # k is ID, v is Name
                        api_map[str(v).lower()] = int(k)
                    print(f"Loaded {len(api_map)} statuses from GLPI API.")
                    return api_map
        except Exception as e:
            print(f"Failed to fetch statuses from API ({e}), using default.")
            
        return standard_statuses

    def get_type_id_map(self):
        """
        Get valid Ticket Types from GLPI.
        Returns dict: {name_lower: id}
        Standard: 1 = Incident, 2 = Request
        """
        standard_types = {
            "incident": 1,
            "request": 2,
            "demande": 2
        }
        
        # Try to fetch from API if possible
        endpoint = f"{self.url}/listSearchOptions/Ticket"
        try:
            response = requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            if response.ok:
                data = response.json()
                # Field 14 is Type
                type_field = data.get('14', {})
                choices = type_field.get('k', {}) or type_field.get('choices', {})
                
                if choices:
                    api_map = {}
                    for k, v in choices.items():
                        # k is ID, v is Name
                        api_map[str(v).lower()] = int(k)
                    print(f"Loaded {len(api_map)} types from GLPI API.")
                    return api_map
        except Exception as e:
            print(f"Failed to fetch types from API ({e}), using default.")
            
        return standard_types

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

    def update_ticket(self, ticket_id, **kwargs):
        """Update an existing ticket."""
        endpoint = f"{self.url}/Ticket/{ticket_id}"
        payload = {"input": kwargs}
        try:
            response = requests.put(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            print(f"  -> Updated Ticket {ticket_id}")
            return True
        except Exception as e:
            print(f"Failed to update Ticket {ticket_id}: {e}")
            return False

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

    # --- Category Management ---
    def get_category_id_map(self):
        """
        Get all ITIL Categories.
        Returns dict: {completename_lower: id}
        """
        endpoint = f"{self.url}/ITILCategory"
        params = {"range": "0-1000"}
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            if response.ok:
                data = response.json()
                # Map 'name' or 'completename' to ID
                # Using lower case for case-insensitive matching
                return {item['name'].lower(): item['id'] for item in data}
        except Exception:
            pass
        return {}

    def create_category(self, name):
        """Create a new ITIL Category."""
        endpoint = f"{self.url}/ITILCategory"
        payload = {"input": {"name": name}}
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json().get('id')
        except Exception as e:
            print(f"Failed to create category '{name}': {e}")
            return None

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
