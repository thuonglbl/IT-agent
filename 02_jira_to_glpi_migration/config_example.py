# Jira Configuration
# URL of your Jira Server
JIRA_URL = "https://your-jira-server/jira"
# Your Personal Access Token (PAT)
JIRA_PAT = "YOUR_JIRA_PAT_HERE"
# Project Key to migrate
JIRA_PROJECT_KEY = "YOUR_PROJECT_KEY"

# GLPI Configuration
GLPI_URL = "https://your-glpi-instance/api.php/v1"
GLPI_APP_TOKEN = "YOUR_GLPI_APP_TOKEN"
GLPI_USER_TOKEN = "YOUR_GLPI_USER_TOKEN"

# SSL Verification
# Options:
# - False: Disable verification (insecure, prints warnings)
# - True: Verify using default system CAs
# - "path/to/cert.pem": Verify using specific CA bundle

# Path to Jira Certificate (or True/False)
JIRA_VERIFY_SSL = True

# Path to GLPI Certificate (or True/False)
GLPI_VERIFY_SSL = True

# Migration Settings
BATCH_SIZE = 50 # Number of tickets to fetch per request (Safe default)
STATE_FILE = "migration_state.json" # to resume if the script is interrupted
