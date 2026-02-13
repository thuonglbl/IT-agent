"""
HTML description generation for GLPI tickets
"""
import re
from lib.utils import format_glpi_date_friendly, format_comment_date

# HTML table styles
TABLE_STYLE = 'border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;"'
HEADER_STYLE = 'style="background-color: #f2f2f2;"'
CELL_WIDTH_30 = 'style="width: 30%;"'


def convert_jira_content(text, attachment_map):
    """
    Convert Jira Textile markup to HTML.

    Conversions:
        1. Links: [Label|URL] -> <a href>
        2. Images: !filename! -> <img src>

    Args:
        text: Jira textile content
        attachment_map: Dict mapping filenames to GLPI doc IDs

    Returns:
        str: HTML content
    """
    if not text:
        return ""

    # 1. Images: !filename! or !filename|thumbnail!
    def replace_image(match):
        filename = match.group(1)  # e.g. image.png

        # If filename in map, replace with GLPI document link
        if filename in attachment_map:
            doc_id = attachment_map[filename]
            src = f"/front/document.send.php?docid={doc_id}"
            return f'<img src="{src}" alt="{filename}" style="max-width: 100%;" />'

        return match.group(0)  # Keep original if not found

    # Regex: ! (filename) [| options] !
    text = re.sub(r'!([^|!]+)(?:\|[^!]+)?!', replace_image, text)

    # 2. Links: [Label|URL]
    text = re.sub(r'\[([^|\]\n]+)\|([^\]\n]+)\]', r'<a href="\2">\1</a>', text)

    # 3. Bare Links: [URL]
    text = re.sub(r'\[(https?://[^\]\n]+)\]', r'<a href="\1">\1</a>', text)

    return text


def build_jira_details_table(issue, basic_fields, custom_fields, config):
    """
    Build Jira Details table.

    Args:
        issue: Jira issue dictionary
        basic_fields: Basic fields dict from field_extractor
        custom_fields: Custom fields dict from field_extractor
        config: Configuration dictionary

    Returns:
        str: HTML table
    """
    key = basic_fields['key']
    jira_url = config.get('jira', {}).get('url', '')

    details_rows = f"""
    <tr><td><strong>Key</strong></td><td><a href="{jira_url}/browse/{key}">{key}</a></td></tr>
    <tr><td><strong>Type</strong></td><td>{basic_fields['issue_type']}</td></tr>
    <tr><td><strong>Priority</strong></td><td>{basic_fields['priority']}</td></tr>
    <tr><td><strong>Resolution</strong></td><td>{basic_fields['resolution']}</td></tr>
    <tr><td><strong>Component</strong></td><td>{basic_fields['components']}</td></tr>
    <tr><td><strong>Classification</strong></td><td>{custom_fields['classification']}</td></tr>
    <tr><td><strong>Security Level</strong></td><td>{basic_fields['security']}</td></tr>
    <tr><td><strong>Reporter Details</strong></td><td>{custom_fields['reporter_details']}</td></tr>
    """

    return f"""
    <h3>Jira Details</h3>
    <table {TABLE_STYLE}>
        <tr><th {HEADER_STYLE} {CELL_WIDTH_30}>Field</th><th {HEADER_STYLE}>Value</th></tr>
        {details_rows}
    </table>
    """


def build_people_table(actors, participants, approvers):
    """
    Build People table (Reporter, Assignee, Participants, Approvers).

    Args:
        actors: Actors dict from field_extractor
        participants: Participants dict from field_extractor
        approvers: Approvers string

    Returns:
        str: HTML table
    """
    return f"""
    <h3>People</h3>
    <table {TABLE_STYLE}>
        <tr><td {CELL_WIDTH_30}><strong>Assignee</strong></td><td>{actors['assignee_display']}</td></tr>
        <tr><td><strong>Reporter</strong></td><td>{actors['reporter_display']}</td></tr>
        <tr><td><strong>Request Participants</strong></td><td>{participants['participants']}</td></tr>
        <tr><td><strong>Approvers</strong></td><td>{approvers}</td></tr>
    </table>
    """


def build_dates_table(dates):
    """
    Build Dates table (Created, Updated, Resolved).

    Args:
        dates: Dates dict from field_extractor

    Returns:
        str: HTML table
    """
    return f"""
    <h3>Dates</h3>
    <table {TABLE_STYLE}>
        <tr><td {CELL_WIDTH_30}><strong>Created</strong></td><td>{format_glpi_date_friendly(dates['created'])}</td></tr>
        <tr><td><strong>Updated</strong></td><td>{format_glpi_date_friendly(dates['updated'])}</td></tr>
        <tr><td><strong>Resolved</strong></td><td>{format_glpi_date_friendly(dates['resolved']) if dates['resolved'] else 'N/A'}</td></tr>
    </table>
    """


def build_sla_table(issue, config):
    """
    Build SLA information table.

    Args:
        issue: Jira issue dictionary
        config: Configuration dictionary

    Returns:
        str: HTML table
    """
    fields = issue['fields']
    custom_fields_config = config.get('custom_fields', {})
    sla_fields = custom_fields_config.get('sla_fields', [])

    sla_info_rows = ""

    for sla_id in sla_fields:
        sla_data = fields.get(sla_id)
        if sla_data and isinstance(sla_data, dict):
            name = sla_data.get('name', 'Unknown SLA')
            completed_list = sla_data.get('completedCycles')
            ongoing = sla_data.get('ongoingCycle')

            if completed_list:
                last_cycle = completed_list[-1]
                breached = last_cycle.get('breached', False)
                status_html = "<span style='color:red'>Breached</span>" if breached else "<span style='color:green'>Met</span>"
                goal_str = (last_cycle.get('goalDuration') or {}).get('friendly', 'N/A')
                actual_str = (last_cycle.get('remainingTime') or {}).get('friendly', 'N/A')
                sla_info_rows += f"<tr><td>{name}</td><td>{status_html}</td><td>{goal_str}</td><td>{actual_str}</td></tr>"
            elif ongoing:
                status_html = "<span style='color:orange'>In Progress</span>"
                goal_str = (ongoing.get('goalDuration') or {}).get('friendly', '')
                actual_str = (ongoing.get('remainingTime') or {}).get('friendly', '')
                sla_info_rows += f"<tr><td>{name}</td><td>{status_html}</td><td>{goal_str}</td><td>{actual_str}</td></tr>"

    if not sla_info_rows:
        sla_info_rows = "<tr><td colspan='4'>No SLA Data</td></tr>"

    return f"""
    <h3>SLAs</h3>
    <table {TABLE_STYLE}>
        <tr>
            <th {HEADER_STYLE}>SLA Name</th>
            <th {HEADER_STYLE}>Status</th>
            <th {HEADER_STYLE}>Goal</th>
            <th {HEADER_STYLE}>Remain Time</th>
        </tr>
        {sla_info_rows}
    </table>
    """


def build_service_request_table(issue, config):
    """
    Build Service Project Request table.

    Args:
        issue: Jira issue dictionary
        config: Configuration dictionary

    Returns:
        str: HTML table
    """
    fields = issue['fields']
    custom_fields_config = config.get('custom_fields', {})

    # Extract request type
    request_type_id = custom_fields_config.get('customer_request_type', '')
    request_type_data = fields.get(request_type_id)

    if isinstance(request_type_data, dict):
        request_type_name = request_type_data.get('requestType', {}).get('name', 'N/A')
        customer_status = request_type_data.get('currentStatus', {}).get('status', 'N/A')
        channel = request_type_data.get('requestType', {}).get('serviceDeskId', 'N/A')
    else:
        request_type_name = str(request_type_data) if request_type_data else 'N/A'
        customer_status = 'N/A'
        channel = 'N/A'

    return f"""
    <h3>Service Project Request</h3>
    <table {TABLE_STYLE}>
        <tr><td {CELL_WIDTH_30}><strong>Request Type</strong></td><td>{request_type_name}</td></tr>
        <tr><td><strong>Customer Status</strong></td><td>{customer_status}</td></tr>
        <tr><td><strong>Channel</strong></td><td>{channel}</td></tr>
    </table>
    """


def build_past_approvals_table(issue, config):
    """
    Build Past Approvals table.

    Args:
        issue: Jira issue dictionary
        config: Configuration dictionary

    Returns:
        str: HTML table or empty string
    """
    fields = issue['fields']
    custom_fields_config = config.get('custom_fields', {})
    approvals_id = custom_fields_config.get('approvals', '')
    approval_data = fields.get(approvals_id)

    if not approval_data or not isinstance(approval_data, list):
        return ""

    approval_rows = ""
    for approval in approval_data:
        if isinstance(approval, dict):
            # Use finalDecision as the status
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

            # Get date
            created = approval.get('createdDate', {}).get('friendly', '') if isinstance(approval.get('createdDate'), dict) else ''
            completed = approval.get('completedDate', {}).get('friendly', '') if isinstance(approval.get('completedDate'), dict) else ''

            # Use completed date if available, otherwise created
            date_str = completed if completed else created

            approval_rows += f"<tr><td>{decision}</td><td>{approver_name}</td><td>{date_str}</td></tr>"

    if not approval_rows:
        return ""

    return f"""
    <h3>Past Approvals</h3>
    <table {TABLE_STYLE}>
        <tr>
            <th {HEADER_STYLE}>Status</th>
            <th {HEADER_STYLE}>Approver</th>
            <th {HEADER_STYLE}>Date</th>
        </tr>
        {approval_rows}
    </table>
    """


def build_history_table(issue, glpi_client, config):
    """
    Build History table from Jira changelog.

    Args:
        issue: Jira issue dictionary
        glpi_client: GLPI client instance
        config: Configuration dictionary

    Returns:
        str: HTML table or empty string
    """
    changelog = issue.get('changelog', {})
    histories = changelog.get('histories', [])

    glpi_url = config.get('glpi', {}).get('url', '')
    base_url = glpi_url.replace('/api.php/v1', '').rstrip('/')

    rows = ""

    # Process histories in reverse order (newest first)
    for history in reversed(histories):
        author = history.get('author', {})
        author_name = author.get('displayName', 'Unknown')
        author_key = author.get('name', '')
        created_str = format_comment_date(history.get('created'))

        # Link to User in GLPI
        user_id = glpi_client.get_user_id_by_name(author_key)

        if user_id:
            user_link = f'<a href="{base_url}/front/user.form.php?id={user_id}">{author_name}</a>'
        else:
            user_link = author_name

        items = history.get('items', [])
        for item in items:
            field = item.get('field', '')
            original = item.get('fromString', '')
            if not original:
                original = ""
            new_val = item.get('toString', '')
            if not new_val:
                new_val = ""

            rows += f"""
            <tr>
                <td>{user_link}</td>
                <td>{created_str}</td>
                <td>{field}</td>
                <td>{original}</td>
                <td>{new_val}</td>
            </tr>
            """

    # Add "Created" event at the end (oldest)
    fields = issue.get('fields', {})
    reporter = fields.get('reporter', {})
    reporter_name = reporter.get('displayName', 'Unknown')
    reporter_key = reporter.get('name', '')
    created_date = format_comment_date(fields.get('created'))

    # Link Reporter
    rep_id = glpi_client.get_user_id_by_name(reporter_key)
    if rep_id:
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
    <table {TABLE_STYLE}>
        <tr>
            <th {HEADER_STYLE}>User</th>
            <th {HEADER_STYLE}>Date</th>
            <th {HEADER_STYLE}>Field</th>
            <th {HEADER_STYLE}>Original</th>
            <th {HEADER_STYLE}>New</th>
        </tr>
        {rows}
    </table>
    """


def build_full_description(issue, basic_fields, custom_fields, actors, participants, approvers, dates, attachment_map, glpi_client, config):
    """
    Build complete HTML description by orchestrating all sections.

    Args:
        issue: Jira issue dictionary
        basic_fields: Basic fields dict
        custom_fields: Custom fields dict
        actors: Actors dict
        participants: Participants dict
        approvers: Approvers string
        dates: Dates dict
        attachment_map: Attachment filename to doc_id mapping
        glpi_client: GLPI client instance
        config: Configuration dictionary

    Returns:
        str: Complete HTML description
    """
    # Build all sections
    html_details = build_jira_details_table(issue, basic_fields, custom_fields, config)
    html_service_req = build_service_request_table(issue, config)
    html_people = build_people_table(actors, participants, approvers)
    html_past_approvals = build_past_approvals_table(issue, config)
    html_dates = build_dates_table(dates)
    html_slas = build_sla_table(issue, config)
    html_history = build_history_table(issue, glpi_client, config)

    # Assemble details block
    details_block = f"{html_details}{html_service_req}{html_people}{html_past_approvals}{html_dates}{html_slas}{html_history}<hr>"

    # Format original description
    description = basic_fields['description']
    desc_linked = convert_jira_content(description, attachment_map)
    desc_formatted = desc_linked.replace('\n', '<br>')

    # Combine all
    full_desc = f"{details_block}<br>{desc_formatted}"

    return full_desc
