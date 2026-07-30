---
baseline_commit: 6febcab
---
# Story 1.2: Home Dashboard Migration

**Epic:** 1 (ITSOPS inventory to GLPI Assets management migration)
**Status:** ready-for-dev

## Story Requirements

**User Story:**
As a user, I want to migrate the "Recent Activities" and "Inventory Statistic" features from the ITSOPS Home Dashboard to the GLPI Assets management system, so that I can see the overview of the system on GLPI.

**Acceptance Criteria:**
- Feature: Recent Activities from ITSOPS Home > Dashboard is successfully mapped and migrated to GLPI.
- Feature: Inventory Statistic from ITSOPS Home > Dashboard is successfully mapped and migrated to GLPI.
- Migration scripts should use the database connection established in story 1.1 to read the data.
- The GLPI target (either API or DB) is correctly populated with the dashboard stats and recent activities data.

## Developer Context

This story begins the actual data extraction and mapping phase for the ITSOPS to GLPI migration, specifically targeting the Home Dashboard modules.

### Technical Requirements
- Utilize `pyodbc` to query ITSOPS.
- Use `common/clients/sql_client.py` for database operations, continuing the pattern from 1-1.
- Write robust mapping logic to map ITSOPS data structure for Dashboard to GLPI's expected format.

### Architecture Compliance
- Use the two-level configuration structure from story 1.1 (`common/config.yaml` and `04_itsops_to_glpi_assests_migration/config.yaml`).
- Maintain modular structure for migration scripts.

### Library/Framework Requirements
- `pyodbc` for SQL Server connections.
- `requests` if using GLPI API.

### File Structure Requirements
- Update `04_itsops_to_glpi_assests_migration/main.py` or create a specific module (e.g., `04_itsops_to_glpi_assests_migration/dashboard.py`) for dashboard migration.
- Add tests in `04_itsops_to_glpi_assests_migration/tests/`.

### Testing Requirements
- Unit tests for the data extraction and mapping logic.
- Ensure integration with `SQLClient` doesn't break.

## Previous Story Intelligence
- Dev notes and learnings from story 1.1: We used Windows Auth fallback for SQLClient. Keep tests robust against explicit vs implicit auth credentials. `main.py` must handle config dictionary loading safely without NoneType errors.
- Test paths: Ensure `import` paths in tests are robust.

## Git Intelligence Summary
Recent work pattern (from commit `6febcab`): The system structure utilizes tests inside the specific module folder (`04_itsops_to_glpi_assests_migration/tests`).

## Project Context Reference
- [USER_GUIDE.md](file:///c:/Users/laub/source/repos/IT-agent/04_itsops_to_glpi_assests_migration/USER_GUIDE.md)

## Tasks/Subtasks
- [x] Map Recent Activities schema from ITSOPS to GLPI.
- [x] Map Inventory Statistic schema from ITSOPS to GLPI.
- [x] Implement data extraction logic for both features.
- [x] Implement data ingestion logic for GLPI.
- [x] Write unit tests for extraction and ingestion.

### Review Findings
- [x] [Review][Patch] Fix SQL injection and limit validation in dashboard extraction [dashboard.py:9,27]
- [x] [Review][Patch] Use fetchmany/yield to avoid loading massive tables into memory [dashboard.py:16,34]
- [x] [Review][Patch] Fix NULL handling to avoid inserting literal 'None' string [dashboard.py:41,55]
- [x] [Review][Patch] Fix exception handling in main.py to not abort loop on single failure [main.py:93]
- [x] [Review][Patch] Fix mapping deviation (remove "Criteria 1: " prefix) [dashboard.py:57]
- [x] [Review][Patch] Fix test_api.py to test Reminder endpoint instead of Log [test_api.py]
- [x] [Review][Patch] Add test assertion for state field in test_dashboard.py [tests/test_dashboard.py:43]
- [x] [Review][Patch] Fix Dev Agent Record in spec file (Log -> Reminder) [_bmad-output/implementation-artifacts/1-2-home-dashboard-migration.md:65]
- [x] [Review][Defer] Hardcoded schema names in SQL queries [dashboard.py:8,28] — deferred, pre-existing

## Dev Agent Record
**Completion Notes:**
Successfully implemented the Home Dashboard migration logic:
- Created `dashboard.py` to extract and map `ITEM_ACTION_LOGS` to GLPI `Reminder` and `KPI_Result` to GLPI `Stat`.
- Updated `main.py` to execute dashboard extraction and ingestion.
- Added unit tests in `tests/test_dashboard.py` to ensure logic correctness.

## File List
- `04_itsops_to_glpi_assests_migration/main.py`
- `04_itsops_to_glpi_assests_migration/dashboard.py` [NEW]
- `04_itsops_to_glpi_assests_migration/tests/test_dashboard.py` [NEW]

## Change Log
- Implemented extraction logic for Recent Activities and Inventory Statistics.
- Mapped schema structures from ITSOPS to GLPI.
- Added data ingestion workflows into `main.py`.
- Included passing unit tests.

## Status Update
Status: done
Completion Note: Implemented the dashboard migration. Code verified and tested. Review issues addressed.
