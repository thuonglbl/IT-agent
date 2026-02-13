# Common Library Unit Tests

Comprehensive unit tests for the common library modules.

## Test Coverage

### Core Modules

1. **test_dates.py** - Date utilities (shared.utils.dates)
   - Timezone conversion (UTC+7)
   - Jira date parsing
   - GLPI date formatting
   - Comment date formatting
   - Edge cases (None, empty, invalid dates)

2. **test_state_manager.py** - State persistence (shared.utils.state_manager)
   - State save/load
   - State reset/delete
   - Backward compatibility functions
   - JSON file format validation
   - Multi-instance persistence

3. **test_user_tracker.py** - Missing user tracking (shared.tracking.user_tracker)
   - User reporting
   - Duplicate detection
   - Report generation (TSV format)
   - Logger integration
   - Count tracking

4. **test_config_loader.py** - Configuration loading (shared.config.loader)
   - YAML config loading
   - Python module loading
   - Auto-detection (config.yaml → config.yml → config.py)
   - Custom file loading
   - Nested structure handling
   - Environment variable overrides

## Running Tests

### Run All Tests

```bash
# From common/tests directory
python run_tests.py

# Or using unittest directly
python -m unittest discover -s . -p "test_*.py" -v
```

### Run Specific Test File

```bash
python -m unittest test_dates
python -m unittest test_state_manager
python -m unittest test_user_tracker
python -m unittest test_config_loader
```

### Run Specific Test Case

```bash
python -m unittest test_dates.TestDateUtils.test_parse_jira_date_basic
python -m unittest test_state_manager.TestStateManager.test_save_and_load_state
```

## Test Structure

Each test file follows this structure:

```python
import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from common.module_name import ClassOrFunction


class TestModuleName(unittest.TestCase):
    """Test class docstring."""

    def setUp(self):
        """Set up test fixtures."""
        pass

    def tearDown(self):
        """Clean up after tests."""
        pass

    def test_feature_name(self):
        """Test specific feature."""
        # Arrange
        # Act
        # Assert
        pass
```

## Test Conventions

1. **File Names**: `test_<module_name>.py`
2. **Class Names**: `Test<ModuleName>` (CamelCase)
3. **Method Names**: `test_<feature_description>` (snake_case)
4. **Docstrings**: Every test should have a clear docstring
5. **AAA Pattern**: Arrange, Act, Assert

## Adding New Tests

When adding new tests:

1. Create new file: `test_<module>.py`
2. Import module under test
3. Create test class inheriting from `unittest.TestCase`
4. Add test methods with descriptive names
5. Use `setUp()` and `tearDown()` for fixtures
6. Run tests to verify they work

## Test Requirements

No additional dependencies needed - all tests use Python's built-in `unittest` framework.

## Expected Output

```
test_format_comment_date (test_dates.TestDateUtils) ... ok
test_format_glpi_date_friendly (test_dates.TestDateUtils) ... ok
test_parse_jira_date_basic (test_dates.TestDateUtils) ... ok
...

----------------------------------------------------------------------
Ran 45 tests in 0.123s

OK
```

## Coverage Goals

- **Unit Tests**: Test individual functions and methods in isolation
- **Edge Cases**: Test None, empty, invalid inputs
- **Integration Points**: Test interaction between modules
- **Backward Compatibility**: Test legacy function wrappers
- **Error Handling**: Test exception raising and handling

## Future Tests

Planned test additions:

1. **test_glpi_client.py** - API client tests (requires mocking)
2. **test_jira_client.py** - API client tests (requires mocking)
3. **test_logger.py** - Logging setup tests

These require mocking HTTP requests and will be added in Phase 5.

## Continuous Integration

Tests can be integrated into CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    cd common/tests
    python run_tests.py
```

## Troubleshooting

### Import Errors

If you encounter import errors:
```python
# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
```

### Test Discovery Issues

If tests aren't discovered:
- Ensure test files start with `test_`
- Ensure test classes inherit from `unittest.TestCase`
- Ensure test methods start with `test_`

### File Permission Errors

If temporary file tests fail:
- Ensure write permissions in temp directory
- Check that tearDown() properly cleans up files

## Contributing

When contributing tests:
1. Write clear, descriptive test names
2. Add docstrings explaining what is tested
3. Test both success and failure cases
4. Clean up any temporary files or state
5. Run all tests before committing

---

For more information, see the main [common library README](../README.md).
