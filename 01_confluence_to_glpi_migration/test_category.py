import config
from glpi_api import GlpiClient

def test_categories():
    client = GlpiClient(
        url=config.GLPI_URL, 
        app_token=config.APP_TOKEN, 
        user_token=config.USER_TOKEN,
        verify_ssl=config.VERIFY_SSL
    )
    
    try:
        client.init_session()
        
        print("Testing Category Hierarchy Creation...")
        
        # 1. Create Root
        root_name = "TEST_ROOT"
        root_id = client.ensure_category_path([root_name])
        print(f"Root '{root_name}' ID: {root_id}")
        
        # 2. Create Child
        child_name = "TEST_CHILD"
        # ensure_category_path handles the logic: Root -> Child
        full_id = client.ensure_category_path([root_name, child_name])
        print(f"Leaf '{child_name}' ID: {full_id}")
        
        # 3. Verify Parent of Child
        # Fetch Child details
        import requests
        endpoint = f"{client.url}/KnowbaseItemCategory/{full_id}"
        resp = requests.get(endpoint, headers=client.headers, verify=client.verify_ssl)
        if resp.status_code == 200:
            data = resp.json()
            parent = data.get('knowbaseitemcategories_id')
            print(f"Verification: Child {full_id} has Parent ID: {parent}")
            if int(parent) == int(root_id):
                print("-> SUCCESS: Hierarchy preserved.")
            else:
                print(f"-> FAILURE: Parent mismatch. Expected {root_id}, got {parent}")
        else:
            print("Failed to fetch child details.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.kill_session()

if __name__ == "__main__":
    test_categories()
