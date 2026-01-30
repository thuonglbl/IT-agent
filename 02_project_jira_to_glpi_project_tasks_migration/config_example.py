# Jira Configuration
# URL of your Jira Server
JIRA_URL = "your-jira-url/jira"
# Your Personal Access Token (PAT)
JIRA_PAT = "your-jira-pat"
# Project Key to migrate
JIRA_PROJECT_KEY = "your-jira-project-key"
# SSL Verification
# Options:
# - False: Disable verification (insecure, prints warnings)
# - True: Verify using default system CAs
# - "path/to/cert.pem": Verify using specific CA bundle
JIRA_VERIFY_SSL = True

# GLPI Configuration
GLPI_URL = "your-glpi-url/api.php/v1"
GLPI_APP_TOKEN = "your-glpi-app-token"
GLPI_USER_TOKEN = "your-glpi-user-token"
# SSL Verification
# Options:
# - False: Disable verification (insecure, prints warnings)
# - True: Verify using default system CAs
# - "path/to/cert.pem": Verify using specific CA bundle
GLPI_VERIFY_SSL = r"path/to/your/cert.pem"

# Migration Settings
BATCH_SIZE = 50 # Number of tickets to fetch per request (Safe default)
STATE_FILE = "migration_state.json" # to resume if the script is interrupted (lost internet, server down, etc)