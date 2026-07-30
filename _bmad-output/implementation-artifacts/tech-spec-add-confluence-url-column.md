---
title: 'Add Confluence URL Column to Contributor Report'
slug: 'add-confluence-url-column'
created: '2026-03-30'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [python, csv, BeautifulSoup, argparse]
files_to_modify: [01_confluence_to_glpi_migration/confluence_contributors.py]
code_patterns: ['scan_pages returns list of page dicts', 'print_report uses fixed-width columns', 'export_csv uses csv.DictWriter with fieldnames list', 'main loads config via load_config(validate=False)']
test_patterns: ['no existing tests for confluence_contributors.py']
---

# Tech-Spec: Add Confluence URL Column to Contributor Report

**Created:** 2026-03-30

## Overview

### Problem Statement

The CSV and console report in `confluence_contributors.py` lack a direct URL column pointing to the original Confluence page. Users reading the report must manually construct URLs to navigate to the source page.

### Solution

Reuse the existing `build_confluence_url` function from `main.py`, load `base_url` from config, and add a `confluence_url` column between `page_title` and `breadcrumbs` in both the console report and CSV export.

### Scope

**In Scope:**

- Add `confluence_url` column to CSV export (between `page_title` and `breadcrumbs`)
- Add `confluence_url` column to console report (between `Page Title` and `Breadcrumbs`)
- Load `confluence.base_url` from config in contributor report script
- Reuse `build_confluence_url` from `main.py`

**Out of Scope:**

- No changes to migration logic in `main.py`
- No changes to `build_confluence_url` function itself
- No changes to config schema

## Context for Development

### Codebase Patterns

- `build_confluence_url(file_path, export_dir, base_url)` in `main.py:10` returns `(page_id, url)`
- Config is loaded via `load_config(validate=False)` — already used in `confluence_contributors.py:205`
- `confluence.base_url` is defined in `01_confluence_to_glpi_migration/config.yaml:12`
- `scan_pages(export_dir)` iterates `os.walk(export_dir)` and has access to `file_path` per page
- `print_report(groups, total_pages, stale_months)` uses fixed-width format strings for column alignment
- `export_csv(pages, output_path)` uses `csv.DictWriter` with explicit `fieldnames` list
- `main()` already loads config and extracts `export_dir` — `base_url` extraction follows same pattern

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `01_confluence_to_glpi_migration/confluence_contributors.py` | Target file — all changes here |
| `01_confluence_to_glpi_migration/confluence_contributors.py:67-104` | `scan_pages()` — add `base_url` param, build URL per page |
| `01_confluence_to_glpi_migration/confluence_contributors.py:127-168` | `print_report()` — add URL column to console output |
| `01_confluence_to_glpi_migration/confluence_contributors.py:171-190` | `export_csv()` — add URL field to CSV fieldnames + rows |
| `01_confluence_to_glpi_migration/confluence_contributors.py:193-231` | `main()` — extract `base_url` from config, pass to `scan_pages()` |
| `01_confluence_to_glpi_migration/main.py:10-51` | Source of `build_confluence_url` function to import |
| `01_confluence_to_glpi_migration/config.yaml:12` | Contains `confluence.base_url` |

### Technical Decisions

- Import `build_confluence_url` from `main` module rather than duplicating the logic
- Add `base_url` parameter to `scan_pages()` signature; build URL inside the loop using existing `file_path` and `export_dir`
- Store `confluence_url` (string or empty string) in each page dict
- Full URL displayed in console — no truncation per user preference
- No existing tests to update

## Implementation Plan

### Tasks

- [x] Task 1: Import `build_confluence_url` at top of file
  - File: `01_confluence_to_glpi_migration/confluence_contributors.py`
  - Action: Add `from main import build_confluence_url` after the existing `from parser import ConfluenceParser` import (line 25)
  - Notes: Function is already defined in `main.py:10`; no circular import risk since `main.py` does not import `confluence_contributors`

- [x] Task 2: Add `base_url` parameter to `scan_pages()` and build URL per page
  - File: `01_confluence_to_glpi_migration/confluence_contributors.py`
  - Action:
    1. Change signature from `scan_pages(export_dir)` to `scan_pages(export_dir, base_url='')`
    2. Inside the loop, after extracting metadata (line 91), call: `_, confluence_url = build_confluence_url(file_path, export_dir, base_url)`
    3. Add `'confluence_url': confluence_url or ''` to the page dict (between `'title'` and `'breadcrumbs'` keys, around line 94)
  - Notes: `build_confluence_url` returns `(page_id, url)` — we only need the URL. `page_id` is already captured separately via `extract_page_id`

- [x] Task 3: Add `confluence_url` column to `print_report()` console output
  - File: `01_confluence_to_glpi_migration/confluence_contributors.py`
  - Action:
    1. Update header format string (line 141) to add `{'Confluence URL'}` column between `Page Title` and `Breadcrumbs`
    2. Update separator line (line 142) to include matching dash segment
    3. Update row format string (line 150) to include `page['confluence_url']` between title and breadcrumbs
  - Notes: Full URL display — no truncation. Column will be variable width

- [x] Task 4: Add `confluence_url` field to `export_csv()` CSV output
  - File: `01_confluence_to_glpi_migration/confluence_contributors.py`
  - Action:
    1. Insert `'confluence_url'` into `fieldnames` list (line 173) between `'page_title'` and `'breadcrumbs'`
    2. Add `'confluence_url': page['confluence_url']` to the `writer.writerow()` dict (line 180) between `'page_title'` and `'breadcrumbs'`
  - Notes: CSV handles variable-length URLs naturally

- [x] Task 5: Extract `base_url` from config in `main()` and pass to `scan_pages()`
  - File: `01_confluence_to_glpi_migration/confluence_contributors.py`
  - Action:
    1. After extracting `export_dir` from config (around line 206), add: `confluence_base_url = config.get('confluence', {}).get('base_url', '')`
    2. Update `scan_pages(export_dir)` call (line 220) to `scan_pages(export_dir, confluence_base_url)`
  - Notes: Follows the same pattern as `main.py:98` for extracting `base_url`

### Acceptance Criteria

- [ ] AC 1: Given a Confluence export with `base_url` configured, when running `confluence_contributors.py`, then the console report displays a `Confluence URL` column between `Page Title` and `Breadcrumbs` with full URLs for each page
- [ ] AC 2: Given a Confluence export with `base_url` configured, when running `confluence_contributors.py`, then the CSV output contains a `confluence_url` column between `page_title` and `breadcrumbs` with full URLs for each page
- [ ] AC 3: Given a Confluence export with `base_url` left empty in config, when running `confluence_contributors.py`, then both console and CSV show an empty `confluence_url` column (no errors)
- [ ] AC 4: Given a Confluence export file without a valid page ID in the filename, when running `confluence_contributors.py`, then the `confluence_url` column is empty for that row (no errors)

## Additional Context

### Dependencies

- `build_confluence_url` function in `main.py` — must remain stable (no signature changes)
- `confluence.base_url` in `config.yaml` — already exists, no config changes needed

### Testing Strategy

- Manual testing: Run `confluence_contributors.py` against existing Confluence export and verify:
  1. Console output shows URL column in correct position
  2. CSV file contains `confluence_url` column in correct position
  3. URLs are correctly formed (match pattern `{base_url}/spaces/{SPACE_KEY}/pages/{PAGE_ID}/{SLUG}`)
  4. Empty `base_url` produces empty URL column without errors

### Notes

- Console column width is dynamic (calculated per editor group based on longest URL) for proper alignment
- The `confluence_id` column already exists in CSV — the new `confluence_url` column provides a clickable link using the same page ID

## Review Notes

- Adversarial review completed
- Findings: 7 total, 3 fixed, 1 out-of-scope, 3 skipped (noise/cosmetic)
- Resolution approach: auto-fix
- F1 (fixed): Config now always loaded; base_url available regardless of --export-dir usage
- F2 (fixed): Console URL column uses dynamic width based on longest URL per group
- F3 (out-of-scope): Regex mismatch between extract_page_id and build_confluence_url is pre-existing
- F4 (fixed): Added --base-url CLI argument for consistency
