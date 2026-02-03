import os
import json
import time
import requests
import datetime
import config
from jira_client import JiraClient
from glpi_api import GlpiClient

# --- Constants ---
# Debug Mode
# Set to True to fetch only 1 ticket and print detailed debug info
# Set to False to run the full migration
DEBUG = True
STATE_FILE = config.STATE_FILE

def load_state():
    """Load the last processed index from state file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not read state file: {e}")
    return {"start_at": 0, "total_processed": 0}

def save_state(start_at, total_processed):
    """Save current progress to state file."""
    state = {
        "start_at": start_at,
        "total_processed": total_processed,
        "timestamp": time.time()
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)
    print(f"  [State Saved] Next fetch starts at {start_at}")

def parse_jira_date(date_str):
    """
    Parse Jira date string '2014-03-04T09:46:56.000+0100' 
    to GLPI format 'YYYY-MM-DD HH:MM:SS'
    """
    if not date_str:
        return None
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"Date parse error ({date_str}): {e}")
            return None

def format_description(issue, fields):
    """
    Format the Jira description into HTML with extra fields.
    """
    key = issue.get('key')
    description = fields.get('description') or ""
    
    # Extra Fields
    reporter = fields.get('reporter', {}).get('displayName', 'Unknown')
    priority = fields.get('priority', {}).get('name', 'None')
    created = fields.get('created')
    
    # Lists
    affects_versions = ", ".join([v.get('name') for v in fields.get('versions', [])])
    fix_versions = ", ".join([v.get('name') for v in fields.get('fixVersions', [])])
    components = ", ".join([c.get('name') for c in fields.get('components', [])])
    environment = fields.get('environment', '')
    
    content_html = f"<p><b>Original Jira Key:</b> {key}</p>"
    content_html += f"<p><b>Reporter:</b> {reporter}</p>"
    content_html += f"<p><b>Priority:</b> {priority}</p>"
    content_html += f"<p><b>Created:</b> {created}</p>"
    
    if affects_versions:
        content_html += f"<p><b>Affects Version/s:</b> {affects_versions}</p>"
    if fix_versions:
        content_html += f"<p><b>Fix Version/s:</b> {fix_versions}</p>"
    if components:
        content_html += f"<p><b>Component/s:</b> {components}</p>"
    if environment:
        content_html += f"<p><b>Environment:</b> {environment}</p>"
    
    content_html += f"<hr><h3>Description</h3>"
    content_html += f"<div>{description.replace(chr(10), '<br>')}</div>"
    
    return content_html

def process_changelog(issue):
    """
    Parse changelog to create a History Log HTML.
    """
    changelog = issue.get('changelog', {})
    histories = changelog.get('histories', [])
    
    if not histories:
        return None

    html = "<h3>Jira History Log</h3>"
    html += "<table border='1' style='border-collapse: collapse; width: 100%;'>"
    html += "<tr><th>Date</th><th>Author</th><th>Field</th><th>From</th><th>To</th></tr>"
    
    for history in histories:
        created = history.get('created')
        author = history.get('author', {}).get('displayName', 'Unknown')
        items = history.get('items', [])
        
        # Parse date nicely
        formatted_date = parse_jira_date(created) or created

        for item in items:
            field = item.get('field', '')
            from_str = item.get('fromString', '')
            to_str = item.get('toString', '')
            
            # Escape HTML just in case
            from_str = str(from_str).replace("<", "&lt;").replace(">", "&gt;") if from_str else ""
            to_str = str(to_str).replace("<", "&lt;").replace(">", "&gt;") if to_str else ""
            
            html += f"<tr>"
            html += f"<td>{formatted_date}</td>"
            html += f"<td>{author}</td>"
            html += f"<td>{field}</td>"
            html += f"<td>{from_str}</td>"
            html += f"<td>{to_str}</td>"
            html += f"</tr>"
            
    html += "</table>"
    return html

def main():
    print("--- Jira to GLPI Migration Tool (ProjecTask + Notes + History) ---")
    
    # 1. Initialize Clients
    jira = JiraClient(config.JIRA_URL, config.JIRA_PAT, verify_ssl=config.JIRA_VERIFY_SSL)
    glpi = GlpiClient(config.GLPI_URL, config.GLPI_APP_TOKEN, config.GLPI_USER_TOKEN, verify_ssl=config.GLPI_VERIFY_SSL)
    
    # Verify Connections
    print("Checking connections...")
    try:
        # Jira Check (fetch 1 issue to test)
        jira.search_issues(f"project = {config.JIRA_PROJECT_KEY}", max_results=1)
        print("-> Jira Connection: OK")
        
        # GLPI Check
        glpi.init_session()
        print("-> GLPI Connection: OK")
        
        # Resolve Project ID for configured project

        target_project_name = config.GLPI_PROJECT_NAME
        print(f"Resolving GLPI Project '{target_project_name}'...")
        project_id = glpi.get_project_id_by_name(target_project_name)
        if not project_id:
            print(f"CRITICAL ERROR: Project '{target_project_name}' not found in GLPI. Please create it manually first.")
            return
        print(f"-> Found Project ID: {project_id}")

        # Fetch Project States (Dynamic Mapping)
        print("Fetching GLPI Project States...")
        project_states_map = glpi.get_project_states()
        print(f"-> Loaded {len(project_states_map)} states: {project_states_map}")

        # Fetch Project Task Types (Dynamic Mapping)
        print("Fetching GLPI Project Task Types...")
        project_types_map = glpi.get_project_task_types()
        print(f"-> Loaded {len(project_types_map)} types: {project_types_map}")
        
    except Exception as e:
        print(f"Connection Failed: {e}")
        return

    # 2. Migration Loop
    state = load_state()
    start_at = state.get("start_at", 0)
    total_processed = state.get("total_processed", 0)
    
    jql = f"project = '{config.JIRA_PROJECT_KEY}' ORDER BY created ASC"
    
    try:
        # Get total count first
        total_issues = jira.get_issue_count(jql)
        print(f"Total Issues to Migrate: {total_issues}")
        print(f"Resuming from: {start_at}")

        while start_at < total_issues:
            # Determine max results based on Debug mode
            fetch_limit = 1 if DEBUG else config.BATCH_SIZE
            
            if DEBUG:
                print(f"\n[DEBUG] Fetching 1 ticket for testing...")
            else:
                print(f"\nFetching batch: {start_at} to {start_at + fetch_limit} ...")
            
            # IMPORTANT: Fetch changelog!
            issues, _ = jira.search_issues(jql, start_at=start_at, max_results=fetch_limit)
            
            if not issues:
                print("No more issues returned.")
                break
                
            for issue in issues:
                key = issue.get('key')
                fields = issue.get('fields', {})
                summary = fields.get('summary', '[No Summary]')
                
                print(f"Processing {key}: {summary[:50]}...")
                
                # --- MAPPING LOGIC ---
                
                # Assignee -> Tech
                jira_assignee_name = fields.get('assignee', {}).get('name')
                assignee_id = None
                if jira_assignee_name:
                    assignee_id = glpi.get_user_id_by_name(jira_assignee_name)
                    if assignee_id:
                        print(f"    -> Mapped Assignee '{jira_assignee_name}' to GLPI ID {assignee_id}")

                # Status Mapping (Dynamic & Case-Insensitive)
                jira_status = fields.get('status', {}).get('name', 'Open')
                jira_status_lower = jira_status.lower()
                glpi_state_id = project_states_map.get(jira_status_lower)
                
                if not glpi_state_id:
                    # Fallback logic if exact name match fails
                    if jira_status_lower in ['in progress', 'reopened'] and 'processing' in project_states_map:
                         glpi_state_id = project_states_map['processing']
                    elif jira_status_lower in ['resolved'] and 'closed' in project_states_map:
                         glpi_state_id = project_states_map['closed']
                    else:
                         # Default to 'new' (if exists) or ID 1
                         glpi_state_id = project_states_map.get('new', 1) 
                         print(f"    [WARN] Status '{jira_status}' not found in GLPI. Defaulting to ID {glpi_state_id}")

                # Type Mapping (Dynamic)
                jira_type = fields.get('issuetype', {}).get('name', 'Task')
                glpi_type_id = project_types_map.get(jira_type.lower())
                if glpi_type_id:
                     print(f"    -> Mapped Type '{jira_type}' to GLPI ID {glpi_type_id}")
                else:
                     print(f"    [WARN] Type '{jira_type}' not found in GLPI.")
                
                # Date Mapping
                jira_created = fields.get('created')
                glpi_date = parse_jira_date(jira_created)
                
                # Format Description
                content_html = format_description(issue, fields)
                
                # Attachments
                attachments = fields.get('attachment', [])
                if attachments:
                    content_html += "<hr><h3>Attachments</h3><ul>"
                    for att in attachments:
                        filename = att.get('filename')
                        content_url = att.get('content')
                        print(f"    - Downloading attachment: {filename}...")
                        
                        file_data = jira.get_attachment_content(content_url)
                        if file_data:
                            temp_path = os.path.join(os.getcwd(), filename)
                            with open(temp_path, 'wb') as f:
                                f.write(file_data)
                            
                            doc_id, doc_url = glpi.upload_document(temp_path)
                            
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                                
                            if doc_url:
                                content_html += f"<li><a href='{doc_url}' target='_blank'>{filename}</a></li>"
                            else:
                                content_html += f"<li>{filename} (Upload Failed)</li>"
                        else:
                            content_html += f"<li>{filename} (Download Failed)</li>"
                    content_html += "</ul>"

                # Create GLPI Project Task
                task_name = summary 
                print(f"    -> Creating GLPI Project Task '{task_name}'...")
                
                task_kwargs = {
                    "projectstates_id": glpi_state_id,
                    "percent_done": 100 if jira_status in ['Resolved', 'Closed'] else 0
                }
                if glpi_date:
                    task_kwargs['date'] = glpi_date
                    task_kwargs['date_creation'] = glpi_date
                
                if assignee_id:
                     task_kwargs['users_id_tech'] = assignee_id
                
                if glpi_type_id:
                     task_kwargs['projecttasktypes_id'] = glpi_type_id
                
                task_id = glpi.create_project_task(project_id, task_name, content_html, **task_kwargs)
                
                if task_id:
                    print(f"       Success! Project Task ID: {task_id}")
                    
                    # 7. Migrate Comments & History (with Fallback)
                    failed_notes = []
                    
                    # 7a. Comments - Use create_note directly (GLPI creates Notes despite returning 400/500)
                    comments = fields.get('comment', {}).get('comments', [])
                    if comments:
                        print(f"       Migrating {len(comments)} comments as Notes...")
                        for comment in comments:
                            author_login = comment.get('author', {}).get('name') 
                            body = comment.get('body', '')
                            created = comment.get('created')
                            display_name = comment.get('author', {}).get('displayName') or author_login
                            
                            comment_author_id = None
                            if author_login:
                                comment_author_id = glpi.get_user_id_by_name(author_login)
                            
                            # Build Note content (HTML)
                            note_html = f"<p><b>[Comment by {display_name} on {created}]</b></p>"
                            note_html += f"<div>{body.replace(chr(10), '<br>')}</div>"
                            
                            kw = {}
                            if comment_author_id: 
                                kw['users_id'] = comment_author_id

                            # Create Note - will succeed despite GLPI returning 400/500
                            glpi.create_note("ProjectTask", task_id, note_html, **kw)
                            
                    # 7b. History
                    history_html = process_changelog(issue)
                    if history_html:
                        print("       Migrating History Log...")
                        if not glpi.create_note("ProjectTask", task_id, history_html):
                             print("          -> History Note creation failed. Queueing for description append.")
                             failed_notes.append(history_html)
                             
                    # 7c. Fallback Append
                    if failed_notes:
                        print(f"       Appending {len(failed_notes)} failed notes to Description...")
                        append_html = "<hr><h3>Migrated Comments & History</h3>"
                        append_html += "<hr>".join(failed_notes)
                        
                        # Append to original content
                        final_content = content_html + append_html
                        
                        glpi.update_project_task(task_id, content=final_content)

                else:
                    print(f"       Failed to create task for {key}")

                time.sleep(0.1) 
                
                total_processed += 1
            
            # Update Batch Progress
            start_at += len(issues)
            save_state(start_at, total_processed)

            # DEBUG 
            if DEBUG:
                print("[DEBUG] Stopping after test batch.")
                break
            
        print("\nMigration Completed Successfully!")
        
    except KeyboardInterrupt:
        print("\nMigration Paused by User.")
        save_state(start_at, total_processed)
    except Exception as e:
        print(f"\nMigration Failed: {e}")
        save_state(start_at, total_processed) 
    finally:
        glpi.kill_session()

if __name__ == "__main__":
    main()
