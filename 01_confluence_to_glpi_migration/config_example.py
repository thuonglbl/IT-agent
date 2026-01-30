# GLPI Configuration
GLPI_URL = "https://your-glpi-instance/api.php/v1"
APP_TOKEN = "YOUR_APP_TOKEN"
USER_TOKEN = "YOUR_USER_TOKEN"

# Confluence Export Path
# Point this to the parent folder of the root folder containing index.html and the 'attachments', 'images', 'styles' folders
EXPORT_DIR = r"C:\path\to\your\confluence\export" 

# General
# SSL Verification
# Options:
# - False: Disable verification (insecure, prints warnings)
# - True: Verify using default system CAs
# - "path/to/cert.pem": Verify using specific CA bundle
VERIFY_SSL = r"C:\path\to\your\cert.pem"

# Cleanup Settings
DEFAULT_CATEGORY_TO_CLEANUP = "your_glpi_root_category_name"

# Logs Fetching Settings (Browser Session)
COOKIE_NAME = "glpi_session_cookie_name"
COOKIE_VALUE = "your_session_cookie_value"
