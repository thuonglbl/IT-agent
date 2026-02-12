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
# Optional: Credentials for fallback Basic Auth (if User Token fails)
GLPI_USERNAME = "your-glpi-username"
GLPI_PASSWORD = "your-glpi-password"

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

# Jira Priority -> GLPI Urgency, Impact Mapping
# GLPI auto-calculates Priority from Urgency × Impact matrix (Setup > General > Assistance)
# GLPI Scale: 1=Very low, 2=Low, 3=Medium, 4=High, 5=Very high
# Format: 'jira_priority_name (lowercase)': (urgency, impact)
PRIORITY_MAPPING = {
    'next hour':            (5, 5),  # Very high
    'next half-day':        (4, 4),  # High
    'next business day':    (3, 3),  # Medium
    'next 5 business day':  (2, 2),  # Low
    'to schedule':          (1, 1),  # Very low
}
DEFAULT_PRIORITY = (3, 3)  # Medium fallback

# Additional Custom Fields for Description Mapping
CLASSIFICATION_ID = 'customfield_12010'
REPORTER_DETAILS_ID = 'customfield_11710'
REQUEST_PARTICIPANTS_ID = 'customfield_10911' # Request participants
CUSTOMER_REQUEST_TYPE_ID = 'customfield_10912' # Service Desk Request Type
APPROVERS_ID = 'customfield_11011' # Approvers (multi-user picker)
APPROVALS_ID = 'customfield_10910' # Approvals (past approvals data)

# Missing Users Report - tracks users not found in GLPI during migration
MISSING_USERS_FILE = "missing_users.txt"

# SLA Configuration: in case Jira has SLA integration
# Custom Field IDs, use Inspect to get this value from Jira
SLA_FIELDS = [
    'customfield_11512', # Time to assign
    'customfield_11515', # In Progress
    'customfield_11514', # In progress To Fixed
    'customfield_12310'  # Approval expiry
]

# --- Classification Mapping ---
# Map Jira Classification -> GLPI Location (Name)
# Check GLPI: Setup > Dropdowns > Common > Locations
CLASSIFICATION_TO_LOCATION = {
    'CH': 'CH',
    'VN': 'VN',
    'ES': 'ES',
    'MU': 'MU',
}

# Map Jira Classification -> GLPI Item
# Format: 'JiraValue': ('ItemType', 'ItemName')
# Supported Types based on your GLPI: 'Business_Service' (Assets > Business Service), 'Software' (Assets > Software), 'Computer' (Assets > Computers)
CLASSIFICATION_TO_ITEM = {
    # Business_Service (Assets > Business Service)
    'Intranet':         ('Business_Service', 'SharePoint Intranet'),
    'Network':          ('Business_Service', 'Network Configuration'),
    'Internet':         ('Business_Service', 'Network Configuration'),
    'Project_Portal':   ('Business_Service', 'Project Monitoring Tool'),
    'SkillMatrix':      ('Business_Service', 'Project Monitoring Tool'),
    'Project_Space':    ('Business_Service', 'Project Space'),
    'ERP':              ('Business_Service', 'ERP'),
    'Firewall':         ('Business_Service', 'Network Configuration'),
    'CV_Tool':          ('Business_Service', 'CV Tool'),
    'ESS':              ('Business_Service', 'ESS'),
    'FCR':              ('Business_Service', 'FCR'),
    'Incident':         ('Business_Service', 'Incident'),
    'Office_Access':    ('Business_Service', 'Office Access'),
    'Oracle_DB':        ('Business_Service', 'ORACLE ERP'),
    'Oracle_HR':        ('Business_Service', 'ORACLE ERP'),
    'Oracle_Procurement': ('Business_Service', 'ORACLE ERP'),
    'Oracle_Other':     ('Business_Service', 'ORACLE ERP'),
    'Other':            ('Business_Service', 'Other'),
    'PT_Tool':          ('Business_Service', 'PT Tool'),
    
    # Software (Assets > Software)
    'Security':         ('Software', 'Windows Security'),
    'Teams':            ('Software', 'Microsoft Teams'),
    'Edge':             ('Software', 'Microsoft Edge'),
    'SharePoint':       ('Software', 'Sharepoint-app'),
    'Azure':            ('Software', 'Azure VPN Client'), 
    'VPN':              ('Software', 'Ashwind VPN'),
    'ashwind':          ('Software', 'Ashwind VPN'),
    'Workstation':      ('Software', 'VMware Workstation'),    
    'Email':            ('Software', 'Email and accounts'),    
    'license':          ('Software', 'Add License in the manager platform'),    
}