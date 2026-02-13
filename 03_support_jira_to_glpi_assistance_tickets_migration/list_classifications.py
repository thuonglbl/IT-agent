"""
List all unique values for the configured Classification custom field from Jira issues.
Usage: python list_classifications.py
"""
import config
from jira_client import JiraClient

def main():
    print("--- Listing Jira Classifications ---")
    
    jira = JiraClient(config.JIRA_URL, config.JIRA_PAT, verify_ssl=config.JIRA_VERIFY_SSL)
    
    classification_id = getattr(config, 'CLASSIFICATION_ID', 'customfield_12010')
    # Extract numeric ID for JQL
    cf_num = classification_id.split('_')[-1]
    print(f"Target Field ID: {classification_id} (cf[{cf_num}])")
    
    # JQL using cf[ID] syntax is safer
    jql = f"project = {config.JIRA_PROJECT_KEY} AND cf[{cf_num}] is not EMPTY"
    print(f"JQL: {jql}")
    
    start_at = 0
    batch_size = 50 # Reduce batch size to be safer
    unique_values = set()
    
    while True:
        print(f"  Fetching batch starting at {start_at}...")
        issues, total = jira.search_issues(jql, start_at=start_at, max_results=batch_size)
        
        if not issues:
            break
            
        for issue in issues:
            fields = issue.get('fields', {})
            val = fields.get(classification_id)
            
            if val:
                if isinstance(val, list):
                    # Multi-select or checkbox
                    for v in val:
                        v_str = str(v.get('value') if isinstance(v, dict) else v)
                        unique_values.add(v_str)
                else:
                    # Single select or text
                    v_str = str(val.get('value') if isinstance(val, dict) else val)
                    unique_values.add(v_str)
        
        start_at += len(issues)
        if start_at >= total:
            break
            
    print("\n--- Unique Classifications Found ---")
    for val in sorted(unique_values):
        print(f"- {val}")
    print("------------------------------------")

if __name__ == "__main__":
    main()
