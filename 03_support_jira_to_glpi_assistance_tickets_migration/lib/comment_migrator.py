"""
Comment migration from Jira to GLPI followups
"""
from lib.utils import parse_jira_date, format_comment_date
from lib.html_builder import convert_jira_content


def migrate_comments(ticket_id, issue, attachment_map, glpi_client, config, logger, user_tracker):
    """
    Migrate all Jira comments to GLPI followups.

    Args:
        ticket_id: GLPI ticket ID
        issue: Jira issue dictionary
        attachment_map: Attachment filename to doc_id mapping
        glpi_client: GLPI client instance
        config: Configuration dictionary
        logger: Logger instance
        user_tracker: UserTracker instance
    """
    fields = issue['fields']
    comments = (fields.get('comment') or {}).get('comments', [])

    if not comments:
        logger.debug("No comments to migrate")
        return

    logger.info(f"Migrating {len(comments)} comments for ticket {ticket_id}")

    for comment in comments:
        process_single_comment(
            comment,
            ticket_id,
            attachment_map,
            glpi_client,
            config,
            logger,
            user_tracker
        )


def process_single_comment(comment, ticket_id, attachment_map, glpi_client, config, logger, user_tracker):
    """
    Process and post a single comment to GLPI.

    Args:
        comment: Jira comment dictionary
        ticket_id: GLPI ticket ID
        attachment_map: Attachment filename to doc_id mapping
        glpi_client: GLPI client instance
        config: Configuration dictionary
        logger: Logger instance
        user_tracker: UserTracker instance
    """
    # Extract comment data
    author_display = (comment.get('author') or {}).get('displayName', 'Unknown')
    author_jira = (comment.get('author') or {}).get('name')
    body = comment.get('body', '')
    created = parse_jira_date(comment.get('created'))

    # Map comment author to GLPI user
    author_id = get_comment_author_id(author_jira, author_display, glpi_client, logger, user_tracker)

    # Convert Jira markup to HTML
    body_converted = convert_jira_content(body, attachment_map)

    # Format comment header (Jira style)
    comment_date_str = format_comment_date(comment.get('created'))
    header = format_comment_header(author_display, comment_date_str)

    # Post to GLPI
    try:
        full_content = header + body_converted
        glpi_client.add_ticket_followup(
            ticket_id,
            full_content,
            users_id=author_id,
            date=created
        )
        logger.debug(f"Posted comment by {author_display} to ticket {ticket_id}")

    except Exception as e:
        logger.error(f"Failed to post comment by {author_display} to ticket {ticket_id}: {e}")


def format_comment_header(author_display, date_str):
    """
    Generate comment header in Jira style.

    Args:
        author_display: Author display name
        date_str: Formatted date string

    Returns:
        str: Comment header

    Example:
        **John Doe added a comment - 15/Jan/24 4:58 PM (UTC+7)**:
    """
    return f"**{author_display} added a comment - {date_str}**:\n"


def get_comment_author_id(author_jira, author_display, glpi_client, logger, user_tracker):
    """
    Map Jira comment author to GLPI user ID.

    Args:
        author_jira: Jira username (login)
        author_display: Author display name
        glpi_client: GLPI client instance
        logger: Logger instance
        user_tracker: UserTracker instance

    Returns:
        int: GLPI user ID or None (posted by API user)
    """
    if not author_jira:
        return None

    author_id = glpi_client.get_user_id_by_name(author_jira)

    if not author_id:
        logger.warning(f"Comment author '{author_jira}' not found in GLPI. Will be posted by API user.")
        user_tracker.report_missing_user(author_jira, author_display)
        return None

    logger.debug(f"Posting comment as User ID {author_id} ({author_display})")
    return author_id
