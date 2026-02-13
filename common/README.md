Unified library for GLPI and Jira migration scripts.

## Overview

The `common/` library unifies code from the 3 migration folders to reduce duplication and provide a single source of truth for API interactions.

**Key Components:**
- Unified GLPI v1 & Jira v2 API clients
- Shared configuration loader (YAML/Env)
- State management for resumable migrations
- Logging & date utilities

## Directory Structure

```
common/
├── clients/                    # API client implementations
│   ├── glpi_client.py         # Unified GLPI REST API v1 client
│   └── jira_client.py         # Unified Jira REST API v2 client
├── config/                     # Configuration management
│   └── loader.py              # Multi-format config loader (YAML + Python)
├── utils/                      # Utility functions
│   ├── dates.py               # Date parsing/formatting (UTC+7)
│   └── state_manager.py       # State persistence (resumability)
├── tracking/                   # Migration tracking
│   └── user_tracker.py        # Missing users tracker
├── logging/                    # Logging setup
│   └── logger.py              # Structured logging
└── README.md                   # This file
```

---

## Module Documentation

### 1. clients/glpi_client.py

**Purpose:** Unified GLPI REST API v1 client consolidating all 3 implementations

**Features:**
- Session management (User Token + Basic Auth fallback)
- Knowledge Base operations (from folder 01)
- Ticket/Assistance operations (from folders 02 & 03)
- Project/Task operations (from folder 02)
- Document management (from all folders)
- Multiple caching (users, groups, categories, locations)

**Usage:**
```python
from common.clients.glpi_client import GlpiClient

# Initialize client
glpi = GlpiClient(
    url="https://glpi.example.com/api.php/v1",
    app_token="your_app_token",
    user_token="your_user_token",  # Optional, tried first
    username="your_username",       # Optional, Basic Auth fallback
    password="your_password",       # Optional, Basic Auth fallback
    verify_ssl=False
)

# Initialize session
glpi.init_session()

# Load caches (O(1) lookups)
glpi.load_user_cache(recursive=True)
glpi.load_group_cache(recursive=True)
glpi.load_category_cache(recursive=True)
glpi.load_location_cache()

# Create a ticket
ticket_id = glpi.create_ticket(
    name="Ticket Title",
    content="<p>Ticket description</p>",
    status=1,
    urgency=3,
    _users_id_requester=123,
    _users_id_assign=456
)

# Upload and link document
doc_id = glpi.upload_document("path/to/file.pdf", name="document.pdf")
glpi.link_document_to_ticket(ticket_id, doc_id)

# Kill session when done
glpi.kill_session()
```

**Key Methods:**
```python
# Session
init_session(), kill_session()

# Knowledge Base
create_knowbase_item(), get_kb_category_id(), create_kb_category()
ensure_category_path(), get_knowbase_items(), delete_knowbase_item()

# Tickets
create_ticket(), update_ticket(), add_ticket_followup()
get_ticket_statuses(), get_status_id_map(), get_type_id_map()
link_item_to_ticket()

# Projects
create_project(), get_project_id_by_name()
create_project_task(), update_project_task()
add_project_task_team_member()
get_project_states(), get_project_task_types()
create_note()

# Documents
upload_document(), link_document_to_ticket(), delete_document()

# Caching
load_user_cache(), get_user_id_by_name()
load_group_cache(), get_group_id_by_name()
load_category_cache(), get_or_create_category()
load_location_cache(), get_location_id()

# Items/Assets
get_item_id(), get_item()
```

---

### 2. clients/jira_client.py

**Purpose:** Unified Jira REST API v2 client merging implementations from folders 02 & 03

**Features:**
- Issue search with pagination
- Attachment download
- Project metadata (statuses, issue types, users)
- Security level discovery (API + JQL fallback)

**Usage:**
```python
from common.clients.jira_client import JiraClient

# Initialize client
jira = JiraClient(
    url="https://jira.example.com",
    token="your_personal_access_token",
    verify_ssl=False
)

# Search issues
jql = "project = PROJ AND status = Open"
issues, total = jira.search_issues(jql, start_at=0, max_results=50)

# Get project statuses
statuses = jira.get_project_statuses("PROJ")
# Returns: [{"name": "Open", "statusCategory": {...}}, ...]

# Get security levels
security_levels = jira.get_security_levels("PROJ")
# Returns: {"Internal": "10001", "Public": "10002"}

# Download attachment
content = jira.get_attachment_content("https://jira.example.com/attachment/12345")
```

**Key Methods:**
```python
search_issues(jql, start_at, max_results)  # Pagination support
get_issue_count(jql)                       # Lightweight count
get_attachment_content(url)                # Download attachments
get_project_statuses(project_key)          # Status list
get_project_issue_types(project_key)       # Issue types
get_project_users(project_key)             # Assignable users
get_security_levels(project_key)           # Security levels (with JQL fallback)
```

---

### 3. config/loader.py

**Purpose:** Multi-format configuration loader with inheritance support

**Features:**
- **Configuration Inheritance**: Loads common config + folder-specific config and merges them
- Auto-detects config format (config.yaml → config.yml → config.py)
- Loads YAML configs (folder 03 style)
- Loads Python modules (folders 01/02 style)
- Environment variable overrides (highest priority)
- Automatic path resolution for SSL certificates
- Optional validation

**Configuration Inheritance:**

The loader supports a two-level configuration system:
1. **Common Config** (`common/config.yaml`): Shared settings for all migrations (GLPI/Jira credentials, logging, default batch size)
2. **Folder-Specific Config** (each folder's `config.yaml`): Project-specific settings (project keys, custom fields, mappings)

**How it works:**
```
1. Load common/config.yaml (if exists)        → Base configuration
2. Load folder-specific config.yaml           → Project settings
3. Deep merge: folder config overrides common → Merged config
4. Apply environment variable overrides       → Final config
5. Resolve relative paths (SSL certificates)  → Absolute paths
```

**Example structure:**

`common/config.yaml` (shared):
```yaml
glpi:
  url: "https://glpi.example.com/api.php/v1"
  app_token: "YOUR_APP_TOKEN"
  user_token: "YOUR_USER_TOKEN"
  verify_ssl: "common/glpi.pem"  # Auto-resolved to absolute path

jira:
  url: "https://jira.example.com"
  pat: "YOUR_PAT"

migration:
  batch_size: 50
  debug: false
```

`02_project_jira_to_glpi_project_tasks_migration/config.yaml` (specific):
```yaml
jira:
  project_key: "MYPROJECT"          # Project-specific
  jql: "project = MYPROJECT"        # Project-specific
  custom_fields:                    # Project-specific
    answer: customfield_10082
    # ... 80+ more fields

glpi:
  project_name: "My GLPI Project"   # Project-specific
```

**Usage:**
```python
from common.config.loader import load_config

# Auto-detect and load config with inheritance
config = load_config()
# Automatically loads:
# 1. ../common/config.yaml (common settings)
# 2. config.yaml (folder-specific overrides)
# 3. Environment variables (highest priority overrides)

# Access merged config values
jira_url = config['jira']['url']              # From common config
project_key = config['jira']['project_key']   # From folder config
glpi_token = config['glpi']['app_token']      # From common config

# Load specific file
config = load_config('custom_config.yaml')

# Load without validation (for legacy configs)
config = load_config(validate=False)
```

**Environment Variables (Highest Priority):**
```bash
# Jira
export JIRA_PAT="your_personal_access_token"
export JIRA_URL="https://jira.example.com"

# GLPI
export GLPI_APP_TOKEN="your_app_token"
export GLPI_USER_TOKEN="your_user_token"
export GLPI_USERNAME="your_username"
export GLPI_PASSWORD="your_password"

# Logging
export LOG_LEVEL="DEBUG"
```

**Benefits of Configuration Inheritance:**
- ✅ **DRY (Don't Repeat Yourself)**: GLPI/Jira credentials stored once in common config
- ✅ **Single Source of Truth**: Update credentials in one place, all migrations benefit
- ✅ **Cleaner Folder Configs**: Only project-specific settings in folder configs
- ✅ **Easier Maintenance**: Clear separation between shared and unique settings
- ✅ **Backward Compatible**: Still supports standalone config files (without common config)

**Supported Formats:**

**YAML (config.yaml):**
```yaml
jira:
  url: https://jira.example.com
  pat: your_token

glpi:
  url: https://glpi.example.com/api.php/v1
  app_token: your_app_token
  user_token: your_user_token

logging:
  level: INFO
  console: true
  file: true
```

**Python (config.py):**
```python
# Structured approach
CONFIG = {
    "jira": {
        "url": "https://jira.example.com",
        "pat": "your_token"
    },
    "glpi": {
        "url": "https://glpi.example.com/api.php/v1",
        "app_token": "your_app_token"
    }
}

# Or flat attributes
JIRA_URL = "https://jira.example.com"
JIRA_PAT = "your_token"
GLPI_URL = "https://glpi.example.com/api.php/v1"
GLPI_APP_TOKEN = "your_app_token"
```

---

### 4. utils/dates.py

**Purpose:** Date parsing and formatting with UTC+7 timezone conversion

**Functions:**
```python
from common.utils.dates import parse_jira_date, format_glpi_date_friendly, format_comment_date

# Parse Jira ISO date to GLPI format
glpi_date = parse_jira_date("2024-01-15T10:30:00.000+0700")
# Returns: "2024-01-15 10:30:00"

# Format for HTML display
friendly = format_glpi_date_friendly("2024-01-15 10:30:00")
# Returns: "2024-01-15 10:30 AM (UTC+7)"

# Format for comment headers (Jira style)
comment_date = format_comment_date("2024-01-15T16:58:30.000+0700")
# Returns: "15/Jan/24 4:58 PM (UTC+7)"
```

**Constant:**
```python
TZ_VN = timezone(timedelta(hours=7))  # UTC+7 timezone
```

---

### 5. utils/state_manager.py

**Purpose:** Migration state persistence for resumability

**Usage:**
```python
from common.utils.state_manager import StateManager

# Initialize state manager
state = StateManager('migration_state.json')

# Load state
current_state = state.load()
start_at = current_state['start_at']
total_processed = current_state['total_processed']

# Process items...

# Save state
state.save(start_at=150, total_processed=150)

# Reset state
state.reset()

# Delete state file
state.delete()
```

**Backward Compatible Functions:**
```python
from common.utils.state_manager import load_state, save_state

state = load_state('migration_state.json')
save_state('migration_state.json', start_at=100, total_processed=100)
```

**State File Format (JSON):**
```json
{
  "start_at": 150,
  "total_processed": 150,
  "timestamp": 1705299600.0
}
```

---

### 6. tracking/user_tracker.py

**Purpose:** Track missing users during migration

**Usage:**
```python
from common.tracking.user_tracker import UserTracker

# Initialize tracker
tracker = UserTracker()
tracker.logger = logger  # Optional: attach logger

# Report missing users
tracker.report_missing_user("john.doe", "John Doe")
tracker.report_missing_user("jane.smith")  # Display name optional

# Get statistics
count = tracker.get_count()
has_missing = bool(tracker)  # True if any missing users

# Save report
tracker.save_report('missing_users.txt')
```

**Report Format (TSV):**
```
Login Name      Full Name
john.doe        John Doe
jane.smith      jane.smith
```

---

### 7. logging/logger.py

**Purpose:** Structured logging with console and file output

**Usage:**
```python
from common.logging.logger import setup_logger, MigrationLogger

# Function-based approach
config = load_config()
logger = setup_logger("migration", config)
logger.info("Migration started")

# Class-based approach
migration_logger = MigrationLogger("migration", config)
migration_logger.info("Migration started")

# Get child logger
child_logger = migration_logger.get_child("field_extractor")
child_logger.debug("Extracting fields...")
```

**Configuration:**
```yaml
logging:
  level: INFO                            # DEBUG, INFO, WARNING, ERROR, CRITICAL
  console: true                          # Enable console output
  file: true                             # Enable file output
  file_path: logs/migration_{timestamp}.log
  format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
```

**Log Levels:**
- **DEBUG**: Field extraction details, mapping logic
- **INFO**: Processing start/end, batch progress
- **WARNING**: Missing users, fallback mappings
- **ERROR**: API failures, validation errors
- **CRITICAL**: Fatal errors that stop migration

**Output Example:**
```
2024-01-15 10:30:00 [INFO] migration: Migration started
2024-01-15 10:30:01 [INFO] migration: Loaded 1500 users into cache
2024-01-15 10:30:05 [WARNING] migration: Missing user: john.doe (John Doe)
2024-01-15 10:30:10 [INFO] migration: Created Ticket 'Issue Title': ID 123
```

---

## Migration Example

Complete migration script using common library:

```python
from common.config.loader import load_config
from common.logging.logger import setup_logger
from common.clients.jira_client import JiraClient
from common.clients.glpi_client import GlpiClient
from common.utils.state_manager import StateManager
from common.tracking.user_tracker import UserTracker

# Load config
config = load_config()

# Setup logging
logger = setup_logger("migration", config)
logger.info("=== Migration Started ===")

# Initialize clients
jira = JiraClient(
    url=config['jira']['url'],
    token=config['jira']['pat'],
    verify_ssl=config['jira'].get('verify_ssl', False)
)

glpi = GlpiClient(
    url=config['glpi']['url'],
    app_token=config['glpi']['app_token'],
    user_token=config['glpi'].get('user_token'),
    username=config['glpi'].get('username'),
    password=config['glpi'].get('password'),
    verify_ssl=config['glpi'].get('verify_ssl', False)
)

try:
    # Initialize GLPI session
    glpi.init_session()
    glpi.load_user_cache(recursive=True)

    # Initialize trackers
    state = StateManager('migration_state.json')
    user_tracker = UserTracker()
    user_tracker.logger = logger

    # Load state
    current_state = state.load()
    start_at = current_state['start_at']
    total_processed = current_state['total_processed']

    logger.info(f"Resuming from offset {start_at}")

    # Migration loop
    batch_size = 50
    jql = "project = PROJ ORDER BY key ASC"

    while True:
        # Fetch issues
        issues, total = jira.search_issues(jql, start_at=start_at, max_results=batch_size)
        if not issues:
            break

        logger.info(f"Processing batch: {len(issues)} issues")

        # Process each issue
        for issue in issues:
            # Extract fields, create ticket, etc.
            # Use user_tracker.report_missing_user() for missing users
            total_processed += 1

        # Save state
        start_at += len(issues)
        state.save(start_at, total_processed)

    logger.info(f"Migration complete. Total processed: {total_processed}")

    # Save reports
    user_tracker.save_report('missing_users.txt')

finally:
    glpi.kill_session()
```

---

## Backward Compatibility

The common library maintains backward compatibility with existing migration scripts:

### Folder 03 (Already Modular)
- **Current**: Uses `lib/` folder structure
- **Migration**: Update imports to use `common.*` instead of `lib.*`
- **Risk**: Low (minimal changes)

### Folder 02 (Python Config)
- **Current**: Uses `config.py` Python module
- **Migration**: ConfigLoader auto-detects and loads Python configs
- **Risk**: Medium (80+ custom field mappings)

### Folder 01 (Simple Script)
- **Current**: Uses `config.py` Python module
- **Migration**: ConfigLoader auto-detects and loads Python configs
- **Risk**: Low (simpler script)

---

## Testing

### Unit Tests (Planned)
```
common/tests/
├── test_glpi_client.py
├── test_jira_client.py
├── test_config_loader.py
├── test_date_utils.py
├── test_state_manager.py
└── test_user_tracker.py
```

### Integration Tests (Planned)
- Mock API responses
- Test each migration script with test data
- Verify output matches legacy implementation

---

## Future Enhancements

1. **Add unit tests** for all modules
2. **Add integration tests** with mock APIs
3. **Add CLI tools** for common operations
4. **Add HTML builder utilities** (extract from folder 03)
5. **Add field extractor utilities** (extract from folders 02 & 03)

---

## Contributing

When adding new features:
1. Keep modules focused and single-purpose
2. Maintain backward compatibility where possible
3. Add docstrings with examples
4. Update this README with usage examples

---

## License

License: MIT

---

## Support

For questions or issues:
1. Check this README
2. Check individual module docstrings
3. Check migration folder USER_GUIDE.md files
4. Contact: thuong.lambale@gmail.com
