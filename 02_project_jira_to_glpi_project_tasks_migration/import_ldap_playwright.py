import time
import getpass
from playwright.sync_api import sync_playwright
import config

# Configuration
GLPI_URL = config.GLPI_URL.replace("/api.php/v1", "")
LDAP_IMPORT_URL = f"{GLPI_URL}/front/ldap.import.php"
LOGIN_URL = f"{GLPI_URL}/front/login.php"

# BATCH_SIZE = 3: GLPI can't handle more than 3 users at a time, so do not modify BATCH_SIZE
# MAX_BATCHES = 1: set to 1 to debug, set to 1000 or similar for full run, depends on number of users
BATCH_SIZE = 3
MAX_BATCHES = 95

def run():
    print("GLPI LDAP Import Automation (Playwright)")
    print("----------------------------------------")
    print("Prerequisites:")
    print("1. pip install playwright")
    print("2. playwright install chromium")
    print("----------------------------------------")
    
    # Try to get credentials from config first
    username = getattr(config, 'GLPI_USERNAME', None)
    password = getattr(config, 'GLPI_PASSWORD', None)

    if not username:
        username = input("GLPI Username: ")
    else:
        print(f"Using GLPI Username from config: {username}")
        
    if not password:
        password = getpass.getpass("GLPI Password: ")
    else:
        print("Using GLPI Password from config.")
    
    with sync_playwright() as p:
        print("Launching browser...")
        # headless=False so you can see what's happening
        # no delay fast click
        browser = p.chromium.launch(headless=False)
        # Ignore SSL errors for internal domains
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        
        # 1. Login
        print(f"Navigating to {LOGIN_URL}...")
        try:
            # Increase timeout to 60s, wait for DOM content only (assets might be slow)
            page.goto(LOGIN_URL, timeout=60000, wait_until='domcontentloaded')
        except Exception as e:
            print(f"Navigation timed out/error ({e}), checking if login form is present...")

        if page.locator('input[name="login_name"]').is_visible():
            print("Login form detected.")
        else:
            print("Login form NOT detected. Waiting more...")
            page.wait_for_load_state('domcontentloaded', timeout=30000)

        page.fill('input[name="login_name"]', username)
        page.fill('input[name="login_password"]', password)
        page.click('button[name="submit"]') # Or input[type=submit]
        
        # Wait for login
        # Increase timeout and use domcontentloaded because networkidle is too strict
        try:
             page.wait_for_load_state('domcontentloaded', timeout=60000)
             # Wait for a logout link or dashboard element to confirm login
             page.wait_for_selector('a[href*="logout"]', timeout=30000)
        except Exception as e:
             print(f"Wait for login timed out: {e}. Checking if logged in...")

        if "login.php" in page.url and "error" in page.content():
            print("Login failed. Please check credentials.")
            return

        print("Login probably successful.")
        
        total_imported = 0
        # Loop through pages/batches
        batch_count = 0
        
        while True:
            if MAX_BATCHES > 0 and batch_count >= MAX_BATCHES:
                print(f"Debug Mode: Stopping before starting batch {batch_count+1} (Limit: {MAX_BATCHES}).")
                break
                
            batch_count += 1
            print(f"\n--- Starting Batch {batch_count} ---")
            # 2. Go to Import Page manually and click search
            # Navigating directly with params might cause session redirect issues
            
            print(f"Navigating to base import page...")
            
            # --- Retry logic for initial navigation ---
            max_nav_retries = 3
            nav_success = False
            for retry in range(max_nav_retries):
                try:
                    page.goto(LDAP_IMPORT_URL, timeout=60000, wait_until='domcontentloaded')
                    nav_success = True
                    break
                except Exception as e:
                    print(f"Navigation error (Attempt {retry+1}/{max_nav_retries}): {e}")
                    time.sleep(5)
            
            if not nav_success:
                print("Failed to navigate to import page after retries. Retrying batch...")
                time.sleep(10)
                continue

            # Verify we are on the correct page (or at least not an error page)
            # Simple approach: Check if we are on the form
            if "ldap.import.php" in str(page.url):
                 print("Import page confirmed. Looking for Search button...")
                 
                 # Try multiple search button locators
                 search_btn = page.locator('button[name="search"]') # Standard GLPI
                 if not search_btn.is_visible():
                     search_btn = page.locator('input[type="submit"][name="search"]')
                 if not search_btn.is_visible():
                     search_btn = page.locator('button[type="submit"]').filter(has_text="Search")
                 if not search_btn.is_visible():
                     search_btn = page.locator('button[type="submit"]').filter(has_text="Tìm kiếm") # Vietnamese
                 if not search_btn.is_visible():
                     search_btn = page.locator('.card-footer .btn-primary').first # GLPI 10 Common
                 # Fallback: Just the word "Search" anywhere
                 if not search_btn.is_visible():
                     search_btn = page.get_by_role("button", name="Search")

                 if search_btn.is_visible():
                     print("Search button found. Clicking...")
                     search_btn.click()
                     # Wait for results
                     try:
                        page.wait_for_load_state('domcontentloaded', timeout=60000)
                     except: 
                        pass
                 else:
                     print("CRITICAL: Search button NOT found! Is page fully loaded?")
            else:
                 print(f"Warning: Not on ldap.import.php (Current URL: {page.url}). Checking for server selection...")
                 pass
            
            # 3. Check for users
            # The checkbox name pattern is item[AuthLDAP][GUID]
            checkboxes = page.locator('input[name^="item[AuthLDAP]"]').all()
            count = len(checkboxes)
            print(f"Found {count} users on this page.")
            
            if count == 0:
                # Double check to ensure we didn't miss loading
                if "ldap.import.php" not in page.url:
                     print(f"Warning: Count is 0 but URL is strange ({page.url}). Might be an error page. Retrying batch...")
                     time.sleep(5)
                     continue
                
                print("No more users found to import. Process complete!")
                break
            
            # 4. Select Users (Limit to 3)
            # The checkbox name pattern is item[AuthLDAP][GUID]
            checkboxes = page.locator('input[name^="item[AuthLDAP]"]').all()
            count = len(checkboxes)
            print(f"Found {count} users on this page.")
            
            if count == 0:
                print("No more users found to import. Process complete!")
                break
            
            # Limit selection to BATCH_SIZE
            to_select = checkboxes[:BATCH_SIZE]
            print(f"Selecting {len(to_select)} users...")
            for cb in to_select:
                if not cb.is_checked():
                    cb.check()
            
            # 5. Perform Import Action
            # Click "Actions" button to reveal massive action
            print("Clicking 'Actions' button...")
            
            # Try multiple selectors for "Actions" button
            action_btn = page.locator('.massiveaction-button').first
            if not action_btn.is_visible():
               action_btn = page.get_by_role("button", name="Actions").first
            if not action_btn.is_visible():
               action_btn = page.locator('button[title="Actions"]').first
            
            if action_btn.is_visible():
                action_btn.click()
                
                # Wait for "Action" dropdown/modal to appear
                # It might be in a modal or inline dropdown
                try:
                    # Wait for modal or dropdown
                    page.wait_for_selector('.modal-body select[name="massiveaction"]', timeout=5000)
                    
                    print("Selecting 'Import' from dropdown...")
                    # Check for the massive action select
                    select_loc = page.locator('.modal-body select[name="massiveaction"]')
                    
                    if select_loc.is_visible():
                         # Value might be AuthLDAP:import or something else.
                         try:
                             select_loc.select_option(value='AuthLDAP:import')
                         except:
                             try:
                                 select_loc.select_option(label='Import')
                             except:
                                 # Try getting value of option containing "Import"
                                 pass
                    else:
                         print("Could not find 'massiveaction' dropdown!")

                    # Click "Post" or "Submit" button inside the modal/form
                    print("Submitting import...")
                    
                    # Wait for Post button (sometimes appears after selection)
                    post_btn = page.locator('button[name="massiveaction"][type="submit"]') # Standard GLPI
                    if not post_btn.is_visible():
                         # Try finding inside modal
                         post_btn = page.locator('.modal-footer button[type="submit"][name="massiveaction"]')
                    
                    if not post_btn.is_visible():
                         # Aggressive search: Any submit button in modal-content
                         print("Trying generic submit button in modal...")
                         post_btn = page.locator('.modal-content button[type="submit"]').first
                    
                    if not post_btn.is_visible():
                         post_btn = page.locator('.modal-content input[type="submit"]').first

                    if post_btn.is_visible():
                        print(f"Found Submit button: {post_btn.inner_text() if post_btn.count()>0 else 'Input'}. Clicking...")
                        try:
                            with page.expect_navigation(timeout=60000, wait_until='domcontentloaded'):
                                post_btn.click()
                            print("Submit successful, page reloaded.")
                        except Exception as e:
                            print(f"Navigation error after submit (likely redirect loop): {e}")
                            print("Continuing to next batch...")
                            # The loop will restart and go to LDAP_IMPORT_URL (HTTP)
                            continue
                    else:
                        # Fallback to specific selector if generic failed
                        print("Trying specific selector...")
                        post_btn = page.locator('button[name="massiveaction"][type="submit"]')
                        try:
                           with page.expect_navigation(timeout=60000, wait_until='domcontentloaded'):
                                post_btn.click()
                           print("Clicked Submit button.")
                        except Exception as e:
                            print(f"Could not submit or navigation error: {e}")
                            print("Continuing...")
                            continue

                except Exception as e:
                    print(f"Error interacting with Massive Action popup: {e}")
                    # Force reload on error
                    continue
            else:
                 print("Could not find 'Actions' button! Cannot proceed.")
                 break

            # 6. Wait for processing (Redundant if expect_navigation used, but kept for safety)
            # print("Waiting for import to complete...")
            
            total_imported += count
            print(f"Imported batch of {len(to_select)} users (Total processed: {total_imported}).")
            
            # Small pause to be safe
            time.sleep(2)
            
            # Loop continues, re-loading the page and searching again
            
        print("Done.")
        if input("Press Enter to close browser..."):
             pass

if __name__ == "__main__":
    run()
