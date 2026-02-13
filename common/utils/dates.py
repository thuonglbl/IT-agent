"""
Date parsing and formatting utilities for Jira to GLPI migrations
Handles timezone conversions (UTC+7) and multiple date formats
"""
from datetime import datetime, timedelta, timezone


# Define UTC+7 Timezone (Vietnam)
TZ_VN = timezone(timedelta(hours=7))


def parse_jira_date(date_str):
    """
    Parse Jira ISO date string to GLPI format (YYYY-MM-DD HH:MM:SS).
    Converts to UTC+7 timezone.

    Args:
        date_str: Jira date string in ISO format (e.g., "2024-01-15T10:30:00.000+0700")

    Returns:
        str: Date in GLPI format (YYYY-MM-DD HH:MM:SS) or None if parsing fails

    Examples:
        >>> parse_jira_date("2024-01-15T10:30:00.000+0700")
        "2024-01-15 10:30:00"

        >>> parse_jira_date("2024-01-15T10:30:00+0700")
        "2024-01-15 10:30:00"

        >>> parse_jira_date(None)
        None
    """
    if not date_str:
        return None

    try:
        # Try parsing with milliseconds
        if '.' in date_str:
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")

        # Convert to UTC+7
        dt_vn = dt.astimezone(TZ_VN)
        return dt_vn.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            # Fallback: parse without timezone
            dt = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return None


def format_glpi_date_friendly(date_str):
    """
    Format date for friendly display in HTML with UTC+7 indicator.

    Args:
        date_str: Date string in GLPI format (YYYY-MM-DD HH:MM:SS)

    Returns:
        str: Formatted date (YYYY-MM-DD HH:MM AM/PM (UTC+7))

    Examples:
        >>> format_glpi_date_friendly("2024-01-15 10:30:00")
        "2024-01-15 10:30 AM (UTC+7)"

        >>> format_glpi_date_friendly(None)
        "N/A"
    """
    if not date_str:
        return "N/A"

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d %I:%M %p (UTC+7)")
    except:
        return f"{date_str} (UTC+7)"


def format_comment_date(date_str):
    """
    Format date for comment headers (Jira style).

    Args:
        date_str: Jira date string in ISO format

    Returns:
        str: Formatted date (dd/Mon/yy h:mm AM/PM (UTC+7))

    Examples:
        >>> format_comment_date("2024-01-15T16:58:30.000+0700")
        "15/Jan/24 4:58 PM (UTC+7)"

        >>> format_comment_date(None)
        "N/A"
    """
    if not date_str:
        return "N/A"

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
