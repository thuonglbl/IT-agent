import os
import json
import re
import time
import requests
from datetime import datetime, timedelta, timezone
import config
from jira_client import JiraClient
from glpi_client_support import GlpiClient

# Define UTC+7 Timezone
TZ_VN = timezone(timedelta(hours=7))

# Track missing users (login -> display_name) across the entire run
_missing_users = {}

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
    if not date_str: return None
    try:
        if '.' in date_str:
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
        dt_vn = dt.astimezone(TZ_VN)
        return dt_vn.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
             dt = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
             return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return None

def format_glpi_date_friendly(date_str):
    if not date_str: return "N/A"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d %I:%M %p (UTC+7)")
    except:
        return f"{date_str} (UTC+7)"

def format_comment_date(date_str):
    """
    Format for Comment Header: dd/Mon/yy h:mm AM/PM (UTC+7)
    Example: 15/Jan/24 4:58 PM (UTC+7)
    """
    if not date_str: return "N/A"
    try:
        # Parse ISO with Timezone
        if '.' in date_str:
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
        
        # Convert to UTC+7
        dt_vn = dt.astimezone(TZ_VN)
        
        # Format: 15/Jan/24 4:58 PM
        return dt_vn.strftime("%d/%b/%y %I:%M %p (UTC+7)")
    except ValueError:
        return f"{date_str} (UTC+7)"

def process_attachments(glpi, jira_headers, jira_verify_ssl, attachments):
    """
    Download attachments from Jira and upload to GLPI.
    Returns map: {filename: doc_id}
    """
    attachment_map = {}
    if not attachments:
        return attachment_map
    
    print(f"  Processing {len(attachments)} attachments...")
    for att in attachments:
        filename = att.get('filename')
        url = att.get('content')
        if not filename or not url: continue
        
        # Avoid processing same filename twice (though unlikely in same ticket)
        if filename in attachment_map: continue
        
        # Download
        try:
             # Use a temp prefix to avoid conflicts
             temp_path = f"temp_{filename}"
             
             with requests.get(url, headers=jira_headers, verify=jira_verify_ssl, stream=True) as r:
                 r.raise_for_status()
                 with open(temp_path, 'wb') as f:
                     for chunk in r.iter_content(chunk_size=8192):
                         f.write(chunk)
             
             # Upload to GLPI
             doc_id = glpi.upload_document(temp_path, name=filename)
             if doc_id:
                 attachment_map[filename] = doc_id
                 print(f"    Uploaded '{filename}' -> Doc ID {doc_id}")
             
             # Cleanup
             if os.path.exists(temp_path):
                 os.remove(temp_path)
                 
        except Exception as e:
            print(f"    Failed to process attachment '{filename}': {e}")
            if os.path.exists(temp_path):
                 os.remove(temp_path)
                 
    return attachment_map

def convert_jira_content(text, attachment_map):
    """
    Convert Jira Textile to HTML:
    1. Links: [Label|URL] -> <a href>
    2. Images: !filename! -> <img src>
    """
    if not text:
        return ""
    
    # 1. Images: !filename! or !filename|thumbnail!
    # Regex matches !...|...! or !...!
    def replace_image(match):
        full_tag = match.group(0) # e.g. !image.png|thumbnail!
        filename = match.group(1) # e.g. image.png
        
        # If filename in map, replace with generic GLPI document link
        if filename in attachment_map:
            doc_id = attachment_map[filename]
            # Use GLPI document send endpoint
            src = f"/front/document.send.php?docid={doc_id}"
            return f'<img src="{src}" alt="{filename}" style="max-width: 100%;" />'
        
        return full_tag # Keep original if not found

    # Regex: ! (filename) [| options] !
    # Non-greedy match for filename until | or !
    text = re.sub(r'!([^|!]+)(?:\|[^!]+)?!', replace_image, text)

    # 2. Links: [Label|URL]
    text = re.sub(r'\[([^|\]\n]+)\|([^\]\n]+)\]', r'<a href="\2">\1</a>', text)
    
    # 3. Bare Links: [URL]
    text = re.sub(r'\[(https?://[^\]\n]+)\]', r'<a href="\1">\1</a>', text)
    
    return text

def extract_history_table(issue, glpi):
    """
    Extract Jira Changelog and format as HTML Table.
    Columns: User, Date, Field, Original, New
    """
    changelog = issue.get('changelog', {})
    histories = changelog.get('histories', [])
    
    rows = ""
    # Sort histories by created date desc (newest first)
    
    for history in reversed(histories):
        author = history.get('author', {})
        author_name = author.get('displayName', 'Unknown')
        author_key = author.get('name', '') # Username 
        created_str = format_comment_date(history.get('created'))
        
        # Link to User in GLPI
        user_id = glpi.get_user_id_by_name(author_key)
        
        if user_id:
            # GLPI User Link
            # Strip api endpoint from config URL to get base URL
            base_url = config.GLPI_URL.replace('/api.php/v1', '').rstrip('/')
            user_link = f'<a href="{base_url}/front/user.form.php?id={user_id}">{author_name}</a>'
        else:
            # Fallback: Just name (or GLPI link)
            user_link = author_name
            
        items = history.get('items', [])
        for item in items:
            field = item.get('field', '')
            original = item.get('fromString', '')
            if not original: original = ""
            new_val = item.get('toString', '')
            if not new_val: new_val = ""
            
            # Truncate very long text.
            
            rows += f"""
            <tr>
                <td>{user_link}</td>
                <td>{created_str}</td>
                <td>{field}</td>
                <td>{original}</td>
                <td>{new_val}</td>
            </tr>
            """
            
    # Manually add "Created" event at the end (Oldest)
    fields = issue.get('fields', {})
    reporter = fields.get('reporter', {})
    reporter_name = reporter.get('displayName', 'Unknown')
    reporter_key = reporter.get('name', '')
    created_date = format_comment_date(fields.get('created'))
    
    # Link Reporter
    rep_id = glpi.get_user_id_by_name(reporter_key)
    if rep_id:
        base_url = config.GLPI_URL.replace('/api.php/v1', '').rstrip('/')
        rep_link = f'<a href="{base_url}/front/user.form.php?id={rep_id}">{reporter_name}</a>'
    else:
        rep_link = reporter_name
        
    rows += f"""
        <tr>
            <td>{rep_link}</td>
            <td>{created_date}</td>
            <td>Issue</td>
            <td></td>
            <td>Created</td>
        </tr>
    """

    if not rows:
        return ""
        
    return f"""
    <h3>History</h3>
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <tr>
            <th style="background-color: #f2f2f2;">User</th>
            <th style="background-color: #f2f2f2;">Date</th>
            <th style="background-color: #f2f2f2;">Field</th>
            <th style="background-color: #f2f2f2;">Original</th>
            <th style="background-color: #f2f2f2;">New</th>
        </tr>
        {rows}
    </table>
    """

def report_missing_user(login_name, display_name):
    """Track a missing user. Each user is reported only once."""
    if not login_name or login_name in _missing_users:
        return
    _missing_users[login_name] = display_name or login_name
    print(f"    [MISSING USER] {login_name} ({display_name})")

def save_missing_users_report():
    """Write missing users to a tab-separated text file."""
    if not _missing_users:
        print("No missing users to report.")
        return
    filepath = getattr(config, 'MISSING_USERS_FILE', 'missing_users.txt')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("Login Name\tFull Name\n")
        for login, display in sorted(_missing_users.items()):
            f.write(f"{login}\t{display}\n")
    print(f"\n[REPORT] {len(_missing_users)} missing users written to {filepath}")

def main():
    print("--- Jira Support to GLPI Assistance Migration ---")
    
    jira = JiraClient(config.JIRA_URL, config.JIRA_PAT, verify_ssl=config.JIRA_VERIFY_SSL)
    glpi = GlpiClient(
        config.GLPI_URL, 
        config.GLPI_APP_TOKEN, 
        user_token=config.GLPI_USER_TOKEN,
        username=config.GLPI_USERNAME,
        password=config.GLPI_PASSWORD,
        verify_ssl=config.GLPI_VERIFY_SSL
    )
    
    try:
        glpi.init_session()
        glpi.load_user_cache(recursive=True) 
        glpi.load_group_cache(recursive=True)
        glpi.load_category_cache(recursive=True)
        
        # Status Mapping
        jira_statuses = jira.get_project_statuses(config.JIRA_PROJECT_KEY)
        glpi_status_map = glpi.get_status_id_map()
        DYNAMIC_MAPPING = config.STATUS_MAPPING.copy()
        for s in jira_statuses:
            lower = s['name'].lower()
            if lower in glpi_status_map:
                DYNAMIC_MAPPING[lower] = glpi_status_map[lower]
        
        state = load_state()
        start_at = state["start_at"]
        total_processed = state["total_processed"]
        
        print(f"Resuming from {start_at}...")
        
        # --- Preparation: Ensure ITIL Categories exist for Jira Security Levels ---
        if start_at == 0:
            print("\n--- Preparation: Syncing Security Levels -> ITIL Categories ---")
            sec_levels = jira.get_project_security_levels(config.JIRA_PROJECT_KEY)
            for level in sec_levels:
                level_name = level.get('name')
                if level_name:
                    glpi.get_or_create_category(level_name)
            print("--- Preparation Complete ---\n")
        
        while True:
            jql = f"project = {config.JIRA_PROJECT_KEY} ORDER BY key ASC"
            issues, total = jira.search_issues(jql, start_at=start_at, max_results=config.BATCH_SIZE)
            if not issues: break
                
            for issue in issues:
                process_issue(jira, glpi, issue, DYNAMIC_MAPPING)
                total_processed += 1
                
                if config.DEBUG:
                    print("[DEBUG] Processed 1 issue. Saving state and Exiting.")
                    save_state(start_at + 1, total_processed)
                    return
                
            start_at += len(issues)
            save_state(start_at, total_processed)
            print(f"  [State Saved] Next batch at {start_at}")
            
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
    finally:
        save_missing_users_report()
        glpi.kill_session()

def process_issue(jira, glpi, issue, status_mapping):
    key = issue['key']
    fields = issue['fields']
    
    summary = fields.get('summary', '[No Title]')
    description = fields.get('description') or ""
    
    # --- Map Users ---
    reporter_jira = (fields.get('reporter') or {}).get('name')
    reporter_display = (fields.get('reporter') or {}).get('displayName', reporter_jira)
    
    assignee_jira = (fields.get('assignee') or {}).get('name')
    assignee_display = (fields.get('assignee') or {}).get('displayName', assignee_jira) or 'Unassigned'
    
    requester_id = glpi.get_user_id_by_name(reporter_jira)
    if reporter_jira and not requester_id:
        report_missing_user(reporter_jira, reporter_display)
    
    assignee_id = glpi.get_user_id_by_name(assignee_jira)
    if assignee_jira and not assignee_id:
        report_missing_user(assignee_jira, assignee_display)

    # --- Map Status & Type ---
    status_jira = (fields.get('status') or {}).get('name', '').lower()
    glpi_status = status_mapping.get(status_jira, config.DEFAULT_STATUS)
    
    type_jira = (fields.get('issuetype') or {}).get('name', '').lower()
    glpi_type = config.TYPE_MAPPING.get(type_jira, config.DEFAULT_TYPE)
    
    creation_date = parse_jira_date(fields.get('created'))
    update_date = parse_jira_date(fields.get('updated'))
    resolution_date = parse_jira_date(fields.get('resolutiondate'))
    
    print(f"Migrating {key}: {summary}...")

    # --- Process Attachments FIRST ---
    attachments = fields.get('attachment', [])
    attachment_map = process_attachments(glpi, jira.headers, jira.verify_ssl, attachments)

    # --- Generate Description ---
    issue_type = (fields.get('issuetype') or {}).get('name', 'Ticket')
    priority = (fields.get('priority') or {}).get('name', 'Normal')
    components = ", ".join([c.get('name') for c in fields.get('components', [])])
    
    classification_raw = fields.get(getattr(config, 'CLASSIFICATION_ID', ''))
    classification = ", ".join(classification_raw) if isinstance(classification_raw, list) else str(classification_raw or '')
    reporter_details = fields.get(getattr(config, 'REPORTER_DETAILS_ID', ''), '')
    resolution = (fields.get('resolution') or {}).get('name', 'Unresolved')
    security = (fields.get('security') or {}).get('name', 'None')
    
    # --- Participants ---
    participants_raw = fields.get(getattr(config, 'REQUEST_PARTICIPANTS_ID', ''))
    participant_ids = []  # GLPI user IDs for observer mapping
    if isinstance(participants_raw, list):
         participant_names = []
         for p in participants_raw:
             p_login = p.get('name', '')
             p_display = p.get('displayName', p_login)
             participant_names.append(p_display)
             p_id = glpi.get_user_id_by_name(p_login)
             if p_id:
                 participant_ids.append(p_id)
             elif p_login:
                 report_missing_user(p_login, p_display)
         participants = ", ".join(participant_names)
    else:
         participants = str(participants_raw) if participants_raw else "None"

    # --- Approvers ---
    approvers_raw = fields.get(getattr(config, 'APPROVERS_ID', ''))
    if isinstance(approvers_raw, list):
        approvers = ", ".join([a.get('displayName', a.get('name', '')) for a in approvers_raw])
    elif isinstance(approvers_raw, dict):
        approvers = approvers_raw.get('displayName', approvers_raw.get('name', 'N/A'))
    else:
        approvers = str(approvers_raw) if approvers_raw else "None"

    # --- Past Approvals ---
    past_approvals_html = ""
    approval_data = fields.get(getattr(config, 'APPROVALS_ID', ''))
    
    if approval_data and isinstance(approval_data, list):
        approval_rows = ""
        for approval in approval_data:
            if isinstance(approval, dict):
                # Use finalDecision as the status (e.g. "approved", "declined")
                decision = approval.get('finalDecision', '').capitalize()
                approver_name = ''
                approvers_list = approval.get('approvers', [])
                if isinstance(approvers_list, list):
                    names = []
                    for apr in approvers_list:
                        if isinstance(apr, dict):
                            a_data = apr.get('approver', apr)
                            names.append(a_data.get('displayName', a_data.get('name', 'Unknown')))
                    approver_name = ', '.join(names)
                
                # Get date and strip time portion (e.g. "26/Jan/24 7:14 PM" -> "26/Jan/24")
                created = approval.get('createdDate', {}).get('friendly', '') if isinstance(approval.get('createdDate'), dict) else ''
                completed = approval.get('completedDate', {}).get('friendly', '') if isinstance(approval.get('completedDate'), dict) else ''
                date_str = completed or created
                date_only = date_str.split(' ')[0] if date_str else ''  # "26/Jan/24"
                
                approval_rows += f"<tr><td>{decision}</td><td>{approver_name}</td><td>{date_only}</td></tr>"
        
        if approval_rows:
            past_approvals_html = f"""
    <h3>Past Approvals</h3>
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <tr>
            <th style="background-color: #f2f2f2;">Status</th>
            <th style="background-color: #f2f2f2;">Approver</th>
            <th style="background-color: #f2f2f2;">Date</th>
        </tr>
        {approval_rows}
    </table>
    """

    req_type_data = fields.get(getattr(config, 'CUSTOMER_REQUEST_TYPE_ID', ''))
    request_type_name = "N/A"
    channel = "N/A"
    customer_status = "N/A"
    if req_type_data:
        request_type_name = (req_type_data.get('requestType') or {}).get('name', 'N/A')
        channel = "Portal" 
        customer_status = (req_type_data.get('currentStatus') or {}).get('status', 'N/A')

    # --- SLA Extraction ---
    sla_info_rows = ""
    if hasattr(config, 'SLA_FIELDS'):
        for sla_id in config.SLA_FIELDS:
            sla_data = fields.get(sla_id)
            if sla_data and isinstance(sla_data, dict):
                name = sla_data.get('name', 'Unknown SLA')
                completed_list = sla_data.get('completedCycles')
                ongoing = sla_data.get('ongoingCycle')
                
                if completed_list:
                    last_cycle = completed_list[-1]
                    breached = last_cycle.get('breached', False)
                    status_html = "<span style='color:red'>Breached</span>" if breached else "<span style='color:green'>Met</span>"
                    goal_str = (last_cycle.get('goalDuration') or {}).get('friendly', 'FAIL')
                    actual_str = (last_cycle.get('remainingTime') or {}).get('friendly', 'FAIL')
                    sla_info_rows += f"<tr><td>{name}</td><td>{status_html}</td><td>{goal_str}</td><td>{actual_str}</td></tr>"
                elif ongoing:
                    status_html = "<span style='color:orange'>In Progress</span>"
                    goal_str = (ongoing.get('goalDuration') or {}).get('friendly', '')
                    actual_str = (ongoing.get('remainingTime') or {}).get('friendly', '')
                    sla_info_rows += f"<tr><td>{name}</td><td>{status_html}</td><td>{goal_str}</td><td>{actual_str}</td></tr>"

    if not sla_info_rows:
        sla_info_rows = "<tr><td colspan='4'>No SLA Data</td></tr>"

    # --- History Extraction ---
    html_history = extract_history_table(issue, glpi)

    html_details = f"""
    <h3>Jira Details</h3>
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <tr><th style="background-color: #f2f2f2; width: 30%;">Field</th><th style="background-color: #f2f2f2;">Value</th></tr>
        <tr><td><strong>Key</strong></td><td><a href="{config.JIRA_URL}/browse/{key}">{key}</a></td></tr>
        <tr><td><strong>Type</strong></td><td>{issue_type}</td></tr>
        <tr><td><strong>Priority</strong></td><td>{priority}</td></tr>
        <tr><td><strong>Resolution</strong></td><td>{resolution}</td></tr>
        <tr><td><strong>Component</strong></td><td>{components}</td></tr>
        <tr><td><strong>Classification</strong></td><td>{classification}</td></tr>
        <tr><td><strong>Security Level</strong></td><td>{security}</td></tr>
        <tr><td><strong>Reporter Details</strong></td><td>{reporter_details}</td></tr>
    </table>
    """

    html_people = f"""
    <h3>People</h3>
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <tr><td style="width: 30%;"><strong>Assignee</strong></td><td>{assignee_display}</td></tr>
        <tr><td><strong>Reporter</strong></td><td>{reporter_display}</td></tr>
        <tr><td><strong>Request Participants</strong></td><td>{participants}</td></tr>
        <tr><td><strong>Approvers</strong></td><td>{approvers}</td></tr>
    </table>
    """

    html_dates = f"""
    <h3>Dates</h3>
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <tr><td style="width: 30%;"><strong>Created</strong></td><td>{format_glpi_date_friendly(creation_date)}</td></tr>
        <tr><td><strong>Updated</strong></td><td>{format_glpi_date_friendly(update_date)}</td></tr>
        <tr><td><strong>Resolved</strong></td><td>{format_glpi_date_friendly(resolution_date) if resolution_date else 'N/A'}</td></tr>
    </table>
    """

    html_slas = f"""
    <h3>SLAs</h3>
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <tr>
            <th style="background-color: #f2f2f2;">SLA Name</th>
            <th style="background-color: #f2f2f2;">Status</th>
            <th style="background-color: #f2f2f2;">Goal</th>
            <th style="background-color: #f2f2f2;">Remain Time</th>
        </tr>
        {sla_info_rows}
    </table>
    """
    
    html_service_req = f"""
    <h3>Service Project Request</h3>
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <tr><td style="width: 30%;"><strong>Request Type</strong></td><td>{request_type_name}</td></tr>
        <tr><td><strong>Customer Status</strong></td><td>{customer_status}</td></tr>
        <tr><td><strong>Channel</strong></td><td>{channel}</td></tr>
    </table>
    """

    # Add History after SLAs
    details_block = f"{html_details}{html_service_req}{html_people}{past_approvals_html}{html_dates}{html_slas}{html_history}<hr>"
    
    # --- Format Description ---
    desc_linked = convert_jira_content(description, attachment_map)
    desc_formatted = desc_linked.replace('\n', '<br>')
    
    full_desc = f"{details_block}<br>{desc_formatted}"

    ticket_args = {
        "status": glpi_status,
        "type": glpi_type,
        "date": creation_date,
    }
    
    # --- Priority Mapping (Jira Priority -> GLPI Urgency + Impact) ---
    # Note: GLPI auto-calculates Priority from Urgency × Impact matrix
    priority_name = (fields.get('priority') or {}).get('name', '')
    urgency, impact = config.PRIORITY_MAPPING.get(
        priority_name.lower(), config.DEFAULT_PRIORITY
    )
    ticket_args['urgency'] = urgency
    ticket_args['impact'] = impact
    print(f"  -> Priority '{priority_name}' -> Urgency={urgency}, Impact={impact}")
    
    if glpi_status in [5, 6]:
        ticket_args["solvedate"] = resolution_date or update_date
    if glpi_status == 6:
        ticket_args["closedate"] = resolution_date or update_date

    if requester_id: ticket_args['_users_id_requester'] = requester_id
    if assignee_id: ticket_args['_users_id_assign'] = assignee_id
    
    # --- Observers (from Request Participants) ---
    if participant_ids:
        ticket_args['_users_id_observer'] = participant_ids
        print(f"  -> Mapped {len(participant_ids)} participants as observers")
    
    # --- Security Level Mapping (to GLPI ITIL Category) ---
    security = fields.get('security')
    if security:
        sec_name = security.get('name')
        if sec_name:
            cat_id = glpi.get_or_create_category(sec_name)
            if cat_id:
                ticket_args['itilcategories_id'] = cat_id
                print(f"  -> Mapped Security Level '{sec_name}' to GLPI Category ID {cat_id}")
            else:
                print(f"  [WARN] Security Level '{sec_name}' could not be mapped to GLPI Category.")
        
    ticket_id = glpi.create_ticket(name=summary, content=full_desc, **ticket_args)
    
    print(f"  -> Ticket created ID: {ticket_id}")
    
    if ticket_id:
        # Link Attachments to Ticket
        for doc_id in attachment_map.values():
            glpi.link_document_to_ticket(ticket_id, doc_id)
            
        # Comments
        comments = (fields.get('comment') or {}).get('comments', [])
        for comment in comments:
            author_display = (comment.get('author') or {}).get('displayName', 'Unknown')
            author_jira = (comment.get('author') or {}).get('name')
            body = comment.get('body', '')
            created = parse_jira_date(comment.get('created'))
            
            # Map Author
            author_id = glpi.get_user_id_by_name(author_jira)
            
            # Debug Author logic
            if not author_id:
                print(f"    [WARN] Comment author '{author_jira}' not found in GLPI. Will be posted by API user.")
                report_missing_user(author_jira, author_display)
            else:
                print(f"    [DEBUG] Posting comment as User ID {author_id} ({author_display})")
                
            body_converted = convert_jira_content(body, attachment_map)
            
            # Jira Style Header: "Name added a comment - 15/Jan/24 4:58 PM (UTC+7)"
            comment_date_str = format_comment_date(comment.get('created'))
            header = f"**{author_display} added a comment - {comment_date_str}**:\n"
            
            glpi.add_ticket_followup(ticket_id, header + body_converted, users_id=author_id, date=created)

if __name__ == "__main__":
    main()
