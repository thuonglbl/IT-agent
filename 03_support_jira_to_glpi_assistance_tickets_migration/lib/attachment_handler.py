"""
Attachment handling for Jira to GLPI migration
Downloads from Jira and uploads to GLPI
"""
import os
import requests


def process_attachments(attachments, jira_client, glpi_client, logger):
    """
    Download attachments from Jira and upload to GLPI.

    Args:
        attachments: List of attachment dictionaries from Jira
        jira_client: Jira client instance
        glpi_client: GLPI client instance
        logger: Logger instance

    Returns:
        dict: Mapping of filename to GLPI doc_id {filename: doc_id}
    """
    attachment_map = {}

    if not attachments:
        return attachment_map

    logger.info(f"Processing {len(attachments)} attachments")

    for att in attachments:
        filename = att.get('filename')
        url = att.get('content')

        if not filename or not url:
            continue

        # Avoid processing same filename twice
        if filename in attachment_map:
            logger.debug(f"Skipping duplicate attachment: {filename}")
            continue

        # Process single attachment
        doc_id = process_single_attachment(filename, url, jira_client, glpi_client, logger)

        if doc_id:
            attachment_map[filename] = doc_id

    return attachment_map


def process_single_attachment(filename, url, jira_client, glpi_client, logger):
    """
    Process a single attachment: download from Jira, upload to GLPI.

    Args:
        filename: Attachment filename
        url: Jira attachment URL
        jira_client: Jira client instance
        glpi_client: GLPI client instance
        logger: Logger instance

    Returns:
        int: GLPI document ID or None
    """
    temp_path = None

    try:
        # Download from Jira
        temp_path = download_attachment(filename, url, jira_client, logger)

        if not temp_path:
            return None

        # Upload to GLPI
        doc_id = upload_to_glpi(temp_path, filename, glpi_client, logger)

        return doc_id

    except Exception as e:
        logger.error(f"Failed to process attachment '{filename}': {e}")
        return None

    finally:
        # Cleanup temp file
        if temp_path:
            cleanup_temp_file(temp_path, logger)


def download_attachment(filename, url, jira_client, logger):
    """
    Download attachment from Jira to temporary file.

    Args:
        filename: Attachment filename
        url: Jira attachment URL
        jira_client: Jira client instance
        logger: Logger instance

    Returns:
        str: Path to temporary file or None
    """
    # Use temp prefix to avoid conflicts
    temp_path = f"temp_{filename}"

    try:
        logger.debug(f"Downloading attachment: {filename}")

        with requests.get(
            url,
            headers=jira_client.headers,
            verify=jira_client.verify_ssl,
            stream=True,
            timeout=300
        ) as r:
            r.raise_for_status()

            with open(temp_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        logger.debug(f"Downloaded: {filename} -> {temp_path}")
        return temp_path

    except requests.exceptions.RequestException as e:
        logger.error(f"Download failed for '{filename}': {e}")
        # Cleanup if partial download
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None


def upload_to_glpi(temp_path, filename, glpi_client, logger):
    """
    Upload file to GLPI Documents.

    Args:
        temp_path: Path to temporary file
        filename: Original filename
        glpi_client: GLPI client instance
        logger: Logger instance

    Returns:
        int: GLPI document ID or None
    """
    try:
        logger.debug(f"Uploading to GLPI: {filename}")

        doc_id = glpi_client.upload_document(temp_path, name=filename)

        if doc_id:
            logger.info(f"Uploaded '{filename}' -> Doc ID {doc_id}")
            return doc_id
        else:
            logger.warning(f"Upload returned no doc_id for '{filename}'")
            return None

    except Exception as e:
        logger.error(f"Upload failed for '{filename}': {e}")
        return None


def cleanup_temp_file(path, logger):
    """
    Delete temporary file.

    Args:
        path: Path to temporary file
        logger: Logger instance
    """
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.debug(f"Cleaned up temp file: {path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file '{path}': {e}")


def link_attachments_to_ticket(ticket_id, attachment_map, glpi_client, logger):
    """
    Link all uploaded documents to GLPI ticket.

    Args:
        ticket_id: GLPI ticket ID
        attachment_map: Dict mapping filenames to doc IDs
        glpi_client: GLPI client instance
        logger: Logger instance
    """
    if not attachment_map:
        return

    logger.info(f"Linking {len(attachment_map)} attachments to ticket {ticket_id}")

    for filename, doc_id in attachment_map.items():
        try:
            glpi_client.link_document_to_ticket(ticket_id, doc_id)
            logger.debug(f"Linked doc {doc_id} ({filename}) to ticket {ticket_id}")
        except Exception as e:
            logger.error(f"Failed to link doc {doc_id} ({filename}) to ticket {ticket_id}: {e}")
