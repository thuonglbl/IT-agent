---
title: 'Migrate GLPI user lookup to use email field'
slug: 'migrate-glpi-user-lookup-to-email'
created: '2026-03-18T11:45:59+07:00'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python', 'Requests', 'YAML']
files_to_modify: ['common/clients/glpi_client.py', 'common/check_missing_users.py', '01_confluence_to_glpi_migration/test_curl.py', '02_project_jira_to_glpi_project_tasks_migration/jira_to_glpi.py', '03_support_jira_to_glpi_assistance_tickets_migration/lib/comment_migrator.py', '03_support_jira_to_glpi_assistance_tickets_migration/lib/field_extractor.py', '03_support_jira_to_glpi_assistance_tickets_migration/lib/html_builder.py', 'common/tests/test_check_missing_users.py', 'common/tests/test_user_linking.py', '01_confluence_to_glpi_migration/main.py']
code_patterns: ['GLPI API Field 5 for Email', 'User and Fullname dictionary caching', 'Jira API user emailAddress extraction', 'Basic Auth and Token Auth fallback handling']
test_patterns: ['pytest with mock', 'requests_mock']
---

# Tech-Spec: Migrate GLPI user lookup to use email field

**Created:** 2026-03-18T11:45:59+07:00

## Overview

### Problem Statement

Current GLPI user mapping uses the `login` field (field 1) which is a username in the Dev environment but an email address in the Pre-Prod environment. This causes Jira-to-GLPI user mapping in scripts to fail in Pre-Prod since the provided Jira login names do not match the Pre-Prod GLPI login format. 

### Solution

Update the GLPI API client and mapping logic across all migration scripts to search and map users using the `email` field (field 5) instead of the `login` field. The email field is consistently formatted as an email address across both environments.

### Scope

**In Scope:**
- Update `GlpiClient.load_user_cache` in `common/clients/glpi_client.py` to fetch field 5 (email).
- Modify caching logic to map by email instead of login.
- Update `get_user_id_by_name` (potentially renaming it to `get_user_id_by_email`).
- Verify and update `01_confluence_to_glpi_migration/test_curl.py` references.
- Update all Jira migration scripts (`check_missing_users.py`, `jira_to_glpi.py`, `field_extractor.py`, `html_builder.py`, etc.) to pass the email address for lookup.
- If Jira payloads currently provide usernames, update Jira extraction logic to use `emailAddress`.

**Out of Scope:**
- Modifying GLPI environment configurations directly.
- Migrating other non-user fields.

## Context for Development

### Codebase Patterns

User lookups in GLPI are heavily cached (`self.user_cache` and `self.fullname_cache`) in `GlpiClient.load_user_cache`. We must update this cache loading to query for `forcedisplay[1]: "5"` (email) instead of `1` (login), and store the lowercase email as the dictionary key mapping to the GLPI user ID.
When retrieving from the cache, we should pass the lowercase email address.
The Jira API responses contain users with `name`, `displayName`, and `emailAddress`. The mapping scripts currently extract `name` (login name). This logic needs to be updated to try extracting `emailAddress` first, and if not present, fallback to `name`.
The test scripts use `unittest.mock` to mock `glpi_client.get_user_id_by_name`. These mocks will need to be updated.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `common/clients/glpi_client.py` | Contains the GLPI user cache and lookup logic. |
| `01_confluence_to_glpi_migration/test_curl.py` | Standalone script testing the user lookup. |
| `02_project_jira_to_glpi_project_tasks_migration/jira_to_glpi.py` | Extracts reporters, assignees, and comment authors. |
| `03_support_jira_to_glpi_assistance_tickets_migration/lib/field_extractor.py` | Extracts actors for assistance tickets. |
| `03_support_jira_to_glpi_assistance_tickets_migration/lib/html_builder.py` | Inlines reporters and authors into description. |
| `03_support_jira_to_glpi_assistance_tickets_migration/lib/comment_migrator.py` | Extracts comment authors. |
| `common/check_missing_users.py` | Audit script comparing Jira users to GLPI users. |
| `common/tests/*.py` | Test cases mocking the GLPI `get_user_id_by_name` capability. |

### Technical Decisions

- **Rename Method:** We will systematically rename `get_user_id_by_name` to `get_user_id_by_email` across the codebase to reflect the new expected input parameter and enforce correctness.
- **Cache Key:** The `self.user_cache` dict in `glpi_client.py` will use the lowercase email as the key.
- **Jira Fallback Extraction:** In the Jira extraction logic (e.g. `assignee_data.get('emailAddress') or assignee_data.get('name')`), we will prioritize the email address. If an email address is not exposed by the Jira API response, we will fallback to the name, as some system users may only have a name.

## Implementation Plan

### Tasks

- [ ] Task 1: Update GLPI Client method names
  - File: `common/clients/glpi_client.py`
  - Action: Rename `get_user_id_by_name` to `get_user_id_by_email` throughout the class.
- [ ] Task 2: Update GLPI caching logic to use email field
  - File: `common/clients/glpi_client.py`
  - Action: In `load_user_cache`, change `forcedisplay[0]: "1"` (login) to `forcedisplay[0]: "5"` (email), and index `self.user_cache` using lowercase email.
- [ ] Task 3: Migrate standalone test script (`test_curl.py`)
  - File: `01_confluence_to_glpi_migration/test_curl.py`
  - Action: Ensure `get_user_by_email` continues to use `criteria[0][field]: '5'` and `criteria[0][value]: email`. Verify `forcedisplay[1]` is `'5'`.
- [ ] Task 4: Extract emailAddress in Jira migration script
  - File: `02_project_jira_to_glpi_project_tasks_migration/jira_to_glpi.py`
  - Action: Change `assignee_name`, `reporter_name`, `author_login` to extract `emailAddress` mapping instead of `name`. Fallback to `name` if `emailAddress` missing. Pass to `glpi.get_user_id_by_email`.
- [ ] Task 5: Extract emailAddress in Assistance Support field extractor
  - File: `03_support_jira_to_glpi_assistance_tickets_migration/lib/field_extractor.py`
  - Action: For `reporter`, `assignee`, and `participants`, attempt to extract `.get('emailAddress')` first, fallback to `.get('name')`, pass to `get_user_id_by_email`.
- [ ] Task 6: Extract emailAddress in HTML Builder descriptions
  - File: `03_support_jira_to_glpi_assistance_tickets_migration/lib/html_builder.py`
  - Action: When generating user profile hyperlinks and lookups, extract `emailAddress` from author/reporter keys.
- [ ] Task 7: Extract emailAddress in Comment Migrator
  - File: `03_support_jira_to_glpi_assistance_tickets_migration/lib/comment_migrator.py`
  - Action: Use `emailAddress` falling back to `name` to get author ID.
- [ ] Task 8: Update check_missing_users.py tool
  - File: `common/check_missing_users.py`
  - Action: Update logic tracking missing mappings to prioritize extracting `emailAddress` from `jira.get_user(login)` when available, and pass to `glpi.get_user_id_by_email`.
- [ ] Task 9: Update Test Cases
  - File: `common/tests/test_check_missing_users.py` and `common/tests/test_user_linking.py`
  - Action: Rename `mock_glpi.get_user_id_by_name` to `mock_glpi.get_user_id_by_email` and adjust expected inputs in assertions to look like emails.

### Acceptance Criteria

- [ ] AC 1: Given `load_user_cache` is called, when the GLPI API returns users, then they are indexed in `self.user_cache` by lowercase email instead of login.
- [ ] AC 2: Given a Jira payload with an `emailAddress`, when extracting user actor fields, then the mapping scripts use the `emailAddress` to query the GLPI client cache.
- [ ] AC 3: Given a Jira payload without an `emailAddress`, when extracting user actor fields, then it gracefully falls back to using the `name` field to query the GLPI client cache.
- [ ] AC 4: Given the `test_curl.py` executes against Pre-Prod, when calling `get_user_by_email(session_token, email)`, then it returns the user ID successfully for recognized emails without using the `login` field mapping.

## Additional Context

### Dependencies
- The GLPI user mapping must match across all environments (Dev, Test, Pre-Prod, Prod) that use emails as primary credentials.

### Testing Strategy
- The automated unit tests located in `common/tests/` should pass locally.
- Run `01_confluence_to_glpi_migration/test_curl.py` to assert integration with actual Pre-Prod GLPI credentials works properly mapping by email.

### Notes
- Ensure fallback to `name` continues to function since old/inactive users inside Jira might lack populated `emailAddress` attributes.
