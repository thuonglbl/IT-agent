"""
Unit tests for shared.utils.state_manager module
Tests state persistence for resumable migrations
"""
import unittest
import json
import os
import sys
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from common.utils.state_manager import StateManager, load_state, save_state


class TestStateManager(unittest.TestCase):
    """Test state management functionality."""

    def setUp(self):
        """Create temporary state file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, 'test_state.json')
        self.manager = StateManager(self.state_file)

    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        os.rmdir(self.temp_dir)

    def test_load_empty_state(self):
        """Test loading state when file doesn't exist."""
        state = self.manager.load()

        # Should return default state
        self.assertEqual(state['start_at'], 0)
        self.assertEqual(state['total_processed'], 0)
        self.assertIn('timestamp', state)

    def test_save_and_load_state(self):
        """Test saving and loading state."""
        # Save state
        self.manager.save(start_at=150, total_processed=150)

        # Load state
        state = self.manager.load()

        # Verify values
        self.assertEqual(state['start_at'], 150)
        self.assertEqual(state['total_processed'], 150)
        self.assertIn('timestamp', state)

    def test_state_file_format(self):
        """Test that state file is valid JSON."""
        self.manager.save(start_at=100, total_processed=95)

        # Read file directly
        with open(self.state_file, 'r') as f:
            data = json.load(f)

        # Verify structure
        self.assertIn('start_at', data)
        self.assertIn('total_processed', data)
        self.assertIn('timestamp', data)
        self.assertEqual(data['start_at'], 100)
        self.assertEqual(data['total_processed'], 95)

    def test_reset_state(self):
        """Test resetting state to defaults."""
        # Save some state
        self.manager.save(start_at=200, total_processed=180)

        # Reset
        self.manager.reset()

        # Load and verify
        state = self.manager.load()
        self.assertEqual(state['start_at'], 0)
        self.assertEqual(state['total_processed'], 0)

    def test_delete_state(self):
        """Test deleting state file."""
        # Save state
        self.manager.save(start_at=50, total_processed=50)
        self.assertTrue(os.path.exists(self.state_file))

        # Delete
        self.manager.delete()
        self.assertFalse(os.path.exists(self.state_file))

    def test_update_state_incrementally(self):
        """Test updating state multiple times."""
        # First save
        self.manager.save(start_at=50, total_processed=50)

        # Second save
        self.manager.save(start_at=100, total_processed=98)

        # Load and verify latest values
        state = self.manager.load()
        self.assertEqual(state['start_at'], 100)
        self.assertEqual(state['total_processed'], 98)

    def test_backward_compatible_load(self):
        """Test backward compatible load_state function."""
        # Save using class method
        self.manager.save(start_at=75, total_processed=70)

        # Load using backward compatible function
        state = load_state(self.state_file)
        self.assertEqual(state['start_at'], 75)
        self.assertEqual(state['total_processed'], 70)

    def test_backward_compatible_save(self):
        """Test backward compatible save_state function."""
        # Save using backward compatible function
        save_state(self.state_file, start_at=125, total_processed=120)

        # Load using class method
        state = self.manager.load()
        self.assertEqual(state['start_at'], 125)
        self.assertEqual(state['total_processed'], 120)

    def test_state_persistence_across_instances(self):
        """Test that state persists across different StateManager instances."""
        # Save with first instance
        manager1 = StateManager(self.state_file)
        manager1.save(start_at=300, total_processed=295)

        # Load with second instance
        manager2 = StateManager(self.state_file)
        state = manager2.load()

        self.assertEqual(state['start_at'], 300)
        self.assertEqual(state['total_processed'], 295)


if __name__ == '__main__':
    unittest.main()
