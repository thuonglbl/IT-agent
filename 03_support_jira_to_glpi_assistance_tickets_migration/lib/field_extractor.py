"""
Field extraction and mapping from Jira issues to GLPI tickets
"""
from lib.utils import parse_jira_date


def extract_basic_fields(issue, config):
    """
    Extract basic fields from Jira issue.

    Args:
        issue: Jira issue dictionary
        config: Configuration dictionary

    Returns:
        dict: Basic fields (key, summary, description, type_jira, status_jira, priority_jira)
    """
    key = issue['key']
    fields = issue['fields']

    summary = fields.get('summary', '[No Title]')
    description = fields.get('description') or ""

    status_jira = (fields.get('status') or {}).get('name', '').lower()
    type_jira = (fields.get('issuetype') or {}).get('name', '').lower()
    priority_jira = (fields.get('priority') or {}).get('name', 'Normal')

    return {
        'key': key,
        'summary': summary,
        'description': description,
        'type_jira': type_jira,
        'status_jira': status_jira,
        'priority_jira': priority_jira,
        'issue_type': (fields.get('issuetype') or {}).get('name', 'Ticket'),
        'priority': priority_jira,
        'resolution': (fields.get('resolution') or {}).get('name', 'Unresolved'),
        'security': (fields.get('security') or {}).get('name', 'None'),
        'components': ", ".join([c.get('name') for c in fields.get('components', [])]),
    }


def extract_actors(issue, glpi_client, logger, user_tracker):
    """
    Extract and map actors (reporter, assignee, participants) from Jira to GLPI.

    Args:
        issue: Jira issue dictionary
        glpi_client: GLPI client instance
        logger: Logger instance
        user_tracker: UserTracker instance

    Returns:
        dict: Actors with GLPI user IDs and display names
    """
    fields = issue['fields']

    # Reporter
    reporter_jira = (fields.get('reporter') or {}).get('name')
    reporter_display = (fields.get('reporter') or {}).get('displayName', reporter_jira)

    requester_id = glpi_client.get_user_id_by_name(reporter_jira) if reporter_jira else None
    if reporter_jira and not requester_id:
        user_tracker.report_missing_user(reporter_jira, reporter_display)
        logger.warning(f"Reporter not found in GLPI: {reporter_jira}")

    # Assignee
    assignee_jira = (fields.get('assignee') or {}).get('name')
    assignee_display = (fields.get('assignee') or {}).get('displayName', assignee_jira) or 'Unassigned'

    assignee_id = glpi_client.get_user_id_by_name(assignee_jira) if assignee_jira else None
    if assignee_jira and not assignee_id:
        user_tracker.report_missing_user(assignee_jira, assignee_display)
        logger.warning(f"Assignee not found in GLPI: {assignee_jira}")

    return {
        'reporter_jira': reporter_jira,
        'reporter_display': reporter_display,
        'requester_id': requester_id,
        'assignee_jira': assignee_jira,
        'assignee_display': assignee_display,
        'assignee_id': assignee_id,
    }


def extract_dates(issue):
    """
    Extract and parse dates from Jira issue.

    Args:
        issue: Jira issue dictionary

    Returns:
        dict: Parsed dates (created, updated, resolved)
    """
    fields = issue['fields']

    return {
        'created': parse_jira_date(fields.get('created')),
        'updated': parse_jira_date(fields.get('updated')),
        'resolved': parse_jira_date(fields.get('resolutiondate')),
    }


def extract_custom_fields(issue, config):
    """
    Extract custom fields from Jira issue.

    Args:
        issue: Jira issue dictionary
        config: Configuration dictionary

    Returns:
        dict: Custom fields
    """
    fields = issue['fields']
    custom_fields_config = config.get('custom_fields', {})

    # Classification
    classification_id = custom_fields_config.get('classification', '')
    classification_raw = fields.get(classification_id)
    classification = ", ".join(classification_raw) if isinstance(classification_raw, list) else str(classification_raw or '')

    # Reporter details
    reporter_details_id = custom_fields_config.get('reporter_details', '')
    reporter_details = fields.get(reporter_details_id, '')

    # Customer request type
    request_type_id = custom_fields_config.get('customer_request_type', '')
    request_type = fields.get(request_type_id, 'N/A')

    return {
        'classification': classification,
        'classification_raw': classification_raw,
        'reporter_details': reporter_details,
        'request_type': request_type,
    }


def extract_participants(issue, config, glpi_client, logger, user_tracker):
    """
    Extract and map participants from Jira to GLPI.

    Args:
        issue: Jira issue dictionary
        config: Configuration dictionary
        glpi_client: GLPI client instance
        logger: Logger instance
        user_tracker: UserTracker instance

    Returns:
        dict: Participants display names and GLPI IDs
    """
    fields = issue['fields']
    custom_fields_config = config.get('custom_fields', {})

    participants_id = custom_fields_config.get('request_participants', '')
    participants_raw = fields.get(participants_id)

    participant_ids = []
    participant_names = []

    if isinstance(participants_raw, list):
        for p in participants_raw:
            p_login = p.get('name', '')
            p_display = p.get('displayName', p_login)
            participant_names.append(p_display)

            p_id = glpi_client.get_user_id_by_name(p_login)
            if p_id:
                participant_ids.append(p_id)
            elif p_login:
                user_tracker.report_missing_user(p_login, p_display)
                logger.warning(f"Participant not found in GLPI: {p_login}")

        participants_str = ", ".join(participant_names)
    else:
        participants_str = str(participants_raw) if participants_raw else "None"

    return {
        'participants': participants_str,
        'participant_ids': participant_ids,
    }


def extract_approvers(issue, config):
    """
    Extract approvers from Jira issue.

    Args:
        issue: Jira issue dictionary
        config: Configuration dictionary

    Returns:
        str: Comma-separated approver display names
    """
    fields = issue['fields']
    custom_fields_config = config.get('custom_fields', {})

    approvers_id = custom_fields_config.get('approvers', '')
    approvers_raw = fields.get(approvers_id)

    if isinstance(approvers_raw, list):
        return ", ".join([a.get('displayName', a.get('name', '')) for a in approvers_raw])
    elif isinstance(approvers_raw, dict):
        return approvers_raw.get('displayName', approvers_raw.get('name', 'N/A'))
    else:
        return str(approvers_raw) if approvers_raw else "None"


def map_status(status_jira, mapping, default):
    """
    Map Jira status to GLPI status ID.

    Args:
        status_jira: Jira status name (lowercase)
        mapping: Status mapping dictionary
        default: Default status ID

    Returns:
        int: GLPI status ID
    """
    return mapping.get(status_jira, default)


def map_type(type_jira, mapping, default):
    """
    Map Jira issue type to GLPI ticket type.

    Args:
        type_jira: Jira issue type name (lowercase)
        mapping: Type mapping dictionary
        default: Default type ID

    Returns:
        int: GLPI ticket type ID
    """
    return mapping.get(type_jira, default)


def map_priority(priority_jira, mapping, default):
    """
    Map Jira priority to GLPI urgency and impact.

    Args:
        priority_jira: Jira priority name
        mapping: Priority mapping dictionary
        default: Default (urgency, impact) tuple

    Returns:
        tuple: (urgency, impact)
    """
    priority_lower = priority_jira.lower()
    return mapping.get(priority_lower, default)


def map_classification_to_assets(issue, config, glpi_client, logger):
    """
    Map Jira classifications to GLPI location and items.

    Args:
        issue: Jira issue dictionary
        config: Configuration dictionary
        glpi_client: GLPI client instance
        logger: Logger instance

    Returns:
        dict: {location_id, items_to_link, classification_str}
    """
    fields = issue['fields']
    custom_fields_config = config.get('custom_fields', {})
    classification_id = custom_fields_config.get('classification', '')
    classification_raw = fields.get(classification_id)

    # Normalize to list of strings
    classifications = []
    if isinstance(classification_raw, list):
        for c in classification_raw:
            classifications.append(str(c.get('value') if isinstance(c, dict) else c))
    elif classification_raw:
        classifications.append(str(classification_raw.get('value') if isinstance(classification_raw, dict) else classification_raw))

    location_id = None
    items_to_link = {}  # {"Type": [ID, ID]}

    classification_to_location = config.get('mappings', {}).get('classification_to_location', {})
    classification_to_item = config.get('mappings', {}).get('classification_to_item', {})

    for cls in classifications:
        # Check Location Mapping
        if cls in classification_to_location:
            loc_name = classification_to_location[cls]
            lid = glpi_client.get_location_id(loc_name)
            if lid:
                location_id = lid
                logger.info(f"Mapped classification '{cls}' to location '{loc_name}' (ID: {lid})")
            else:
                logger.warning(f"Location '{loc_name}' not found in GLPI (mapped from '{cls}')")

        # Check Item Mapping
        if cls in classification_to_item:
            item_type, item_name = classification_to_item[cls]

            # Normalize Business_Service -> BusinessService for API
            if item_type == 'Business_Service':
                item_type = 'BusinessService'

            iid = glpi_client.get_item_id(item_type, item_name)
            if iid:
                if item_type not in items_to_link:
                    items_to_link[item_type] = []
                items_to_link[item_type].append(iid)
                logger.info(f"Found item '{item_name}' ({item_type}) ID: {iid}")
            else:
                logger.warning(f"Item '{item_name}' ({item_type}) not found in GLPI (mapped from '{cls}')")

    classification_str = ", ".join(classifications)

    return {
        'location_id': location_id,
        'items_to_link': items_to_link,
        'classification_str': classification_str,
        'classifications': classifications,
    }


def extract_security_category(issue, glpi_client, logger):
    """
    Extract security level and map to GLPI ITIL category.

    Args:
        issue: Jira issue dictionary
        glpi_client: GLPI client instance
        logger: Logger instance

    Returns:
        int: GLPI category ID or None
    """
    fields = issue['fields']
    security = (fields.get('security') or {}).get('name', '')

    if not security or security == 'None':
        return None

    # Try to find matching category in GLPI
    category_id = glpi_client.get_category_id(security)

    if category_id:
        logger.debug(f"Mapped security level '{security}' to category ID {category_id}")
    else:
        logger.debug(f"Security level '{security}' not found in GLPI categories")

    return category_id
