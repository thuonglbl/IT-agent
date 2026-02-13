from jira_client import JiraClient
import config

jira = JiraClient(config.JIRA_URL, config.JIRA_PAT, verify_ssl=config.JIRA_VERIFY_SSL)

start_at = 0
unique_levels = set()

# Search ALL issues in the project
# Note: Security Level name is usually in fields.security.name
print("Scannning Jira issues for Security Levels...")

while True:
    issues, total = jira.search_issues(f"project = {config.JIRA_PROJECT_KEY}", start_at=start_at, max_results=50)
    if not issues:
        break
        
    for issue in issues:
        sec = issue.get('fields', {}).get('security')
        if sec:
            name = sec.get('name')
            if name:
                unique_levels.add(name)
                
    start_at += len(issues)
    print(f"Scanned {start_at}/{total} issues...", end='\r')
    if start_at >= total:
        break

print("\n\n--- Found Security Levels ---")
for level in sorted(list(unique_levels)):
    print(f"- {level}")
