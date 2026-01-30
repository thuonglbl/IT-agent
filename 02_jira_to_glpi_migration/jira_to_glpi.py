import os
import json
import time
import requests
import config
from jira_client import JiraClient
from glpi_api import GlpiClient

# --- Constants ---
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

def main():
    print("--- Jira to GLPI Migration Tool (API Mode) ---")
    
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
    except Exception as e:
        print(f"Connection Failed: {e}")
        return

    # 2. Migration Loop
    state = load_state()
    start_at = state.get("start_at", 0)
    total_processed = state.get("total_processed", 0)
    
    # JQL: Order by Created to ensure stable pagination
    jql = f"project = '{config.JIRA_PROJECT_KEY}' ORDER BY created ASC"
    
    try:
        # Get total count first
        total_issues = jira.get_issue_count(jql)
        print(f"Total Issues to Migrate: {total_issues}")
        print(f"Resuming from: {start_at}")

        while start_at < total_issues:
            print(f"\nFetching batch: {start_at} to {start_at + config.BATCH_SIZE} ...")
            
            issues, _ = jira.search_issues(jql, start_at=start_at, max_results=config.BATCH_SIZE)
            
            if not issues:
                print("No more issues returned.")
                break
                
            for issue in issues:
                key = issue.get('key')
                fields = issue.get('fields', {})
                summary = fields.get('summary', '[No Summary]')
                description = fields.get('description') or ""
                
                print(f"Processing {key}: {summary[:50]}...")
                
                # --- MAPPING LOGIC ---
                
                # 1. Format Description
                content_html = f"<p><b>Original Jira Key:</b> {key}</p>"
                content_html += f"<p><b>Reporter:</b> {issue['fields'].get('reporter', {}).get('displayName', 'Unknown')}</p>"
                content_html += f"<p><b>Priority:</b> {issue['fields'].get('priority', {}).get('name', 'None')}</p>"
                content_html += f"<p><b>Created:</b> {issue['fields'].get('created')}</p>"
                content_html += f"<hr><h3>Description</h3>"
                content_html += f"<div>{description.replace(chr(10), '<br>')}</div>"
                
                # 2. Handle Attachments (in Description)
                attachments = fields.get('attachment', [])
                if attachments:
                    content_html += "<hr><h3>Attachments</h3><ul>"
                    for att in attachments:
                        filename = att.get('filename')
                        content_url = att.get('content')
                        print(f"    - Downloading attachment: {filename}...")
                        
                        file_data = jira.get_attachment_content(content_url)
                        if file_data:
                            # Save temp
                            temp_path = os.path.join(os.getcwd(), filename)
                            with open(temp_path, 'wb') as f:
                                f.write(file_data)
                            
                            # Upload to GLPI
                            doc_id, doc_url = glpi.upload_document(temp_path)
                            
                            # Cleanup
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                                
                            if doc_url:
                                content_html += f"<li><a href='{doc_url}' target='_blank'>{filename}</a></li>"
                            else:
                                content_html += f"<li>{filename} (Upload Failed)</li>"
                        else:
                            content_html += f"<li>{filename} (Download Failed)</li>"
                    content_html += "</ul>"

                # 3. Create GLPI Ticket
                print(f"    -> Creating GLPI Ticket...")
                ticket_id = glpi.create_ticket(f"[{key}] {summary}", content_html)
                
                if ticket_id:
                    print(f"       Success! Ticket ID: {ticket_id}")
                    
                    # 4. Migrate Comments
                    comments = fields.get('comment', {}).get('comments', [])
                    if comments:
                        print(f"       Migrating {len(comments)} comments...")
                        for comment in comments:
                            author = comment.get('author', {}).get('displayName', 'Unknown')
                            body = comment.get('body', '')
                            created = comment.get('created')
                            
                            comment_html = f"<p><b>[{created}] {author} wrote:</b></p>"
                            comment_html += f"<div>{body.replace(chr(10), '<br>')}</div>"
                            
                            glpi.add_ticket_followup(ticket_id, comment_html)
                else:
                    print(f"       Failed to create ticket for {key}")

                time.sleep(0.1) # Brief pause/throttle
                
                total_processed += 1
            
            # Update Batch Progress
            start_at += len(issues)
            save_state(start_at, total_processed)
            
        print("\nMigration Completed Successfully!")
        
    except KeyboardInterrupt:
        print("\nMigration Paused by User.")
        save_state(start_at, total_processed)
    except Exception as e:
        print(f"\nMigration Failed: {e}")
        save_state(start_at, total_processed) # Save progress even on crash
    finally:
        glpi.kill_session()

if __name__ == "__main__":
    main()
