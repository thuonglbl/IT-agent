import requests
import re

# Import from shared library
from common.config.loader import load_config
from common.clients.glpi_client import GlpiClient

def cleanup_category():
    # 1. Load config from YAML
    cfg = load_config(validate=False)
    
    # 2. Extract data from Dictionary
    # Map with config.yaml
    category_name = cfg.get('cleanup', {}).get('default_category')
    
    # Map with common/config.yaml
    glpi_url = cfg.get('glpi', {}).get('url')
    app_token = cfg.get('glpi', {}).get('app_token')
    user_token = cfg.get('glpi', {}).get('user_token')
    verify_ssl = cfg.get('glpi', {}).get('verify_ssl', False)

    print(f"--- Cleanup Script: Deleting items in '{category_name}' ---")

    if not category_name:
         print("Error: Category name is empty. Check your config.yaml file.")
         return

    # 3. Init Client with new variables
    client = GlpiClient(
        url=glpi_url, 
        app_token=app_token, 
        user_token=user_token,
        verify_ssl=verify_ssl
    )

    try:
        client.init_session()

        # Switch to Root entity (ID=0) with recursive=True so all KB categories are visible
        client.change_active_entity(0, is_recursive=True)

        root_id = client.get_kb_category_id(category_name)

        if not root_id:
            print(f"Category '{category_name}' not found.")
            return

        print(f"Found Category '{category_name}' ID: {root_id}")
        
        visited_ids = set()

        def cleanup_recursive(cat_id, cat_name):
            if cat_id in visited_ids:
                return
            visited_ids.add(cat_id)
            
            print(f"\nProcessing Category: {cat_name} ({cat_id})")
            
            # 1. Post-Order: Process Children First
            endpoint = f"{client.url}/KnowbaseItemCategory"
            params = {
                "is_deleted": 0,
                "range": "0-1000",
                "is_recursive": 1
            }
            try:
                resp = requests.get(endpoint, headers=client.headers, params=params, verify=client.verify_ssl)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    # Filter children by parent = cat_id
                    children = [c for c in data if int(c.get('knowbaseitemcategories_id', 0)) == int(cat_id)]
                    for child in children:
                        cleanup_recursive(child.get('id'), child.get('name'))
            except Exception as e:
                print(f"  Error scanning children of {cat_id}: {e}")

            # 2. Delete Items in current category
            items = client.get_knowbase_items(cat_id)
            if items:
                print(f"  Found {len(items)} items in '{cat_name}'. Deleting...")
                for item in items:
                    item_id = item.get('id')
                    
                    full_item = client.get_item('KnowbaseItem', item_id)
                    if full_item:
                         content = full_item.get('answer', '')
                         doc_ids = re.findall(r'document\.send\.php\?docid=(\d+)', content)
                         for doc_id in set(doc_ids):
                             client.delete_document(doc_id)
                    
                    client.delete_knowbase_item(item_id)
            
            # 3. Delete the Category Itself
            if cat_id != root_id:
                 client.delete_kb_category(cat_id)

        print("Starting Recursive Cleanup (Post-Order)...")
        cleanup_recursive(root_id, category_name)
        print("\nCleanup Complete.")

    finally:
        client.kill_session()

if __name__ == "__main__":
    cleanup_category()