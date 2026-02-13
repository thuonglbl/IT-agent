"""
Unified GLPI REST API Client
Consolidates functionality from all 3 migration folders
Supports: Knowledge Base, Tickets, Projects, Documents, Caching
"""
import requests
import json
import os
import mimetypes
import base64


class GlpiClient:
    """
    Unified GLPI REST API v1 Client.

    Features:
    - Session management (User Token + Basic Auth fallback)
    - Multiple caches (users, groups, categories, locations)
    - Knowledge Base operations
    - Ticket management (Assistance)
    - Project & Task management
    - Document handling
    - Asset/Item search
    """

    def __init__(self, url, app_token, user_token=None, username=None, password=None, verify_ssl=False):
        """
        Initialize GLPI client.

        Args:
            url: GLPI API base URL (e.g., https://glpi.example.com/api.php/v1)
            app_token: Application token
            user_token: User token (optional, tried first)
            username: Username for Basic Auth fallback (optional)
            password: Password for Basic Auth fallback (optional)
            verify_ssl: Verify SSL certificates (default: False)
        """
        self.url = url.rstrip('/')
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

        # Caches
        self.user_cache = {}      # login_name (lowercase) -> user_id
        self.group_cache = {}     # name (lowercase) -> group_id
        self.category_cache = {}  # name (lowercase) -> category_id (ITIL)
        self.location_cache = {}  # name (lowercase) -> location_id

    # ===== Session Management =====

    def init_session(self):
        """
        Initialize GLPI session.
        Tries User Token first, then falls back to Basic Auth if provided.
        """
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
        """Kill the current GLPI session."""
        if not self.session_token:
            return
        endpoint = f"{self.url}/killSession"
        try:
            requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            print("Session killed.")
        except Exception as e:
            print(f"Error killing session: {e}")

    def change_active_profile(self, profile_id):
        """Switch the active profile for the session."""
        endpoint = f"{self.url}/changeActiveProfile"
        payload = {"profiles_id": profile_id}
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Failed to switch profile to {profile_id}: {e}")
            return False

    # ===== User Cache =====

    def load_user_cache(self, recursive=True):
        """
        Load ALL GLPI users into memory cache for O(1) lookups.

        Args:
            recursive: Include users from sub-entities (default: True)
        """
        print("Loading GLPI User Cache (Recursive)..." if recursive else "Loading GLPI User Cache...")
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
        """
        Get GLPI User ID by login name.
        Uses pre-loaded cache for O(1) lookup.

        Args:
            username: User login name

        Returns:
            int: User ID or None
        """
        if not username:
            return None
        return self.user_cache.get(username.lower())

    # ===== Group Cache =====

    def load_group_cache(self, recursive=True):
        """
        Load ALL GLPI groups into memory cache.

        Args:
            recursive: Include groups from sub-entities (default: True)
        """
        print("Loading GLPI Group Cache (Recursive)..." if recursive else "Loading GLPI Group Cache...")
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
        """
        Get GLPI Group ID by name.

        Args:
            group_name: Group name or completename

        Returns:
            int: Group ID or None
        """
        if not group_name:
            return None
        return self.group_cache.get(group_name.lower())

    # ===== Category Cache (ITIL Categories) =====

    def load_category_cache(self, recursive=True):
        """
        Load ALL GLPI ITIL Categories into memory cache.

        Args:
            recursive: Include categories from sub-entities (default: True)
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
        Get ITIL category ID by name. If not found, create it.

        Args:
            category_name: Category name

        Returns:
            int: Category ID or None
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

    def get_category_id_map(self):
        """
        Get all ITIL Categories as a dict.

        Returns:
            dict: {name_lower: id}
        """
        endpoint = f"{self.url}/ITILCategory"
        params = {"range": "0-1000"}
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            if response.ok:
                data = response.json()
                return {item['name'].lower(): item['id'] for item in data if 'name' in item}
        except Exception:
            pass
        return {}

    def create_category(self, name, parent_id=0):
        """
        Create a new ITIL Category.

        Args:
            name: Category name
            parent_id: Parent category ID (default: 0 = root)

        Returns:
            int: Category ID or None
        """
        endpoint = f"{self.url}/ITILCategory"
        payload = {
            "input": {
                "name": name,
                "itilcategories_id": parent_id
            }
        }
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json().get('id')
        except Exception as e:
            print(f"Failed to create ITIL category '{name}': {e}")
            return None

    # ===== Location Cache =====

    def load_location_cache(self):
        """Load ALL GLPI Locations into memory cache."""
        print("Loading GLPI Location Cache...")
        endpoint = f"{self.url}/search/Location"
        params = {
            "range": "0-10000",
            "forcedisplay[0]": "1",  # name
            "forcedisplay[1]": "2",  # id
            "forcedisplay[2]": "14", # completename (Location > SubLocation)
        }

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            response.raise_for_status()

            result = response.json()
            data = result.get('data', [])

            if data:
                for item in data:
                    name = str(item.get('1', '')).lower().strip()
                    completename = str(item.get('14', '')).lower().strip()
                    loc_id = item.get('2')

                    if name and loc_id:
                        self.location_cache[name] = loc_id
                    if completename and loc_id:
                        self.location_cache[completename] = loc_id

            print(f"-> Loaded {len(self.location_cache)} locations into cache.")

        except Exception as e:
            print(f"[ERROR] Failed to load location cache: {e}")

    def get_location_id(self, location_name):
        """
        Get GLPI Location ID by name.

        Args:
            location_name: Location name or completename

        Returns:
            int: Location ID or None
        """
        if not location_name:
            return None
        return self.location_cache.get(location_name.lower())

    # ===== Knowledge Base Operations =====

    def create_knowbase_item(self, subject, content, category_id=0):
        """
        Create a Knowledge Base entry.

        Args:
            subject: KB item title
            content: KB item content (HTML)
            category_id: KnowbaseItemCategory ID (default: 0 = root)

        Returns:
            int: KB item ID or None
        """
        endpoint = f"{self.url}/KnowbaseItem"
        payload = {
            "input": {
                "name": subject,
                "answer": content,
                "is_faq": 1,
                "knowbaseitemcategories_id": category_id,
            }
        }

        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            result = response.json()
            print(f"Created KB Item '{subject}': ID {result.get('id')}")
            return result.get('id')
        except Exception as e:
            print(f"Failed to create KB Item '{subject}': {e}")
            if hasattr(e, 'response') and e.response:
                print(e.response.text)
            return None

    def get_kb_category_id(self, name, parent_id=0):
        """
        Find Knowledge Base category ID by name and parent.

        Args:
            name: Category name
            parent_id: Parent category ID (default: 0 = root)

        Returns:
            int: Category ID or None
        """
        endpoint = f"{self.url}/KnowbaseItemCategory"
        params = {
            "is_deleted": 0,
            "searchText": name,
            "range": "0-100"
        }

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    for item in data:
                        if item.get("name") == name:
                            item_parent = item.get("knowbaseitemcategories_id", 0)
                            if int(item_parent) == int(parent_id):
                                return item.get("id")
        except Exception as e:
            print(f"Error searching KB category {name}: {e}")

        return None

    def create_kb_category(self, name, parent_id=0):
        """
        Create a new Knowledge Base category.

        Args:
            name: Category name
            parent_id: Parent category ID (default: 0 = root)

        Returns:
            int: Category ID or None
        """
        endpoint = f"{self.url}/KnowbaseItemCategory"
        payload = {
            "input": {
                "name": name,
                "knowbaseitemcategories_id": parent_id
            }
        }
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json().get('id')
        except Exception as e:
            print(f"Failed to create KB category {name}: {e}")
            return None

    def ensure_category_path(self, path_list, root_id=0):
        """
        Traverse KB category path, creating categories as needed.

        Args:
            path_list: List of category names (e.g., ['Parent', 'Child'])
            root_id: Starting parent ID (default: 0 = root)

        Returns:
            int: ID of the last category in the path
        """
        if not path_list:
            return root_id

        current_parent_id = root_id

        for name in path_list:
            name = name.strip()
            if not name:
                continue

            cat_id = self.get_kb_category_id(name, current_parent_id)
            if not cat_id:
                print(f"Creating KB Category: {name} (Parent: {current_parent_id})")
                cat_id = self.create_kb_category(name, current_parent_id)

            if cat_id:
                current_parent_id = cat_id
            else:
                print(f"Warning: Could not resolve KB category {name}. Using parent.")
                break

        return current_parent_id

    def get_knowbase_items(self, category_id=None):
        """
        Get list of KB items, optionally filtered by category.

        Args:
            category_id: Filter by category ID (optional)

        Returns:
            list: List of KB item dicts
        """
        endpoint = f"{self.url}/KnowbaseItem"
        params = {
            "is_deleted": 0,
            "range": "0-1000",
            "expand_dropdowns": "true"
        }

        if category_id:
            params['knowbaseitemcategories_id'] = category_id

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            response.raise_for_status()
            data = response.json()

            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get('data', [])

            # Strict filtering if category specified
            if category_id:
                filtered_items = []
                for item in items:
                    cat_val = item.get('knowbaseitemcategories_id')
                    if cat_val is None:
                        filtered_items.append(item)
                        continue
                    try:
                        if int(cat_val) == int(category_id):
                            filtered_items.append(item)
                    except ValueError:
                        pass
                return filtered_items

            return items

        except Exception as e:
            print(f"Error fetching KB items: {e}")
            return []

    def delete_knowbase_item(self, item_id):
        """
        Delete a KB item by ID.

        Args:
            item_id: KB item ID

        Returns:
            bool: True if successful
        """
        endpoint = f"{self.url}/KnowbaseItem/{item_id}"
        try:
            response = requests.delete(endpoint, headers=self.headers, params={"force_purge": "true"}, verify=self.verify_ssl)
            response.raise_for_status()
            print(f"Deleted KB Item ID: {item_id}")
            return True
        except Exception as e:
            print(f"Failed to delete KB item {item_id}: {e}")
            return False

    def delete_kb_category(self, cat_id):
        """
        Delete a KB Category by ID.

        Args:
            cat_id: Category ID

        Returns:
            bool: True if successful
        """
        endpoint = f"{self.url}/KnowbaseItemCategory/{cat_id}"
        try:
            response = requests.delete(endpoint, headers=self.headers, params={"force_purge": "true"}, verify=self.verify_ssl)
            response.raise_for_status()
            print(f"Deleted KB Category ID: {cat_id}")
            return True
        except Exception as e:
            print(f"Failed to delete KB category {cat_id}: {e}")
            return False

    # ===== Ticket Operations (Assistance) =====

    def get_ticket_statuses(self):
        """
        Get valid Ticket Statuses from GLPI.

        Returns:
            list: List of status dicts with 'id' and 'name'
        """
        # Standard GLPI Statuses (hardcoded)
        return [
            {"id": 1, "name": "New"},
            {"id": 10, "name": "Approval"},
            {"id": 2, "name": "Processing (Assigned)"},
            {"id": 3, "name": "Processing (Planned)"},
            {"id": 4, "name": "Pending"},
            {"id": 5, "name": "Solved"},
            {"id": 6, "name": "Closed"}
        ]

    def get_status_id_map(self):
        """
        Get Ticket Statuses as a dict for mapping.

        Returns:
            dict: {name_lower: id}
        """
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

        # Try to fetch from API
        endpoint = f"{self.url}/listSearchOptions/Ticket"
        try:
            response = requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            if response.ok:
                data = response.json()
                status_field = data.get('12', {})
                choices = status_field.get('k', {}) or status_field.get('choices', {})

                if choices:
                    api_map = {}
                    for k, v in choices.items():
                        api_map[str(v).lower()] = int(k)
                    print(f"Loaded {len(api_map)} statuses from GLPI API.")
                    return api_map
        except Exception as e:
            print(f"Failed to fetch statuses from API ({e}), using default.")

        return standard_statuses

    def get_type_id_map(self):
        """
        Get Ticket Types as a dict for mapping.

        Returns:
            dict: {name_lower: id}
        """
        standard_types = {
            "incident": 1,
            "request": 2,
            "demande": 2
        }

        # Try to fetch from API
        endpoint = f"{self.url}/listSearchOptions/Ticket"
        try:
            response = requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            if response.ok:
                data = response.json()
                type_field = data.get('14', {})
                choices = type_field.get('k', {}) or type_field.get('choices', {})

                if choices:
                    api_map = {}
                    for k, v in choices.items():
                        api_map[str(v).lower()] = int(k)
                    print(f"Loaded {len(api_map)} types from GLPI API.")
                    return api_map
        except Exception as e:
            print(f"Failed to fetch types from API ({e}), using default.")

        return standard_types

    def create_ticket(self, name, content, **kwargs):
        """
        Create a Ticket (Assistance).

        Args:
            name: Ticket title
            content: Ticket content (HTML)
            **kwargs: Additional ticket fields (status, urgency, date, etc.)

        Returns:
            int: Ticket ID or None
        """
        endpoint = f"{self.url}/Ticket"
        payload = {
            "input": {
                "name": name,
                "content": content,
                "status": 1,    # New
                "urgency": 3,   # Medium
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
        """
        Update an existing ticket.

        Args:
            ticket_id: Ticket ID
            **kwargs: Fields to update

        Returns:
            bool: True if successful
        """
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
        """
        Add a comment (Followup) to a ticket.

        Args:
            ticket_id: Ticket ID
            content: Comment content (HTML)
            users_id: Comment author user ID (optional)
            is_private: Private comment flag (default: 0)
            date: Comment date (optional)

        Returns:
            bool: True if successful
        """
        endpoint = f"{self.url}/ITILFollowup"
        payload = {
            "input": {
                "items_id": ticket_id,
                "itemtype": "Ticket",
                "content": content,
                "is_private": is_private
            }
        }
        if users_id:
            payload['input']['users_id'] = users_id
        if date:
            payload['input']['date'] = date

        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Failed to add followup to ticket {ticket_id}: {e}")
            return False

    def link_item_to_ticket(self, ticket_id, item_type, item_id):
        """
        Link an asset/item to a ticket.

        Args:
            ticket_id: Ticket ID
            item_type: Item type (e.g., 'BusinessService', 'Software')
            item_id: Item ID

        Returns:
            bool: True if successful
        """
        endpoint = f"{self.url}/Item_Ticket"
        payload = {
            "input": {
                "tickets_id": ticket_id,
                "itemtype": item_type,
                "items_id": item_id
            }
        }
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Failed to link {item_type} {item_id} to ticket {ticket_id}: {e}")
            return False

    # ===== Project Operations =====

    def create_project(self, name, content=""):
        """
        Create a Project.

        Args:
            name: Project name
            content: Project description (optional)

        Returns:
            int: Project ID or None
        """
        endpoint = f"{self.url}/Project"
        payload = {
            "input": {
                "name": name,
                "content": content,
                "priority": 3
            }
        }
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            result = response.json()
            print(f"Created Project '{name}': ID {result.get('id')}")
            return result.get('id')
        except Exception as e:
            print(f"Failed to create Project '{name}': {e}")
            if hasattr(e, 'response') and e.response:
                print(e.response.text)
            return None

    def get_project_id_by_name(self, name):
        """
        Find Project ID by name.

        Args:
            name: Project name

        Returns:
            int: Project ID or None
        """
        endpoint = f"{self.url}/Project"
        params = {
            "is_deleted": 0,
            "searchText": name,
            "range": "0-10"
        }
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    for item in data:
                        if item.get("name") == name:
                            return item.get("id")
        except Exception as e:
            print(f"Error searching project {name}: {e}")
        return None

    def get_project_states(self):
        """
        Fetch all available Project States.

        Returns:
            dict: {name_lower: id}
        """
        endpoint = f"{self.url}/ProjectState"
        try:
            params = {"range": "0-1000"}
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            response.raise_for_status()

            states = response.json()
            if not states:
                return {}

            state_map = {}
            for s in states:
                name = s.get('name')
                sid = s.get('id')
                if name and sid:
                    state_map[name.lower()] = sid
            return state_map

        except Exception as e:
            print(f"[ERROR] Failed to fetch Project States: {e}")
            return {}

    def get_project_task_types(self):
        """
        Fetch all available Project Task Types.

        Returns:
            dict: {name_lower: id}
        """
        endpoint = f"{self.url}/ProjectTaskType"
        try:
            params = {"range": "0-1000"}
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            response.raise_for_status()

            types = response.json()
            if not types:
                return {}

            type_map = {}
            for t in types:
                name = t.get('name')
                tid = t.get('id')
                if name and tid:
                    type_map[name.lower()] = tid
            return type_map

        except Exception as e:
            print(f"[ERROR] Failed to fetch Project Task Types: {e}")
            return {}

    def create_project_state(self, name, color, is_finished=0):
        """Create a Project State."""
        endpoint = f"{self.url}/ProjectState"
        payload = {
            "input": {
                "name": name,
                "color": color,
                "is_finished": is_finished
            }
        }
        try:
            requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
        except Exception as e:
            print(f"  [ERROR] Failed to create State '{name}': {e}")

    def create_project_task_type(self, name):
        """Create a Project Task Type."""
        endpoint = f"{self.url}/ProjectTaskType"
        payload = {"input": {"name": name}}
        try:
            requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
        except Exception as e:
            print(f"  [ERROR] Failed to create Type '{name}': {e}")

    def create_project_task(self, project_id, name, content, **kwargs):
        """
        Create a Task inside a Project.

        Args:
            project_id: Project ID
            name: Task name
            content: Task description
            **kwargs: Additional fields (users_id_tech, percent_done, etc.)

        Returns:
            int: Task ID or None
        """
        endpoint = f"{self.url}/ProjectTask"
        payload = {
            "input": {
                "projects_id": project_id,
                "name": name,
                "content": content,
                "percent_done": 0,
            }
        }

        if kwargs:
            payload['input'].update(kwargs)

        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            result = response.json()
            print(f"Created ProjectTask '{name}': ID {result.get('id')}")
            return result.get('id')
        except Exception as e:
            print(f"Failed to create ProjectTask '{name}': {e}")
            if hasattr(e, 'response') and e.response:
                print(e.response.text)
            return None

    def update_project_task(self, task_id, **kwargs):
        """
        Update a Project Task.

        Args:
            task_id: Task ID
            **kwargs: Fields to update

        Returns:
            bool: True if successful
        """
        endpoint = f"{self.url}/ProjectTask/{task_id}"
        payload = {"input": kwargs}
        try:
            response = requests.put(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Failed to update ProjectTask {task_id}: {e}")
            if hasattr(e, 'response') and e.response:
                print(e.response.text)
            return False

    def add_project_task_team_member(self, task_id, user_id):
        """
        Link a User to a Project Task (Task Team).

        Args:
            task_id: Task ID
            user_id: User ID

        Returns:
            bool: True if successful
        """
        endpoint = f"{self.url}/ProjectTaskTeam"
        payload = {
            "input": {
                "projecttasks_id": task_id,
                "itemtype": "User",
                "items_id": user_id
            }
        }
        try:
            requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            return True
        except Exception as e:
            print(f"  [ERROR] Failed to add User {user_id} to Task {task_id}: {e}")
            return False

    def create_note(self, itemtype, items_id, content, **kwargs):
        """
        Create a Note (Notepad) for an item.

        NOTE: GLPI 11.x has a bug where it returns 400/500 status codes
        even when the Note is created successfully. We ignore these errors.

        Args:
            itemtype: Item type (e.g., 'ProjectTask')
            items_id: Item ID
            content: Note content
            **kwargs: Additional fields

        Returns:
            bool: True (assumes success due to GLPI bug)
        """
        endpoint = f"{self.url}/Notepad"
        payload = {
            "input": {
                "itemtype": itemtype,
                "items_id": items_id,
                "content": content
            }
        }
        if kwargs:
            payload['input'].update(kwargs)

        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, verify=self.verify_ssl)
            if response.status_code >= 400:
                print(f"[WARN] Note API returned {response.status_code} (GLPI bug - Note likely created anyway)")
            return True
        except Exception as e:
            print(f"[ERROR] Network error creating Note: {e}")
            return False

    # ===== Document Operations =====

    def upload_document(self, file_path, name=None):
        """
        Upload a file to GLPI as a Document.

        Args:
            file_path: Path to file
            name: Document name (default: filename)

        Returns:
            int: Document ID or None
        """
        if not name:
            name = os.path.basename(file_path)

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
            if not response.ok:
                print(f"Upload failed. Status: {response.status_code}")
                print(f"Response: {response.text}")
            response.raise_for_status()
            result = response.json()
            print(f"Uploaded {name}: {result}")
            doc_id = result.get('id')
            return doc_id
        except Exception as e:
            print(f"Failed to upload {name}: {e}")
            if hasattr(e, 'response') and e.response:
                print(e.response.text)
            return None
        finally:
            files['filename[0]'][1].close()

    def link_document_to_ticket(self, ticket_id, doc_id):
        """
        Link an uploaded Document to a Ticket.

        Args:
            ticket_id: Ticket ID
            doc_id: Document ID

        Returns:
            bool: True if successful
        """
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
            return True
        except Exception as e:
            print(f"Failed to link doc {doc_id} to ticket {ticket_id}: {e}")
            return False

    def delete_document(self, doc_id):
        """
        Delete a Document by ID.

        Args:
            doc_id: Document ID

        Returns:
            bool: True if successful
        """
        endpoint = f"{self.url}/Document/{doc_id}"
        try:
            response = requests.delete(endpoint, headers=self.headers, params={"force_purge": "true"}, verify=self.verify_ssl)
            response.raise_for_status()
            print(f"Deleted Document ID: {doc_id}")
            return True
        except Exception as e:
            print(f"Failed to delete document {doc_id}: {e}")
            return False

    # ===== Asset/Item Search =====

    def get_item_id(self, item_type, item_name):
        """
        Search for an asset/item by name and type.

        Args:
            item_type: Item type (e.g., 'BusinessService', 'Software', 'Computer')
                       Note: 'Business_Service' is converted to 'BusinessService'
            item_name: Item name

        Returns:
            int: Item ID or None
        """
        if not item_type or not item_name:
            return None

        # Normalize item_type
        if item_type == 'Business_Service':
            item_type = 'BusinessService'

        endpoint = f"{self.url}/search/{item_type}"
        params = {
            "criteria[0][field]": "1",  # Name
            "criteria[0][searchtype]": "equals",
            "criteria[0][value]": item_name,
            "forcedisplay[0]": "1",     # Name
            "forcedisplay[1]": "2",     # ID
        }

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            if response.status_code != 200:
                return None

            result = response.json()
            data = result.get('data', [])

            for item in data:
                found_id = item.get('2')
                found_name = str(item.get('1', ''))
                if found_name.lower() == item_name.lower():
                    return found_id

            return None

        except Exception:
            return None

    def get_item(self, item_type, item_id):
        """
        Get a specific item by ID.

        Args:
            item_type: Item type (e.g., 'Ticket', 'KnowbaseItem')
            item_id: Item ID

        Returns:
            dict: Item data or None
        """
        endpoint = f"{self.url}/{item_type}/{item_id}"
        try:
            response = requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Failed to get {item_type} {item_id}: {e}")
            return None

    # ===== Utilities =====

    def delete_all_items(self, endpoint_suffix):
        """
        Generic delete all items from an endpoint.

        Args:
            endpoint_suffix: Endpoint suffix (e.g., 'ProjectState')
        """
        endpoint = f"{self.url}/{endpoint_suffix}"
        try:
            params = {"range": "0-1000"}
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            if response.status_code != 200:
                return

            items = response.json()
            if not items:
                return

            print(f"  > Deleting {len(items)} items from {endpoint_suffix}...")
            count = 0
            for item in items:
                try:
                    del_url = f"{endpoint}/{item['id']}"
                    requests.delete(del_url, headers=self.headers, params={"force_purge": "true"}, verify=self.verify_ssl)
                    count += 1
                except:
                    pass
            print(f"  > Deleted {count} items.")

        except Exception as e:
            print(f"  > Error clearing {endpoint_suffix}: {e}")
