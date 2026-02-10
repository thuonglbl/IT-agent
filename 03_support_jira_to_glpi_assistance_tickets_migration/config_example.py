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
STATE_FILE = "migration_state.json" # to resume if the script is interrupted (lost internet, VPN down, computer sleep, etc)
DEBUG = True # Set to True to process only 1 issue for testing, set to False to run the full migration

# Mapping Settings
# Jira Status -> GLPI Status ID Mapping
# GLPI Statuses (cannot change): 1=New, 10=Approval, 2=Processing(Assigned), 3=Processing(Planned), 4=Pending, 5=Solved, 6=Closed
STATUS_MAPPING = {
    'assigned': 2,
    'in progress': 3,
    'resolved': 5,
    'on hold': 4,
    'closed': 6,
    'submitted': 10,
    'waiting for approval': 1,
    'open': 1,
    'planned': 3,
    'delivered': 5,
    'completed': 6,
    'ready for delivery': 5,
}
# Default if not found
DEFAULT_STATUS = 3

# Jira Issue Type -> GLPI Ticket Type Mapping
# 1 = Incident, 2 = Request
TYPE_MAPPING = {
    'change': 2,
    'incident': 1,
    'support request': 2,
    'rollout': 2,
}
# Default if not found
DEFAULT_TYPE = 2

# Additional Custom Fields for Description Mapping
CLASSIFICATION_ID = 'customfield_12010'
REPORTER_DETAILS_ID = 'customfield_11710'
REQUEST_PARTICIPANTS_ID = 'customfield_10911' # Request participants
CUSTOMER_REQUEST_TYPE_ID = 'customfield_10912' # Service Desk Request Type

# SLA Configuration: in case Jira has SLA integration
# Custom Field IDs, use Inspect to get this value from Jira
SLA_FIELDS = [
    'customfield_11512', # Time to assign
    'customfield_11515', # In Progress
    'customfield_11514', # In progress To Fixed
    'customfield_11516', # Resolved to Closed
    'customfield_12310'  # Approval expiry
]