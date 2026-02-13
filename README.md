# IT Agent System

## Project Objective
1. Migrate data from Atlassian to GLPI
**Reason:** GLPI has a free community version on premise - no more license costs for Atlassian Confluence and Jira, but no built-in migration tool.
2. The final goal is to create an intelligent agent system that automatically triggers when an IT ticket is created or updated in GLPI.

The agent performs the following actions:
1.  **Analyze**: Reads the content of the GLPI ticket.
2.  **Retrieve**: Searches for relevant knowledge stored in the GLPI Knowledge Base.
3.  **Respond (Automated/AI)**:
    *   If relevant information is found with **high confidence**, the agent posts a comment on the GLPI ticket to answer the user directly.
4.  **Escalate (Human-in-the-loop)**:
    *   If no relevant information is found, OR
    *   If the confidence score is low, OR
    *   If the user remains unsatisfied after 3 automated attempts:
    *   The system assigns the ticket to a human IT agent, providing AI-generated suggestions to assist them.

![Workflow Diagram](common/images/workflow_diagram.png)

## Project Structure

```
IT-agent/
├── common/                    # Shared library (imported by all migrations)
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

4.  **RAG & Agent Orchestration**
    *   Implement Retrieval-Augmented Generation (RAG).
    *   Build agent orchestration connected to an AI server running **Ollama** via API.
    *   *Status: Not Started*

5.  **Improvements & Features**
    *   **Auto-Update Index**: Automatically update the index when the Knowledge Base changes.
    *   **Agent Management UI**: Create a user interface to manage agents.
    *   **Human Feedback**: Enable feedback loops (RLHF) to improve agent performance.
    *   *Status: Not Started*

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

### 2. Run Migration

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

**Why using configuration inheritance?**

It allows managing credentials in one place (`common/config.yaml`) while keeping project-specific settings (like JQL queries and custom fields) separated in their respective folders. This makes it easier to maintain multiple migration projects without duplicating sensitive information.

## Common Library

All migrations use the shared `common/` library:

```python
from common.config.loader import load_config
from common.clients.glpi_client import GlpiClient
from common.clients.jira_client import JiraClient
from common.utils.state_manager import StateManager
```

**Documentation:** See [common/README.md](common/README.md)

By sharing the `common/` library, we significantly reduced code duplication and ensured consistent behavior across all migration scripts. The unified API clients also make it easier to handle rate limiting and session management centrally.

## Features

- **Resumability:** All migrations save state and can resume from interruption
- **User Tracking:** Tracks missing users in `missing_users.txt`
- **Structured Logging:** Console + file output with configurable levels
- **Error Handling:** Automatic retries and graceful degradation
- **Configuration Inheritance:** Common + folder-specific configs

## Support

For questions or issues:
1. Check migration-specific USER_GUIDE.md files
2. Check [common/README.md](common/README.md) for library documentation
3. Review logs in `logs/` directory

---

**Version:** 2.0 (with shared library and configuration inheritance)
**Last Updated:** 2026-02-13
**Contact:** thuong.lambale@gmail.com