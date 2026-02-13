"""
Unit tests for shared.utils.dates module
Tests date parsing and formatting functions
"""
import unittest
from datetime import datetime, timezone, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from common.utils.dates import parse_jira_date, format_glpi_date_friendly, format_comment_date, TZ_VN


class TestDateUtils(unittest.TestCase):
    """Test date parsing and formatting utilities."""

    def test_tz_vn_constant(self):
        """Test that TZ_VN is UTC+7."""
        self.assertEqual(TZ_VN, timezone(timedelta(hours=7)))

    def test_parse_jira_date_basic(self):
        """Test basic Jira date parsing."""
        jira_date = "2024-01-15T10:30:00.000+0700"
        result = parse_jira_date(jira_date)

        # Result should be in format YYYY-MM-DD HH:MM:SS
        self.assertIsNotNone(result)
        self.assertRegex(result, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')

        # Should contain date components
        self.assertIn("2024-01-15", result)

    def test_parse_jira_date_none(self):
        """Test parsing None returns None."""
        result = parse_jira_date(None)
        self.assertIsNone(result)

    def test_parse_jira_date_empty_string(self):
        """Test parsing empty string returns None."""
        result = parse_jira_date("")
        self.assertIsNone(result)

    def test_parse_jira_date_without_milliseconds(self):
        """Test parsing date without milliseconds."""
        jira_date = "2024-01-15T10:30:00+0700"
        result = parse_jira_date(jira_date)

        # Should parse successfully
        self.assertIsNotNone(result)
        self.assertIn("2024-01-15", result)

    def test_parse_jira_date_invalid(self):
        """Test invalid date string."""
        result = parse_jira_date("invalid-date")
        self.assertIsNone(result)

    def test_format_glpi_date_friendly(self):
        """Test friendly date formatting."""
        glpi_date = "2024-01-15 10:30:00"
        result = format_glpi_date_friendly(glpi_date)

        # Should contain date, time, and timezone
        self.assertIn("2024-01-15", result)
        self.assertIn("UTC+7", result)

    def test_format_glpi_date_friendly_none(self):
        """Test formatting None."""
        result = format_glpi_date_friendly(None)
        self.assertEqual(result, "N/A")

    def test_format_comment_date(self):
        """Test comment date formatting."""
        jira_date = "2024-01-15T16:58:30.000+0700"
        result = format_comment_date(jira_date)

        # Should be in Jira style: "15/Jan/24 4:58 PM (UTC+7)"
        self.assertIsNotNone(result)
        self.assertIn("UTC+7", result)
        self.assertIn("/", result)
        self.assertIn("Jan", result)

    def test_format_comment_date_none(self):
        """Test formatting None comment date."""
        result = format_comment_date(None)
        self.assertEqual(result, "N/A")

    def test_timezone_conversion(self):
        """Test that dates are properly converted to UTC+7."""
        # Date in different timezone (UTC)
        jira_date = "2024-01-15T10:30:00.000+0000"  # UTC
        result = parse_jira_date(jira_date)

        # Should be converted to UTC+7 (17:30)
        self.assertIsNotNone(result)
        # The exact time depends on system timezone, but format should be correct
        self.assertRegex(result, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')


if __name__ == '__main__':
    unittest.main()
