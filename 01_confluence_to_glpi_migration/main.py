import os
import sys
import config
from glpi_api import GlpiClient
from parser import ConfluenceParser
from css_styles import CONFLUENCE_CSS

def main():
    # 1. Verification
    if config.APP_TOKEN == "YOUR_APP_TOKEN" or config.USER_TOKEN == "YOUR_USER_TOKEN":
        print("Error: Please update config.py with your GLPI App Token and User Token.")
        return

    if not os.path.exists(config.EXPORT_DIR):
        print(f"Error: Export directory not found at {config.EXPORT_DIR}")
        return

    # 2. Init API
    client = GlpiClient(
        url=config.GLPI_URL, 
        app_token=config.APP_TOKEN, 
        user_token=config.USER_TOKEN,
        verify_ssl=config.VERIFY_SSL
    )
    try:
        client.init_session()
    except Exception:
        print("Failed to initialize GLPI session. Check credentials and URL.")
        return

    processed_count = 0
    error_count = 0

    try:
        # 3. Walk directory
        for root, dirs, files in os.walk(config.EXPORT_DIR):
            for filename in files:
                if filename.endswith(".html"):
                    file_path = os.path.join(root, filename)
                    
                    # Optional: Skip navigation files
                    # if filename == 'index.html': continue 

                    print(f"\nProcessing: {filename}")
                    
                    try:
                        parser = ConfluenceParser(file_path)
                        parser.parse()
                        
                        # Handle Images
                        for img_data in parser.images:
                            local_path = img_data['local_path']
                            img_tag = img_data['tag']
                            
                            if os.path.exists(local_path):
                                print(f"  - Uploading image: {os.path.basename(local_path)}")
                                doc_id, doc_url = client.upload_document(local_path)
                                
                                if doc_url:
                                    parser.update_image_src(img_tag, doc_url)
                                else:
                                    print("    Failed to upload image.")
                            else:
                                print(f"    Warning: Image file not found at {local_path}")
                        
                        # Create KB Item
                        content = parser.get_content_html()
                        # Inject CSS Styles
                        content = CONFLUENCE_CSS + "\n" + content
                        
                        subject = parser.title
                        
                        # 1. Add Metadata (Author/History)
                        if parser.metadata_html:
                            content = parser.metadata_html + "<hr>" + content
                            
                        # 2. Add Confluence ID reference
                        import re
                        match = re.search(r'_(\d+)\.html$', filename)
                        confluence_id = match.group(1) if match else None
                        if confluence_id:
                            # Add visible reference at bottom
                            content += f"<br><hr><p style='color: #888; font-size: 0.8em;'>Reference: Confluence Page ID {confluence_id}</p>"
                        
                        # 3. Handle Categories (Breadcrumbs)
                        category_id = 0
                        
                        if parser.breadcrumbs:
                            print(f"  - Resolving Category Path: {' > '.join(parser.breadcrumbs)}")
                            category_id = client.ensure_category_path(parser.breadcrumbs)
                        else:
                            print("  - No breadcrumbs found. Item will be in Root (0).")
                            category_id = 0

                        kb_id = client.create_knowbase_item(subject, content, category_id)
                        if kb_id:
                            print(f"  -> Success! KB Item ID: {kb_id}")
                            processed_count += 1
                        else:
                            print("  -> Failed to create KB item.")
                            error_count += 1
                        
                        # DEBUG: Stop after 1 file (Uncomment to test)
                        # print("\n[DEBUG] Stopping after 1 file.")
                        # return
                        
                    except Exception as e:
                        print(f"  Error processing content: {e}")
                        error_count += 1
    
    finally:
        client.kill_session()
        print(f"\nMigration finished. Processed: {processed_count}, Errors: {error_count}")

if __name__ == "__main__":
    main()
