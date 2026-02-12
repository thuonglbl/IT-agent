# Jira Configuration
# URL of your Jira Server
JIRA_URL = "https://your-jira-server/jira"
# Your Personal Access Token (PAT)
JIRA_PAT = "your-jira-pat"
# Project Key to migrate
JIRA_PROJECT_KEY = "PROJECTKEY"
# JQL Filter for migration
JIRA_JQL = "project = PROJECTKEY ORDER BY key ASC"
# SSL Verification
# Options:
# - False: Disable verification (insecure, prints warnings)
# - True: Verify using default system CAs
# - "path/to/cert.pem": Verify using specific CA bundle
JIRA_VERIFY_SSL = True

# GLPI Configuration
GLPI_URL = "https://your-glpi-server/api.php/v1"
# GLPI Target Project Name (Must match exactly or be found via search)
GLPI_PROJECT_NAME = "Target GLPI Project Name"
GLPI_APP_TOKEN = "your-app-token"
GLPI_USER_TOKEN = "your-user-token"
# SSL Verification
# Options:
# - False: Disable verification (insecure, prints warnings)
# - True: Verify using default system CAs
# - "path/to/cert.pem": Verify using specific CA bundle
GLPI_VERIFY_SSL = r"path/to/your/cert.pem"
# Optional: Credentials for automation import LDAP users on GLPI, migration backup plan in case user token fails
GLPI_USERNAME = ""
GLPI_PASSWORD = ""

# Migration Settings
BATCH_SIZE = 50 # Number of tickets to fetch per request (Safe default)
# Debug Mode
# Set to True to fetch only 1 batch and print detailed debug info
# Set to False to run the full migration
DEBUG = False
STATE_FILE = "migration_state.json" # to resume if the script is interrupted (lost internet, server down, etc)
MAPPING_FILE = "jira_glpi_id_map.json" # DO NOT delete, it stores Jira Key mapping used for GLPI sub-tasks to parent tasks linkage

# Jira Custom Field IDs
# Update these IDs based on your Jira instance
# Go to Project Settings > Fields > select your current schema > on Screens column hover on the link "X screens" to get customfield IDs 
JIRA_CUSTOM_FIELDS = {
    "answer": "customfield_XXXXX",
    "approvers": "customfield_XXXXX",
    "automatic_test": "customfield_XXXXX",
    "begin_date": "customfield_XXXXX",
    "bug_cause": "customfield_XXXXX",
    "business_id": "customfield_XXXXX",
    "business_services": "customfield_XXXXX",
    "business_value": "customfield_XXXXX",
    "change_details": "customfield_XXXXX",
    "classification": "customfield_XXXXX",
    "complexity_points": "customfield_XXXXX",
    "complexity_points_in_vn": "customfield_XXXXX",
    "conditions": "customfield_XXXXX",
    "contingency_plan": "customfield_XXXXX",
    "contract_scope_status": "customfield_XXXXX",
    "cucumber_scenario": "customfield_XXXXX",
    "customer_request_type": "customfield_XXXXX",
    "decision": "customfield_XXXXX",
    "dr_impacted_by_change": "customfield_XXXXX",
    "end_date": "customfield_XXXXX",
    "epx_project": "customfield_XXXXX",
    "estimated_story_points": "customfield_XXXXX",
    "estimation": "customfield_XXXXX",
    "expected_risk_costs": "customfield_XXXXX",
    "expected_risk_costs_assumption": "customfield_XXXXX",
    "feature_link": "customfield_XXXXX",
    "feature_name": "customfield_XXXXX",
    "feature_status": "customfield_XXXXX",
    "figma_license": "customfield_XXXXX",
    "flagged": "customfield_XXXXX",
    "frequency": "customfield_XXXXX",
    "generic_test_definition": "customfield_XXXXX",
    "groups": "customfield_XXXXX",
    "how_to_repeat": "customfield_XXXXX",
    "how_to_test": "customfield_XXXXX",
    "impact": "customfield_XXXXX",
    "imputation": "customfield_XXXXX",
    "manual_test_steps": "customfield_XXXXX",
    "module": "customfield_XXXXX",
    "organizations": "customfield_XXXXX",
    "overdue_status": "customfield_XXXXX",
    "pre_condition_type": "customfield_XXXXX",
    "pre_conditions_association_with_a_test": "customfield_XXXXX",
    "probability": "customfield_XXXXX",
    "product_pr": "customfield_XXXXX",
    "project_code": "customfield_XXXXX",
    "project_manager": "customfield_XXXXX",
    "queue": "customfield_XXXXX",
    "realization": "customfield_XXXXX",
    "reference": "customfield_XXXXX",
    "reporter_details": "customfield_XXXXX",
    "reporter_group": "customfield_XXXXX",
    "request_participants": "customfield_XXXXX",
    "requirement": "customfield_XXXXX",
    "requirement_status": "customfield_XXXXX",
    "residual_impact": "customfield_XXXXX",
    "residual_probability": "customfield_XXXXX",
    "revision": "customfield_XXXXX",
    "risk_costs": "customfield_XXXXX",
    "risk_costs_assumption": "customfield_XXXXX",
    "root_cause": "customfield_XXXXX",
    "scoped_labels": "customfield_XXXXX",
    "security_component": "customfield_XXXXX",
    "severity": "customfield_XXXXX",
    "sprint": "customfield_XXXXX",
    "sprint_ba": "customfield_XXXXX",
    "substitute_manager": "customfield_XXXXX",
    "test_environments": "customfield_XXXXX",
    "test_plan": "customfield_XXXXX",
    "test_plan_status": "customfield_XXXXX",
    "test_plan_tests_filter": "customfield_XXXXX",
    "test_plans_associated_with_a_test": "customfield_XXXXX",
    "test_repository_path": "customfield_XXXXX",
    "test_sets_association_with_a_test": "customfield_XXXXX",
    "test_type": "customfield_XXXXX",
    "tests_associated_with_a_test_plan": "customfield_XXXXX",
    "tests_association_with_a_pre_condition": "customfield_XXXXX",
    "tests_association_with_a_test_execution": "customfield_XXXXX",
    "tests_association_with_a_test_set": "customfield_XXXXX",
    "time_to_sla": "customfield_XXXXX",
    "total_us_cp": "customfield_XXXXX",
    "treatment": "customfield_XXXXX",
    "treatment_costs": "customfield_XXXXX",
    "treatment_costs_assumption": "customfield_XXXXX",
    "treatment_plan": "customfield_XXXXX",
    "urgency": "customfield_XXXXX",
    "work_around_fix": "customfield_XXXXX",
}

# Jira Color Mapping (JIRA Color Name -> GLPI Hex Color)
# Limitation: Jira API returns the color name 'success', 'inprogress', 'default' but GLPI expects the hex value
JIRA_COLOR_MAP = {
    "success": "#00875A", # Green
    "inprogress": "#0052CC", # Blue
    "default": "#42526E", # Gray
}