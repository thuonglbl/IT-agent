# Jira Configuration
# URL of your Jira Server
JIRA_URL = "https://your-jira-url"
# Your Personal Access Token (PAT)
JIRA_PAT = "your_jira_pat"
# Project Key to migrate
JIRA_PROJECT_KEY = "your_jira_project_key"
# SSL Verification
# Options:
# - False: Disable verification (insecure, prints warnings)
# - True: Verify using default system CAs
# - "path/to/cert.pem": Verify using specific CA bundle
JIRA_VERIFY_SSL = True

# GLPI Configuration
GLPI_URL = "https://your-glpi-server/api.php/v1"
# App Token (API Client)
GLPI_APP_TOKEN = "your_glpi_app_token"
# User Token (API Client)
GLPI_USER_TOKEN = "your_glpi_user_token"
# SSL Verification
# Options:
# - False: Disable verification (insecure, prints warnings)
# - True: Verify using default system CAs
# - "path/to/cert.pem": Verify using specific CA bundle
GLPI_VERIFY_SSL = r"path/to/your/cert.pem"

# Migration Settings
BATCH_SIZE = 50 # Number of tickets to fetch per request (Safe default)
STATE_FILE = "migration_state.json" # to resume if the script is interrupted (lost internet, server down, etc)