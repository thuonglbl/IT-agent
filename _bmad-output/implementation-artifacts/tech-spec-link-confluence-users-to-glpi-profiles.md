---
title: 'Link Confluence users to GLPI user profiles'
slug: 'link-confluence-users-to-glpi-profiles'
created: '2026-03-05'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: [python, beautifulsoup4, glpi-rest-api, unicodedata]
files_to_modify: [01_confluence_to_glpi_migration/main.py, 01_confluence_to_glpi_migration/parser.py, common/clients/glpi_client.py]
code_patterns: [glpi_client.load_user_cache, glpi_client.get_user_id_by_name, glpi_client.fullname_cache]
test_patterns: [pytest, common/tests/]
---

# Tech-Spec: Link Confluence users to GLPI user profiles

**Created:** 2026-03-05

## Overview

### Problem Statement

KB articles migrated from Confluence to GLPI have user references (author, editor, @mentions) rendered as plain text. There is no link to the corresponding GLPI user profile, making it hard to identify who authored or modified content.

### Solution

Resolve Confluence user references to GLPI user IDs and convert them to clickable HTML links pointing to GLPI user profile pages (`/front/user.form.php?id=X`).

- **@mentions** (`confluence-userlink` with `data-username`): Resolve via login name using existing `glpi_client.get_user_id_by_name()`.
- **Author/editor** (`<span class='author/editor'>`): Resolve via display name using a new fullname cache on `GlpiClient`.

### Scope

**In Scope:**
- Convert `confluence-userlink` @mentions in content body to GLPI profile links (using `data-username` login)
- Convert author/editor spans in page metadata to GLPI profile links (using display name reverse lookup)
- Extend `GlpiClient.load_user_cache()` to also fetch firstname/realname and build a fullname cache
- Track unresolved users (display names not found in GLPI)
- Unit tests for cache builder and resolver methods

**Out of Scope:**
- Creating missing users in GLPI
- Linking users in attachment filenames that happen to contain email addresses

## Context for Development

### Codebase Patterns

- `GlpiClient.load_user_cache()` fetches GLPI users via `GET /search/User` with `forcedisplay` fields. Currently fetches field 1 (login) and 2 (id). Fields 9 (realname/lastname) and 34 (firstname) are also available on the same endpoint.
- `GlpiClient.get_user_id_by_name(username)` does O(1) lookup by login name (lowercase).
- `ConfluenceParser.parse()` extracts metadata at line 130-135: finds `<div class="page-metadata">`, converts to plain text via `get_text(separator=' ', strip=True)`, and stores as `self.metadata_html`. **This destroys the `<span class='author'>` and `<span class='editor'>` elements.** The resolve method must extract structured spans from `self.soup` BEFORE this flattening occurs.
- `confluence_contributors.extract_metadata()` is a standalone function (NOT a class method) that opens its own file and soup — it demonstrates the span extraction pattern but cannot be directly reused inside the parser.
- Confluence HTML @mentions use: `<a class="confluence-userlink" data-username="login">Display Name</a>`. Note: `data-username` may be absent on some tags (malformed export, deleted users).
- Confluence metadata format: `Created by <span class='author'> Display Name</span>, last updated by <span class='editor'> Display Name</span> on Date`
- Display names follow pattern: `Firstname LASTNAME` (e.g. `Jean DUPONT`, `Maria SANTOS`)

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `common/clients/glpi_client.py` | GLPI client — extend `load_user_cache()` to also fetch fields 9, 34 and build `fullname_cache` |
| `01_confluence_to_glpi_migration/parser.py` | HTML parser — needs new methods + restructured `parse()` to preserve metadata spans |
| `01_confluence_to_glpi_migration/main.py` | Migration orchestrator — integrate user linking calls |
| `01_confluence_to_glpi_migration/confluence_contributors.py` | Reference only — demonstrates span extraction pattern |

### Technical Decisions

- **Fullname cache**: Extend `GlpiClient.load_user_cache()` to also fetch fields 9 (realname) and 34 (firstname) in the same API call. Build `self.fullname_cache` as `{normalize(f"{firstname} {realname}"): user_id}`. Add `get_user_id_by_fullname(display_name)` method. This keeps all user lookup logic in the client where it belongs.
- **Name normalization**: Use `unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii').lower().strip()` to handle accented characters (e.g. `é` → `e`, `ñ` → `n`). Collapse multiple whitespace to single space. Apply to both GLPI fullnames and Confluence display names.
- **GLPI profile link format**: `/front/user.form.php?id={user_id}`
- **Metadata preservation**: Restructure `parse()` to extract structured author/editor data from `self.soup` BEFORE flattening metadata to text. Store as `self.author_name` and `self.editor_name`. Build `metadata_html` with link placeholders that resolve methods can fill.
- **Unresolved users**: Keep original text (no link), log warning.

## Implementation Plan

### Tasks

- [x] Task 1: Extend `GlpiClient` with fullname cache and normalization
  - File: `common/clients/glpi_client.py`
  - Action: (1) Add `import unicodedata` at top. (2) Add module-level helper `_normalize_name(name)` that applies NFKD unicode normalization, strips accents, lowercases, collapses whitespace. (3) In `load_user_cache()`, add `forcedisplay[2]: "9"` (realname) and `forcedisplay[3]: "34"` (firstname) to params. (4) In the data loop, also extract fields 9 and 34, construct `fullname = f"{firstname} {realname}"`, store in `self.fullname_cache[_normalize_name(fullname)] = user_id` (skip if both fields empty). (5) Add `self.fullname_cache = {}` in `__init__`. (6) Add method `get_user_id_by_fullname(display_name)` that normalizes input and looks up in `self.fullname_cache`.
  - Notes: Single API call, no duplication. Existing `user_cache` (login→id) is unchanged.

- [x] Task 2: Restructure `ConfluenceParser.parse()` to preserve author/editor data
  - File: `01_confluence_to_glpi_migration/parser.py`
  - Action: In `parse()`, BEFORE the metadata flattening block (current lines 130-135): (1) Find `<span class='author'>` and `<span class='editor'>` in the metadata div using `self.soup`. (2) Store as `self.author_name = author_span.get_text(strip=True) if author_span else None`. Same for `self.editor_name`. (3) Initialize both as `None` in `__init__`.
  - Notes: The existing `metadata_html` flattening stays as-is for now. The new attributes give resolve methods access to structured names.

- [x] Task 3: Add `resolve_user_mentions(login_cache)` method to `ConfluenceParser`
  - File: `01_confluence_to_glpi_migration/parser.py`
  - Action: Add method that finds all `<a class="confluence-userlink">` tags in `self.content_div`. For each: (1) Extract `data-username` — if absent, skip tag. (2) Look up in `login_cache`. (3) If found → set `href="/front/user.form.php?id={user_id}"`. (4) If not found → remove `href` attribute, keep as plain text. Return list of unresolved usernames.
  - Notes: Must be called AFTER `parse()` and BEFORE `get_content_html()`. Guard: if `self.content_div is None`, return empty list.

- [x] Task 4: Add `resolve_metadata_users(fullname_cache_lookup)` method to `ConfluenceParser`
  - File: `01_confluence_to_glpi_migration/parser.py`
  - Action: Add method that: (1) Guard: if `self.soup is None`, return empty list. (2) Find the metadata div from `self.soup` (same `<div class="page-metadata">`). (3) Find `<span class='author'>` and `<span class='editor'>` in it. (4) For each span with a name: call `fullname_cache_lookup(name)` to get user_id. If found → replace span innerHTML with `<a href="/front/user.form.php?id={user_id}">{name}</a>`. (5) Rebuild `self.metadata_html` from the modified metadata div: wrap in styled `<p>` tag matching current format (`color: #666; font-style: italic; font-size: 0.9em`). (6) Return list of unresolved display names.
  - Notes: Operates on `self.soup` (original HTML), not the flattened text. Must be called AFTER `parse()` (which populates `self.soup`) and BEFORE `metadata_html` is consumed by `main.py`. The `fullname_cache_lookup` parameter is `glpi.get_user_id_by_fullname` — a callable, keeping parser decoupled from GlpiClient.

- [x] Task 5: Integrate user linking into migration orchestrator
  - File: `01_confluence_to_glpi_migration/main.py`
  - Action: (1) After `glpi.init_session()`, add `glpi.load_user_cache(recursive=True)` and `log(f"Loaded {len(glpi.user_cache)} users, {len(glpi.fullname_cache)} fullnames")`. (2) Inside the file processing loop, after `parser.parse()` and before `parser.get_content_html()`: call `unresolved_mentions = parser.resolve_user_mentions(glpi.user_cache)` then `unresolved_metadata = parser.resolve_metadata_users(glpi.get_user_id_by_fullname)`. (3) Log unresolved users: `for u in unresolved_mentions: log(f"  - Unresolved @mention: {u}", "warning")`. Same for unresolved_metadata.
  - Notes: No `import requests` needed in `main.py`. All API logic stays in GlpiClient.

- [x] Task 6: Add unit tests for fullname cache and resolver methods
  - File: `common/tests/test_user_linking.py` (new file)
  - Action: Add pytest tests:
    - `test_normalize_name_basic`: `"Jean DUPONT"` → `"jean dupont"`
    - `test_normalize_name_accents`: `"José García"` → `"jose garcia"`
    - `test_normalize_name_extra_whitespace`: `"  First   LAST  "` → `"first last"`
    - `test_fullname_cache_skips_empty`: Users with empty firstname or realname are not in fullname_cache
    - `test_resolve_mentions_found`: Mock content with `confluence-userlink` + `data-username="user1"`, verify href set correctly
    - `test_resolve_mentions_not_found`: Unknown username → href removed, returned in unresolved list
    - `test_resolve_mentions_missing_data_username`: Tag without `data-username` → skipped, no error
    - `test_resolve_metadata_author_found`: Author span → linked
    - `test_resolve_metadata_not_found`: Unknown author → plain text, returned in unresolved list
    - `test_resolve_metadata_no_metadata_div`: Page without metadata div → returns empty list gracefully

### Acceptance Criteria

- [ ] AC 1: Given a Confluence page with `<a class="confluence-userlink" data-username="user1">Firstname LASTNAME</a>` in the content, when the page is migrated, then the link href is replaced with `/front/user.form.php?id={user1_user_id}` in the GLPI KB article content.
- [ ] AC 2: Given a Confluence page with `<span class='author'> Jean DUPONT</span>` in the metadata, when the page is migrated, then the metadata HTML contains `<a href="/front/user.form.php?id={user_id}">Jean DUPONT</a>`.
- [ ] AC 3: Given a Confluence page with `<span class='editor'> Maria SANTOS</span>` in the metadata, when the page is migrated, then the editor name is linked to the GLPI profile.
- [ ] AC 4: Given a Confluence @mention with `data-username="xyz"` where "xyz" does NOT exist in GLPI user cache, when the page is migrated, then the mention is rendered as plain text (no broken link) and a warning is logged.
- [ ] AC 5: Given a Confluence page with an author display name that does NOT match any GLPI user fullname, when the page is migrated, then the author is rendered as plain text (no link) and a warning is logged.
- [ ] AC 6: Given GLPI users loaded via `load_user_cache()`, when `fullname_cache` is built, then it contains an entry for every user that has both a non-empty firstname and non-empty realname, with normalized fullname as key.
- [ ] AC 7: Given a `confluence-userlink` tag WITHOUT `data-username` attribute, when the page is migrated, then the tag is skipped gracefully (no error, no broken link).
- [ ] AC 8: Given a GLPI user with accented name (e.g. `José García`), when matched against Confluence display name `Jose Garcia`, then the match succeeds via unicode normalization.
- [ ] AC 9: All unit tests in `test_user_linking.py` pass.

## Additional Context

### Dependencies

- `unicodedata` (Python stdlib — no new install needed)
- `beautifulsoup4` (already used by parser)
- GLPI API fields 9 (realname) and 34 (firstname) available on User search endpoint
- GLPI session must be initialized before loading caches

### Testing Strategy

- **Unit tests** (`common/tests/test_user_linking.py`): Cover normalization, cache building, mention resolution, metadata resolution, edge cases (missing attributes, empty names, accents).
- **Manual testing**: Run migration with a single file (uncomment debug block at `main.py:169-171`). Target a page with known @mentions and known author/editor. Verify output HTML in GLPI KB article.
- **Spot checks**: After full migration, open 3-5 random KB articles in GLPI and verify user links are clickable.
- **Log review**: Check migration log for "unresolved" warnings — verify they are legitimate missing users.

### Notes

- **Risk**: Display name matching is fuzzy — unicode normalization handles accents but some mismatches (middle names, name ordering differences) are still expected.
- **Known limitation**: Duplicate fullnames (same firstname+realname) → last one wins in cache. Acceptable risk.
- **Known limitation**: GLPI profile links (`/front/user.form.php?id=X`) may return access-denied for users without profile view permissions. This is a GLPI permission issue, not a migration issue.
- **Future consideration**: Manual mapping file for known name mismatches (out of scope for now).

## Review Notes

- Adversarial review completed
- Findings: 12 total, 7 fixed, 5 skipped
- Resolution approach: auto-fix
- **Fixed:** F1 (XSS sanitization), F3 (consistent metadata output), F4 (unused variable), F5 (Tag without builder), F6 (user_id=0 falsy check), F7 (dead code author_name/editor_name), F10 (import inside loop)
- **Skipped (pre-existing/documented/cosmetic):** F2 (fullname collision - documented limitation), F8 (pagination cap - pre-existing), F9 (name ordering - documented), F11 (test reimplements logic), F12 (sys.path in tests)
