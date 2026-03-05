"""
Unit and integration tests for check_missing_users module.
Tests user collection from Jira, GLPI comparison, AD status checking,
LDAP config fetching, report generation, and CLI main flow.
"""
import unittest
import os
import sys
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, call, PropertyMock

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from common.check_missing_users import (
    collect_project_users,
    collect_issue_users,
    merge_users,
    check_against_glpi,
    check_ad_status,
    get_ldap_config,
    save_detailed_report,
)


class TestCollectProjectUsers(unittest.TestCase):
    """Test collect_project_users function."""

    def test_basic_collection(self):
        """Test collecting users from project assignable API."""
        mock_jira = Mock()
        mock_jira.get_project_users.return_value = [
            {'name': 'john.doe', 'displayName': 'John Doe'},
            {'name': 'jane.smith', 'displayName': 'Jane Smith'},
        ]

        result = collect_project_users(mock_jira, 'PROJ')

        self.assertEqual(len(result), 2)
        self.assertEqual(result['john.doe']['display_name'], 'John Doe')
        self.assertEqual(result['jane.smith']['display_name'], 'Jane Smith')
        self.assertIsInstance(result['john.doe']['issues'], set)
        self.assertEqual(len(result['john.doe']['issues']), 0)
        mock_jira.get_project_users.assert_called_once_with('PROJ')

    def test_empty_project(self):
        """Test collecting from a project with no assignable users."""
        mock_jira = Mock()
        mock_jira.get_project_users.return_value = []

        result = collect_project_users(mock_jira, 'EMPTY')

        self.assertEqual(len(result), 0)

    def test_user_with_key_fallback(self):
        """Test user where 'name' is missing, falls back to 'key'."""
        mock_jira = Mock()
        mock_jira.get_project_users.return_value = [
            {'key': 'bob.key', 'displayName': 'Bob Key'},
        ]

        result = collect_project_users(mock_jira, 'PROJ')

        self.assertEqual(len(result), 1)
        self.assertEqual(result['bob.key']['display_name'], 'Bob Key')

    def test_user_without_display_name(self):
        """Test user missing displayName defaults to login."""
        mock_jira = Mock()
        mock_jira.get_project_users.return_value = [
            {'name': 'no.display'},
        ]

        result = collect_project_users(mock_jira, 'PROJ')

        self.assertEqual(result['no.display']['display_name'], 'no.display')

    def test_user_with_no_name_or_key_is_skipped(self):
        """Test that a user with neither name nor key is skipped."""
        mock_jira = Mock()
        mock_jira.get_project_users.return_value = [
            {'displayName': 'Ghost User'},
            {'name': 'valid.user', 'displayName': 'Valid'},
        ]

        result = collect_project_users(mock_jira, 'PROJ')

        self.assertEqual(len(result), 1)
        self.assertIn('valid.user', result)

    def test_name_takes_priority_over_key(self):
        """Test that 'name' field is preferred over 'key'."""
        mock_jira = Mock()
        mock_jira.get_project_users.return_value = [
            {'name': 'preferred.name', 'key': 'fallback.key', 'displayName': 'User'},
        ]

        result = collect_project_users(mock_jira, 'PROJ')

        self.assertIn('preferred.name', result)
        self.assertNotIn('fallback.key', result)


class TestCollectIssueUsers(unittest.TestCase):
    """Test collect_issue_users function."""

    def test_single_page_with_issues_tracking(self):
        """Test collecting users from a single page of issues with issue tracking."""
        mock_jira = Mock()
        mock_jira.get_issue_count.return_value = 2
        mock_jira.search_issues_lightweight.return_value = (
            [
                {
                    'key': 'PROJ-1',
                    'fields': {
                        'assignee': {'name': 'john.doe', 'displayName': 'John Doe'},
                        'reporter': {'name': 'jane.smith', 'displayName': 'Jane Smith'},
                    }
                },
                {
                    'key': 'PROJ-2',
                    'fields': {
                        'assignee': {'name': 'john.doe', 'displayName': 'John Doe'},
                        'reporter': {'name': 'bob.jones', 'displayName': 'Bob Jones'},
                    }
                },
            ],
            2
        )

        result = collect_issue_users(mock_jira, 'PROJ', batch_size=100)

        self.assertEqual(len(result), 3)
        self.assertIn('john.doe', result)
        self.assertIn('jane.smith', result)
        self.assertIn('bob.jones', result)
        # john.doe appears in PROJ-1 and PROJ-2
        self.assertEqual(result['john.doe']['issues'], {'PROJ-1', 'PROJ-2'})
        self.assertEqual(result['jane.smith']['issues'], {'PROJ-1'})
        self.assertEqual(result['bob.jones']['issues'], {'PROJ-2'})

    def test_pagination(self):
        """Test pagination across multiple API pages."""
        mock_jira = Mock()
        mock_jira.get_issue_count.return_value = 3

        page1 = (
            [
                {'key': 'P-1', 'fields': {
                    'assignee': {'name': 'user1', 'displayName': 'User 1'},
                    'reporter': None,
                }},
                {'key': 'P-2', 'fields': {
                    'assignee': None,
                    'reporter': {'name': 'user2', 'displayName': 'User 2'},
                }},
            ],
            3
        )
        page2 = (
            [
                {'key': 'P-3', 'fields': {
                    'assignee': {'name': 'user3', 'displayName': 'User 3'},
                    'reporter': {'name': 'user1', 'displayName': 'User 1'},
                }},
            ],
            3
        )

        mock_jira.search_issues_lightweight.side_effect = [page1, page2]

        result = collect_issue_users(mock_jira, 'PROJ', batch_size=2)

        self.assertEqual(len(result), 3)
        self.assertEqual(result['user1']['issues'], {'P-1', 'P-3'})
        self.assertEqual(result['user2']['issues'], {'P-2'})
        self.assertEqual(result['user3']['issues'], {'P-3'})
        self.assertEqual(mock_jira.search_issues_lightweight.call_count, 2)

    def test_zero_issues(self):
        """Test project with no issues."""
        mock_jira = Mock()
        mock_jira.get_issue_count.return_value = 0

        result = collect_issue_users(mock_jira, 'EMPTY', batch_size=100)

        self.assertEqual(len(result), 0)
        mock_jira.search_issues_lightweight.assert_not_called()

    def test_null_assignee_and_reporter(self):
        """Test issues with null assignee and reporter are handled."""
        mock_jira = Mock()
        mock_jira.get_issue_count.return_value = 1
        mock_jira.search_issues_lightweight.return_value = (
            [
                {
                    'key': 'P-1',
                    'fields': {
                        'assignee': None,
                        'reporter': None,
                    }
                },
            ],
            1
        )

        result = collect_issue_users(mock_jira, 'PROJ', batch_size=100)

        self.assertEqual(len(result), 0)

    def test_deduplication_across_issues(self):
        """Test that the same user appearing in multiple issues collects all issue keys."""
        mock_jira = Mock()
        mock_jira.get_issue_count.return_value = 3
        mock_jira.search_issues_lightweight.return_value = (
            [
                {'key': 'P-1', 'fields': {
                    'assignee': {'name': 'alice', 'displayName': 'Alice'},
                    'reporter': {'name': 'alice', 'displayName': 'Alice'},
                }},
                {'key': 'P-2', 'fields': {
                    'assignee': {'name': 'alice', 'displayName': 'Alice'},
                    'reporter': {'name': 'bob', 'displayName': 'Bob'},
                }},
                {'key': 'P-3', 'fields': {
                    'assignee': {'name': 'bob', 'displayName': 'Bob'},
                    'reporter': {'name': 'bob', 'displayName': 'Bob'},
                }},
            ],
            3
        )

        result = collect_issue_users(mock_jira, 'PROJ', batch_size=100)

        self.assertEqual(len(result), 2)
        self.assertEqual(result['alice']['issues'], {'P-1', 'P-2'})
        self.assertEqual(result['bob']['issues'], {'P-2', 'P-3'})

    def test_key_fallback_in_issues(self):
        """Test that 'key' is used when 'name' is absent in issue fields."""
        mock_jira = Mock()
        mock_jira.get_issue_count.return_value = 1
        mock_jira.search_issues_lightweight.return_value = (
            [
                {'key': 'P-1', 'fields': {
                    'assignee': {'key': 'user.key', 'displayName': 'User Key'},
                    'reporter': None,
                }},
            ],
            1
        )

        result = collect_issue_users(mock_jira, 'PROJ', batch_size=100)

        self.assertEqual(len(result), 1)
        self.assertIn('user.key', result)

    def test_empty_issues_page_breaks_loop(self):
        """Test that an empty issues response breaks the pagination loop."""
        mock_jira = Mock()
        mock_jira.get_issue_count.return_value = 5
        mock_jira.search_issues_lightweight.return_value = ([], 5)

        result = collect_issue_users(mock_jira, 'PROJ', batch_size=100)

        self.assertEqual(len(result), 0)
        self.assertEqual(mock_jira.search_issues_lightweight.call_count, 1)


class TestMergeUsers(unittest.TestCase):
    """Test merge_users function."""

    def test_merge_disjoint(self):
        """Test merging two dicts with no overlapping users."""
        target = {
            'alice': {'display_name': 'Alice', 'issues': {'P-1'}},
        }
        source = {
            'bob': {'display_name': 'Bob', 'issues': {'P-2'}},
        }

        merge_users(target, source)

        self.assertEqual(len(target), 2)
        self.assertEqual(target['alice']['issues'], {'P-1'})
        self.assertEqual(target['bob']['issues'], {'P-2'})

    def test_merge_overlapping_unions_issues(self):
        """Test merging overlapping users unions their issues sets."""
        target = {
            'alice': {'display_name': 'Alice', 'issues': {'P-1'}},
        }
        source = {
            'alice': {'display_name': 'Alice A', 'issues': {'P-2', 'P-3'}},
        }

        merge_users(target, source)

        self.assertEqual(len(target), 1)
        self.assertEqual(target['alice']['issues'], {'P-1', 'P-2', 'P-3'})
        # Target display_name is preserved
        self.assertEqual(target['alice']['display_name'], 'Alice')

    def test_merge_empty_source(self):
        """Test merging empty source is a no-op."""
        target = {'alice': {'display_name': 'Alice', 'issues': set()}}
        merge_users(target, {})
        self.assertEqual(len(target), 1)

    def test_merge_empty_target(self):
        """Test merging into empty target copies source."""
        target = {}
        source = {'alice': {'display_name': 'Alice', 'issues': {'P-1'}}}
        merge_users(target, source)
        self.assertEqual(len(target), 1)
        self.assertEqual(target['alice']['issues'], {'P-1'})

    def test_merge_does_not_mutate_source(self):
        """Test that merging does not mutate the source dict's sets."""
        target = {'alice': {'display_name': 'Alice', 'issues': {'P-1'}}}
        source = {'alice': {'display_name': 'Alice', 'issues': {'P-2'}}}
        merge_users(target, source)
        # Target should have both
        self.assertEqual(target['alice']['issues'], {'P-1', 'P-2'})
        # Source should be unchanged
        self.assertEqual(source['alice']['issues'], {'P-2'})


class TestCheckAgainstGlpi(unittest.TestCase):
    """Test check_against_glpi function."""

    def test_all_users_found(self):
        """Test when all Jira users exist in GLPI."""
        mock_glpi = Mock()
        mock_glpi.get_user_id_by_name.return_value = 42

        users = {
            'john.doe': {'display_name': 'John Doe', 'issues': set()},
            'jane.smith': {'display_name': 'Jane Smith', 'issues': set()},
        }
        result = check_against_glpi(users, mock_glpi)

        self.assertEqual(result, [])

    def test_all_users_missing(self):
        """Test when no Jira users exist in GLPI."""
        mock_glpi = Mock()
        mock_glpi.get_user_id_by_name.return_value = None

        users = {
            'john.doe': {'display_name': 'John Doe', 'issues': set()},
            'jane.smith': {'display_name': 'Jane Smith', 'issues': set()},
        }
        result = check_against_glpi(users, mock_glpi)

        self.assertEqual(result, ['jane.smith', 'john.doe'])

    def test_partial_missing(self):
        """Test when some users exist and some don't."""
        mock_glpi = Mock()
        mock_glpi.get_user_id_by_name.side_effect = lambda name: {
            'john.doe': 10,
            'jane.smith': None,
            'bob.jones': 20,
        }.get(name.lower())

        users = {
            'john.doe': {'display_name': 'John Doe', 'issues': set()},
            'jane.smith': {'display_name': 'Jane Smith', 'issues': set()},
            'bob.jones': {'display_name': 'Bob Jones', 'issues': set()},
        }
        result = check_against_glpi(users, mock_glpi)

        self.assertEqual(result, ['jane.smith'])

    def test_empty_users(self):
        """Test with empty user dict."""
        mock_glpi = Mock()

        result = check_against_glpi({}, mock_glpi)

        self.assertEqual(result, [])
        mock_glpi.get_user_id_by_name.assert_not_called()


class TestCheckAdStatus(unittest.TestCase):
    """Test check_ad_status function."""

    def test_no_connection_returns_not_in_glpi(self):
        """When LDAP connection is None, return 'Not in GLPI'."""
        result = check_ad_status(None, 'DC=test,DC=local', 'jdoe')
        self.assertEqual(result, "Not in GLPI")

    def test_user_found_and_active(self):
        """User found in AD with active account."""
        conn = Mock()
        entry = Mock()
        entry.__getitem__ = lambda self, key: Mock(value=512)  # normal account
        conn.entries = [entry]

        result = check_ad_status(conn, 'DC=test,DC=local', 'jdoe')
        self.assertEqual(result, "Active in AD but not in GLPI")

    def test_user_found_and_disabled(self):
        """User found in AD with disabled account (bit 2 set)."""
        conn = Mock()
        entry = Mock()
        entry.__getitem__ = lambda self, key: Mock(value=514)  # 512 + 2 = disabled
        conn.entries = [entry]

        result = check_ad_status(conn, 'DC=test,DC=local', 'jdoe')
        self.assertEqual(result, "Disabled in AD")

    def test_user_not_found_no_jira_key(self):
        """User not found by login, no usable jira_key."""
        conn = Mock()
        conn.entries = []  # not found

        result = check_ad_status(conn, 'DC=test,DC=local', 'jdoe')
        self.assertEqual(result, "Deleted from AD")

    def test_user_not_found_jira_key_same_as_login(self):
        """User not found, jira_key equals login — no fallback."""
        conn = Mock()
        conn.entries = []

        result = check_ad_status(conn, 'DC=test,DC=local', 'jdoe', jira_key='jdoe')
        self.assertEqual(result, "Deleted from AD")

    def test_user_not_found_jira_key_is_jirauser(self):
        """User not found, jira_key starts with JIRAUSER — no fallback."""
        conn = Mock()
        conn.entries = []

        result = check_ad_status(conn, 'DC=test,DC=local', '12345', jira_key='JIRAUSER12345')
        self.assertEqual(result, "Deleted from AD")

    def test_fallback_to_jira_key_found_active(self):
        """User not found by login, found by jira_key and active."""
        conn = Mock()
        entry_active = Mock()
        entry_active.__getitem__ = lambda self, key: Mock(value=512)

        # First search (by login) returns nothing, second (by key) returns active
        conn.entries = []

        def search_side_effect(base_dn, filter_str, attributes=None):
            if 'ast' in filter_str:
                conn.entries = [entry_active]
            else:
                conn.entries = []

        conn.search.side_effect = search_side_effect

        result = check_ad_status(conn, 'DC=test,DC=local', '1234567890', jira_key='abc')
        self.assertEqual(result, "Active in AD as ast, not in GLPI")

    def test_fallback_to_jira_key_found_disabled(self):
        """User not found by login, found by jira_key and disabled."""
        conn = Mock()
        entry_disabled = Mock()
        entry_disabled.__getitem__ = lambda self, key: Mock(value=514)

        def search_side_effect(base_dn, filter_str, attributes=None):
            if 'ast' in filter_str:
                conn.entries = [entry_disabled]
            else:
                conn.entries = []

        conn.search.side_effect = search_side_effect

        result = check_ad_status(conn, 'DC=test,DC=local', '1234567890', jira_key='abc')
        self.assertEqual(result, "Disabled in AD (sAMAccountName=abc)")

    def test_fallback_to_jira_key_not_found(self):
        """User not found by login or by jira_key."""
        conn = Mock()
        conn.entries = []

        result = check_ad_status(conn, 'DC=test,DC=local', '12345', jira_key='xyz')
        self.assertEqual(result, "Deleted from AD")

    def test_search_exception_returns_not_in_glpi(self):
        """LDAP search exception returns safe default."""
        conn = Mock()
        conn.search.side_effect = Exception("LDAP error")

        result = check_ad_status(conn, 'DC=test,DC=local', 'jdoe')
        self.assertEqual(result, "Not in GLPI")


class TestGetLdapConfig(unittest.TestCase):
    """Test get_ldap_config function."""

    def test_successful_fetch(self):
        """Test successful LDAP config fetch from GLPI API."""
        mock_glpi = Mock()
        mock_glpi.url = 'https://glpi.test/api.php/v1'
        mock_glpi.headers = {'Session-Token': 'tok'}
        mock_glpi.verify_ssl = False

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'host': 'ad.example.com', 'port': 389, 'basedn': 'DC=example,DC=com'}
        ]

        with patch('requests.get', return_value=mock_response):
            result = get_ldap_config(mock_glpi)

        self.assertEqual(result['host'], 'ad.example.com')
        self.assertEqual(result['port'], 389)
        self.assertEqual(result['basedn'], 'DC=example,DC=com')

    def test_api_returns_single_dict(self):
        """Test LDAP config when API returns a single dict instead of list."""
        mock_glpi = Mock()
        mock_glpi.url = 'https://glpi.test/api.php/v1'
        mock_glpi.headers = {}
        mock_glpi.verify_ssl = False

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'host': 'ldap.test.com', 'port': 636, 'basedn': 'DC=test,DC=local'
        }

        with patch('requests.get', return_value=mock_response):
            result = get_ldap_config(mock_glpi)

        self.assertEqual(result['host'], 'ldap.test.com')
        self.assertEqual(result['port'], 636)

    def test_api_error(self):
        """Test LDAP config fetch when API returns error."""
        mock_glpi = Mock()
        mock_glpi.url = 'https://glpi.test/api.php/v1'
        mock_glpi.headers = {}
        mock_glpi.verify_ssl = False

        mock_response = Mock()
        mock_response.status_code = 401

        with patch('requests.get', return_value=mock_response):
            result = get_ldap_config(mock_glpi)

        self.assertIsNone(result)

    def test_missing_host_returns_none(self):
        """Test LDAP config with missing host field."""
        mock_glpi = Mock()
        mock_glpi.url = 'https://glpi.test/api.php/v1'
        mock_glpi.headers = {}
        mock_glpi.verify_ssl = False

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'port': 389, 'basedn': 'DC=test'}]

        with patch('requests.get', return_value=mock_response):
            result = get_ldap_config(mock_glpi)

        self.assertIsNone(result)

    def test_exception_returns_none(self):
        """Test LDAP config fetch when requests raises exception."""
        mock_glpi = Mock()
        mock_glpi.url = 'https://glpi.test/api.php/v1'
        mock_glpi.headers = {}
        mock_glpi.verify_ssl = False

        with patch('requests.get', side_effect=Exception("Connection error")):
            result = get_ldap_config(mock_glpi)

        self.assertIsNone(result)


class TestSaveDetailedReport(unittest.TestCase):
    """Test save_detailed_report function."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_file = os.path.join(self.temp_dir, 'report.txt')

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_basic_report(self):
        """Test report with multiple users."""
        details = [
            {
                'login': 'bob',
                'jira_key': 'bob',
                'display_name': 'Bob B',
                'reason': 'Deleted from AD',
                'issues': set(),
            },
            {
                'login': 'ano',
                'jira_key': 'ano',
                'display_name': 'John Doe [X]',
                'reason': 'Deleted from AD',
                'issues': {'PROJ1-101', 'PROJ1-250'},
            },
        ]

        save_detailed_report(details, self.output_file)

        with open(self.output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Header
        self.assertEqual(lines[0].strip(), 'Login Name\tJira Key\tFull Name\tReason\tRelated Tickets')
        # Sorted by login: abc before xyz
        self.assertIn('abc', lines[1])
        self.assertIn('John Doe [X]', lines[1])
        self.assertIn('Deleted from AD', lines[1])
        self.assertIn('PROJ1-101', lines[1])
        self.assertIn('xyz', lines[2])

    def test_report_with_jira_key_different_from_login(self):
        """Test report shows different jira_key."""
        details = [
            {
                'login': '1234567890',
                'jira_key': 'abc',
                'display_name': 'Sarah Connor',
                'reason': 'Disabled in AD (sAMAccountName=abc)',
                'issues': {'PROJ1-42'},
            },
        ]

        save_detailed_report(details, self.output_file)

        with open(self.output_file, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('1234567890\tabc\tSarah Connor\tDisabled in AD (sAMAccountName=abc)\tPROJ1-42', content)

    def test_empty_report(self):
        """Test that empty details list does not create file."""
        save_detailed_report([], self.output_file)

        self.assertFalse(os.path.exists(self.output_file))

    def test_empty_issues_column(self):
        """Test that users with no issues have empty ticket column."""
        details = [
            {
                'login': 'alice',
                'jira_key': 'alice',
                'display_name': 'Alice',
                'reason': 'Deleted from AD',
                'issues': set(),
            },
        ]

        save_detailed_report(details, self.output_file)

        with open(self.output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Last column should be empty — line ends with \t\n
        data_line = lines[1].rstrip('\n')
        columns = data_line.split('\t')
        self.assertEqual(len(columns), 5)
        self.assertEqual(columns[4], '')

    def test_tickets_are_sorted(self):
        """Test that related tickets are comma-separated and sorted."""
        details = [
            {
                'login': 'user1',
                'jira_key': 'user1',
                'display_name': 'User 1',
                'reason': 'Deleted from AD',
                'issues': {'PROJ-3', 'PROJ-1', 'PROJ-2'},
            },
        ]

        save_detailed_report(details, self.output_file)

        with open(self.output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        columns = lines[1].strip().split('\t')
        self.assertEqual(columns[4], 'PROJ-1, PROJ-2, PROJ-3')


class TestSearchIssuesLightweight(unittest.TestCase):
    """Test JiraClient.search_issues_lightweight method."""

    @patch('common.clients.jira_client.requests.get')
    def test_lightweight_search_default_fields(self, mock_get):
        """Test lightweight search uses assignee+reporter by default."""
        from common.clients.jira_client import JiraClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'total': 1,
            'issues': [{'key': 'T-1', 'fields': {'assignee': None, 'reporter': None}}]
        }
        mock_get.return_value = mock_response

        client = JiraClient(url='https://jira.test.com', token='tok')
        issues, total = client.search_issues_lightweight('project = TEST')

        self.assertEqual(total, 1)
        self.assertEqual(len(issues), 1)

        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get('params') or call_kwargs[1].get('params')
        self.assertEqual(params['fields'], ['assignee', 'reporter'])
        self.assertNotIn('expand', params)

    @patch('common.clients.jira_client.requests.get')
    def test_lightweight_search_custom_fields(self, mock_get):
        """Test lightweight search with custom fields list."""
        from common.clients.jira_client import JiraClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'total': 0, 'issues': []}
        mock_get.return_value = mock_response

        client = JiraClient(url='https://jira.test.com', token='tok')
        client.search_issues_lightweight(
            'project = TEST',
            fields=['summary', 'status'],
            start_at=10,
            max_results=25
        )

        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get('params') or call_kwargs[1].get('params')
        self.assertEqual(params['fields'], ['summary', 'status'])
        self.assertEqual(params['startAt'], 10)
        self.assertEqual(params['maxResults'], 25)

    @patch('common.clients.jira_client.requests.get')
    def test_lightweight_search_api_error(self, mock_get):
        """Test lightweight search raises on API error."""
        from common.clients.jira_client import JiraClient

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Bad Request'
        mock_response.raise_for_status.side_effect = Exception('400 Bad Request')
        mock_get.return_value = mock_response

        client = JiraClient(url='https://jira.test.com', token='tok')

        with self.assertRaises(Exception):
            client.search_issues_lightweight('invalid jql!!!')


class TestGetUser(unittest.TestCase):
    """Test JiraClient.get_user method."""

    @patch('common.clients.jira_client.requests.get')
    def test_get_user_success(self, mock_get):
        """Test successful user fetch returns user dict."""
        from common.clients.jira_client import JiraClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'key': 'abc',
            'name': '1234567890',
            'displayName': 'Sarah Connor',
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = JiraClient(url='https://jira.test.com', token='tok')
        result = client.get_user('1234567890')

        self.assertEqual(result['key'], 'abc')
        self.assertEqual(result['name'], '1234567890')

    @patch('common.clients.jira_client.requests.get')
    def test_get_user_not_found(self, mock_get):
        """Test user not found returns None."""
        from common.clients.jira_client import JiraClient

        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        client = JiraClient(url='https://jira.test.com', token='tok')
        result = client.get_user('nonexistent')

        self.assertIsNone(result)

    @patch('common.clients.jira_client.requests.get')
    def test_get_user_exception(self, mock_get):
        """Test exception during fetch returns None."""
        from common.clients.jira_client import JiraClient

        mock_get.side_effect = Exception("Connection error")

        client = JiraClient(url='https://jira.test.com', token='tok')
        result = client.get_user('user')

        self.assertIsNone(result)


class TestMainFlow(unittest.TestCase):
    """Integration tests for the main() function."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_file = os.path.join(self.temp_dir, 'missing_users.txt')

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('common.check_missing_users.check_ad_status')
    @patch('common.check_missing_users.connect_ldap')
    @patch('common.check_missing_users.get_ldap_config')
    @patch('common.check_missing_users.GlpiClient')
    @patch('common.check_missing_users.JiraClient')
    @patch('common.check_missing_users.load_config')
    def test_main_basic_flow(self, mock_load_config, mock_jira_cls, mock_glpi_cls,
                              mock_get_ldap, mock_connect_ldap, mock_check_ad):
        """Test main() with one project, both sources, some missing users."""
        from common.check_missing_users import main

        mock_load_config.return_value = {
            'jira': {'url': 'https://jira.test', 'pat': 'tok'},
            'glpi': {
                'url': 'https://glpi.test/api.php/v1',
                'app_token': 'app',
                'user_token': 'usr',
            },
        }

        mock_jira = Mock()
        mock_jira_cls.return_value = mock_jira
        mock_jira.get_project_users.return_value = [
            {'name': 'alice', 'displayName': 'Alice A'},
            {'name': 'bob', 'displayName': 'Bob B'},
        ]
        mock_jira.get_issue_count.return_value = 1
        mock_jira.search_issues_lightweight.return_value = (
            [{'key': 'P-1', 'fields': {
                'assignee': {'name': 'alice', 'displayName': 'Alice A'},
                'reporter': {'name': 'charlie', 'displayName': 'Charlie C'},
            }}],
            1
        )
        mock_jira.get_user.side_effect = lambda login: {'key': login, 'name': login}

        mock_glpi = Mock()
        mock_glpi_cls.return_value = mock_glpi
        mock_glpi.user_cache = {'alice': 1}
        mock_glpi.get_user_id_by_name.side_effect = lambda name: {
            'alice': 1,
        }.get(name.lower())

        mock_get_ldap.return_value = None
        mock_connect_ldap.return_value = None
        mock_check_ad.return_value = "Deleted from AD"

        test_args = ['check_missing_users.py', 'PROJ', '-o', self.output_file]
        with patch('sys.argv', test_args):
            main()

        mock_glpi.init_session.assert_called_once()
        mock_glpi.load_user_cache.assert_called_once()
        mock_glpi.kill_session.assert_called_once()

        self.assertTrue(os.path.exists(self.output_file))
        with open(self.output_file, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('bob', content)
        self.assertIn('charlie', content)
        # Header should have 5 columns
        header = content.split('\n')[0]
        self.assertEqual(len(header.split('\t')), 5)
        self.assertIn('Reason', header)
        self.assertIn('Related Tickets', header)

    @patch('common.check_missing_users.check_ad_status')
    @patch('common.check_missing_users.connect_ldap')
    @patch('common.check_missing_users.get_ldap_config')
    @patch('common.check_missing_users.GlpiClient')
    @patch('common.check_missing_users.JiraClient')
    @patch('common.check_missing_users.load_config')
    def test_main_skip_issues(self, mock_load_config, mock_jira_cls, mock_glpi_cls,
                               mock_get_ldap, mock_connect_ldap, mock_check_ad):
        """Test main() with --skip-issues flag skips issue scan."""
        from common.check_missing_users import main

        mock_load_config.return_value = {
            'jira': {'url': 'https://jira.test', 'pat': 'tok'},
            'glpi': {
                'url': 'https://glpi.test/api.php/v1',
                'app_token': 'app',
                'user_token': 'usr',
            },
        }

        mock_jira = Mock()
        mock_jira_cls.return_value = mock_jira
        mock_jira.get_project_users.return_value = [
            {'name': 'alice', 'displayName': 'Alice A'},
        ]
        mock_jira.get_user.return_value = {'key': 'alice', 'name': 'alice'}

        mock_glpi = Mock()
        mock_glpi_cls.return_value = mock_glpi
        mock_glpi.user_cache = {}
        mock_glpi.get_user_id_by_name.return_value = None

        mock_get_ldap.return_value = None
        mock_check_ad.return_value = "Deleted from AD"

        test_args = ['check_missing_users.py', 'PROJ', '--skip-issues', '-o', self.output_file]
        with patch('sys.argv', test_args):
            main()

        mock_jira.get_issue_count.assert_not_called()
        mock_jira.search_issues_lightweight.assert_not_called()
        mock_jira.get_project_users.assert_called_once_with('PROJ')

        # Report should have empty Related Tickets for assignable-only users
        with open(self.output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        data_cols = lines[1].rstrip('\n').split('\t')
        self.assertEqual(data_cols[4], '')  # empty tickets

    @patch('common.check_missing_users.check_ad_status')
    @patch('common.check_missing_users.connect_ldap')
    @patch('common.check_missing_users.get_ldap_config')
    @patch('common.check_missing_users.GlpiClient')
    @patch('common.check_missing_users.JiraClient')
    @patch('common.check_missing_users.load_config')
    def test_main_multiple_projects(self, mock_load_config, mock_jira_cls, mock_glpi_cls,
                                     mock_get_ldap, mock_connect_ldap, mock_check_ad):
        """Test main() with multiple project keys."""
        from common.check_missing_users import main

        mock_load_config.return_value = {
            'jira': {'url': 'https://jira.test', 'pat': 'tok'},
            'glpi': {
                'url': 'https://glpi.test/api.php/v1',
                'app_token': 'app',
                'user_token': 'usr',
            },
        }

        mock_jira = Mock()
        mock_jira_cls.return_value = mock_jira
        mock_jira.get_project_users.side_effect = [
            [{'name': 'user1', 'displayName': 'User 1'}],
            [{'name': 'user2', 'displayName': 'User 2'}],
        ]
        mock_jira.get_issue_count.return_value = 0
        mock_jira.get_user.side_effect = lambda login: {'key': login, 'name': login}

        mock_glpi = Mock()
        mock_glpi_cls.return_value = mock_glpi
        mock_glpi.user_cache = {}
        mock_glpi.get_user_id_by_name.return_value = None

        mock_get_ldap.return_value = None
        mock_check_ad.return_value = "Deleted from AD"

        test_args = ['check_missing_users.py', 'PROJ1', 'PROJ2', '--skip-issues', '-o', self.output_file]
        with patch('sys.argv', test_args):
            main()

        self.assertEqual(mock_jira.get_project_users.call_count, 2)

        with open(self.output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('user1', content)
        self.assertIn('user2', content)

    @patch('common.check_missing_users.GlpiClient')
    @patch('common.check_missing_users.JiraClient')
    @patch('common.check_missing_users.load_config')
    def test_main_no_missing_users(self, mock_load_config, mock_jira_cls, mock_glpi_cls):
        """Test main() when all users exist in GLPI — no output file created."""
        from common.check_missing_users import main

        mock_load_config.return_value = {
            'jira': {'url': 'https://jira.test', 'pat': 'tok'},
            'glpi': {
                'url': 'https://glpi.test/api.php/v1',
                'app_token': 'app',
                'user_token': 'usr',
            },
        }

        mock_jira = Mock()
        mock_jira_cls.return_value = mock_jira
        mock_jira.get_project_users.return_value = [
            {'name': 'alice', 'displayName': 'Alice'},
        ]
        mock_jira.get_issue_count.return_value = 0

        mock_glpi = Mock()
        mock_glpi_cls.return_value = mock_glpi
        mock_glpi.user_cache = {'alice': 1}
        mock_glpi.get_user_id_by_name.return_value = 1

        test_args = ['check_missing_users.py', 'PROJ', '--skip-issues', '-o', self.output_file]
        with patch('sys.argv', test_args):
            main()

        self.assertFalse(os.path.exists(self.output_file))

    @patch('common.check_missing_users.check_ad_status')
    @patch('common.check_missing_users.connect_ldap')
    @patch('common.check_missing_users.get_ldap_config')
    @patch('common.check_missing_users.GlpiClient')
    @patch('common.check_missing_users.JiraClient')
    @patch('common.check_missing_users.load_config')
    def test_main_merges_assignable_and_issue_users(self, mock_load_config, mock_jira_cls, mock_glpi_cls,
                                                      mock_get_ldap, mock_connect_ldap, mock_check_ad):
        """Test that users from both sources are merged (deduplicated) with issues unioned."""
        from common.check_missing_users import main

        mock_load_config.return_value = {
            'jira': {'url': 'https://jira.test', 'pat': 'tok'},
            'glpi': {
                'url': 'https://glpi.test/api.php/v1',
                'app_token': 'app',
                'user_token': 'usr',
            },
        }

        mock_jira = Mock()
        mock_jira_cls.return_value = mock_jira
        mock_jira.get_project_users.return_value = [
            {'name': 'alice', 'displayName': 'Alice'},
            {'name': 'bob', 'displayName': 'Bob'},
        ]
        mock_jira.get_issue_count.return_value = 1
        mock_jira.search_issues_lightweight.return_value = (
            [{'key': 'P-1', 'fields': {
                'assignee': {'name': 'alice', 'displayName': 'Alice'},
                'reporter': {'name': 'charlie', 'displayName': 'Charlie'},
            }}],
            1
        )
        mock_jira.get_user.side_effect = lambda login: {'key': login, 'name': login}

        mock_glpi = Mock()
        mock_glpi_cls.return_value = mock_glpi
        mock_glpi.user_cache = {}
        mock_glpi.get_user_id_by_name.return_value = None

        mock_get_ldap.return_value = None
        mock_check_ad.return_value = "Deleted from AD"

        test_args = ['check_missing_users.py', 'PROJ', '-o', self.output_file]
        with patch('sys.argv', test_args):
            main()

        with open(self.output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Header + 3 unique users (alice, bob, charlie)
        data_lines = [l for l in lines[1:] if l.strip()]
        self.assertEqual(len(data_lines), 3)

    @patch('common.check_missing_users.check_ad_status')
    @patch('common.check_missing_users.connect_ldap')
    @patch('common.check_missing_users.get_ldap_config')
    @patch('common.check_missing_users.GlpiClient')
    @patch('common.check_missing_users.JiraClient')
    @patch('common.check_missing_users.load_config')
    def test_main_with_ldap_connection(self, mock_load_config, mock_jira_cls, mock_glpi_cls,
                                        mock_get_ldap, mock_connect_ldap, mock_check_ad):
        """Test main() attempts LDAP connection when config available."""
        from common.check_missing_users import main

        mock_load_config.return_value = {
            'jira': {'url': 'https://jira.test', 'pat': 'tok'},
            'glpi': {
                'url': 'https://glpi.test/api.php/v1',
                'app_token': 'app',
                'username': 'admin',
                'password': 'pass',
            },
        }

        mock_jira = Mock()
        mock_jira_cls.return_value = mock_jira
        mock_jira.get_project_users.return_value = [
            {'name': 'bob', 'displayName': 'Bob'},
        ]
        mock_jira.get_issue_count.return_value = 0
        mock_jira.get_user.return_value = {'key': 'bob', 'name': 'bob'}

        mock_glpi = Mock()
        mock_glpi_cls.return_value = mock_glpi
        mock_glpi.user_cache = {}
        mock_glpi.get_user_id_by_name.return_value = None

        ldap_cfg = {'host': 'ad.test', 'port': 389, 'basedn': 'DC=test,DC=local'}
        mock_get_ldap.return_value = ldap_cfg
        mock_ldap_conn = Mock()
        mock_connect_ldap.return_value = mock_ldap_conn
        mock_check_ad.return_value = "Disabled in AD"

        test_args = ['check_missing_users.py', 'PROJ', '--skip-issues', '-o', self.output_file]
        with patch('sys.argv', test_args):
            main()

        mock_get_ldap.assert_called_once()
        mock_connect_ldap.assert_called_once()
        mock_check_ad.assert_called_once_with(mock_ldap_conn, 'DC=test,DC=local', 'bob', 'bob')

        with open(self.output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('Disabled in AD', content)

        # LDAP connection should be unbound
        mock_ldap_conn.unbind.assert_called_once()


class TestMainEdgeCases(unittest.TestCase):
    """Edge case tests for the main flow."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_file = os.path.join(self.temp_dir, 'missing_users.txt')

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('common.check_missing_users.check_ad_status')
    @patch('common.check_missing_users.connect_ldap')
    @patch('common.check_missing_users.get_ldap_config')
    @patch('common.check_missing_users.GlpiClient')
    @patch('common.check_missing_users.JiraClient')
    @patch('common.check_missing_users.load_config')
    def test_main_custom_batch_size(self, mock_load_config, mock_jira_cls, mock_glpi_cls,
                                     mock_get_ldap, mock_connect_ldap, mock_check_ad):
        """Test that --batch-size is passed to issue scan."""
        from common.check_missing_users import main

        mock_load_config.return_value = {
            'jira': {'url': 'https://jira.test', 'pat': 'tok'},
            'glpi': {
                'url': 'https://glpi.test/api.php/v1',
                'app_token': 'app',
                'user_token': 'usr',
            },
        }

        mock_jira = Mock()
        mock_jira_cls.return_value = mock_jira
        mock_jira.get_project_users.return_value = []
        mock_jira.get_issue_count.return_value = 1
        mock_jira.search_issues_lightweight.return_value = (
            [{'key': 'P-1', 'fields': {'assignee': None, 'reporter': None}}],
            1
        )

        mock_glpi = Mock()
        mock_glpi_cls.return_value = mock_glpi
        mock_glpi.user_cache = {}
        mock_glpi.get_user_id_by_name.return_value = None

        mock_get_ldap.return_value = None

        test_args = ['check_missing_users.py', 'PROJ', '--batch-size', '50', '-o', self.output_file]
        with patch('sys.argv', test_args):
            main()

        call_kwargs = mock_jira.search_issues_lightweight.call_args
        self.assertEqual(call_kwargs.kwargs.get('max_results') or call_kwargs[1].get('max_results'), 50)

    @patch('common.check_missing_users.check_ad_status')
    @patch('common.check_missing_users.connect_ldap')
    @patch('common.check_missing_users.get_ldap_config')
    @patch('common.check_missing_users.GlpiClient')
    @patch('common.check_missing_users.JiraClient')
    @patch('common.check_missing_users.load_config')
    def test_main_config_with_token_key(self, mock_load_config, mock_jira_cls, mock_glpi_cls,
                                         mock_get_ldap, mock_connect_ldap, mock_check_ad):
        """Test that config using 'token' key (instead of 'pat') works."""
        from common.check_missing_users import main

        mock_load_config.return_value = {
            'jira': {'url': 'https://jira.test', 'token': 'my_token'},
            'glpi': {
                'url': 'https://glpi.test/api.php/v1',
                'app_token': 'app',
                'user_token': 'usr',
            },
        }

        mock_jira = Mock()
        mock_jira_cls.return_value = mock_jira
        mock_jira.get_project_users.return_value = []
        mock_jira.get_issue_count.return_value = 0

        mock_glpi = Mock()
        mock_glpi_cls.return_value = mock_glpi
        mock_glpi.user_cache = {}

        mock_get_ldap.return_value = None

        test_args = ['check_missing_users.py', 'PROJ', '--skip-issues', '-o', self.output_file]
        with patch('sys.argv', test_args):
            main()

        mock_jira_cls.assert_called_once()
        call_kwargs = mock_jira_cls.call_args
        self.assertEqual(call_kwargs.kwargs.get('token') or call_kwargs[1].get('token'), 'my_token')


if __name__ == '__main__':
    unittest.main()
