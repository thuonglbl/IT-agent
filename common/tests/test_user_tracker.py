"""
Unit tests for shared.tracking.user_tracker module
Tests missing user tracking functionality
"""
import unittest
import os
import sys
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from common.tracking.user_tracker import UserTracker


class TestUserTracker(unittest.TestCase):
    """Test user tracking functionality."""

    def setUp(self):
        """Create tracker instance for testing."""
        self.tracker = UserTracker()
        self.temp_dir = tempfile.mkdtemp()
        self.report_file = os.path.join(self.temp_dir, 'missing_users.txt')

    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.report_file):
            os.remove(self.report_file)
        os.rmdir(self.temp_dir)

    def test_initial_state(self):
        """Test tracker starts empty."""
        self.assertEqual(self.tracker.get_count(), 0)
        self.assertFalse(bool(self.tracker))

    def test_report_single_user(self):
        """Test reporting a single missing user."""
        self.tracker.report_missing_user("john.doe", "John Doe")

        self.assertEqual(self.tracker.get_count(), 1)
        self.assertTrue(bool(self.tracker))

    def test_report_multiple_users(self):
        """Test reporting multiple missing users."""
        self.tracker.report_missing_user("john.doe", "John Doe")
        self.tracker.report_missing_user("jane.smith", "Jane Smith")
        self.tracker.report_missing_user("bob.jones")

        self.assertEqual(self.tracker.get_count(), 3)

    def test_report_duplicate_user(self):
        """Test that duplicate users are only tracked once."""
        self.tracker.report_missing_user("john.doe", "John Doe")
        self.tracker.report_missing_user("john.doe", "John Doe")
        self.tracker.report_missing_user("john.doe", "John D.")

        # Should only count once
        self.assertEqual(self.tracker.get_count(), 1)

    def test_report_user_without_display_name(self):
        """Test reporting user with only login name."""
        self.tracker.report_missing_user("bob.jones")

        self.assertEqual(self.tracker.get_count(), 1)

    def test_save_report(self):
        """Test saving report to file."""
        self.tracker.report_missing_user("john.doe", "John Doe")
        self.tracker.report_missing_user("jane.smith", "Jane Smith")

        # Save report
        self.tracker.save_report(self.report_file)

        # Verify file exists and has content
        self.assertTrue(os.path.exists(self.report_file))

        with open(self.report_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check header and users
        self.assertIn("Login Name", content)
        self.assertIn("Full Name", content)
        self.assertIn("john.doe", content)
        self.assertIn("John Doe", content)
        self.assertIn("jane.smith", content)
        self.assertIn("Jane Smith", content)

    def test_save_empty_report(self):
        """Test saving report when no users tracked."""
        self.tracker.save_report(self.report_file)

        # File should not be created when no users
        self.assertFalse(os.path.exists(self.report_file))

        # Verify count is 0
        self.assertEqual(self.tracker.get_count(), 0)

    def test_bool_conversion(self):
        """Test __bool__ method."""
        # Empty tracker
        self.assertFalse(bool(self.tracker))

        # Add user
        self.tracker.report_missing_user("john.doe")
        self.assertTrue(bool(self.tracker))

    def test_report_format(self):
        """Test report file format (TSV)."""
        self.tracker.report_missing_user("user1", "User One")
        self.tracker.report_missing_user("user2", "User Two")

        self.tracker.save_report(self.report_file)

        with open(self.report_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Check header
        self.assertIn('\t', lines[0])  # Tab-separated

        # Check data lines
        for line in lines[1:]:
            if line.strip():  # Skip empty lines
                self.assertIn('\t', line)

    def test_case_sensitivity(self):
        """Test that usernames are case-sensitive."""
        self.tracker.report_missing_user("John.Doe", "John Doe")
        self.tracker.report_missing_user("john.doe", "John Doe")

        # Should track both as different users
        self.assertEqual(self.tracker.get_count(), 2)

    def test_logger_integration(self):
        """Test that logger can be attached."""
        # Mock logger
        class MockLogger:
            def __init__(self):
                self.warnings = []

            def warning(self, msg):
                self.warnings.append(msg)

        mock_logger = MockLogger()
        self.tracker.logger = mock_logger

        # Report user
        self.tracker.report_missing_user("john.doe", "John Doe")

        # Logger should have been called
        self.assertEqual(len(mock_logger.warnings), 1)
        self.assertIn("john.doe", mock_logger.warnings[0])


if __name__ == '__main__':
    unittest.main()
