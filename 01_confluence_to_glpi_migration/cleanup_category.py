import requests
import config
import re
from glpi_api import GlpiClient

jls_extract_var = config.DEFAULT_CATEGORY_TO_CLEANUP
def cleanup_category(category_name=jls_extract_var):

    print(f"--- Cleanup Script: Deleting items in '{category_name}' ---")

    # Init Client
    client = GlpiClient(
        url=config.GLPI_URL, 
        app_token=config.APP_TOKEN, 
        user_token=config.USER_TOKEN,
        verify_ssl=config.VERIFY_SSL
    )

    try:
        client.init_session()

        # 1. Get Root Category ID
        # find named category, delete everything inside.
        
        if not category_name:
             print("Error: Category name is empty. Accessing Root (0) directly is risky without explicit confirmation.")
             return

        root_id = client.get_category_id(category_name)

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
            # Find sub-categories
            endpoint = f"{client.url}/KnowbaseItemCategory"
            params = {
                "is_deleted": 0,
                "range": "0-100",
                "criteria[0][field]": "knowbaseitemcategories_id",
                "criteria[0][searchtype]": "equals",
                "criteria[0][value]": cat_id
            }
            try:
                resp = requests.get(endpoint, headers=client.headers, params=params, verify=client.verify_ssl)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    for child in data:
                        cleanup_recursive(child.get('id'), child.get('name'))
            except Exception as e:
                print(f"  Error scanning children of {cat_id}: {e}")

            # 2. Delete Items in current category
            items = client.get_knowbase_items(cat_id)
            if items:
                print(f"  Found {len(items)} items in '{cat_name}'. Deleting...")
                for item in items:
                    item_id = item.get('id')
                    
                    # Delete linked docs
                    full_item = client.get_item('KnowbaseItem', item_id)
                    if full_item:
                         content = full_item.get('answer', '')
                         doc_ids = re.findall(r'document\.send\.php\?docid=(\d+)', content)
                         for doc_id in set(doc_ids):
                             client.delete_document(doc_id)
                    
                    client.delete_knowbase_item(item_id)
            
            # 3. Delete the Category Itself
            if cat_id != root_id:
                 client.delete_category(cat_id)

        print("Starting Recursive Cleanup (Post-Order)...")
        cleanup_recursive(root_id, category_name)
        print("\nCleanup Complete.")

    finally:
        client.kill_session()

if __name__ == "__main__":
    cleanup_category()
