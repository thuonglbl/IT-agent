"""
Jira to GLPI Project Tasks Migration
Migrates Jira project issues to GLPI Project Tasks with full metadata and attachments
"""
import os
import json
import time
import datetime
import re

# Import from shared library
from common.clients.jira_client import JiraClient
from common.clients.glpi_client import GlpiClient
from common.config.loader import load_config
from common.utils.state_manager import StateManager

# Load configuration
config = load_config(validate=False)  # Skip validation for legacy Python config

# --- Constants ---
STATE_FILE = config.get('migration', {}).get('state_file', config.get('STATE_FILE', 'migration_state.json'))
MAPPING_FILE = config.get('migration', {}).get('mapping_file', config.get('MAPPING_FILE', 'jira_glpi_mapping.json'))


def load_mapping(log_func=None):
    """Load Jira Key -> GLPI ID mapping from file."""
    if os.path.exists(MAPPING_FILE):
        try:
            with open(MAPPING_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            if log_func:
                log_func(f"Warning: Could not read mapping file: {e}", "warning")
            else:
                print(f"Warning: Could not read mapping file: {e}")
    return {}


def save_mapping(mapping, log_func=None):
    """Save Jira Key -> GLPI ID mapping to file."""
    try:
        with open(MAPPING_FILE, 'w') as f:
            json.dump(mapping, f, indent=4)
    except Exception as e:
        if log_func:
            log_func(f"Warning: Could not save mapping file: {e}", "warning")
        else:
            print(f"Warning: Could not save mapping file: {e}")


def parse_jira_date(date_str, format_str="%Y-%m-%d %H:%M:%S", log_func=None):
    """
    Parse Jira date string '2014-03-04T09:46:56.000+0100'
    to GLPI format (default: 'YYYY-MM-DD HH:MM:SS')
    Converts to Local System Timezone
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
            if log_func:
                log_func(f"Date parse error ({date_str}): {e}", "error")
            else:
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

    jira_custom_fields = config.get('jira', {}).get('custom_fields', config.get('JIRA_CUSTOM_FIELDS', {}))

    for field_key, field_id in jira_custom_fields.items():
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

    if resolution:
        content_html += f"<p><b>Resolution:</b> {resolution}</p>"
    if security:
        content_html += f"<p><b>Security Level:</b> {security}</p>"

    # Standard Jira fields (not custom fields)
    if fix_versions:
        content_html += f"<p><b>Fix Version/s:</b> {fix_versions}</p>"
    if affects_versions:
        content_html += f"<p><b>Affects Version/s:</b> {affects_versions}</p>"
    if components:
        content_html += f"<p><b>Component/s:</b> {components}</p>"
    if labels:
        content_html += f"<p><b>Labels:</b> {labels}</p>"
    if environment:
        content_html += f"<p><b>Environment:</b> {environment}</p>"

    # Add all custom fields with values (dynamic from config.JIRA_CUSTOM_FIELDS)
    if custom_fields_html:
        content_html += custom_fields_html

    # Section 5: Description
    content_html += "<hr><h3>Description</h3>"
    content_html += f"<div>{description.replace(chr(10), '<br>')}</div>"

    return content_html


def process_changelog(issue, glpi, log_func=None):
    """
    Parse changelog to create a History Log HTML.
    Includes "Issue Created" event.
    """
    def log_msg(msg, level="info"):
        if log_func:
            log_func(msg, level)
        else:
            print(msg)

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
                log_msg(f"       [DEBUG-HIST] User lookup failed for login '{author_name}' (Display: {author_display})", "debug")

        # Fallback to Display Name lookup if failed
        if not uid and author_display:
            uid = glpi.get_user_id_by_name(author_display)
            if not uid:
                log_msg(f"       [DEBUG-HIST] Fallback lookup also failed for display '{author_display}'", "debug")

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
    jira_color_map = config.get('jira', {}).get('color_map', config.get('JIRA_COLOR_MAP', {}))
    default_color = jira_color_map.get("default", "#42526E")

    if not color_name:
        return default_color

    c = color_name.lower().replace(" ", "").replace("-", "")
    return jira_color_map.get(c, default_color)


def run_preparation(glpi, jira, project_key, log_func=None):
    """Run automated environment setup (sync statuses and types)."""
    def log_msg(msg, level="info"):
        if log_func:
            log_func(msg, level)
        else:
            print(msg)

    log_msg("\n[PREPARATION] Starting automated environment setup...")

    # 1. Sync Statuses
    log_msg("\n--- 1. Syncing Project Statuses ---")
    # 1a. Clear existing
    glpi.delete_all_items("ProjectState")

    # 1b. Fetch Jira Statuses
    log_msg("  > Fetching Statuses from Jira...")
    jira_statuses = jira.get_project_statuses(project_key)

    # 1c. Create in GLPI
    for s in jira_statuses:
        name = s['name']
        color_name = s['statusCategory'].get('colorName')
        is_finished = 1 if s['statusCategory'].get('key') == 'done' else 0
        hex_color = get_hex_color(color_name)

        log_msg(f"  > Creating Status '{name}' (Color: {color_name}/{hex_color}, Finished: {is_finished})...")
        glpi.create_project_state(name, hex_color, is_finished)
        time.sleep(0.2)

    # 2. Sync Types
    log_msg("\n--- 2. Syncing Project Task Types ---")
    # 2a. Clear existing
    glpi.delete_all_items("ProjectTaskType")

    # 2b. Fetch Jira Types
    log_msg("  > Fetching Issue Types from Jira...")
    jira_types = jira.get_project_issue_types(project_key)

    # 2c. Create in GLPI
    for t in jira_types:
        name = t['name']
        log_msg(f"  > Creating Type '{name}'...")
        glpi.create_project_task_type(name)
        time.sleep(0.2)

    log_msg("\n[PREPARATION] Completed.\n")


def main():
    """Main migration orchestrator."""

    # Optional: Setup structured logging if logging config is present
    logger = None
    if config.get('logging', {}).get('console') or config.get('logging', {}).get('file'):
        try:
            from common.logging.logger import setup_logger
            logger = setup_logger("jira_project_migration", config)
        except Exception as e:
            print(f"Warning: Could not initialize logger: {e}")

    # Helper function: Use logger if available, otherwise print
    def log(message, level="info"):
        if logger:
            getattr(logger, level)(message)
        else:
            print(message)

    log(f"=== Jira to GLPI Project Tasks Migration ===\n")

    # Extract config values
    jira_url = config.get('jira', {}).get('url', config.get('JIRA_URL', ''))
    jira_pat = config.get('jira', {}).get('pat', config.get('JIRA_PAT', ''))
    jira_verify_ssl = config.get('jira', {}).get('verify_ssl', config.get('JIRA_VERIFY_SSL', False))
    jira_project_key = config.get('jira', {}).get('project_key', config.get('JIRA_PROJECT_KEY', ''))
    jira_jql = config.get('jira', {}).get('jql', config.get('JIRA_JQL', f'project = {jira_project_key} ORDER BY key ASC'))

    glpi_url = config.get('glpi', {}).get('url', config.get('GLPI_URL', ''))
    glpi_app_token = config.get('glpi', {}).get('app_token', config.get('GLPI_APP_TOKEN', ''))
    glpi_user_token = config.get('glpi', {}).get('user_token', config.get('GLPI_USER_TOKEN'))
    glpi_username = config.get('glpi', {}).get('username', config.get('GLPI_USERNAME'))
    glpi_password = config.get('glpi', {}).get('password', config.get('GLPI_PASSWORD'))
    glpi_verify_ssl = config.get('glpi', {}).get('verify_ssl', config.get('GLPI_VERIFY_SSL', False))
    glpi_project_name = config.get('glpi', {}).get('project_name', config.get('GLPI_PROJECT_NAME', ''))

    batch_size = config.get('migration', {}).get('batch_size', config.get('BATCH_SIZE', 50))
    debug_mode = config.get('migration', {}).get('debug', config.get('DEBUG', False))

    # 1. Init Connections
    try:
        jira = JiraClient(jira_url, jira_pat, verify_ssl=jira_verify_ssl)

        # Init GLPI Client with both User Token (Primary) and Basic Auth (Fallback)
        glpi = GlpiClient(
            glpi_url,
            glpi_app_token,
            user_token=glpi_user_token,
            username=glpi_username,
            password=glpi_password,
            verify_ssl=glpi_verify_ssl
        )

        glpi.init_session()
        log("✓ GLPI Connection: OK")

        # Load user cache for fast lookups
        glpi.load_user_cache()

        # Resolve Project ID for configured project
        log(f"Resolving GLPI Project '{glpi_project_name}'...")
        project_id = glpi.get_project_id_by_name(glpi_project_name)
        if not project_id:
            log(f"[ERROR] Project '{glpi_project_name}' not found!", "error")
            return
        log(f"✓ Found Project ID: {project_id}\n")

        # --- PROACTIVE PREPARATION ---
        # Run preparation only if state file doesn't exist (First Run)
        if not os.path.exists(STATE_FILE):
            run_preparation(glpi, jira, jira_project_key, log_func=log)

        # Fetch Project States (Dynamic Mapping)
        log("Fetching GLPI Project States...")
        project_states_map = glpi.get_project_states()
        log(f"✓ Loaded {len(project_states_map)} states: {project_states_map}\n")

        # Fetch Project Task Types (Dynamic Mapping)
        log("Fetching GLPI Project Task Types...")
        project_types_map = glpi.get_project_task_types()
        log(f"✓ Loaded {len(project_types_map)} types: {project_types_map}\n")

    except Exception as e:
        log(f"Connection Failed: {e}", "error")
        return

    # 2. Migration Loop
    state_manager = StateManager(STATE_FILE)
    state = state_manager.load()
    start_at = state.get("start_at", 0)
    total_processed = state.get("total_processed", 0)

    # Store Jira Key -> GLPI Project Task ID for Parent-Child linking
    jira_map = load_mapping(log_func=log)
    log(f"Loaded {len(jira_map)} existing ID mappings.\n")

    log(f"Using JQL: {jira_jql}")

    try:
        # Get total count first
        total_issues = jira.get_issue_count(jira_jql)
        log(f"Total Issues to Migrate: {total_issues}")
        log(f"Resuming from: {start_at}\n")

        while start_at < total_issues:
            # Determine max results based on Debug mode
            fetch_limit = batch_size

            if debug_mode:
                log(f"[DEBUG] Fetching 1 batch for testing...\n", "debug")
            else:
                log(f"Fetching batch: {start_at} to {start_at + fetch_limit} ...")

            # IMPORTANT: Fetch changelog!
            issues, _ = jira.search_issues(jira_jql, start_at=start_at, max_results=fetch_limit)

            if not issues:
                log("No more issues returned.")
                break

            for issue in issues:
                key = issue.get('key')
                fields = issue.get('fields', {})
                summary = fields.get('summary', '[No Summary]')

                log(f"\nProcessing {key}: {summary[:50]}...")

                # --- MAPPING LOGIC ---

                # Assignee -> Tech
                assignee_data = fields.get('assignee') or {}
                assignee_name = assignee_data.get('name')  # Username used for mapping
                assignee_display = assignee_data.get('displayName', assignee_name)

                assignee_id = None
                if assignee_name:
                    assignee_id = glpi.get_user_id_by_name(assignee_name)
                    if assignee_id:
                        log(f"    ✓ Mapped Assignee '{assignee_display}' to GLPI ID {assignee_id}")
                    else:
                        log(f"    [WARN] Assignee '{assignee_name}' not found in GLPI.", "warning")

                # Reporter -> Requester (for Task Team)
                reporter_data = fields.get('reporter') or {}
                reporter_name = reporter_data.get('name')  # Username used for mapping
                reporter_display = reporter_data.get('displayName', reporter_data.get('name'))

                reporter_id = None
                if reporter_name:
                    reporter_id = glpi.get_user_id_by_name(reporter_name)
                    if reporter_id:
                        log(f"    ✓ Mapped Reporter '{reporter_display}' to GLPI ID {reporter_id}")
                    else:
                        log(f"    [WARN] Reporter '{reporter_name}' not found in GLPI.", "warning")

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
                        log(f"    [WARN] Status '{jira_status}' not found. Defaulting to ID {glpi_state_id}", "warning")

                # Type Mapping (Dynamic)
                jira_type = (fields.get('issuetype') or {}).get('name', 'Task')
                glpi_type_id = project_types_map.get(jira_type.lower())
                if glpi_type_id:
                    log(f"    ✓ Mapped Type '{jira_type}' to GLPI ID {glpi_type_id}")
                else:
                    log(f"    [WARN] Type '{jira_type}' not found in GLPI.", "warning")

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
                        log(f"    - Downloading attachment: {filename}...")

                        file_data = jira.get_attachment_content(content_url)
                        if file_data:
                            temp_path = os.path.join(os.getcwd(), filename)
                            with open(temp_path, 'wb') as f:
                                f.write(file_data)

                            doc_id = glpi.upload_document(temp_path)

                            if os.path.exists(temp_path):
                                os.remove(temp_path)

                            if doc_id:
                                doc_url = f"/front/document.send.php?docid={doc_id}"
                                content_html += f"<li><a href='{doc_url}' target='_blank'>{filename}</a></li>"
                            else:
                                content_html += f"<li>{filename} (Upload Failed)</li>"
                        else:
                            content_html += f"<li>{filename} (Download Failed)</li>"
                    content_html += "</ul>"

                # Create GLPI Project Task
                task_name = summary
                log(f"    → Creating GLPI Project Task '{task_name}'...")

                # Urgency Mapping - For Task Field
                urgency_field_id = config.get('jira', {}).get('custom_fields', {}).get("urgency", config.get('JIRA_CUSTOM_FIELDS', {}).get("urgency"))
                urgency_raw = (fields.get(urgency_field_id) or {}).get('value', 'Medium') if urgency_field_id else 'Medium'
                urgency_map = {'Low': 2, 'Medium': 3, 'High': 4, 'Very High': 5, 'Critical': 5, 'Blocker': 5, 'Serious': 4}
                urgency_val = urgency_map.get(urgency_raw, 3)

                task_kwargs = {
                    "projectstates_id": glpi_state_id,
                    "percent_done": 100 if jira_status_lower in ['resolved', 'closed', 'done'] else 0,
                    "urgency": urgency_val,
                    "real_start_date": "NULL",  # string literal NULL to force unset
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
                            log(f"    → Linking as child of {parent_key} (GLPI ID: {parent_glpi_id})")
                            task_kwargs['projecttasks_id'] = parent_glpi_id
                        else:
                            log(f"    [WARN] Parent {parent_key} not found in current map (maybe not processed yet?)", "warning")

                task_id = glpi.create_project_task(project_id, task_name, content_html, **task_kwargs)

                if task_id:
                    log(f"    ✓ Created Project Task ID: {task_id}")

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
                    history_html = process_changelog(issue, glpi, log_func=log)
                    if history_html:
                        log("    - Migrating History Log...")
                        if not glpi.create_note("ProjectTask", task_id, history_html):
                            log("      → History Note creation failed. Queueing for description append.", "warning")
                            # If note fails, we append to Description later.
                            # But here we just want to ensure it's created first.
                            failed_notes.append(history_html)

                    # 7b. Comments
                    comments = (fields.get('comment') or {}).get('comments', [])
                    if comments:
                        log(f"    - Migrating {len(comments)} comments as Notes...")
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
                        log(f"    - Appending {len(failed_notes)} failed notes to Description...")
                        append_html = "<hr><h3>Migrated Comments & History</h3>"
                        append_html += "<hr>".join(failed_notes)

                        # Append to original content
                        final_content = content_html + append_html

                        glpi.update_project_task(task_id, content=final_content)

                else:
                    log(f"    ✗ Failed to create task for {key}", "error")

                time.sleep(0.1)

                total_processed += 1

            # Update Batch Progress
            start_at += len(issues)
            state_manager.save(start_at, total_processed)
            save_mapping(jira_map, log_func=log)

            # DEBUG
            if debug_mode:
                log("\n[DEBUG] Stopping after test batch.", "debug")
                break

        log(f"\n{'='*50}")
        log("Migration Completed Successfully!")
        log(f"Total Processed: {total_processed}")
        log(f"{'='*50}")

    except KeyboardInterrupt:
        log("\n\nMigration Paused by User.", "warning")
        state_manager.save(start_at, total_processed)
    except Exception as e:
        log(f"\n\nMigration Failed: {e}", "error")
        state_manager.save(start_at, total_processed)
        raise
    finally:
        glpi.kill_session()


if __name__ == "__main__":
    main()
