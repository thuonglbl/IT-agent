import os
import json
import time
import requests
import re
import datetime
import config
from jira_client import JiraClient
from glpi_api import GlpiClient

# --- Constants ---
STATE_FILE = config.STATE_FILE
MAPPING_FILE = config.MAPPING_FILE

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

def load_mapping():
    """Load Jira Key -> GLPI ID mapping from file."""
    if os.path.exists(MAPPING_FILE):
        try:
            with open(MAPPING_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not read mapping file: {e}")
    return {}

def save_mapping(mapping):
    """Save Jira Key -> GLPI ID mapping to file."""
    try:
        with open(MAPPING_FILE, 'w') as f:
            json.dump(mapping, f, indent=4)
    except Exception as e:
        print(f"Warning: Could not save mapping file: {e}")

def parse_jira_date(date_str, format_str="%Y-%m-%d %H:%M:%S"):
    """
    Parse Jira date string '2014-03-04T09:46:56.000+0100' 
    to GLPI format (default: 'YYYY-MM-DD HH:MM:SS')
    """
    if not date_str:
        return None
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        # Convert to Local System Timezone
        dt_local = dt.astimezone()
        return dt_local.strftime(format_str)
    except ValueError:
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
            dt_local = dt.astimezone()
            return dt_local.strftime(format_str)
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
    reporter = (fields.get('reporter') or {}).get('displayName', 'Unknown')
    priority = (fields.get('priority') or {}).get('name', 'None')
    
    # Dates (Formatted)
    # Match Jira style: "19/Jun/14 3:40 PM"
    date_fmt = "%d/%b/%y %I:%M %p"
    created = parse_jira_date(fields.get('created'), date_fmt)
    updated = parse_jira_date(fields.get('updated'), date_fmt)
    resolved = parse_jira_date(fields.get('resolutiondate'), date_fmt)
    
    # ... (snip) ...

    # Lists & Other Fields
    resolution = (fields.get('resolution') or {}).get('name')
    security = (fields.get('security') or {}).get('name')
    labels = ", ".join(fields.get('labels', []))
    
    affects_versions = ", ".join([v.get('name') for v in fields.get('versions', [])])
    fix_versions = ", ".join([v.get('name') for v in fields.get('fixVersions', [])])
    components = ", ".join([c.get('name') for c in fields.get('components', [])])
    environment = fields.get('environment', '')

    # Custom Fields Mapping (Dynamic)
    # Iterate over ALL fields in config.JIRA_CUSTOM_FIELDS
    # and add non-empty values to the Details section.
    custom_fields_html = ""
    for field_key, field_id in config.JIRA_CUSTOM_FIELDS.items():
        if not field_id:
            continue
        
        raw_value = fields.get(field_id)
        
        # Skip empty values
        if raw_value is None or raw_value == '' or raw_value == [] or raw_value == {}:
            continue
        
        # Format the label: "change_details" -> "Change Details"
        label = field_key.replace("_", " ").title()
        
        # Extract display value based on type
        display_value = ""
        
        if isinstance(raw_value, dict):
            # Most Jira select fields return {value: "X", id: "Y"}
            display_value = raw_value.get('value') or raw_value.get('name') or raw_value.get('displayName') or str(raw_value)
        
        elif isinstance(raw_value, list):
            # Could be Sprint, Labels, or multi-select
            parts = []
            for item in raw_value:
                if isinstance(item, dict):
                    parts.append(item.get('value') or item.get('name') or item.get('displayName') or str(item))
                elif isinstance(item, str):
                    # Sprint special format: 'com.atlassian.greenhopper....[name=Sprint 1,id=1...]'
                    sprint_match = re.search(r'name=([^,\]]+)', item)
                    if sprint_match:
                        parts.append(sprint_match.group(1))
                    else:
                        parts.append(item)
                else:
                    parts.append(str(item))
            display_value = ", ".join(parts) if parts else ""
        
        elif isinstance(raw_value, (int, float)):
            display_value = str(raw_value)
        
        elif isinstance(raw_value, str):
            display_value = raw_value
        
        else:
            display_value = str(raw_value)
        
        # Only add if we got a meaningful value
        if display_value and display_value.strip():
            custom_fields_html += f"<p><b>{label}:</b> {display_value}</p>"


    # Section 1: Header
    content_html = f"<p><b>Original Jira Key:</b> {key}</p>"
    
    # Section 2: People
    content_html += "<hr>"
    content_html += f"<h3>People</h3>"
    assignee = (fields.get('assignee') or {}).get('displayName', 'Unassigned')
    content_html += f"<p><b>Assignee:</b> {assignee}</p>" 
    content_html += f"<p><b>Reporter:</b> {reporter}</p>"

    # Section 3: Dates
    content_html += "<hr>"
    content_html += f"<h3>Dates</h3>"
    # UTC+7 suffix is hardcoded here
    content_html += f"<p><b>Created:</b> {created} UTC+7</p>"
    if updated:
        content_html += f"<p><b>Updated:</b> {updated} UTC+7</p>"
    if resolved:
        content_html += f"<p><b>Resolved:</b> {resolved} UTC+7</p>"

    # Section 4: Details (Priority, etc.)
    content_html += "<hr>"
    content_html += f"<h3>Details</h3>"
    content_html += f"<p><b>Priority:</b> {priority}</p>"
    
    if resolution: content_html += f"<p><b>Resolution:</b> {resolution}</p>"
    if security:   content_html += f"<p><b>Security Level:</b> {security}</p>"
    
    # Standard Jira fields (not custom fields)
    if fix_versions:     content_html += f"<p><b>Fix Version/s:</b> {fix_versions}</p>"
    if affects_versions: content_html += f"<p><b>Affects Version/s:</b> {affects_versions}</p>"
    if components:       content_html += f"<p><b>Component/s:</b> {components}</p>"
    if labels:           content_html += f"<p><b>Labels:</b> {labels}</p>"
    if environment:      content_html += f"<p><b>Environment:</b> {environment}</p>"

    # Add all custom fields with values (dynamic from config.JIRA_CUSTOM_FIELDS)
    if custom_fields_html:
        content_html += custom_fields_html

    # Section 5: Description
    content_html += "<hr><h3>Description</h3>"
    content_html += f"<div>{description.replace(chr(10), '<br>')}</div>"
    
    return content_html

def process_changelog(issue, glpi):
    """
    Parse changelog to create a History Log HTML.
    Includes "Issue Created" event.
    """
    changelog = issue.get('changelog', {})
    histories = changelog.get('histories', [])
    
    # Prepend "Issue Created" event
    fields = issue.get('fields', {})
    created_date = fields.get('created')
    reporter_display = (fields.get('reporter') or {}).get('displayName', 'Unknown')
    reporter_name = (fields.get('reporter') or {}).get('name')
    
    # Construct a history item for Creation
    creation_event = {
        'created': created_date,
        'author': {
            'displayName': reporter_display,
            'name': reporter_name
        },
        'items': [{
            'field': 'Issue',
            'fromString': '',
            'toString': 'Created'
        }]
    }
    
    # Combine
    all_events = histories + [creation_event]
    
    # Sort by Date DESC (Newest First) to match Jira UI
    # Jira dates are ISO strings, so string comparison works for sorting
    all_events.sort(key=lambda x: x.get('created'), reverse=True)
    
    html = "<h3>Jira History Log</h3>"
    html += "<table border='1' style='border-collapse: collapse; width: 100%;'>"
    html += "<tr><th>Date Time</th><th>Author</th><th>Field</th><th>From</th><th>To</th></tr>"
    
    for history in all_events:
        created = history.get('created')
        author_display = (history.get('author') or {}).get('displayName', 'Unknown')
        author_name = (history.get('author') or {}).get('name')
        items = history.get('items', [])
        
        # Parse date nicely matching Jira format: "19/Jun/14 3:40 PM"
        # And append UTC+7
        date_fmt = "%d/%b/%y %I:%M %p"
        base_date = parse_jira_date(created, date_fmt) or created
        formatted_date = f"{base_date} UTC+7" if base_date else ""
        
        # Linkify Author
        author_html = author_display
        base_glpi_url = glpi.url.replace('/api.php/v1', '')
        
        uid = None
        if author_name:
            uid = glpi.get_user_id_by_name(author_name)
            if not uid:
                print(f"       [DEBUG-HIST] User lookup failed for login '{author_name}' (Display: {author_display})")
        
        # Fallback to Display Name lookup if failed
        if not uid and author_display:
             uid = glpi.get_user_id_by_name(author_display)
             if not uid:
                 print(f"       [DEBUG-HIST] Fallback lookup also failed for display '{author_display}'")
             
        if uid:
            author_html = f"<a href='{base_glpi_url}/front/user.form.php?id={uid}' target='_blank'>{author_display}</a>"

        for item in items:
            field = item.get('field', '')
            from_str = item.get('fromString', '')
            to_str = item.get('toString', '')
            
            # Escape HTML just in case
            from_str = str(from_str).replace("<", "&lt;").replace(">", "&gt;") if from_str else ""
            to_str = str(to_str).replace("<", "&lt;").replace(">", "&gt;") if to_str else ""
            
            html += f"<tr>"
            html += f"<td>{formatted_date}</td>"
            html += f"<td>{author_html}</td>"
            html += f"<td>{field}</td>"
            html += f"<td>{from_str}</td>"
            html += f"<td>{to_str}</td>"
            html += f"</tr>"
            
    html += "</table>"
    return html

def get_hex_color(color_name):
    """
    Map Jira color names to Hex values.
    Handles both legacy (Server) and modern (Cloud) color names.
    Uses config.JIRA_COLOR_MAP for mapping.
    """
    default_color = config.JIRA_COLOR_MAP.get("default", "#42526E")

    if not color_name:
        return default_color
        
    c = color_name.lower().replace(" ", "").replace("-", "")
    return config.JIRA_COLOR_MAP.get(c, default_color)

def run_preparation(glpi, jira):
    print("\n[PREPARATION] Starting automated environment setup...")
    
    # 1. Sync Statuses
    print("\n--- 1. Syncing Project Statuses ---")
    # 1a. Clear existing
    glpi.delete_all_items("ProjectState")
    
    # 1b. Fetch Jira Statuses
    print("  > Fetching Statuses from Jira...")
    jira_statuses = jira.get_project_statuses(config.JIRA_PROJECT_KEY)
    
    # 1c. Create in GLPI
    for s in jira_statuses:
        name = s['name']
        color_name = s['statusCategory'].get('colorName')
        is_finished = 1 if s['statusCategory'].get('key') == 'done' else 0
        hex_color = get_hex_color(color_name)
        
        print(f"  > Creating Status '{name}' (Color: {color_name}/{hex_color}, Finished: {is_finished})...")
        glpi.create_project_state(name, hex_color, is_finished)
        time.sleep(0.2)
        
    # 2. Sync Types
    print("\n--- 2. Syncing Project Task Types ---")
    # 2a. Clear existing
    glpi.delete_all_items("ProjectTaskType")
    
    # 2b. Fetch Jira Types
    print("  > Fetching Issue Types from Jira...")
    jira_types = jira.get_project_issue_types(config.JIRA_PROJECT_KEY)
    
    # 2c. Create in GLPI
    for t in jira_types:
        name = t['name']
        print(f"  > Creating Type '{name}'...")
        glpi.create_project_task_type(name)
        time.sleep(0.2)

        
    print("\n[PREPARATION] Completed.\n")

def main():
    print(f"--- Jira to GLPI Migration Tool (ProjecTask + Notes) ---")
    
    # 1. Init Connections
    try:
        jira = JiraClient(config.JIRA_URL, config.JIRA_PAT, verify_ssl=config.JIRA_VERIFY_SSL)
        # Init GLPI Client with both User Token (Primary) and Basic Auth (Fallback)
        glpi = GlpiClient(
            config.GLPI_URL, 
            config.GLPI_APP_TOKEN, 
            user_token=config.GLPI_USER_TOKEN,
            username=config.GLPI_USERNAME,
            password=config.GLPI_PASSWORD,
            verify_ssl=config.GLPI_VERIFY_SSL
        )
        
        glpi.init_session()
        print("-> GLPI Connection: OK")
        
        # Load user cache for fast lookups
        glpi.load_user_cache()
        
        # Resolve Project ID for configured project
        target_project_name = config.GLPI_PROJECT_NAME
        print(f"Resolving GLPI Project '{target_project_name}'...")
        project_id = glpi.get_project_id_by_name(target_project_name)
        if not project_id:
            print(f"[ERROR] Project '{target_project_name}' not found!")
            return
        print(f"-> Found Project ID: {project_id}")
        
        # --- PROACTIVE PREPARATION ---
        # Run preparation only if state file doesn't exist (First Run)
        if not os.path.exists(STATE_FILE):
             run_preparation(glpi, jira)
        
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
    
    # Store Jira Key -> GLPI Project Task ID for Parent-Child linking
    jira_map = load_mapping()
    print(f"Loaded {len(jira_map)} existing ID mappings.")

    jql = config.JIRA_JQL
    print(f"Using JQL: {jql}")
    
    try:
        # Get total count first
        total_issues = jira.get_issue_count(jql)
        print(f"Total Issues to Migrate: {total_issues}")
        print(f"Resuming from: {start_at}")

        while start_at < total_issues:
            # Determine max results based on Debug mode
            fetch_limit = config.BATCH_SIZE
            
            if config.DEBUG:
                print(f"\n[DEBUG] Fetching 1 batch for testing...")
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
                assignee_data = fields.get('assignee') or {}
                assignee_name = assignee_data.get('name') # Username used for mapping
                assignee_display = assignee_data.get('displayName', assignee_name)
                
                assignee_id = None
                if assignee_name:
                    assignee_id = glpi.get_user_id_by_name(assignee_name)
                    if assignee_id:
                        print(f"    -> Mapped Assignee '{assignee_display}' (User: {assignee_name}) to GLPI ID {assignee_id}")
                    else:
                        print(f"    [WARN] Assignee '{assignee_name}' not found in GLPI via Username.")

                # Reporter -> Requester (for Task Team)
                reporter_data = fields.get('reporter') or {}
                reporter_name = reporter_data.get('name') # Username used for mapping
                reporter_display = reporter_data.get('displayName', reporter_data.get('name'))
                
                reporter_id = None
                if reporter_name:
                    reporter_id = glpi.get_user_id_by_name(reporter_name)
                    if reporter_id:
                         print(f"    -> Mapped Reporter '{reporter_display}' (User: {reporter_name}) to GLPI ID {reporter_id}")
                    else:
                         print(f"    [WARN] Reporter '{reporter_name}' not found in GLPI via Username.")

                # Status Mapping (Dynamic & Case-Insensitive)
                jira_status = (fields.get('status') or {}).get('name', 'Open')
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
                jira_type = (fields.get('issuetype') or {}).get('name', 'Task')
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
                
                # Urgency Mapping - For Task Field
                urgency_field_id = config.JIRA_CUSTOM_FIELDS.get("urgency")
                urgency_raw = (fields.get(urgency_field_id) or {}).get('value', 'Medium') if urgency_field_id else 'Medium'
                urgency_map = {'Low': 2, 'Medium': 3, 'High': 4, 'Very High': 5, 'Critical': 5, 'Blocker': 5, 'Serious': 4}
                urgency_val = urgency_map.get(urgency_raw, 3)

                task_kwargs = {
                    "projectstates_id": glpi_state_id,
                    "percent_done": 100 if jira_status_lower in ['resolved', 'closed', 'done'] else 0,
                    "urgency": urgency_val,
                    "real_start_date": "NULL", # string literal NULL to force unset
                    "real_end_date": "NULL"
                }
                # map Jira Created -> GLPI 'date'
                if glpi_date:
                    task_kwargs['date'] = glpi_date
                    task_kwargs['date_creation'] = glpi_date
                
                if assignee_id:
                     task_kwargs['users_id_tech'] = assignee_id
                
                # Note: 'users_id' in ProjectTask usually means 'Created By'. 
                # We can map Reporter to it, but also add to Team.
                if reporter_id:
                     task_kwargs['users_id'] = reporter_id
                
                if glpi_type_id:
                     task_kwargs['projecttasktypes_id'] = glpi_type_id
                
                # Parent-Child Linking
                # If issue has a parent, try to find its GLPI ID from our map
                parent_field = fields.get('parent')
                if parent_field:
                    parent_key = parent_field.get('key')
                    if parent_key:
                        parent_glpi_id = jira_map.get(parent_key)
                        if parent_glpi_id:
                            print(f"    -> Linking as child of {parent_key} (GLPI ID: {parent_glpi_id})")
                            task_kwargs['projecttasks_id'] = parent_glpi_id
                        else:
                            print(f"    [WARN] Parent {parent_key} not found in current map (maybe not processed yet?)")

                task_id = glpi.create_project_task(project_id, task_name, content_html, **task_kwargs)
                
                if task_id:
                    print(f"       Success! Project Task ID: {task_id}")
                    
                    # Store in Map for children
                    jira_map[key] = task_id
                    
                    # Add to Task Team
                    if assignee_id:
                        glpi.add_project_task_team_member(task_id, assignee_id)
                    if reporter_id and reporter_id != assignee_id:
                        glpi.add_project_task_team_member(task_id, reporter_id)

                    # 7. Migrate Comments & History
                    failed_notes = []
                    
                    # 7a. History (Migrate FIRST so it appears at the bottom/oldest in GLPI)
                    history_html = process_changelog(issue, glpi)
                    if history_html:
                        print("       Migrating History Log...")
                        if not glpi.create_note("ProjectTask", task_id, history_html):
                             print("          -> History Note creation failed. Queueing for description append.")
                             # If note fails, we append to Description later.
                             # But here we just want to ensure it's created first.
                             failed_notes.append(history_html)

                    # 7b. Comments
                    comments = (fields.get('comment') or {}).get('comments', [])
                    if comments:
                        print(f"       Migrating {len(comments)} comments as Notes...")
                        for comment in comments:
                            author_login = (comment.get('author') or {}).get('name') 
                            body = comment.get('body', '')
                            created = comment.get('created')
                            display_name = (comment.get('author') or {}).get('displayName') or author_login
                            
                            comment_author_id = None
                            if author_login:
                                # Try to map by login first, then display name
                                comment_author_id = glpi.get_user_id_by_name(author_login)
                                if not comment_author_id and display_name:
                                     comment_author_id = glpi.get_user_id_by_name(display_name)
                            
                            # Format Date: "19/Jun/14 3:40 PM UTC+7"
                            date_fmt = "%d/%b/%y %I:%M %p"
                            formatted_date = parse_jira_date(created, date_fmt) or created
                            if formatted_date and not formatted_date.endswith("UTC+7"):
                                formatted_date = f"{formatted_date} UTC+7"

                            # Linkify Author for Comment Header using BASE URL (strip /api.php/v1)
                            # User Link: .../front/user.form.php?id=ID
                            base_glpi_url = glpi.url.replace('/api.php/v1', '')
                            author_html = display_name
                            
                            if comment_author_id:
                                author_html = f"<a href='{base_glpi_url}/front/user.form.php?id={comment_author_id}' target='_blank'>{display_name}</a>"

                            # Build Note content (HTML)
                            note_html = f"<p><b>{author_html} added a comment - {formatted_date}</b></p>"
                            note_html += f"<div>{body.replace(chr(10), '<br>')}</div>"
                            
                            kw = {}
                            if comment_author_id: 
                                kw['users_id'] = comment_author_id

                            # Create Note
                            glpi.create_note("ProjectTask", task_id, note_html, **kw)
                             
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
            save_mapping(jira_map)

            # DEBUG 
            if config.DEBUG:
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
