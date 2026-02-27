# IT Agent System

## Project Objective

Migrate data from Atlassian to GLPI.

**Reason:** GLPI has a free community version on premise - no more license costs for Atlassian Confluence and Jira, but no built-in migration tool.

## Project Structure

```
IT-agent/
├── common/                    # Shared library (imported by all migrations)
│   ├── import_ldap_playwright.py  # LDAP user import automation
│   ├── clients/              # API clients (GLPI, Jira)
│   ├── config/               # Configuration loader with inheritance
│   ├── utils/                # Utilities (dates, state management)
│   ├── tracking/             # User tracking
│   └── logging/              # Structured logging
│
├── 01_confluence_to_glpi_migration/           # Migration 1: Knowledge Base
├── 02_project_jira_to_glpi_project_tasks_migration/  # Migration 2: Projects
└── 03_support_jira_to_glpi_assistance_tickets_migration/  # Migration 3: Tickets
```

**Note:** Migrations are numbered for organization. Each migration is independent and can be run in any order based on your needs.

## Roadmap & Milestones

1.  **Data Migration (from Confluence to GLPI > Tools > Knowledge Base)**
    *   See [User Guide](01_confluence_to_glpi_migration/USER_GUIDE.md)
    *   *Status: Done*

2.  **Data Migration (from Project Jira to GLPI > Tools > Projects)**
    *   See [User Guide](02_project_jira_to_glpi_project_tasks_migration/USER_GUIDE.md)
    *   *Status: Done*

3.  **Data Migration (from Support Jira to GLPI > Assistance)**
    *   See [User Guide](03_support_jira_to_glpi_assistance_tickets_migration/USER_GUIDE.md)
    *   *Status: Done*

## Quick Start

### 1. Setup Configuration

**Create common configuration:**
```bash
cp common/config.yaml.example common/config.yaml
# Edit common/config.yaml with your GLPI/Jira credentials
```

**Create migration-specific configuration:**
```bash
cd 01_confluence_to_glpi_migration
cp config.yaml.example config.yaml
# Edit config.yaml with migration-specific settings
```

### 2. Import LDAP Users (Required Before Any Migration)

All migrations depend on users existing in GLPI for correct ticket/task assignment. You must import LDAP users first:

```bash
# Install dependencies (once)
pip install -r common/requirements.txt
playwright install chromium

# Run LDAP import
python common/import_ldap_playwright.py
```

Before running the import, ensure your GLPI LDAP directory is properly configured (paged results enabled, correct connection filter). See [common/USER_GUIDE.md](common/USER_GUIDE.md#glpi-ldap-configuration-guide) for detailed setup instructions.

### 3. Run Migration

```bash
# Choose the migration you need to run
cd 01_confluence_to_glpi_migration  # OR
cd 02_project_jira_to_glpi_project_tasks_migration  # OR
cd 03_support_jira_to_glpi_assistance_tickets_migration

# Run the migration
python main.py  # (or migrate_support_tickets.py for folder 03, jira_to_glpi.py for folder 02)
```

## Configuration System

### Two-Level Configuration (New in v2.0)

**Common Config** (`common/config.yaml`) - Shared settings:
- GLPI credentials (URL, tokens, username, password)
- Jira credentials (URL, PAT)
- Migration defaults (batch_size, debug mode)
- Logging configuration

**Folder-Specific Config** - Project-specific settings:
- Project keys, JQL queries
- Custom field mappings
- Status/Type/Priority mappings

**Benefits:**
- ✅ Single source of truth for credentials
- ✅ Update credentials once, all migrations benefit
- ✅ Cleaner folder configs (only project-specific settings)

See [Configuration Documentation](.claude/CONFIGURATION_REFACTORING.md) for details.

## Common Library

All migrations use the shared `common/` library:

```python
from common.config.loader import load_config
from common.clients.glpi_client import GlpiClient
from common.clients.jira_client import JiraClient
from common.utils.state_manager import StateManager
```

**Documentation:** See [common/USER_GUIDE.md](common/USER_GUIDE.md)

**Benefits:**
- ✅ -83% code duplication eliminated
- ✅ Consistent patterns across all migrations
- ✅ Single source of truth for API clients
- ✅ Easier maintenance

## Features

- **Resumability:** All migrations save state and can resume from interruption
- **User Tracking:** Tracks missing users in `missing_users.txt`
- **Structured Logging:** Console + file output with configurable levels
- **Error Handling:** Automatic retries and graceful degradation
- **Configuration Inheritance:** Common + folder-specific configs

## Support

For questions or issues:
1. Check migration-specific USER_GUIDE.md files
2. Check [common/USER_GUIDE.md](common/USER_GUIDE.md) for library documentation
3. Review logs in `logs/` directory

---

**Version:** 2.0 (with shared library and configuration inheritance)
**Last Updated:** 2026-02-13
