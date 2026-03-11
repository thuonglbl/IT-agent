---
title: 'Add Execution Time Tracking to Jira-GLPI Migration'
slug: 'add-execution-time-tracking-02'
created: '2026-03-09'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [python3.13]
files_to_modify: ['02_project_jira_to_glpi_project_tasks_migration/jira_to_glpi.py']
code_patterns: ['log(msg, level) helper', 'try/except/finally structure', 'config-driven']
test_patterns: ['none - no tests exist for this script']
---

# Tech-Spec: Add Execution Time Tracking to Jira-GLPI Migration

**Created:** 2026-03-09

## Overview

### Problem Statement

The migration script `02_project_jira_to_glpi_project_tasks_migration/jira_to_glpi.py` has no visibility into how long it takes to run. There is no start time, end time, or duration logged anywhere.

### Solution

Record start time right after the `log` helper is defined in `main()`, then log start time, end time, and human-readable duration in the `finally` block so all exit paths (success, KeyboardInterrupt, exception) are covered in one place without duplication.

### Scope

**In Scope:**
- Record start time at script begin
- Log start time, end time, and human-readable duration
- Log timing at all exit points: success, interrupt, error

**Out of Scope:**
- Per-batch timing
- Per-issue timing
- Performance optimization

## Context for Development

### Codebase Patterns

- The script already imports `time` and `datetime` (line 7-8)
- Logging uses a `log(message, level)` helper defined at line 390 that wraps either a structured logger or `print()`
- The `main()` function has three exit paths: normal completion (line 735), `KeyboardInterrupt` (line 740), and generic `Exception` (line 743)
- The existing `try` block starts at line 417; `start_time` must be captured before this block so it's available in `finally`
- Timing output goes in `finally` block (line 747) — single location covers all 3 exit paths without duplication
- The `finally` block currently only calls `glpi.kill_session()` — timing code goes before that call
- No shared timing utilities exist in `common/`

### Files to Reference

| File | Purpose | Lines of Interest |
| ---- | ------- | ----------------- |
| `02_.../jira_to_glpi.py` | Main migration script | L396 (insert start capture), L747 (insert timing in finally) |

### Technical Decisions

- Use `datetime.datetime.now()` for human-readable start/end timestamps
- Use `time.monotonic()` for accurate duration calculation (not affected by system clock changes; `time` already imported)
- Smart duration format: skip leading zero units (e.g., `5m 12s` not `0h 5m 12s`), but keep inner zeros for clarity (e.g., `1h 0m 5s`)
- Use `"info"` log level for timing output, consistent with existing summary block
- Place timing in `finally` block to guarantee it runs on all exit paths

## Implementation Plan

### Tasks

- [x] Task 1: Capture start time after `log` helper definition
  - File: `02_project_jira_to_glpi_project_tasks_migration/jira_to_glpi.py`
  - Action: Insert after line 396 (`log(f"=== Jira to GLPI Project Tasks Migration ===\n")`):
    ```python
    start_time_wall = datetime.datetime.now()
    start_time_mono = time.monotonic()
    ```
  - Notes: Must be before the `try` block (line 417) so variables are in scope for `finally`

- [x] Task 2: Add `format_duration` helper function
  - File: `02_project_jira_to_glpi_project_tasks_migration/jira_to_glpi.py`
  - Action: Add a helper inside `main()`, after the start time capture:
    ```python
    def format_duration(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}h {m}m {s}s"
        elif m > 0:
            return f"{m}m {s}s"
        else:
            return f"{s}s"
    ```
  - Notes: Nested inside `main()` like the existing `log` helper. Smart format skips leading zero units.

- [x] Task 3: Add timing output in `finally` block
  - File: `02_project_jira_to_glpi_project_tasks_migration/jira_to_glpi.py`
  - Action: Insert timing log **before** `glpi.kill_session()` in the `finally` block (line 747):
    ```python
    finally:
        end_time_wall = datetime.datetime.now()
        elapsed = time.monotonic() - start_time_mono
        log(f"\nStart time:  {start_time_wall.strftime('%Y-%m-%d %H:%M:%S')}")
        log(f"End time:    {end_time_wall.strftime('%Y-%m-%d %H:%M:%S')}")
        log(f"Duration:    {format_duration(elapsed)}")
        glpi.kill_session()
    ```
  - Notes: Timing logs run before session cleanup. Uses `time.monotonic()` delta for accurate duration, `datetime.now()` for human-readable wall clock.

### Acceptance Criteria

- [ ] AC 1: Given a successful migration run, when the script completes normally, then start time, end time, and duration are logged at info level
- [ ] AC 2: Given a user pressing Ctrl+C during migration, when KeyboardInterrupt is raised, then start time, end time, and duration are still logged before the script exits
- [ ] AC 3: Given an unexpected error during migration, when an Exception is raised, then start time, end time, and duration are still logged before the error propagates
- [ ] AC 4: Given a migration that runs for less than 1 minute, when duration is displayed, then format shows only seconds (e.g., `45s`)
- [ ] AC 5: Given a migration that runs for less than 1 hour, when duration is displayed, then format shows minutes and seconds (e.g., `5m 12s`)
- [ ] AC 6: Given a migration that runs for over 1 hour, when duration is displayed, then format shows hours, minutes, and seconds (e.g., `1h 0m 5s`)

## Additional Context

### Dependencies

None. Uses only `time` and `datetime` which are already imported.

### Testing Strategy

- Manual testing: Run the migration script in debug mode (processes 1 batch) and verify timing output appears in the log
- Manual testing: Interrupt with Ctrl+C mid-run and verify timing still appears
- No automated tests needed for this change (no existing test infrastructure for this script)

### Notes

- The existing `finally` block has a latent issue: if `glpi` init fails before line 428, `glpi.kill_session()` will raise `NameError`. This is a pre-existing issue, not in scope for this change.
- Future consideration: if per-batch timing is later needed, the `format_duration` helper can be reused.

## Review Notes
- Adversarial review completed
- Findings: 10 total, 1 fixed, 9 skipped
- Resolution approach: auto-fix
- F1 (Medium, Real): Fixed — extracted `log_timing()` helper, added calls at early-return paths (connection failure, project not found) so timing is logged on ALL exit paths
