---
title: 'Add Status-Based Project Routing for Jira-to-GLPI Migration'
slug: 'status-based-project-routing'
created: '2026-04-01'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [Python, YAML]
files_to_modify: ['02_project_jira_to_glpi_project_tasks_migration/jira_to_glpi.py', '02_project_jira_to_glpi_project_tasks_migration/config.yaml', '02_project_jira_to_glpi_project_tasks_migration/config.yaml.example']
code_patterns: ['nested YAML config accessed via config.get(section, {}).get(key)', 'case-insensitive status comparison with .lower()', 'glpi_client shared lib provides get_project_id_by_name()']
test_patterns: ['no unit test framework — only test_execution_timing.py exists']
---

# Tech-Spec: Add Status-Based Project Routing for Jira-to-GLPI Migration

**Created:** 2026-04-01

## Overview

### Problem Statement

Currently all Jira tickets are migrated into a single GLPI project regardless of their status. There is no way to separate closed/archived tickets into a different project, making it harder to manage active vs completed work in GLPI.

### Solution

Add a configurable `routing_mode` with two options: `single` (current behavior — all tickets to one project) or `split_by_status` (route tickets to either the main project or an archived project based on their Jira status). The list of statuses considered "archived" is configurable.

### Scope

**In Scope:**
- New config fields: `routing_mode`, `archived_project_name`, `archived_statuses`
- Routing logic: case-insensitive status comparison against `archived_statuses` list to select target project
- Resolve both project IDs when mode = `split_by_status`
- Keep existing `percent_done` logic unchanged

**Out of Scope:**
- Auto-creating projects in GLPI (archived project must already exist)
- Changes to other migration logic (comments, attachments, mapping, etc.)

## Context for Development

### Codebase Patterns

- Config is nested YAML loaded via `load_config()` returning a dict. Values accessed with `config.get('section', {}).get('key', default)`.
- GLPI client is a shared lib at `common/clients/glpi_client.py` with `get_project_id_by_name(name)` already available.
- Jira status is already read and lowercased at line 556-557 of `jira_to_glpi.py`.
- Project ID is resolved once at startup (line 458-464) and passed to `create_project_task()` at line 661.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `02_.../jira_to_glpi.py` line 432 | Reads `glpi_project_name` from config |
| `02_.../jira_to_glpi.py` line 458-464 | Resolves project ID by name |
| `02_.../jira_to_glpi.py` line 556-557 | Reads Jira status (case-insensitive) |
| `02_.../jira_to_glpi.py` line 661 | Creates project task with `project_id` |
| `02_.../config.yaml` line 116-118 | Current `glpi.project_name` config |
| `common/clients/glpi_client.py` line 1081 | `get_project_id_by_name()` method |

### Technical Decisions

- `routing_mode: single` is the default to maintain backward compatibility
- Status comparison is case-insensitive (consistent with existing status mapping logic at line 557)
- Archived project is resolved at startup alongside the main project, not per-ticket
- Reuse existing `get_project_id_by_name()` from shared GLPI client

## Implementation Plan

### Tasks

- [x] Task 1: Add routing config fields to `config.yaml`
  - File: `02_project_jira_to_glpi_project_tasks_migration/config.yaml`
  - Action: Add the following under the `glpi:` section, after `project_name`:
    ```yaml
    # Routing mode: "single" (all tickets to one project) or "split_by_status" (route by ticket status)
    routing_mode: "split_by_status"

    # Archived project name in GLPI (required when routing_mode is "split_by_status")
    archived_project_name: "Archived"

    # Jira statuses that route tickets to the archived project (case-insensitive)
    archived_statuses:
      - closed
      - resolved
      - completed
    ```

- [x] Task 2: Update `config.yaml.example` with routing config documentation
  - File: `02_project_jira_to_glpi_project_tasks_migration/config.yaml.example`
  - Action: Add the same fields under `glpi:` section with example values and comments explaining the two modes:
    ```yaml
    # Routing mode: "single" (all tickets to one project) or "split_by_status" (route by ticket status)
    # Default: "single" (backward compatible)
    routing_mode: "single"

    # Archived project name in GLPI (required when routing_mode is "split_by_status")
    # archived_project_name: "My Archived Project"

    # Jira statuses that route tickets to the archived project (case-insensitive)
    # archived_statuses:
    #   - closed
    #   - resolved
    #   - completed
    ```

- [x] Task 3: Read new config values in `main()`
  - File: `02_project_jira_to_glpi_project_tasks_migration/jira_to_glpi.py`
  - Action: After line 432 (`glpi_project_name = ...`), add:
    ```python
    routing_mode = config.get('glpi', {}).get('routing_mode', 'single')
    archived_project_name = config.get('glpi', {}).get('archived_project_name', '')
    archived_statuses = [s.lower() for s in config.get('glpi', {}).get('archived_statuses', [])]
    ```

- [x] Task 4: Resolve archived project ID at startup
  - File: `02_project_jira_to_glpi_project_tasks_migration/jira_to_glpi.py`
  - Action: After the existing project ID resolution block (line 464, after `log(f"✓ Found Project ID: {project_id}\n")`), add:
    ```python
    # Resolve Archived Project ID (if split_by_status mode)
    archived_project_id = None
    if routing_mode == 'split_by_status':
        if not archived_project_name:
            log("[ERROR] routing_mode is 'split_by_status' but 'archived_project_name' is not configured!", "error")
            log_timing()
            return
        if not archived_statuses:
            log("[ERROR] routing_mode is 'split_by_status' but 'archived_statuses' list is empty!", "error")
            log_timing()
            return
        log(f"Resolving GLPI Archived Project '{archived_project_name}'...")
        archived_project_id = glpi.get_project_id_by_name(archived_project_name)
        if not archived_project_id:
            log(f"[ERROR] Archived Project '{archived_project_name}' not found!", "error")
            log_timing()
            return
        log(f"✓ Found Archived Project ID: {archived_project_id}")
        log(f"  Archived statuses: {archived_statuses}\n")
    ```

- [x] Task 5: Add routing logic per ticket in the migration loop
  - File: `02_project_jira_to_glpi_project_tasks_migration/jira_to_glpi.py`
  - Action: After the existing `jira_status_lower` assignment (line 557), before the status mapping block, add:
    ```python
    # Determine target project based on routing mode
    if routing_mode == 'split_by_status' and jira_status_lower in archived_statuses:
        target_project_id = archived_project_id
        log(f"    → Routing to Archived project (status: {jira_status})")
    else:
        target_project_id = project_id
    ```
  - Then at line 661, replace `project_id` with `target_project_id`:
    ```python
    task_id = glpi.create_project_task(target_project_id, task_name, content_html, **task_kwargs)
    ```

### Acceptance Criteria

- [ ] AC 1: Given `routing_mode: "single"` (or not set) in config, when migration runs, then all tickets are created in the single `project_name` project — identical to current behavior.
- [ ] AC 2: Given `routing_mode: "split_by_status"` with `archived_statuses: [closed, resolved, completed]`, when a ticket has Jira status "Closed", then it is created in the `archived_project_name` project.
- [ ] AC 3: Given `routing_mode: "split_by_status"` with `archived_statuses: [closed, resolved, completed]`, when a ticket has Jira status "In Progress", then it is created in the main `project_name` project.
- [ ] AC 4: Given `routing_mode: "split_by_status"` with `archived_statuses: [closed]`, when a ticket has Jira status "CLOSED" (uppercase), then it is routed to archived project (case-insensitive match).
- [ ] AC 5: Given `routing_mode: "split_by_status"` but `archived_project_name` is empty or not set, when migration starts, then it logs an error and exits before processing any tickets.
- [ ] AC 6: Given `routing_mode: "split_by_status"` but `archived_statuses` list is empty, when migration starts, then it logs an error and exits before processing any tickets.
- [ ] AC 7: Given `routing_mode: "split_by_status"` but the archived project name does not exist in GLPI, when migration starts, then it logs an error and exits before processing any tickets.

## Additional Context

### Dependencies

- No new external libraries required.
- `glpi.get_project_id_by_name()` already exists in shared client — no changes to `common/` needed.
- Archived GLPI project must be pre-created by the user before running migration.

### Testing Strategy

- **Manual testing (debug mode):** Run with `debug: true` in config to process a single batch. Verify:
  1. Mode `single`: all tasks go to main project (regression check).
  2. Mode `split_by_status`: closed tickets go to archived project, open tickets go to main project.
  3. Missing config validation: remove `archived_project_name` and confirm error message.
- **Log verification:** Check migration logs for routing messages (`→ Routing to Archived project`).

### Notes

- The `percent_done` logic (line 628) uses a hardcoded list `['resolved', 'closed', 'done']`. This is independent of `archived_statuses` and is intentionally left unchanged. Users may configure different archived statuses without affecting percent_done behavior.
- Parent-child linking (`projecttasks_id`) works across projects in GLPI, so sub-tasks routed to a different project than their parent will still link correctly.

## Review Notes

- Adversarial review completed
- Findings: 10 total, 6 fixed, 4 skipped (2 noise/undecided, 1 awareness-only, 1 pre-existing debt)
- Resolution approach: auto-fix
- Fixes applied: routing_mode validation, non-string archived_statuses safety, cross-project parent-child warning, routing summary counters, same-project-name warning
