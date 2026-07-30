import os
import sys
import re
import argparse
import logging

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from common.clients.glpi_client import GlpiClient
from common.config.loader import load_config
from common.utils.mapping_manager import IdMappingManager

def setup_logger():
    logger = logging.getLogger("link_updater")
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger

def get_link_regexes(config):
    jira_url = config.get('jira', {}).get('url', '')
    patterns = config.get('jira', {}).get('link_patterns', [])
    if not patterns:
        patterns = [
            "{jira_url}/secure/RapidBoard.jspa?.*?selectedIssue={jira_key}.*",
            "{jira_url}/browse/{jira_key}",
            "{jira_url}/projects/.*/issues/{jira_key}.*"
        ]
    
    regex_list = []
    # Jira keys: usually uppercase letters followed by hyphen and numbers
    # We will just substitute the placeholders to build the regex string
    for pat in patterns:
        pat_str = pat.replace("{jira_url}", re.escape(jira_url))
        # jira_key is a named group
        pat_str = pat_str.replace("{jira_key}", r"(?P<jira_key>[A-Z0-9]+-\d+)")
        regex_list.append(re.compile(pat_str))
    
    # Also add a plain text key matcher (not part of a URL)
    # Be careful not to match things inside existing hrefs if possible, 
    # but since we are processing HTML/Text we'll do our best.
    plain_text_pattern = re.compile(r'(?<![a-zA-Z0-9\-])(?P<jira_key>[A-Z0-9]+-\d+)(?![a-zA-Z0-9\-])')
    
    return regex_list, plain_text_pattern

def replace_links_in_content(content, regex_list, plain_text_pattern, mapping_manager, glpi_url, item_type, glpi_link_patterns):
    if not content:
        return content, False

    modified = False

    def get_glpi_link(glpi_id, jira_key):
        pattern = glpi_link_patterns.get(item_type)
        if pattern:
            return pattern.replace("{glpi_base_url}", glpi_url).replace("{glpi_id}", str(glpi_id))
        
        # Fallback to defaults
        if item_type == 'Ticket':
            return f"{glpi_url}/front/ticket.form.php?id={glpi_id}"
        else: # ProjectTask
            return f"{glpi_url}/front/projecttask.form.php?id={glpi_id}"

    # 0. Hide the Jira Details Key row so we don't replace its Jira tracking link
    # The html_builder.py creates this row exactly like: <tr><td><strong>Key</strong></td><td><a href="...">...</a></td></tr>
    # We will temporarily substitute it with a placeholder.
    hidden_keys = []
    key_row_pattern = re.compile(r'(<tr>\s*<td>\s*<strong>Key</strong>\s*</td>\s*<td>\s*)(<a[^>]+href="[^"]+"[^>]*>.*?</a>)(\s*</td>\s*</tr>)', re.IGNORECASE)
    
    def hide_key(match):
        hidden_keys.append(match.group(2))
        return f"{match.group(1)}___HIDDEN_KEY_{len(hidden_keys)-1}___{match.group(3)}"
        
    content = key_row_pattern.sub(hide_key, content)
    
    # 0.5 Hide the Original Jira Key row (module 02) so we don't replace its Jira tracking link
    original_key_pattern = re.compile(r'(<p>\s*<b>\s*Original Jira Key:</b>\s*)(.*?)(</p>)', re.IGNORECASE)
    content = original_key_pattern.sub(hide_key, content)

    # 1. First, replace URLs inside <a href="...">...</a>
    # We look for <a href="JIRA_URL">text</a> and replace the href and possibly the text
    def replace_a_tag(match):
        nonlocal modified
        full_tag = match.group(0)
        href = match.group('href')
        inner_text = match.group('inner')
        
        # Check if href matches any jira url
        for regex in regex_list:
            m = regex.search(href)
            if m:
                key = m.group('jira_key')
                glpi_id = mapping_manager.get_glpi_id(key)
                if glpi_id:
                    modified = True
                    new_href = get_glpi_link(glpi_id, key)
                    # Replace the Jira key in the inner text with just the GLPI ID
                    new_inner = plain_text_pattern.sub(lambda x: f"GLPI-{glpi_id}", inner_text)
                    # Strip out " - JIRA" which Jira often appends to page titles
                    new_inner = new_inner.replace(" - JIRA", "").strip()
                    return f'<a href="{new_href}" target="_blank">{new_inner}</a>'
        
        return full_tag
        
    a_tag_pattern = re.compile(r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<inner>.*?)</a>', re.IGNORECASE)
    content = a_tag_pattern.sub(replace_a_tag, content)

    # 2. Replace plain text Jira URLs that are NOT inside <a> tags
    # Wait, they are probably already inside <a> tags because html_builder.py converts them, 
    # but just in case, we do a split by HTML tags and replace plain text keys and URLs
    parts = re.split(r'(<[^>]+>)', content)
    for i, part in enumerate(parts):
        if not part.startswith('<'):
            # Replace raw URLs first
            for regex in regex_list:
                def replace_raw_url(match):
                    nonlocal modified
                    key = match.group('jira_key')
                    glpi_id = mapping_manager.get_glpi_id(key)
                    if glpi_id:
                        modified = True
                        new_href = get_glpi_link(glpi_id, key)
                        return f'<a href="{new_href}" target="_blank">GLPI-{glpi_id}</a>'
                    return match.group(0)
                part = regex.sub(replace_raw_url, part)
                
            # Replace plain text keys
            def replace_plain_key(match):
                nonlocal modified
                key = match.group('jira_key')
                glpi_id = mapping_manager.get_glpi_id(key)
                if glpi_id:
                    modified = True
                    new_href = get_glpi_link(glpi_id, key)
                    return f'<a href="{new_href}" target="_blank">GLPI-{glpi_id}</a>'
                return match.group(0)
            
            # Also strip out " - JIRA" from plain text parts
            part = part.replace(" - JIRA", "")
            parts[i] = plain_text_pattern.sub(replace_plain_key, part)

    content = "".join(parts)
    
    # 3. Restore the hidden Jira Details Key row
    for i, hidden_tag in enumerate(hidden_keys):
        placeholder = f"___HIDDEN_KEY_{i}___"
        if placeholder in content:
            content = content.replace(placeholder, hidden_tag)
            # We don't set modified = True here because it's just restoring what we hid
            
    return content, modified

def main():
    parser = argparse.ArgumentParser(description="Update Jira links to GLPI links")
    parser.add_argument('--module', choices=['02', '03'], required=True, help="Module to process: 02 (ProjectTasks) or 03 (Tickets)")
    args = parser.add_argument_parse() if hasattr(parser, 'add_argument_parse') else parser.parse_args()

    logger = setup_logger()
    
    # Select module specifics and load config
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if args.module == '02':
        config_path = os.path.join(root_dir, '02_project_jira_to_glpi_project_tasks_migration/config.yaml')
        map_path = os.path.join(root_dir, '02_project_jira_to_glpi_project_tasks_migration/jira_glpi_mapping.json')
        item_type = 'ProjectTask'
        subitem_type = 'Notepad'
    else:
        config_path = os.path.join(root_dir, '03_support_jira_to_glpi_assistance_tickets_migration/config.yaml')
        map_path = os.path.join(root_dir, '03_support_jira_to_glpi_assistance_tickets_migration/jira_glpi_id_map.json')
        item_type = 'Ticket'
        subitem_type = 'ITILFollowup'

    try:
        from common.config.loader import ConfigLoader
        loader = ConfigLoader(config_path=config_path)
        config = loader.load()
    except Exception as e:
        logger.error(f"Failed to load config from {config_path}: {e}")
        return

    # Base URLs
    glpi_url_api = config.get('glpi', {}).get('url', '')
    glpi_url = glpi_url_api.replace('/apirest.php', '').replace('/api.php/v1', '').replace('/api.php/v2.1', '').rstrip('/')

    # Load mapping
    if not os.path.exists(map_path):
        # Fallback check
        map_path = map_path.replace('jira_glpi_mapping.json', 'jira_glpi_id_map.json')
        if not os.path.exists(map_path):
            logger.error(f"Mapping file not found: {map_path}")
            return
            
    mapping_manager = IdMappingManager(map_path)
    mapping = mapping_manager.get_all()
    if not mapping:
        logger.info("Mapping is empty. Nothing to do.")
        return
        
    logger.info(f"Loaded {len(mapping)} mappings from {map_path}")

    # Init GLPI Client
    glpi_config = config.get('glpi', {})
    glpi = GlpiClient(
        glpi_config.get('url'),
        glpi_config.get('app_token'),
        user_token=glpi_config.get('user_token'),
        username=glpi_config.get('username'),
        password=glpi_config.get('password'),
        verify_ssl=glpi_config.get('verify_ssl', True)
    )
    
    try:
        glpi.init_session()
        logger.info("GLPI session initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize GLPI session: {e}")
        return

    regex_list, plain_text_pattern = get_link_regexes(config)

    glpi_link_patterns = config.get('glpi', {}).get('link_patterns', {})
    
    # Debug Mode
    debug_mode = config.get('migration', {}).get('debug', False)
    debug_ticket = config.get('migration', {}).get('debug_ticket', '')
    
    if debug_mode and debug_ticket:
        logger.info(f"DEBUG MODE ENABLED: Processing only ticket {debug_ticket}")
        if debug_ticket in mapping:
            mapping = {debug_ticket: mapping[debug_ticket]}
        else:
            logger.warning(f"Debug ticket {debug_ticket} not found in mapping. Exiting.")
            return

    for jira_key, glpi_id in mapping.items():
        logger.info(f"Processing {item_type} {glpi_id} (Jira: {jira_key})")
        
        # 1. Update Main Item Content
        item = glpi.get_item(item_type, glpi_id)
        if not item:
            logger.warning(f"Could not fetch {item_type} {glpi_id}")
            continue
            
        content = item.get('content', '')
        new_content, modified = replace_links_in_content(
            content, regex_list, plain_text_pattern, mapping_manager, glpi_url, item_type, glpi_link_patterns
        )
        
        if modified:
            logger.info(f"  -> Updating description links for {glpi_id}")
            success = glpi.update_item(item_type, glpi_id, {"content": new_content})
            if not success:
                logger.error(f"  -> Failed to update {item_type} {glpi_id}")
                
        # 2. Update Subitems (Followups/Notes)
        subitems = glpi.get_subitems(item_type, glpi_id, subitem_type)
        if subitems:
            for sub in subitems:
                sub_id = sub.get('id')
                sub_content = sub.get('content', '')
                new_sub_content, sub_mod = replace_links_in_content(
                    sub_content, regex_list, plain_text_pattern, mapping_manager, glpi_url, item_type, glpi_link_patterns
                )
                
                if sub_mod:
                    logger.info(f"  -> Updating {subitem_type} {sub_id} links for {glpi_id}")
                    success = glpi.update_item(subitem_type, sub_id, {"content": new_sub_content})
                    if not success:
                        logger.error(f"  -> Failed to update {subitem_type} {sub_id}")

    try:
        glpi.kill_session()
    except:
        pass
        
    logger.info("Update links complete.")

if __name__ == "__main__":
    main()
