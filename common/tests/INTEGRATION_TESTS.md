# Integration Testing Guide

This guide explains how to write and run integration tests for the common library and migration scripts.

## What are Integration Tests?

Integration tests verify that multiple components work together correctly. Unlike unit tests that test individual functions, integration tests check:

- **Component Interaction**: How modules communicate
- **Workflow Validation**: Complete migration processes
- **API Integration**: Client interactions with external services (mocked)
- **Error Handling**: How errors propagate through the system

## Test Structure

### Integration Test Examples (`test_integration_example.py`)

The integration test file demonstrates several patterns:

#### 1. Config + State Manager Integration
```python
def test_config_driven_state_management(self):
    """Test that config and state manager work together."""
    # Load config
    config = load_config(validate=False)

    # Use state file path from config
    state_file = config['migration']['state_file']
    state_manager = StateManager(state_file)

    # Test save/load
    state_manager.save(start_at=100, total_processed=95)
    state = state_manager.load()
```

#### 2. User Tracker + Logger Integration
```python
def test_user_tracker_with_mock_logger(self):
    """Test user tracker with logging."""
    mock_logger = Mock()
    tracker = UserTracker()
    tracker.logger = mock_logger

    tracker.report_missing_user("john.doe", "John Doe")

    # Verify logger was called
    assert mock_logger.warning.call_count == 1
```

#### 3. Complete Migration Workflow Simulation
```python
def test_resumable_migration_workflow(self):
    """Test full migration with state persistence."""
    # First run: process batch and save state
    state_manager.save(start_at=50, total_processed=50)

    # Second run: resume from saved state
    state = state_manager.load()
    assert state['start_at'] == 50
```

## Running Integration Tests

### Run All Integration Tests
```bash
cd common/tests
python -m unittest test_integration_example -v
```

### Run Specific Integration Test
```bash
python -m unittest test_integration_example.TestMigrationWorkflow.test_resumable_migration_workflow
```

### Run All Tests (Unit + Integration)
```bash
python run_tests.py
```

## Mocking External APIs

For testing API clients (GlpiClient, JiraClient), use mocking to avoid real HTTP requests:

### Pattern 1: Using `unittest.mock.patch`
```python
from unittest.mock import Mock, patch

@patch('shared.clients.glpi_client.requests.Session')
def test_glpi_client(self, mock_session_class):
    mock_session = Mock()
    mock_session_class.return_value = mock_session

    # Mock API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'session_token': 'test'}
    mock_session.get.return_value = mock_response

    # Test client
    client = GlpiClient(url='...', app_token='...')
    client.init_session()
```

### Pattern 2: Using `responses` Library
```python
import responses

@responses.activate
def test_jira_search():
    # Mock endpoint
    responses.add(
        responses.GET,
        'https://jira.example.com/rest/api/2/search',
        json={'total': 100, 'issues': [...]},
        status=200
    )

    # Test client
    client = JiraClient(url='...', token='...')
    issues, total = client.search_issues("project = TEST")
```

## Writing New Integration Tests

### Step 1: Identify Components to Test
Example: Config Loader + GLPI Client + State Manager

### Step 2: Create Test Class
```python
class TestMyIntegration(unittest.TestCase):
    def setUp(self):
        # Set up test fixtures
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Clean up
        shutil.rmtree(self.temp_dir)

    def test_component_interaction(self):
        # Test implementation
        pass
```

### Step 3: Mock External Dependencies
```python
@patch('module.external_api_call')
def test_with_mock(self, mock_api):
    mock_api.return_value = {'status': 'success'}
    # Test code
```

### Step 4: Verify Expected Behavior
```python
# Verify state changes
self.assertEqual(state['start_at'], 100)

# Verify method calls
mock_logger.warning.assert_called_once()

# Verify file operations
self.assertTrue(os.path.exists(output_file))
```

## Common Integration Test Scenarios

### 1. Migration Resume After Interruption
```python
def test_migration_resume(self):
    # Run 1: Process 50 issues, save state
    process_batch(0, 50)
    save_state(start_at=50)

    # Simulate restart
    state = load_state()

    # Run 2: Resume from 50
    process_batch(state['start_at'], 100)
```

### 2. Error Handling Across Components
```python
def test_error_propagation(self):
    # Simulate API error
    with self.assertRaises(APIError):
        client.fetch_data()

    # Verify state still valid
    state = state_manager.load()
    self.assertIsNotNone(state)
```

### 3. Multi-Component Workflow
```python
def test_full_workflow(self):
    # 1. Load config
    config = load_config()

    # 2. Initialize clients
    jira = JiraClient(config['jira'])
    glpi = GlpiClient(config['glpi'])

    # 3. Process data
    issues = jira.search_issues("...")
    for issue in issues:
        ticket_id = glpi.create_ticket(...)

    # 4. Verify results
    self.assertEqual(processed_count, expected_count)
```

## Test Data Management

### Creating Test Configs
```python
def create_test_config(temp_dir):
    config_data = {
        'jira': {'url': 'https://test.jira.com', 'pat': 'test'},
        'glpi': {'url': 'https://test.glpi.com/api.php/v1', 'app_token': 'test'}
    }

    config_file = os.path.join(temp_dir, 'config.yaml')
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)

    return config_file
```

### Creating Test State
```python
def create_test_state(temp_dir):
    state_manager = StateManager(f'{temp_dir}/state.json')
    state_manager.save(start_at=0, total_processed=0)
    return state_manager
```

## Performance Testing

Integration tests can also measure performance:

```python
import time

def test_batch_processing_performance(self):
    start_time = time.time()

    # Process batch
    process_large_batch(1000)

    elapsed = time.time() - start_time

    # Verify performance target
    self.assertLess(elapsed, 60.0, "Batch took too long")
```

## Debugging Integration Tests

### Enable Detailed Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Print Mock Call History
```python
print(f"Mock called {mock_api.call_count} times")
print(f"Call args: {mock_api.call_args_list}")
```

### Inspect Temporary Files
```python
def tearDown(self):
    # Don't delete temp files for debugging
    if os.environ.get('DEBUG_TESTS'):
        print(f"Test files in: {self.temp_dir}")
    else:
        shutil.rmtree(self.temp_dir)
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run Tests
        run: |
          cd common/tests
          python run_tests.py
```

## Best Practices

1. **Isolate Tests**: Each test should be independent
2. **Use Mocks**: Don't make real API calls
3. **Clean Up**: Always clean up temporary files
4. **Descriptive Names**: Use clear test method names
5. **Document**: Add docstrings explaining what's tested
6. **Fast Tests**: Keep integration tests under 5 seconds each
7. **Reproducible**: Tests should pass consistently

## Troubleshooting

### Test Hangs
- Check for unmocked HTTP requests
- Verify timeout settings
- Look for infinite loops

### Intermittent Failures
- Check for timing issues
- Verify cleanup in tearDown
- Look for shared state between tests

### Mock Not Working
- Verify correct import path in @patch
- Check mock is created before calling code
- Ensure mock return values match expected types

## Future Enhancements

Planned integration test additions:

1. **Full Migration E2E**: Complete migration from Jira to GLPI with realistic data
2. **Error Recovery**: Test recovery from various failure scenarios
3. **Large Dataset**: Test with 10,000+ issues
4. **Concurrent Processing**: Test parallel batch processing
5. **Database Integration**: Test with real GLPI database

---

For questions or issues with integration testing, see the main [README](README.md) or contact the development team.
