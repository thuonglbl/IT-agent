import requests
import json
import os
import mimetypes

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
        else:
            print("Error: No User Token provided.")
            return

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
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response Body: {e.response.text}")
            raise

    def kill_session(self):
        """Kill the current session."""
        if not self.session_token:
            return
        endpoint = f"{self.url}/killSession"
        try:
            requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            print("Session killed.")
        except Exception as e:
            print(f"Error killing session: {e}")

    def upload_document(self, file_path, name=None):
        """
        Upload a file to GLPI as a Document.
        Returns the Document ID and the Download URL if possible.
        """
        if not name:
            name = os.path.basename(file_path)

        endpoint = f"{self.url}/Document"
        
        # Prepare the manifest
        # Adjust entities_id if needed, default 0 (Root)
        manifest = {
            "input": {
                "name": name,
                "_filename": [name]
            }
        }

        files = {
            'uploadManifest': (None, json.dumps(manifest), 'application/json'),
            'filename[0]': (name, open(file_path, 'rb'), mimetypes.guess_type(file_path)[0] or 'application/octet-stream')
        }

        # remove Content-Type header for multipart upload to let requests set boundary
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
            
            # Extract ID
            doc_id = result.get('id')
            
            # Construct a usage URL. 
            # In GLPI KB, images are often referenced via /front/document.send.php?docid=ID
            # Or /front/document.send.php?file=_pictures/filename.png (but secure access requires docid)
            doc_url = f"/front/document.send.php?docid={doc_id}"
            
            return doc_id, doc_url
        except Exception as e:
            print(f"Failed to upload {name}: {e}")
            if hasattr(e, 'response') and e.response:
                print(e.response.text)
            return None, None
        finally:
            files['filename[0]'][1].close()

    def create_knowbase_item(self, subject, content, category_id=0):
        """Create a Knowledge Base entry."""
        endpoint = f"{self.url}/KnowbaseItem"
        
        payload = {
            "input": {
                "name": subject,
                "answer": content,
                "is_faq": 1, # Add to FAQ?
                "knowbaseitemcategories_id": category_id,
                # "users_id": ... # Optional: set author
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

    def get_category_id(self, name, parent_id=0):
        """Find category ID by name and parent."""
        # Use simpler List endpoint with searchText, then filter manually.
        endpoint = f"{self.url}/KnowbaseItemCategory"
        params = {
            "is_deleted": 0,
            "searchText": name,
            "range": "0-100" # Get enough candidates
        }
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            if response.status_code == 200:
                data = response.json()
                # data should be list of dicts
                if isinstance(data, list):
                    for item in data:
                        # Check strict name match
                        if item.get("name") == name:
                            # Check parent match
                            # Parent ID might be integer or string
                            item_parent = item.get("knowbaseitemcategories_id", 0)
                            if int(item_parent) == int(parent_id):
                                return item.get("id")
        except Exception as e:
            print(f"Error searching category {name}: {e}")
            
        return None

    def create_category(self, name, parent_id=0):
        """Create a new category."""
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
            print(f"Failed to create category {name}: {e}")
            return None
            
    def get_knowbase_items(self, category_id=None):
        """Get list of KB items, optionally filtered by category."""
        # Using List endpoint to fetch items and filter strict in Python to be safe.
        endpoint = f"{self.url}/KnowbaseItem"
        params = {
            "is_deleted": 0,
            "range": "0-1000", # Fetch up to 1000 items
            "expand_dropdowns": "true" # Request expanded fields to get category
        }
        
        # Try simple filter supported by GLPI community version
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
            
            # DEBUG
            # print(f"[DEBUG] get_knowbase_items fetched {len(items)} items (Total in range).")
            # if items:
            #    print(f"[DEBUG] First item keys: {list(items[0].keys())}")
            #    print(f"[DEBUG] First item knowbaseitemcategories_id: {items[0].get('knowbaseitemcategories_id')}")

            # STRICT FILTERING IN PYTHON
            if category_id:
                filtered_items = []
                # print(f"  Filtering {len(items)} candidates for Category {category_id}...", end="", flush=True)
                
                for i, item in enumerate(items):
                    cat_val = item.get('knowbaseitemcategories_id')
                    
                    # to avoid infinite loop
                    if cat_val is None:
                         filtered_items.append(item)
                         continue

                    if cat_val is not None:
                         # Handle string/int types
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
        """Delete a KB item by ID."""
        endpoint = f"{self.url}/KnowbaseItem/{item_id}"
        try:
            # force_purge=true skips the Trash and deletes permanently
            response = requests.delete(endpoint, headers=self.headers, params={"force_purge": "true"}, verify=self.verify_ssl)
            response.raise_for_status()
            print(f"Deleted KB Item ID: {item_id}")
            return True
        except Exception as e:
            print(f"Failed to delete item {item_id}: {e}")
            return False

    def delete_category(self, cat_id):
        """Delete a KB Category by ID."""
        endpoint = f"{self.url}/KnowbaseItemCategory/{cat_id}"
        try:
            response = requests.delete(endpoint, headers=self.headers, params={"force_purge": "true"}, verify=self.verify_ssl)
            response.raise_for_status()
            print(f"Deleted Category ID: {cat_id}")
            return True
        except Exception as e:
            print(f"Failed to delete category {cat_id}: {e}")
            return False

    def get_item(self, item_type, item_id):
        """Get a specific item by ID."""
        endpoint = f"{self.url}/{item_type}/{item_id}"
        try:
            response = requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Failed to get {item_type} {item_id}: {e}")
            return None

    def delete_document(self, doc_id):
        """Delete a Document by ID."""
        endpoint = f"{self.url}/Document/{doc_id}"
        try:
            # force_purge=true for permanently delete, false to stay on Trash
            response = requests.delete(endpoint, headers=self.headers, params={"force_purge": "true"}, verify=self.verify_ssl)
            response.raise_for_status()
            print(f"Deleted Document ID: {doc_id}")
            return True
        except Exception as e:
            print(f"Failed to delete document {doc_id}: {e}")
            return False

    def ensure_category_path(self, path_list, root_id=0):
        """
        Traverse the path creating categories.
        path_list: ['Parent', 'Child']
        root_id: ID of the parent category to start from (default 0).
        Returns the ID of the last category.
        """
        if not path_list:
            return root_id
            
        current_parent_id = root_id 
        
        for name in path_list:
            # Check if likely root ('Home' mentioned in breadcrumbs)
            # GLPI Root is 0.            
            # Clean name
            name = name.strip()
            if not name: continue
            
            cat_id = self.get_category_id(name, current_parent_id)
            if not cat_id:
                print(f"Creating Category: {name} (Parent: {current_parent_id})")
                cat_id = self.create_category(name, current_parent_id)
            
            if cat_id:
                current_parent_id = cat_id
            else:
                print(f"Warning: Could not resolve category {name}. Using parent.")
                break
                
        return current_parent_id

if __name__ == "__main__":
    # Test stub
    pass
