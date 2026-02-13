"""
User Tracker for Missing Users Reporting
Tracks Jira users not found in GLPI during migration
"""


class UserTracker:
    """
    Tracks missing users during migration.

    Features:
    - Deduplicated tracking of missing users (by login name)
    - Report generation to file (tab-separated format)
    - Statistics and boolean evaluation
    """

    def __init__(self):
        """Initialize user tracker with empty dict."""
        self._missing_users = {}  # login -> display_name
        self.logger = None  # Optional logger instance

    def report_missing_user(self, login, display_name=None):
        """
        Report a missing user (deduplicated by login).

        Args:
            login: Jira user login name
            display_name: User display name (optional)
        """
        if not login or login in self._missing_users:
            return

        self._missing_users[login] = display_name or login

        # Log if logger available
        if self.logger:
            self.logger.warning(f"Missing user: {login} ({display_name})")
        else:
            print(f"    [MISSING USER] {login} ({display_name})")

    def get_count(self):
        """
        Get count of missing users.

        Returns:
            int: Number of unique missing users
        """
        return len(self._missing_users)

    def save_report(self, filepath='missing_users.txt'):
        """
        Save missing users report to tab-separated file.

        Args:
            filepath: Output file path (default: missing_users.txt)
        """
        if not self._missing_users:
            if self.logger:
                self.logger.info("No missing users to report")
            else:
                print("No missing users to report.")
            return

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("Login Name\tFull Name\n")
            for login, display in sorted(self._missing_users.items()):
                f.write(f"{login}\t{display}\n")

        count = len(self._missing_users)
        if self.logger:
            self.logger.info(f"Missing users report: {count} users written to {filepath}")
        else:
            print(f"\n[REPORT] {count} missing users written to {filepath}")

    def clear(self):
        """Clear tracked users (for testing)."""
        self._missing_users.clear()

    def __len__(self):
        """
        Support len() function.

        Returns:
            int: Number of missing users
        """
        return len(self._missing_users)

    def __bool__(self):
        """
        Support boolean evaluation.

        Returns:
            bool: True if there are missing users, False otherwise
        """
        return len(self._missing_users) > 0
