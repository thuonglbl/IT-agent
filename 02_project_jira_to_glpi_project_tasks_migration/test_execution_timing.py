"""
Tests for execution time tracking in jira_to_glpi migration script.
Tests format_duration logic and timing output on all exit paths.
"""
import unittest
import os
import sys
import io
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# --- Unit Tests: format_duration logic ---
# The function is nested inside main(), so we replicate it here for unit testing.

def format_duration(seconds):
    """Replica of format_duration from jira_to_glpi.main() for unit testing."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"


class TestFormatDuration(unittest.TestCase):
    """Test format_duration produces correct human-readable output."""

    def test_seconds_only(self):
        """Given < 60 seconds, shows only seconds."""
        self.assertEqual(format_duration(0), "0s")
        self.assertEqual(format_duration(1), "1s")
        self.assertEqual(format_duration(45), "45s")
        self.assertEqual(format_duration(59), "59s")

    def test_minutes_and_seconds(self):
        """Given >= 60s and < 3600s, shows minutes and seconds."""
        self.assertEqual(format_duration(60), "1m 0s")
        self.assertEqual(format_duration(61), "1m 1s")
        self.assertEqual(format_duration(312), "5m 12s")
        self.assertEqual(format_duration(3599), "59m 59s")

    def test_hours_minutes_seconds(self):
        """Given >= 3600s, shows hours, minutes, and seconds."""
        self.assertEqual(format_duration(3600), "1h 0m 0s")
        self.assertEqual(format_duration(3605), "1h 0m 5s")
        self.assertEqual(format_duration(7384), "2h 3m 4s")
        self.assertEqual(format_duration(86399), "23h 59m 59s")

    def test_truncates_fractional_seconds(self):
        """Fractional seconds are truncated (not rounded)."""
        self.assertEqual(format_duration(59.9), "59s")
        self.assertEqual(format_duration(0.5), "0s")
        self.assertEqual(format_duration(61.7), "1m 1s")


# --- Integration Tests: timing output on all exit paths ---

class TestTimingOnExitPaths(unittest.TestCase):
    """Test that timing is logged on all exit paths of main()."""

    def _build_config(self):
        """Build a minimal config dict for main()."""
        return {
            'jira': {
                'url': 'http://jira.test',
                'pat': 'fake-pat',
                'verify_ssl': False,
                'project_key': 'TEST',
                'jql': 'project = TEST ORDER BY key ASC',
            },
            'glpi': {
                'url': 'http://glpi.test/api.php/v1',
                'app_token': 'fake-app',
                'user_token': 'fake-user',
                'username': None,
                'password': None,
                'verify_ssl': False,
                'project_name': 'Test Project',
            },
            'migration': {
                'state_file': 'test_state.json',
                'mapping_file': 'test_mapping.json',
                'batch_size': 1,
                'debug': True,
            },
            'logging': {},
        }

    @patch('jira_to_glpi.load_config')
    @patch('jira_to_glpi.GlpiClient')
    @patch('jira_to_glpi.JiraClient')
    def test_timing_on_connection_failure(self, mock_jira_class, mock_glpi_class, mock_load_config):
        """Given connection failure, timing is still logged."""
        mock_load_config.return_value = self._build_config()

        # Make GLPI connection fail
        mock_glpi_instance = MagicMock()
        mock_glpi_instance.init_session.side_effect = Exception("Connection refused")
        mock_glpi_class.return_value = mock_glpi_instance

        import jira_to_glpi
        # Patch the module-level config
        with patch.object(jira_to_glpi, 'config', self._build_config()):
            captured = io.StringIO()
            with patch('sys.stdout', captured):
                jira_to_glpi.main()

            output = captured.getvalue()
            self.assertIn("Start time:", output)
            self.assertIn("End time:", output)
            self.assertIn("Duration:", output)
            self.assertIn("Connection Failed", output)

    @patch('jira_to_glpi.load_config')
    @patch('jira_to_glpi.GlpiClient')
    @patch('jira_to_glpi.JiraClient')
    def test_timing_on_project_not_found(self, mock_jira_class, mock_glpi_class, mock_load_config):
        """Given project not found, timing is still logged."""
        mock_load_config.return_value = self._build_config()

        mock_glpi_instance = MagicMock()
        mock_glpi_instance.init_session.return_value = True
        mock_glpi_instance.get_project_id_by_name.return_value = None  # Project not found
        mock_glpi_class.return_value = mock_glpi_instance

        import jira_to_glpi
        with patch.object(jira_to_glpi, 'config', self._build_config()):
            captured = io.StringIO()
            with patch('sys.stdout', captured):
                jira_to_glpi.main()

            output = captured.getvalue()
            self.assertIn("Start time:", output)
            self.assertIn("End time:", output)
            self.assertIn("Duration:", output)
            self.assertIn("not found", output)

    @patch('jira_to_glpi.StateManager')
    @patch('jira_to_glpi.load_config')
    @patch('jira_to_glpi.GlpiClient')
    @patch('jira_to_glpi.JiraClient')
    def test_timing_on_successful_debug_run(self, mock_jira_class, mock_glpi_class, mock_load_config, mock_state_mgr):
        """Given successful debug run (1 batch), timing is logged at the end."""
        config = self._build_config()
        mock_load_config.return_value = config

        mock_glpi_instance = MagicMock()
        mock_glpi_instance.init_session.return_value = True
        mock_glpi_instance.get_project_id_by_name.return_value = 1
        mock_glpi_instance.get_project_states.return_value = {'open': 1}
        mock_glpi_instance.get_project_task_types.return_value = {'task': 1}
        mock_glpi_instance.url = 'http://glpi.test/api.php/v1'
        mock_glpi_instance.create_project_task.return_value = 100
        mock_glpi_class.return_value = mock_glpi_instance

        mock_jira_instance = MagicMock()
        mock_jira_instance.get_issue_count.return_value = 1
        mock_jira_instance.search_issues.return_value = ([{
            'key': 'TEST-1',
            'fields': {
                'summary': 'Test Issue',
                'description': 'Test',
                'reporter': {'displayName': 'User', 'name': 'user'},
                'assignee': None,
                'priority': {'name': 'Medium'},
                'status': {'name': 'Open', 'statusCategory': {}},
                'issuetype': {'name': 'Task'},
                'created': '2024-01-01T10:00:00.000+0000',
                'updated': None,
                'resolutiondate': None,
                'resolution': None,
                'security': None,
                'labels': [],
                'versions': [],
                'fixVersions': [],
                'components': [],
                'environment': None,
                'attachment': [],
                'comment': {'comments': []},
            },
            'changelog': {'histories': []},
        }], 1)
        mock_jira_class.return_value = mock_jira_instance

        mock_state_instance = MagicMock()
        mock_state_instance.load.return_value = {'start_at': 0, 'total_processed': 0}
        mock_state_mgr.return_value = mock_state_instance

        import jira_to_glpi
        with patch.object(jira_to_glpi, 'config', config), \
             patch.object(jira_to_glpi, 'STATE_FILE', 'nonexistent_state.json'), \
             patch.object(jira_to_glpi, 'MAPPING_FILE', 'nonexistent_mapping.json'), \
             patch('os.path.exists', return_value=False), \
             patch('builtins.open', MagicMock()):
            captured = io.StringIO()
            with patch('sys.stdout', captured):
                jira_to_glpi.main()

            output = captured.getvalue()
            self.assertIn("Start time:", output)
            self.assertIn("End time:", output)
            self.assertIn("Duration:", output)
            self.assertIn("Migration Completed Successfully", output)


if __name__ == '__main__':
    unittest.main()
