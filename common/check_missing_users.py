"""
Check Missing Users: Identify Jira users not present in GLPI.

Run BEFORE migration to find which Jira users need manual LDAP import.
Combines two sources: project assignable users + issue assignee/reporter scan.
Compares against GLPI user cache, checks AD status via LDAP, and outputs
a detailed TSV report with reason and related tickets.

Usage:
    cd common
    python check_missing_users.py PROJ1 PROJ2
    python check_missing_users.py PROJ1 --skip-issues -o report.txt
"""

import os
import sys

# Fix: common/logging/ shadows stdlib logging. Remove script dir from path,
# add project root instead so "common" is a proper package.
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir in sys.path:
    sys.path.remove(_script_dir)
sys.path.insert(0, os.path.abspath(os.path.join(_script_dir, '..')))

import argparse
import urllib3

from common.config.loader import load_config
from common.clients.jira_client import JiraClient
from common.clients.glpi_client import GlpiClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def collect_project_users(jira, project_key):
    """
    Collect assignable users for a project via Jira API.

    Args:
        jira: JiraClient instance
        project_key: Jira project key

    Returns:
        dict: {login: {'display_name': str, 'issues': set()}}
    """
    users = {}
    raw_users = jira.get_project_users(project_key)
    for u in raw_users:
        login = u.get('name') or u.get('key')
        display = u.get('displayName', login)
        if login:
            users[login] = {'display_name': display, 'issues': set()}
    print(f"  [Assignable] {len(users)} users from {project_key}")
    return users


def collect_issue_users(jira, project_key, batch_size=100):
    """
    Collect unique assignee/reporter users by paginating all project issues.
    Tracks which issue keys reference each user.

    Args:
        jira: JiraClient instance
        project_key: Jira project key
        batch_size: Number of issues per API page

    Returns:
        dict: {login: {'display_name': str, 'issues': set(issue_keys)}}
    """
    users = {}
    jql = f"project = {project_key} ORDER BY key ASC"
    start_at = 0

    total = jira.get_issue_count(jql)
    print(f"  [Issues] Scanning {total} issues in {project_key}...")

    while start_at < total:
        issues, _ = jira.search_issues_lightweight(
            jql,
            fields=["assignee", "reporter"],
            start_at=start_at,
            max_results=batch_size
        )
        if not issues:
            break

        for issue in issues:
            issue_key = issue.get('key', '')
            fields = issue.get('fields', {})
            for field_name in ('assignee', 'reporter'):
                person = fields.get(field_name)
                if person:
                    login = person.get('name') or person.get('key')
                    display = person.get('displayName', login)
                    if login:
                        if login not in users:
                            users[login] = {'display_name': display, 'issues': set()}
                        if issue_key:
                            users[login]['issues'].add(issue_key)

        start_at += len(issues)
        print(f"    Scanned {min(start_at, total)}/{total} issues, {len(users)} unique users so far")

    print(f"  [Issues] {len(users)} unique users from issues in {project_key}")
    return users


def merge_users(target, source):
    """
    Merge source user dict into target, unioning issues sets.

    Args:
        target: dict to merge into (modified in place)
        source: dict to merge from
    """
    for login, info in source.items():
        if login in target:
            target[login]['issues'] |= info['issues']
        else:
            target[login] = {
                'display_name': info['display_name'],
                'issues': set(info['issues']),
            }


def check_against_glpi(users_dict, glpi):
    """
    Check each Jira user against GLPI user cache, return missing logins.

    Args:
        users_dict: {login: {'display_name': str, 'issues': set()}}
        glpi: GlpiClient instance (with user cache loaded)

    Returns:
        list: sorted list of logins not found in GLPI
    """
    missing = []
    for login in sorted(users_dict.keys()):
        glpi_id = glpi.get_user_id_by_name(login)
        if glpi_id is None:
            missing.append(login)
    return missing


def get_ldap_config(glpi):
    """
    Fetch LDAP server configuration from GLPI API.

    Args:
        glpi: GlpiClient instance (with active session)

    Returns:
        dict: {'host': str, 'port': int, 'basedn': str} or None on failure
    """
    import requests as req
    endpoint = f"{glpi.url}/AuthLDAP"
    params = {"range": "0-0", "expand_dropdowns": "false"}
    try:
        response = req.get(endpoint, headers=glpi.headers, params=params, verify=glpi.verify_ssl)
        if response.status_code != 200:
            print(f"  GLPI AuthLDAP API returned {response.status_code}")
            return None
        data = response.json()
        if isinstance(data, list) and data:
            entry = data[0]
        elif isinstance(data, dict):
            entry = data
        else:
            return None
        host = entry.get('host')
        port = entry.get('port', 389)
        basedn = entry.get('basedn')
        if not host or not basedn:
            return None
        return {'host': host, 'port': int(port), 'basedn': basedn}
    except Exception as e:
        print(f"  Failed to fetch LDAP config from GLPI: {e}")
        return None


def connect_ldap(ldap_cfg, glpi_cfg):
    """
    Connect to Active Directory using ldap3 library.
    Derives AD domain from basedn, binds with GLPI credentials.

    Args:
        ldap_cfg: dict with 'host', 'port', 'basedn'
        glpi_cfg: dict with 'username' and 'password'

    Returns:
        ldap3.Connection or None
    """
    try:
        import ldap3
    except ImportError:
        print("  ldap3 not installed — skipping AD check")
        return None

    username = glpi_cfg.get('username')
    password = glpi_cfg.get('password')
    if not username or not password:
        print("  No GLPI username/password — skipping AD check")
        return None

    # Derive domain from basedn (e.g. "DC=example,DC=com" -> "example.com")
    parts = []
    for component in ldap_cfg['basedn'].split(','):
        component = component.strip()
        if component.upper().startswith('DC='):
            parts.append(component[3:])
    domain = '.'.join(parts) if parts else None
    if not domain:
        print(f"  Cannot derive domain from basedn: {ldap_cfg['basedn']}")
        return None

    bind_user = f"{username}@{domain}"
    try:
        server = ldap3.Server(ldap_cfg['host'], port=ldap_cfg['port'], get_info=ldap3.NONE)
        conn = ldap3.Connection(server, user=bind_user, password=password, auto_bind=True)
        print(f"  Connected to AD: {ldap_cfg['host']} as {bind_user}")
        return conn
    except Exception as e:
        print(f"  LDAP connection failed: {e}")
        return None


def check_ad_status(conn, base_dn, login, jira_key=None):
    """
    Check a user's Active Directory status.

    Args:
        conn: ldap3.Connection (or None to skip)
        base_dn: LDAP base DN for search
        login: Jira login name (tried first as sAMAccountName)
        jira_key: Jira key field (tried as fallback if different from login)

    Returns:
        str: reason string describing AD status
    """
    if conn is None:
        return "Not in GLPI"

    import ldap3

    # Search by login first
    search_filter = f"(sAMAccountName={login})"
    try:
        conn.search(base_dn, search_filter, attributes=['userAccountControl', 'sAMAccountName'])
    except Exception:
        return "Not in GLPI"

    if conn.entries:
        uac = int(conn.entries[0]['userAccountControl'].value)
        if uac & 2:
            return "Disabled in AD"
        return "Active in AD but not in GLPI"

    # Not found by login — try jira_key if usable
    if jira_key and jira_key != login and not jira_key.startswith('JIRAUSER'):
        search_filter = f"(sAMAccountName={jira_key})"
        try:
            conn.search(base_dn, search_filter, attributes=['userAccountControl', 'sAMAccountName'])
        except Exception:
            return "Deleted from AD"

        if conn.entries:
            uac = int(conn.entries[0]['userAccountControl'].value)
            if uac & 2:
                return f"Disabled in AD (sAMAccountName={jira_key})"
            return f"Active in AD as {jira_key}, not in GLPI"

    return "Deleted from AD"


def save_detailed_report(missing_details, filepath):
    """
    Write detailed missing users report as TSV.

    Args:
        missing_details: list of dicts with keys:
            'login', 'jira_key', 'display_name', 'reason', 'issues'
        filepath: output file path
    """
    if not missing_details:
        print("No missing users to report.")
        return

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("Login Name\tJira Key\tFull Name\tReason\tRelated Tickets\n")
        for entry in sorted(missing_details, key=lambda e: e['login']):
            tickets = ', '.join(sorted(entry.get('issues', [])))
            f.write(f"{entry['login']}\t{entry['jira_key']}\t{entry['display_name']}\t{entry['reason']}\t{tickets}\n")

    print(f"\n[REPORT] {len(missing_details)} missing users written to {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Check which Jira users are missing from GLPI"
    )
    parser.add_argument(
        'project_keys',
        nargs='+',
        help="One or more Jira project keys (e.g. PROJ1 PROJ2)"
    )
    parser.add_argument(
        '-o', '--output',
        default='missing_users.txt',
        help="Output file path (default: missing_users.txt)"
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help="Issues per API page (default: 100)"
    )
    parser.add_argument(
        '--skip-issues',
        action='store_true',
        help="Only use assignable users (skip issue scan)"
    )
    args = parser.parse_args()

    # Load config
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    config = load_config(config_path, validate=False)

    jira_cfg = config.get('jira', {})
    glpi_cfg = config.get('glpi', {})

    # Init Jira client
    jira = JiraClient(
        url=jira_cfg['url'],
        token=jira_cfg.get('pat') or jira_cfg.get('token'),
        verify_ssl=jira_cfg.get('verify_ssl', False)
    )

    # Init GLPI client and load user cache
    glpi = GlpiClient(
        url=glpi_cfg['url'],
        app_token=glpi_cfg['app_token'],
        user_token=glpi_cfg.get('user_token'),
        username=glpi_cfg.get('username'),
        password=glpi_cfg.get('password'),
        verify_ssl=glpi_cfg.get('verify_ssl', False)
    )
    glpi.init_session()
    glpi.load_user_cache()

    # Collect users from all projects
    all_users = {}
    for project_key in args.project_keys:
        print(f"\nCollecting users from project: {project_key}")

        # Source 1: Assignable users
        assignable = collect_project_users(jira, project_key)
        merge_users(all_users, assignable)

        # Source 2: Issue assignees/reporters
        if not args.skip_issues:
            from_issues = collect_issue_users(jira, project_key, args.batch_size)
            merge_users(all_users, from_issues)

    print(f"\nTotal unique Jira users collected: {len(all_users)}")
    print(f"GLPI users in cache: {len(glpi.user_cache)}")

    # Filter missing users
    print("\nChecking against GLPI...")
    missing_logins = check_against_glpi(all_users, glpi)
    print(f"  {len(missing_logins)} users not found in GLPI")

    if not missing_logins:
        print("No missing users to report.")
        glpi.kill_session()
        print(f"\nDone. 0 missing users found.")
        return

    # Connect to LDAP (auto-detect from GLPI API)
    print("\nFetching LDAP config from GLPI...")
    ldap_cfg = get_ldap_config(glpi)
    ldap_conn = None
    base_dn = None
    if ldap_cfg:
        print(f"  LDAP server: {ldap_cfg['host']}:{ldap_cfg['port']}, basedn: {ldap_cfg['basedn']}")
        ldap_conn = connect_ldap(ldap_cfg, glpi_cfg)
        base_dn = ldap_cfg['basedn']
    else:
        print("  Could not get LDAP config — AD status will be 'Not in GLPI'")

    # For each missing user: get Jira key + check AD status
    print(f"\nChecking AD status for {len(missing_logins)} missing users...")
    missing_details = []
    for login in missing_logins:
        user_info = all_users[login]

        # Get Jira key
        jira_user = jira.get_user(login)
        jira_key = login
        if jira_user:
            jira_key = jira_user.get('key', login)

        # Check AD status
        reason = check_ad_status(ldap_conn, base_dn, login, jira_key)
        print(f"    [MISSING] {login} (key={jira_key}): {reason}")

        missing_details.append({
            'login': login,
            'jira_key': jira_key,
            'display_name': user_info['display_name'],
            'reason': reason,
            'issues': user_info['issues'],
        })

    # Save detailed report
    save_detailed_report(missing_details, args.output)

    # Cleanup
    if ldap_conn:
        try:
            ldap_conn.unbind()
        except Exception:
            pass
    glpi.kill_session()

    print(f"\nDone. {len(missing_details)} missing users found.")


if __name__ == '__main__':
    main()
