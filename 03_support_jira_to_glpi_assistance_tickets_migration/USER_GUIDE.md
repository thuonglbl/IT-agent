# User Guide: Jira Support to GLPI Assistance Tickets

## Overview
This tool migrates support tickets from a Jira Project to GLPI Assistance Tickets.

## Features
- Creates GLPI Tickets from Jira Issues.
- Maps Reporter and Assignee to GLPI Users.
- Migrates Comments and History as Followups.
- Preserves Dates (Creation, Update).
- Maps Statuses (Open, Done, etc. -> New, Solved, etc.).

## Prerequisites
1.  **Config**: Update `config.py` in this directory.
    - Set `JIRA_PROJECT_KEY`.
    - Set `GLPI_APP_TOKEN` and `GLPI_USER_TOKEN`.
2.  **Dependencies**: Install typical python requests.

## How to Run
```bash
python migrate_support_tickets.py
```
