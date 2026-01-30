import config
from glpi_api import GlpiClient

def main():
    glpi = GlpiClient(config.GLPI_URL, config.GLPI_APP_TOKEN, config.GLPI_USER_TOKEN, verify_ssl=config.GLPI_VERIFY_SSL)
    glpi.init_session()
    
    task_id = 128 # The one the user confirmed exists
    
    print(f"--- Debugging Notes for ProjectTask {task_id} ---")
    
    # Test 3: Get Item Details to check links/types
    print("\nAttempt 3: Get ProjectTask Details")
    item = glpi.get_item("ProjectTask", task_id)
    if item:
        print(f"Item ID: {item.get('id')}")
        links = item.get('links', [])
        # Print rels
        rels = [x.get('rel') for x in links]
        print(f"Relations count: {len(rels)}")
        for r in rels:
            print(f" - {r}")
        
        # Check specific
        if 'Note' in rels:
            print("FOUND Relation: Note (Notepad)")
        if 'ITILFollowup' in rels:
            print("FOUND Relation: ITILFollowup")
            
    else:
        print("Failed to get item.")

    glpi.kill_session()

if __name__ == "__main__":
    main()
