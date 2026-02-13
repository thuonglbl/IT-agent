"""
Confluence to GLPI Knowledge Base Migration
Migrates Confluence HTML export to GLPI KB articles with category structure
"""
import os
import sys
import re

# Import from shared library
from common.clients.glpi_client import GlpiClient
from common.config.loader import load_config

# Import local modules
from parser import ConfluenceParser
from css_styles import CONFLUENCE_CSS


def main():
    """Main migration orchestrator."""

    # Load configuration
    try:
        config = load_config(validate=False)  # Skip validation for legacy Python config
    except FileNotFoundError:
        print("Error: Configuration file not found.")
        print("Please create config.py or config.yaml with your settings.")
        return
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return

    # Optional: Setup structured logging if logging config is present
    logger = None
    if config.get('logging', {}).get('console') or config.get('logging', {}).get('file'):
        try:
            from common.logging.logger import setup_logger
            logger = setup_logger("confluence_migration", config)
        except Exception as e:
            print(f"Warning: Could not initialize logger: {e}")

    # Helper function: Use logger if available, otherwise print
    def log(message, level="info"):
        if logger:
            getattr(logger, level)(message)
        else:
            print(message)

    log("=== Confluence to GLPI Knowledge Base Migration ===\n")

    # Extract config values
    glpi_url = config.get('glpi', {}).get('url')
    app_token = config.get('glpi', {}).get('app_token')
    user_token = config.get('glpi', {}).get('user_token')
    verify_ssl = config.get('glpi', {}).get('verify_ssl', False)
    export_dir = config.get('confluence', {}).get('export_dir', config.get('EXPORT_DIR', ''))

    # Validation
    if not glpi_url or not app_token:
        log("Error: Missing required GLPI configuration.", "error")
        log("Please update config with GLPI URL and tokens.", "error")
        return

    if not user_token:
        log("Warning: No user_token provided. Ensure username/password are set.", "warning")

    if not os.path.exists(export_dir):
        log(f"Error: Export directory not found at {export_dir}", "error")
        return

    # Initialize GLPI client
    glpi = GlpiClient(
        url=glpi_url,
        app_token=app_token,
        user_token=user_token,
        username=config.get('glpi', {}).get('username'),
        password=config.get('glpi', {}).get('password'),
        verify_ssl=verify_ssl
    )

    try:
        # Initialize session
        glpi.init_session()
        log("✓ GLPI session initialized\n")
    except Exception as e:
        log(f"Failed to initialize GLPI session: {e}", "error")
        log("Check credentials and URL.", "error")
        return

    # Statistics
    processed_count = 0
    error_count = 0

    try:
        # Walk through export directory
        log(f"Scanning directory: {export_dir}\n")

        for root, dirs, files in os.walk(export_dir):
            for filename in files:
                if not filename.endswith(".html"):
                    continue

                file_path = os.path.join(root, filename)

                # Optional: Skip navigation files
                # if filename == 'index.html': continue

                log(f"Processing: {filename}")

                try:
                    # Parse Confluence HTML
                    parser = ConfluenceParser(file_path)
                    parser.parse()

                    # Process images
                    for img_data in parser.images:
                        local_path = img_data['local_path']
                        img_tag = img_data['tag']

                        if os.path.exists(local_path):
                            log(f"  - Uploading image: {os.path.basename(local_path)}")
                            doc_id = glpi.upload_document(local_path)

                            if doc_id:
                                # Update image src to GLPI document URL
                                doc_url = f"/front/document.send.php?docid={doc_id}"
                                parser.update_image_src(img_tag, doc_url)
                            else:
                                log("    Failed to upload image.", "warning")
                        else:
                            log(f"    Warning: Image file not found at {local_path}", "warning")

                    # Build content
                    content = parser.get_content_html()

                    # Inject CSS styles
                    content = CONFLUENCE_CSS + "\n" + content

                    subject = parser.title

                    # Add metadata (author/history)
                    if parser.metadata_html:
                        content = parser.metadata_html + "<hr>" + content

                    # Add Confluence ID reference
                    match = re.search(r'_(\d+)\.html$', filename)
                    confluence_id = match.group(1) if match else None
                    if confluence_id:
                        content += f"<br><hr><p style='color: #888; font-size: 0.8em;'>Reference: Confluence Page ID {confluence_id}</p>"

                    # Resolve category path from breadcrumbs
                    category_id = 0

                    if parser.breadcrumbs:
                        log(f"  - Resolving Category Path: {' > '.join(parser.breadcrumbs)}")
                        category_id = glpi.ensure_category_path(parser.breadcrumbs)
                    else:
                        log("  - No breadcrumbs found. Item will be in Root (0).")

                    # Create KB item
                    kb_id = glpi.create_knowbase_item(subject, content, category_id)

                    if kb_id:
                        log(f"  ✓ Created KB Item ID: {kb_id}\n")
                        processed_count += 1
                    else:
                        log("  ✗ Failed to create KB item.\n", "error")
                        error_count += 1

                    # DEBUG: Stop after 1 file (uncomment to test)
                    # log("\n[DEBUG] Stopping after 1 file.", "debug")
                    # return

                except Exception as e:
                    log(f"  Error processing content: {e}\n", "error")
                    error_count += 1

    finally:
        glpi.kill_session()
        log(f"\n{'='*50}")
        log(f"Migration Complete!")
        log(f"  Processed: {processed_count}")
        log(f"  Errors:    {error_count}")
        log(f"{'='*50}")


if __name__ == "__main__":
    main()
