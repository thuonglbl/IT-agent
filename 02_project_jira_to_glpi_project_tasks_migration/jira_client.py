import requests
import time

class JiraClient:
    def __init__(self, url, token, verify_ssl=False):
        self.url = url.rstrip('/')
        self.token = token
        self.verify_ssl = verify_ssl
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def search_issues(self, jql, start_at=0, max_results=50):
        """
        Search issues using JQL with pagination.
        Returns: (issues_list, total_count, next_start_at)
        """
        endpoint = f"{self.url}/rest/api/2/search"
        
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": [
                "summary", "description", "created", "status", 
                "comment", "attachment", "reporter", "priority",
                "assignee", "fixVersions", "components", "environment", "resolution"
            ],
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
        """Get total number of issues for a JQL."""
        issues, total = self.search_issues(jql, start_at=0, max_results=0)
        return total

    def get_attachment_content(self, download_url):
        """Download attachment content."""
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

    def get_project_statuses(self, project_key):
        """
        Get all statuses for a specific project.
        Returns a list of dicts with name, color, statusCategory (done/new/indeterminate).
        """
        endpoint = f"{self.url}/rest/api/2/project/{project_key}/statuses"
        try:
            response = requests.get(endpoint, headers=self.headers, verify=self.verify_ssl)
            response.raise_for_status()
            data = response.json()
            
            # Helper to flatten the nested structure (IssueType -> Statuses)
            # We want unique statuses across all issue types in the project
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
