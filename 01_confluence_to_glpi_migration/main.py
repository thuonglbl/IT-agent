"""
Confluence to GLPI Knowledge Base Migration
Migrates Confluence HTML export to GLPI KB articles with category structure
"""
import os
import sys
import re


def build_confluence_url(file_path, export_dir, base_url):
    """
    Build original Confluence URL from a local export file path.

    Confluence export filename pattern: {TITLE}_{PAGE_ID}.html
    Confluence export folder structure:  {export_dir}/{SPACE_KEY}/{filename}.html

    URL built: {base_url}/spaces/{SPACE_KEY}/pages/{PAGE_ID}/{SLUG}
    where SLUG = filename-without-suffix with dashes replaced by '+'

    Args:
        file_path (str): Absolute path to the local .html file.
        export_dir (str): Root export directory (to derive the space key).
        base_url (str): Confluence base URL, e.g. 'https://confluence.example.com'.
                        If empty/None, URL construction is skipped.

    Returns:
        tuple: (page_id, url) where url is None if base_url is not provided,
               or (None, None) if page_id cannot be extracted from the filename.
    """
    filename = os.path.basename(file_path)

    # Extract page_id from trailing _<digits>.html
    match = re.search(r'_(\d+)\.html$', filename)
    if not match:
        return None, None
    page_id = match.group(1)

    if not base_url:
        return page_id, None

    # Space key: first folder component under export_dir
    rel_path = os.path.relpath(file_path, export_dir)
    parts = rel_path.replace('\\', '/').split('/')
    space_key = parts[0] if len(parts) > 1 else ''

    # Slug: filename without _{page_id}.html suffix, dashes replaced by '+'
    slug_raw = filename[:match.start()]
    slug = slug_raw.replace('-', '+')

    url = f"{base_url.rstrip('/')}/spaces/{space_key}/pages/{page_id}/{slug}"
    return page_id, url

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

    # Extract config values
    glpi_url = config.get('glpi', {}).get('url')
    app_token = config.get('glpi', {}).get('app_token')
    user_token = config.get('glpi', {}).get('user_token')
    verify_ssl = config.get('glpi', {}).get('verify_ssl', False)
    export_dir = config.get('confluence', {}).get('export_dir', config.get('EXPORT_DIR', ''))
    confluence_base_url = config.get('confluence', {}).get('base_url', '')
    debug_mode = config.get('migration', {}).get('debug', False)
    batch_size = config.get('migration', {}).get('batch_size', 50)

    log("=== Confluence to GLPI Knowledge Base Migration ===")
    if debug_mode:
        log(f"[DEBUG MODE] Will stop after 1 batch (batch_size={batch_size})")
    log("")

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

    # Load user caches for user linking
    log("Loading GLPI user cache...")
    glpi.load_user_cache(recursive=True)
    log(f"Loaded {len(glpi.user_cache)} users, {len(glpi.fullname_cache)} fullnames\n")

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

                    # Resolve user references to GLPI profile links
                    unresolved_mentions = parser.resolve_user_mentions(glpi.user_cache)
                    unresolved_metadata = parser.resolve_metadata_users(glpi.get_user_id_by_fullname)
                    for u in unresolved_mentions:
                        log(f"  - Unresolved @mention: {u}", "warning")
                    for u in unresolved_metadata:
                        log(f"  - Unresolved metadata user: {u}", "warning")

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

                    # Add Confluence source link
                    page_id, confluence_url = build_confluence_url(file_path, export_dir, confluence_base_url)
                    if confluence_url:
                        content += (
                            f"<br><hr>"
                            f"<p style='color: #888; font-size: 0.8em;'>"
                            f"Source: <a href='{confluence_url}' target='_blank'>View on Confluence</a>"
                            f" (Page ID {page_id})</p>"
                        )
                    elif page_id:
                        content += f"<br><hr><p style='color: #888; font-size: 0.8em;'>Reference: Confluence Page ID {page_id}</p>"

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

                    # Debug mode: stop after batch_size files
                    if debug_mode and processed_count >= batch_size:
                        log(f"\n[DEBUG] debug=true → Processed {processed_count} files (batch_size={batch_size}). Stopping.", "debug")
                        return

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
