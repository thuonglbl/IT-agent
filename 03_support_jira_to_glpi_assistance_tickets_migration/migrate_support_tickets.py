"""
Jira to GLPI Migration Script - Refactored Version 2.0
Migrates support tickets from Jira to GLPI Assistance with resumable state
"""
import os

# Import from shared library
from common.config.loader import load_config
from common.logging.logger import setup_logger
from common.tracking.user_tracker import UserTracker
from common.clients.jira_client import JiraClient
from common.clients.glpi_client import GlpiClient
from common.utils.state_manager import StateManager

# Import local lib modules (domain-specific logic)
from lib.field_extractor import (
    extract_basic_fields,
    extract_actors,
    extract_dates,
    extract_custom_fields,
    extract_participants,
    extract_approvers,
    map_status,
    map_type,
    map_priority,
    map_classification_to_assets,
    extract_security_category,
)
from lib.html_builder import build_full_description
from lib.attachment_handler import process_attachments, link_attachments_to_ticket
from lib.comment_migrator import migrate_comments


# Note: State management now uses shared.utils.state_manager
# Keeping these wrapper functions for backward compatibility
def load_state(state_file):
    """Load migration state from JSON file (wrapper for StateManager)."""
    manager = StateManager(state_file)
    return manager.load()


def save_state(state_file, start_at, total_processed):
    """Save migration state to JSON file (wrapper for StateManager)."""
    manager = StateManager(state_file)
    manager.save(start_at, total_processed)


def sync_security_levels(jira_client, glpi_client, config, logger):
    """
    Sync Jira security levels to GLPI ITIL categories.
    Creates categories in GLPI if they don't exist.

    Args:
        jira_client: Jira client instance
        glpi_client: GLPI client instance
        config: Configuration dictionary
        logger: Logger instance
    """
    logger.info("Syncing Jira security levels to GLPI categories...")

    try:
        # Get security levels from Jira
        security_levels = jira_client.get_security_levels()

        if not security_levels:
            logger.warning("No security levels found in Jira")
            return

        for level_name in security_levels:
            # Check if category exists in GLPI
            category_id = glpi_client.get_category_id(level_name)

            if not category_id:
                # Create category if it doesn't exist
                try:
                    category_id = glpi_client.create_category(level_name)
                    logger.info(f"Created GLPI category: {level_name} (ID: {category_id})")
                except Exception as e:
                    logger.warning(f"Failed to create category '{level_name}': {e}")

    except Exception as e:
        logger.error(f"Failed to sync security levels: {e}")


def build_dynamic_status_mapping(jira_client, glpi_client, config, logger):
    """
    Build dynamic status mapping from Jira project statuses and GLPI statuses.

    Args:
        jira_client: Jira client instance
        glpi_client: GLPI client instance
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        dict: Status mapping (lowercase jira status -> glpi status id)
    """
    logger.info("Building dynamic status mapping...")

    # Start with configured mapping
    status_mapping = config.get('mappings', {}).get('status', {}).copy()

    try:
        # Get Jira project statuses
        project_key = config.get('jira', {}).get('project_key', '')
        jira_statuses = jira_client.get_project_statuses(project_key)

        # Get GLPI statuses (fixed list)
        glpi_statuses = glpi_client.get_ticket_statuses()

        # Build lowercase map for GLPI statuses
        glpi_status_map = {s['name'].lower(): s['id'] for s in glpi_statuses}

        # Add dynamic mappings for matching names
        for s in jira_statuses:
            jira_status_lower = s['name'].lower()
            if jira_status_lower in glpi_status_map:
                status_mapping[jira_status_lower] = glpi_status_map[jira_status_lower]
                logger.debug(f"Dynamic mapping: '{s['name']}' -> {glpi_status_map[jira_status_lower]}")

    except Exception as e:
        logger.warning(f"Failed to build dynamic status mapping: {e}")

    logger.info(f"Status mapping has {len(status_mapping)} entries")
    return status_mapping


def process_issue(jira_client, glpi_client, issue, status_mapping, config, logger, user_tracker):
    """
    Process a single Jira issue and create corresponding GLPI ticket.

    Args:
        jira_client: Jira client instance
        glpi_client: GLPI client instance
        issue: Jira issue dictionary
        status_mapping: Dynamic status mapping dictionary
        config: Configuration dictionary
        logger: Logger instance
        user_tracker: UserTracker instance

    Returns:
        int: GLPI ticket ID
    """
    # 1. Extract basic fields
    basic = extract_basic_fields(issue, config)
    logger.info(f"Processing {basic['key']}: {basic['summary']}")

    # 2. Extract actors (reporter, assignee)
    actors = extract_actors(issue, glpi_client, logger, user_tracker)

    # 3. Extract dates
    dates = extract_dates(issue)

    # 4. Extract custom fields
    custom = extract_custom_fields(issue, config)

    # 5. Extract participants
    participants = extract_participants(issue, config, glpi_client, logger, user_tracker)

    # 6. Extract approvers
    approvers = extract_approvers(issue, config)

    # 7. Process attachments
    attachments = issue['fields'].get('attachment', [])
    attachment_map = process_attachments(attachments, jira_client, glpi_client, logger)

    # 8. Map classification to location and items
    classification_assets = map_classification_to_assets(issue, config, glpi_client, logger)

    # 9. Extract security level -> ITIL category
    itilcategories_id = extract_security_category(issue, glpi_client, logger)

    # 10. Build complete HTML description
    full_desc = build_full_description(
        issue,
        basic,
        custom,
        actors,
        participants,
        approvers,
        dates,
        attachment_map,
        glpi_client,
        config
    )

    # 11. Map status, type, priority
    glpi_status = map_status(
        basic['status_jira'],
        status_mapping,
        config.get('mappings', {}).get('status_default', 3)
    )

    glpi_type = map_type(
        basic['type_jira'],
        config.get('mappings', {}).get('type', {}),
        config.get('mappings', {}).get('type_default', 2)
    )

    urgency, impact = map_priority(
        basic['priority_jira'],
        config.get('mappings', {}).get('priority', {}),
        config.get('mappings', {}).get('priority_default', [3, 3])
    )

    # 12. Build ticket arguments
    ticket_args = {
        "status": glpi_status,
        "type": glpi_type,
        "urgency": urgency,
        "impact": impact,
        "date": dates['created'],
    }

    # Add optional fields
    if dates['updated']:
        ticket_args["date_mod"] = dates['updated']

    if dates['resolved']:
        ticket_args["solvedate"] = dates['resolved']
        ticket_args["closedate"] = dates['resolved']

    if actors['requester_id']:
        ticket_args["_users_id_requester"] = actors['requester_id']

    if actors['assignee_id']:
        ticket_args["_users_id_assign"] = actors['assignee_id']

    if participants['participant_ids']:
        ticket_args["_users_id_observer"] = participants['participant_ids']

    if classification_assets['location_id']:
        ticket_args["locations_id"] = classification_assets['location_id']

    if itilcategories_id:
        ticket_args["itilcategories_id"] = itilcategories_id

    # 13. Create ticket in GLPI
    ticket_id = glpi_client.create_ticket(
        name=basic['summary'],
        content=full_desc,
        **ticket_args
    )

    logger.info(f"  -> Created Ticket ID: {ticket_id}")

    # 14. Link items (Business Services, Software, etc.)
    for item_type, item_ids in classification_assets['items_to_link'].items():
        for item_id in item_ids:
            try:
                glpi_client.link_item_to_ticket(ticket_id, item_type, item_id)
                logger.debug(f"Linked {item_type} {item_id} to ticket {ticket_id}")
            except Exception as e:
                logger.warning(f"Failed to link {item_type} {item_id} to ticket {ticket_id}: {e}")

    # 15. Link attachments
    link_attachments_to_ticket(ticket_id, attachment_map, glpi_client, logger)

    # 16. Migrate comments
    migrate_comments(ticket_id, issue, attachment_map, glpi_client, config, logger, user_tracker)

    return ticket_id


def main():
    """
    Main migration orchestrator.
    Coordinates configuration, clients, and migration flow.
    """
    # Load configuration
    try:
        config = load_config()
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}")
        return

    # Setup logging
    logger = setup_logger("migration", config)
    logger.info("=== Jira Support to GLPI Assistance Migration v2.0 ===")

    # Initialize user tracker
    user_tracker = UserTracker()
    user_tracker.logger = logger

    # Get configuration sections
    jira_config = config.get('jira', {})
    glpi_config = config.get('glpi', {})
    migration_config = config.get('migration', {})

    # Initialize clients
    logger.info("Initializing Jira client...")
    jira = JiraClient(
        jira_config.get('url'),
        jira_config.get('pat'),
        verify_ssl=jira_config.get('verify_ssl', True)
    )

    logger.info("Initializing GLPI client...")
    glpi = GlpiClient(
        glpi_config.get('url'),
        glpi_config.get('app_token'),
        user_token=glpi_config.get('user_token'),
        username=glpi_config.get('username'),
        password=glpi_config.get('password'),
        verify_ssl=glpi_config.get('verify_ssl', True)
    )

    try:
        # Initialize GLPI session
        logger.info("Initializing GLPI session...")
        glpi.init_session()

        # Load GLPI caches
        logger.info("Loading GLPI user cache...")
        glpi.load_user_cache(recursive=True)

        logger.info("Loading GLPI group cache...")
        glpi.load_group_cache(recursive=True)

        logger.info("Loading GLPI category cache...")
        glpi.load_category_cache(recursive=True)

        logger.info("Loading GLPI location cache...")
        glpi.load_location_cache()

        # Build dynamic status mapping
        status_mapping = build_dynamic_status_mapping(jira, glpi, config, logger)

        # Load state
        state_file = migration_config.get('state_file', 'migration_state.json')
        state = load_state(state_file)
        start_at = state["start_at"]
        total_processed = state["total_processed"]

        logger.info(f"Resuming from offset {start_at}, {total_processed} processed so far")

        # Sync security levels (only on first run)
        if start_at == 0:
            sync_security_levels(jira, glpi, config, logger)

        # Debug mode configuration
        debug_config = migration_config.get('debug', {})
        debug_ticket = debug_config.get('target_ticket_key')
        debug_enabled = debug_config.get('enabled', False)

        if debug_ticket:
            logger.info(f"[DEBUG MODE] Targeting single ticket: {debug_ticket}")
        elif debug_enabled:
            logger.info("[DEBUG MODE] Will process 1 ticket and exit")

        # Main migration loop
        batch_size = migration_config.get('batch_size', 50)
        project_key = jira_config.get('project_key')

        while True:
            # Build JQL query
            if debug_ticket:
                jql = f"key = {debug_ticket}"
                search_start = 0
            else:
                jql = f"project = {project_key} ORDER BY key ASC"
                search_start = start_at

            # Fetch issues from Jira
            logger.info(f"Fetching issues (offset: {search_start}, limit: {batch_size})...")
            issues, total = jira.search_issues(jql, start_at=search_start, max_results=batch_size)

            if not issues:
                logger.info("No more issues to process")
                break

            logger.info(f"Batch: {len(issues)} issues (Total in Jira: {total})")

            # Process each issue
            for issue in issues:
                try:
                    process_issue(jira, glpi, issue, status_mapping, config, logger, user_tracker)
                    total_processed += 1

                    # Debug mode: process 1 and exit
                    if debug_enabled and not debug_ticket:
                        logger.info("[DEBUG] Processed 1 issue. Exiting.")
                        save_state(state_file, start_at + 1, total_processed)
                        return

                except Exception as e:
                    logger.error(f"Failed to process issue {issue.get('key', 'UNKNOWN')}: {e}", exc_info=True)

            # Check if debug_ticket mode (process only that ticket)
            if debug_ticket:
                logger.info("[DEBUG MODE] Finished target ticket")
                break

            # Update state
            start_at += len(issues)
            save_state(state_file, start_at, total_processed)
            logger.info(f"State saved. Next batch at offset {start_at}")

        # Migration complete
        logger.info(f"Migration complete. Total processed: {total_processed}")

    except Exception as e:
        logger.critical(f"Migration failed: {e}", exc_info=True)
        raise

    finally:
        # Save missing users report
        missing_users_file = migration_config.get('missing_users_file', 'missing_users.txt')
        user_tracker.save_report(missing_users_file)

        # Kill GLPI session
        try:
            glpi.kill_session()
            logger.info("GLPI session closed")
        except:
            pass


if __name__ == "__main__":
    main()
