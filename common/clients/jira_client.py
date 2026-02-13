"""
Unified Jira REST API Client
Consolidates functionality from folders 02 and 03
Supports: Issue search, Attachments, Project metadata, Security levels
"""
import requests


class JiraClient:
    """
    Unified Jira REST API v2 Client.

    Features:
    - Issue search with pagination
    - Attachment download
    - Project statuses, issue types, users
    - Security level discovery (API + JQL fallback)
    """

    def __init__(self, url, token, verify_ssl=False):
        """
        Initialize Jira client.

        Args:
            url: Jira base URL (e.g., https://jira.example.com)
            token: Personal Access Token (PAT) or Bearer token
            verify_ssl: Verify SSL certificates (default: False)
        """
        self.url = url.rstrip('/')
        self.token = token
        self.verify_ssl = verify_ssl
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    # ===== Issue Search =====

    def search_issues(self, jql, start_at=0, max_results=50):
        """
        Search issues using JQL with pagination.

        Args:
            jql: JQL query string
            start_at: Pagination offset (default: 0)
            max_results: Maximum results per page (default: 50)

        Returns:
            tuple: (issues_list, total_count)
        """
        endpoint = f"{self.url}/rest/api/2/search"

        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": ["*all"],
            "expand": "changelog"
        }

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)

            if response.status_code != 200:
                print(f"Jira API Error ({response.status_code}): {response.text}")
                response.raise_for_status()

            data = response.json()
            issues = data.get("issues", [])
            total = data.get("total", 0)

            return issues, total

        except Exception as e:
            print(f"Failed to fetch issues: {e}")
            raise

    def get_issue_count(self, jql):
        """
        Get total number of issues for a JQL (lightweight request).

        Args:
            jql: JQL query string

        Returns:
            int: Total issue count
        """
        endpoint = f"{self.url}/rest/api/2/search"
        params = {
            "jql": jql,
            "startAt": 0,
            "maxResults": 0,
            "fields": ["key"]  # minimal field to reduce payload
        }
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            if response.status_code != 200:
                print(f"Jira Count Error ({response.status_code}): {response.text[:500]}")
                response.raise_for_status()
            data = response.json()
            return data.get("total", 0)
        except Exception as e:
            print(f"Failed to get issue count: {e}")
            raise

    # ===== Attachments =====

    def get_attachment_content(self, download_url):
        """
        Download attachment content.

        Args:
            download_url: Attachment download URL

        Returns:
            bytes: Attachment content or None
        """
        try:
            response = requests.get(download_url, headers=self.headers, verify=self.verify_ssl, stream=True)
            if response.status_code == 200:
                return response.content
            else:
                print(f"Failed to download attachment: Status {response.status_code}")
                return None
        except Exception as e:
            print(f"Error downloading attachment: {e}")
            return None

    # ===== Project Metadata =====

    def get_project_statuses(self, project_key):
        """
        Get all statuses for a specific project.

        Args:
            project_key: Project key (e.g., 'PROJ')

        Returns:
            list: List of status dicts with name, description, statusCategory
        """
        endpoint = f"{self.url}/rest/api/2/project/{project_key}/statuses"
        try:
            response = requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            response.raise_for_status()
            data = response.json()

            # Flatten nested structure (IssueType -> Statuses)
            # Get unique statuses across all issue types
            unique_statuses = {}

            for issue_type in data:
                statuses = issue_type.get('statuses', [])
                for status in statuses:
                    s_id = status.get('id')
                    if s_id not in unique_statuses:
                        unique_statuses[s_id] = {
                            'name': status.get('name'),
                            'description': status.get('description'),
                            'statusCategory': status.get('statusCategory', {})
                        }

            return list(unique_statuses.values())

        except Exception as e:
            print(f"Failed to fetch project statuses: {e}")
            return []

    def get_project_issue_types(self, project_key):
        """
        Get all issue types for a specific project.

        Args:
            project_key: Project key (e.g., 'PROJ')

        Returns:
            list: List of issue type dicts
        """
        endpoint = f"{self.url}/rest/api/2/project/{project_key}"
        try:
            response = requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            response.raise_for_status()
            data = response.json()
            return data.get('issueTypes', [])

        except Exception as e:
            print(f"Failed to fetch project issue types: {e}")
            return []

    def get_project_users(self, project_key):
        """
        Get all assignable users for a project.

        Args:
            project_key: Project key (e.g., 'PROJ')

        Returns:
            list: List of user dicts
        """
        endpoint = f"{self.url}/rest/api/2/user/assignable/search"
        params = {"project": project_key, "maxResults": 1000}
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Failed to fetch project users: {e}")
            return []

    # ===== Security Levels =====

    def get_security_levels(self, project_key=None):
        """
        Get all security levels for a project.

        Method 1: Try direct API (requires 'Set Issue Security' permission)
        Method 2: Fallback to JQL scan of issues with 'level is not EMPTY'

        Args:
            project_key: Project key (optional, for JQL fallback)

        Returns:
            dict: {level_name: level_id} mapping
        """
        if not project_key:
            return {}

        # --- Method 1: Direct API ---
        endpoint = f"{self.url}/rest/api/2/project/{project_key}/securitylevel"
        try:
            response = requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            response.raise_for_status()
            data = response.json()
            levels = data.get('levels', [])
            if levels:
                print(f"Found {len(levels)} security levels via API for project {project_key}.")
                level_map = {}
                for lvl in levels:
                    name = lvl.get('name')
                    lid = lvl.get('id')
                    if name and lid:
                        level_map[name] = lid
                        print(f"  - {name} (ID: {lid})")
                return level_map
        except Exception as e:
            print(f"Security level API failed: {e}")

        # --- Method 2: JQL Scan Fallback ---
        print(f"API returned 0 levels (likely permission issue). Scanning issues via JQL...")
        return self._scan_security_levels_from_issues(project_key)

    def _scan_security_levels_from_issues(self, project_key):
        """
        Fallback: discover security levels by scanning issues with JQL.
        Uses 'level is not EMPTY' filter and collects unique security levels.

        Args:
            project_key: Project key

        Returns:
            dict: {level_name: level_id} mapping
        """
        jql = f"project = {project_key} AND level is not EMPTY"
        unique_levels = {}  # name -> id
        start_at = 0

        try:
            # First get total count
            _, total = self.search_issues(jql, start_at=0, max_results=0)
            print(f"  Found {total} issues with security levels. Scanning...")

            while start_at < total:
                issues, _ = self.search_issues(jql, start_at=start_at, max_results=50)
                if not issues:
                    break

                for issue in issues:
                    sec = issue.get('fields', {}).get('security')
                    if sec:
                        sec_id = sec.get('id')
                        sec_name = sec.get('name')
                        if sec_id and sec_name and sec_name not in unique_levels:
                            unique_levels[sec_name] = sec_id
                            print(f"  - Discovered: {sec_name} (ID: {sec_id})")

                start_at += len(issues)

                # Early exit: if we have enough unique levels, stop scanning
                # (After scanning 200 issues, new levels are unlikely)
                if start_at >= 200 and len(unique_levels) > 0:
                    print(f"  Scanned {start_at} issues, found {len(unique_levels)} unique levels. Stopping early.")
                    break

            print(f"  Discovered {len(unique_levels)} security levels via JQL scan.")
            return unique_levels

        except Exception as e:
            print(f"  JQL scan failed: {e}")
            return {}
