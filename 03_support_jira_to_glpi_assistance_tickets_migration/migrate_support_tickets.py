import os
import json
import time
from datetime import datetime
import config
from jira_client import JiraClient
from glpi_client_support import GlpiClient

def load_state():
    if os.path.exists(config.STATE_FILE):
        with open(config.STATE_FILE, 'r') as f:
            return json.load(f)
    return {"start_at": 0, "total_processed": 0}

def save_state(start_at, total_processed):
    abs_path = os.path.abspath(config.STATE_FILE)
    print(f"  [DEBUG] Saving state to: {abs_path}")
    with open(config.STATE_FILE, 'w') as f:
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
        
        # --- PREPARATION: Check Statuses ---
        print("\n--- Checking Statuses ---")
        # 1. Load Jira Statuses
        jira_statuses = jira.get_project_statuses(config.JIRA_PROJECT_KEY)
        jira_status_names = {s['name'].lower(): s['name'] for s in jira_statuses} # lower -> Original
        print(f"Jira Project Statuses: {list(jira_status_names.values())}")
        
        # 2. Check existence in GLPI
        glpi_status_map = glpi.get_status_id_map() # name_lower -> id
        
        # 3. Build Dynamic Mapping
        # Start with default mapping to cover standard cases
        DYNAMIC_MAPPING = config.STATUS_MAPPING.copy()
        
        for j_lower, j_original in jira_status_names.items():
            if j_lower in glpi_status_map:
                glpi_id = glpi_status_map[j_lower]
                DYNAMIC_MAPPING[j_lower] = glpi_id
                print(f"  [MATCH] '{j_original}' maps to GLPI Status ID {glpi_id}")
            else:
                # Try fuzzy matching or fallback
                # Note: GLPI Ticket Statuses are fixed (1-6). We cannot create new ones via API.
                # We map to DEFAULT_STATUS and log warning.
                if j_lower not in DYNAMIC_MAPPING:
                    print(f"  [MISSING] '{j_original}' not found in GLPI. Mapping to Default ({config.DEFAULT_STATUS}).")
                    # DYNAMIC_MAPPING[j_lower] = DEFAULT_STATUS # Explicitly set default
        
        print("Status Mapping Ready.\n")
        
        print("Type Mapping Ready.\n")
        
        # 3. Load State
        state = load_state()
        start_at = state["start_at"]
        total_processed = state["total_processed"]
        
        print(f"Resuming migration from index {start_at}...")
        
        while True:
            # JQL: Fetch ALL tickets (Open & Closed), Ordered by KEY/ID ASC
            jql = f"project = {config.JIRA_PROJECT_KEY} ORDER BY key ASC"
            issues, total = jira.search_issues(jql, start_at=start_at, max_results=config.BATCH_SIZE)
            
            if not issues:
                print("All issues processed.")
                break
                
            print(f"Fetched {len(issues)} issues (Total: {total}). processing...")
            
            for issue in issues:
                process_issue(jira, glpi, issue, DYNAMIC_MAPPING)
                total_processed += 1
                
                if config.DEBUG:
                    print("[DEBUG] Mode enabled. Processed 1 issue. Saving state and Exiting.")
                    save_state(start_at + 1, total_processed)
                    return
                
            start_at += len(issues)
            save_state(start_at, total_processed)
            print(f"  [State Saved] Next batch at {start_at}")
            
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
    finally:
        glpi.kill_session()

def process_issue(jira, glpi, issue, status_mapping):
    key = issue['key']
    fields = issue['fields']
    # 1. Title: Use summary directly (No ID)
    summary = fields.get('summary', '[No Title]')
    description = fields.get('description') or ""
    
    # --- Map Users ---
    reporter_jira = (fields.get('reporter') or {}).get('name')
    # Use display name for better logging/fallback
    reporter_display = (fields.get('reporter') or {}).get('displayName', reporter_jira)
    
    assignee_jira = (fields.get('assignee') or {}).get('name')
    
    # Debug User Mapping
    requester_id = glpi.get_user_id_by_name(reporter_jira)
    if not requester_id:
        print(f"  [WARN] Requester not found in GLPI: '{reporter_jira}' ({reporter_display})")
    
    assignee_id = glpi.get_user_id_by_name(assignee_jira)
    if assignee_jira and not assignee_id:
         print(f"  [WARN] Assignee not found in GLPI: '{assignee_jira}'")

    # --- Map Status ---
    status_jira = (fields.get('status') or {}).get('name', '').lower()
    glpi_status = status_mapping.get(status_jira, config.DEFAULT_STATUS)
    print(f"  Status Check: Jira '{status_jira}' -> GLPI ID {glpi_status}")
    
    # --- Map Type ---
    type_jira = (fields.get('issuetype') or {}).get('name', '').lower()
    
    # --- Type Fallback ---
    # Map Jira Type to GLPI Ticket Type (1=Incident, 2=Request)
    glpi_type = config.TYPE_MAPPING.get(type_jira, config.DEFAULT_TYPE)
    
    # NOTE: SLA (Time to Own) is now auto-calculated by GLPI. Removed extraction logic.

    # --- Dates ---
    
    # --- Dates ---
    creation_date = parse_jira_date(fields.get('created'))
    update_date = parse_jira_date(fields.get('updated'))
    resolution_date = parse_jira_date(fields.get('resolutiondate'))
    
    print(f"Migrating {key}: {summary}...")
    
    # --- 3. Description Header & Details ---
    # Construct "Jira Details" table
    issue_type = (fields.get('issuetype') or {}).get('name', 'Ticket')
    priority = (fields.get('priority') or {}).get('name', 'Normal')
    components = ", ".join([c.get('name') for c in fields.get('components', [])])
    labels = ", ".join(fields.get('labels', []))
    
    # "Imported from Jira" header removed. Link is embedded in details.
    details_table = (
        f"**Jira Details**:\n"
        f"| Field | Value |\n"
        f"|---|---|\n"
        f"| **Key** | [{key}]({config.JIRA_URL}/browse/{key}) |\n"
        f"| **Type** | {issue_type} |\n"
        f"| **Priority** | {priority} |\n"
        f"| **Component** | {components} |\n"
        f"| **Labels** | {labels} |\n"
        f"| **Reporter** | {reporter_display} |\n"
        f"\n---\n\n"
    )
    
    full_desc = details_table + description
    
    ticket_args = {
        "status": glpi_status,
        "type": glpi_type,
        "date": creation_date,
        # NOTE: date_mod and time_to_own are auto-generated by GLPI, not set here.
    }
    
    # 4. Fix Dates (Solved/Closed)
    # If ticket is solved (5) or closed (6), set solvedate
    if glpi_status in [5, 6]:
        # Use resolution date if available, else update date
        final_date = resolution_date or update_date
        ticket_args["solvedate"] = final_date
    
    if glpi_status == 6:
         # For closed tickets, usually closedate = solvedate
         ticket_args["closedate"] = resolution_date or update_date

    # 5. Actors
    if requester_id:
        ticket_args['_users_id_requester'] = requester_id
    if assignee_id:
        ticket_args['_users_id_assign'] = assignee_id
        
    ticket_id = glpi.create_ticket(name=summary, content=full_desc, **ticket_args)
    
    if ticket_id:
        # --- Migrate Comments ---
        comments = (fields.get('comment') or {}).get('comments', [])
        for comment in comments:
            author_jira = (comment.get('author') or {}).get('name')
            author_display = (comment.get('author') or {}).get('displayName', author_jira)
            body = comment.get('body', '')
            created = parse_jira_date(comment.get('created'))
            
            author_id = glpi.get_user_id_by_name(author_jira)
            
            # Format comment header
            header = f"**Comment by {author_display} ({created})**:\n"
            glpi.add_ticket_followup(ticket_id, header + body, users_id=author_id, date=created)
            
        # NOTE: Last Update Date (date_mod) is auto-generated by GLPI and cannot be overwritten.
            
        print(f"  -> Done. ID: {ticket_id}")

if __name__ == "__main__":
    main()
