"""
Migration state management for resumable migrations
Persists progress to JSON file
"""
import os
import json
import time


class StateManager:
    """
    Manages migration state for resumability.

    Tracks:
    - start_at: Current pagination offset
    - total_processed: Total items migrated
    - timestamp: Last update time
    """

    def __init__(self, state_file='migration_state.json'):
        """
        Initialize state manager.

        Args:
            state_file: Path to state file (default: migration_state.json)
        """
        self.state_file = state_file

    def load(self):
        """
        Load migration state from JSON file.

        Returns:
            dict: State dictionary with keys:
                - start_at: Current offset (default: 0)
                - total_processed: Total processed (default: 0)
                - timestamp: Last save time (default: None)
        """
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)

        return {
            "start_at": 0,
            "total_processed": 0,
            "timestamp": None
        }

    def save(self, start_at, total_processed):
        """
        Save migration state to JSON file.

        Args:
            start_at: Current pagination offset
            total_processed: Total items processed
        """
        state = {
            "start_at": start_at,
            "total_processed": total_processed,
            "timestamp": time.time()
        }

        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def reset(self):
        """Reset state to initial values."""
        self.save(start_at=0, total_processed=0)

    def delete(self):
        """Delete state file."""
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
            print(f"Deleted state file: {self.state_file}")


# Convenience functions for backward compatibility
def load_state(state_file='migration_state.json'):
    """
    Load migration state from JSON file (convenience function).

    Args:
        state_file: Path to state file

    Returns:
        dict: State dictionary with start_at and total_processed
    """
    manager = StateManager(state_file)
    return manager.load()


def save_state(state_file, start_at, total_processed):
    """
    Save migration state to JSON file (convenience function).

    Args:
        state_file: Path to state file
        start_at: Current pagination offset
        total_processed: Total tickets processed
    """
    manager = StateManager(state_file)
    manager.save(start_at, total_processed)
