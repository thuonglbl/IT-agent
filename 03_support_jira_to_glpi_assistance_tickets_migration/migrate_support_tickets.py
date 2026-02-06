import os
import json
import time
from datetime import datetime
import config
from jira_client import JiraClient
from glpi_client_support import GlpiClient

# --- Configuration ---
DEBUG = True # Set to True to process only 1 issue for testing
BATCH_SIZE = 50
STATE_FILE = "migration_state_tickets.json"
# Jira Status -> GLPI Status ID Mapping (Core Statuses)
# 1=New, 2=Processing(Assigned), 3=Processing(Planned), 4=Pending, 5=Solved, 6=Closed
STATUS_MAPPING = {
    'open': 1,
    'new': 1,
    'to do': 1,
    'in progress': 2,
    'analyzing': 2,
    'pending': 4,
    'resolved': 5,
    'done': 5,
    'closed': 6,
    'cancelled': 6
}
# Default if not found
DEFAULT_STATUS = 2

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"start_at": 0, "total_processed": 0}

def save_state(start_at, total_processed):
    with open(STATE_FILE, 'w') as f:
        json.dump({"start_at": start_at, "total_processed": total_processed, "timestamp": time.time()}, f)

def parse_jira_date(date_str):
    """Convert Jira date string to GLPI compatible SQL format (YYYY-MM-DD HH:MM:SS)"""
    if not date_str: return None
    try:
        # Jira: 2024-01-21T10:30:00.000+0700
        # Simple parse keeping local time
        dt = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

def main():
    print("--- Jira Support to GLPI Assistance Migration ---")
    
    # 1. Initialize Clients
    jira = JiraClient(config.JIRA_URL, config.JIRA_PAT, verify_ssl=config.JIRA_VERIFY_SSL)
    glpi = GlpiClient(config.GLPI_URL, config.GLPI_APP_TOKEN, config.GLPI_USER_TOKEN, verify_ssl=config.GLPI_VERIFY_SSL)
    
    try:
        glpi.init_session()
        
        # 2. Load cached data
        glpi.load_user_cache(recursive=True) # Recursive as requested
        
        # 3. Load State
        state = load_state()
        start_at = state["start_at"]
        total_processed = state["total_processed"]
        
        print(f"Resuming migration from index {start_at}...")
        
        while True:
            # JQL: Fetch ALL tickets (Open & Closed)
            jql = f"project = {config.JIRA_PROJECT_KEY} ORDER BY created ASC"
            issues, total = jira.search_issues(jql, start_at=start_at, max_results=BATCH_SIZE)
            
            if not issues:
                print("All issues processed.")
                break
                
            print(f"Fetched {len(issues)} issues (Total: {total}). processing...")
            
            for issue in issues:
                process_issue(jira, glpi, issue)
                total_processed += 1
                
                if DEBUG:
                    print("[DEBUG] Mode enabled. Processed 1 issue. Exiting.")
                    return
                
            start_at += len(issues)
            save_state(start_at, total_processed)
            print(f"  [State Saved] Next batch at {start_at}")
            
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
    finally:
        glpi.kill_session()

def process_issue(jira, glpi, issue):
    key = issue['key']
    fields = issue['fields']
    summary = fields.get('summary', '[No Title]')
    description = fields.get('description') or ""
    
    # --- Map Users ---
    reporter_jira = (fields.get('reporter') or {}).get('name')
    assignee_jira = (fields.get('assignee') or {}).get('name')
    
    requester_id = glpi.get_user_id_by_name(reporter_jira)
    assignee_id = glpi.get_user_id_by_name(assignee_jira)
    
    # --- Map Status ---
    status_jira = (fields.get('status') or {}).get('name', '').lower()
    glpi_status = STATUS_MAPPING.get(status_jira, DEFAULT_STATUS)
    
    # --- Dates ---
    creation_date = parse_jira_date(fields.get('created'))
    update_date = parse_jira_date(fields.get('updated'))
    
    print(f"Migrating {key}: {summary}...")
    
    # --- Create Ticket ---
    # Prepend Jira Link to description
    full_desc = f"**Imported from Jira**: [{key}]({config.JIRA_URL}/browse/{key})\n\n{description}"
    
    ticket_args = {
        "status": glpi_status,
        "date": creation_date,
        "date_mod": update_date
    }
    
    # Actors
    if requester_id:
        ticket_args['_users_id_requester'] = requester_id
    if assignee_id:
        ticket_args['_users_id_assign'] = assignee_id
        
    ticket_id = glpi.create_ticket(name=f"[{key}] {summary}", content=full_desc, **ticket_args)
    
    if ticket_id:
        # --- Migrate Comments ---
        # Jira 'comment' field usually contains comments list
        comments = (fields.get('comment') or {}).get('comments', [])
        for comment in comments:
            author_jira = (comment.get('author') or {}).get('name')
            body = comment.get('body', '')
            created = parse_jira_date(comment.get('created'))
            
            author_id = glpi.get_user_id_by_name(author_jira)
            
            # Format comment header
            header = f"**Comment by {author_jira} ({created})**:\n"
            glpi.add_ticket_followup(ticket_id, header + body, users_id=author_id, date=created)
            
        print(f"  -> Done. ID: {ticket_id}")

if __name__ == "__main__":
    main()
