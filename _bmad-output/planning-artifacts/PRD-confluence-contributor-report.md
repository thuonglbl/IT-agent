# PRD: Confluence Contributor Report

**Document ID:** PRD-CONTRIB-001
**Created:** 2026-03-03
**Status:** Ready for Implementation
**Priority:** Medium

---

## 1. Objective

Create a standalone script that scans Confluence HTML export files and generates a contributor report. The report shows one row per page, grouped by **Last Updated By**, to identify who is responsible for each page's latest content.

**Purpose:** Provide a list to remind the last editor of each page to review and update their content on GLPI Knowledge Base after migration.

---

## 2. Data Source

The script parses **Confluence HTML export files** (same source as folder 01 migration). No Confluence API connection required.

**Export directory:** Configured via `confluence.export_dir` in `01_confluence_to_glpi_migration/config.yaml`.

### Available Data from HTML Export

| Field | HTML Source | Extraction Method |
|-------|-----------|-------------------|
| **Created By** | `<span class='author'>` inside `<div class="page-metadata">` | BeautifulSoup `.find('span', class_='author')` |
| **Last Updated By** | `<span class='editor'>` (if present), otherwise falls back to `<span class='author'>` | BeautifulSoup `.find('span', class_='editor')` or author |
| **Page title** | `<h1 id="title-heading">` or `<title>` | Existing `parser.py` logic |
| **Breadcrumbs** | `<ol id="breadcrumbs">` > `<li>` items | Existing `parser.py` logic |
| **Last update date** | Text after "on" in metadata string | Regex: `on\s+(\w+\s+\d{1,2},\s+\d{4})` |

### Metadata Patterns Found in Export

**Pattern 1** — Different creator and last editor:
```html
Created by <span class='author'> Cuong DOAN PHI</span>, last updated by <span class='editor'> Pierre GUIOL</span> on Mar 12, 2025
```
→ Created By: `Cuong DOAN PHI` | Last Updated By: `Pierre GUIOL`

**Pattern 2** — Same person created and last updated (no editor span):
```html
Created by <span class='author'> Jose Luis ORTEGA MARTIN</span>, last updated on Apr 11, 2025
```
→ Created By: `Jose Luis ORTEGA MARTIN` | Last Updated By: `Jose Luis ORTEGA MARTIN`

**Pattern 3** — Empty metadata (no author/date info):
```html
<div class="page-metadata">
</div>
```
→ Created By: `Unknown` | Last Updated By: `Unknown`

### Limitation

Confluence HTML export does **NOT** include creation date. Only the **last update date** is available.

---

## 3. Output Format

### 3.1 Console Output (Grouped by Last Updated By)

Each page appears as **one row**. Pages are grouped under the person who last updated them.

```
============================================================
CONFLUENCE CONTRIBUTOR REPORT
Generated: 2026-03-03
Total pages: 202 | Last editors: 15
============================================================

## Pierre GUIOL (12 pages)
| # | Page Title                          | Breadcrumbs                                  | Created By         | Last Updated |
|---|-------------------------------------|----------------------------------------------|--------------------|--------------|
| 1 | API manager - Bruno & Postman       | Home > User Knowledge Base                   | Cuong DOAN PHI     | Mar 12, 2025 |
| 2 | Print and Scan                      | Home > User Knowledge Base                   | Michele POTALIVO   | Feb 12, 2025 |
| 3 | ELCA Wi-Fi Configuration            | Home > User Knowledge Base > Network         | Minh NGUYEN LE HOANG | Apr 01, 2025 |
...

## Jose Luis ORTEGA MARTIN (6 pages)
| # | Page Title                          | Breadcrumbs                                  | Created By                  | Last Updated |
|---|-------------------------------------|----------------------------------------------|-----------------------------|--------------|
| 1 | Set up Outlook app for IOS          | Home > User KB > Outlook > IOS               | Jose Luis ORTEGA MARTIN     | Apr 11, 2025 |
| 2 | Enroll Badge for Printers           | Home > User Knowledge Base                   | Jose Luis ORTEGA MARTIN     | Mar 26, 2025 |
...

## Unknown (5 pages)
| # | Page Title                          | Breadcrumbs                                  | Created By | Last Updated |
|---|-------------------------------------|----------------------------------------------|------------|--------------|
| 1 | Some Page Without Metadata          | Home                                         | Unknown    | N/A          |
...
```

### 3.2 CSV Export

File: `confluence_contributors.csv` — one row per page.

| last_updated_by | page_title | breadcrumbs | created_by | last_updated | confluence_id | filename |
|-----------------|-----------|-------------|------------|--------------|---------------|----------|
| Pierre GUIOL | API manager - Bruno & Postman | Home > User Knowledge Base | Cuong DOAN PHI | Mar 12, 2025 | 1315046768 | 1315046768.html |
| Jose Luis ORTEGA MARTIN | Set up Outlook app for IOS | Home > User KB > Outlook > IOS | Jose Luis ORTEGA MARTIN | Apr 11, 2025 | 1317137011 | Set-up-Outlook-app-for-IOS_1317137011.html |

### 3.3 Summary Statistics

```
TOP LAST EDITORS (by page count):
  1. Pierre GUIOL              - 12 pages
  2. Siegfried DE ROECK         - 8 pages
  3. Jose Luis ORTEGA MARTIN   - 6 pages
  ...

PAGES WITHOUT METADATA: 5
PAGES LAST UPDATED > 6 MONTHS AGO: 42 (potential stale content)
```

---

## 4. Functional Requirements

### FR-1: Parse All HTML Files
- Walk through `confluence.export_dir` recursively
- Parse each `.html` file using BeautifulSoup
- Reuse breadcrumb and title extraction logic from existing `parser.py`

### FR-2: Extract Page Data (One Row Per Page)
- Extract **Created By** from `<span class='author'>`
- Extract **Last Updated By** from `<span class='editor'>` — if no editor span, use author (same person)
- Extract **last update date** from metadata text
- Extract **Confluence page ID** from filename pattern `_(\d+)\.html` or numeric-only filename `(\d+)\.html`
- Handle all 3 metadata patterns

### FR-3: Group by Last Updated By
- Each group header shows the person's name and page count
- Pages within each group sorted by last update date (newest first)
- Groups sorted by page count (descending)
- Pages with no metadata grouped under "Unknown"

### FR-4: Generate Reports
- Console output: formatted table grouped by last editor
- CSV export: flat table (one row per page) for spreadsheet analysis
- Summary statistics: top last editors, stale pages count

### FR-5: Configurable Stale Threshold
- Default: pages not updated in last 6 months flagged as "stale"
- Configurable via command-line argument or config

---

## 5. Technical Design

### 5.1 File Location

```
01_confluence_to_glpi_migration/
├── confluence_contributors.py     # New standalone script
├── parser.py                      # Existing (reused)
├── main.py                        # Existing migration script
└── ...
```

### 5.2 Dependencies

- `beautifulsoup4` (already in requirements.txt)
- `pyyaml` (already in requirements.txt)
- `common.config.loader` (reuse existing config loading)
- `parser.ConfluenceParser` (reuse existing HTML parser)
- Standard library: `csv`, `re`, `os`, `datetime`, `collections`

### 5.3 Data Flow

```
Confluence HTML Export Dir
        │
        ▼
  Walk .html files
        │
        ▼
  Parse each file (parser.py)
  ├── title
  ├── breadcrumbs
  └── raw metadata div
        │
        ▼
  Extract from metadata:
  ├── created_by (span.author)
  ├── last_updated_by (span.editor or span.author)
  └── last_updated (regex)
        │
        ▼
  Build page list:
  [
    {title, breadcrumbs, created_by, last_updated_by, last_updated, confluence_id, filename},
    ...
  ]
        │
        ▼
  Group by last_updated_by → dict
  {
    "Pierre GUIOL": [page1, page2, ...],
    "Jose Luis ORTEGA MARTIN": [page3, ...],
  }
        │
        ▼
  Output:
  ├── Console table (grouped by last editor)
  ├── CSV file (flat, one row per page)
  └── Summary statistics
```

### 5.4 Key Implementation Notes

1. **Reuse `parser.py`**: Call `ConfluenceParser(file_path).parse()` to get `title`, `breadcrumbs`. Then re-parse the raw HTML for structured metadata extraction.

2. **Last Updated By logic**:
   - If `<span class='editor'>` exists → use editor name
   - If no editor span → use `<span class='author'>` (same person created and last updated)
   - If no metadata at all → `"Unknown"`

3. **Date parsing**: Extract date string using regex `on\s+(\w+\s+\d{1,2},\s+\d{4})`, then parse with `datetime.strptime(date_str, "%b %d, %Y")`.

4. **One row per page**: Each page appears exactly once in the report under its Last Updated By group.

---

## 6. Usage

```bash
cd 01_confluence_to_glpi_migration

# Generate report (console + CSV)
python confluence_contributors.py

# With custom stale threshold (in months)
python confluence_contributors.py --stale-months 3
```

---

## 7. Acceptance Criteria

- [ ] Script scans all HTML files in configured export directory
- [ ] Correctly extracts created_by, last_updated_by, title, breadcrumbs, last update date
- [ ] Handles all 3 metadata patterns without errors
- [ ] One row per page — no duplicates
- [ ] Groups pages by Last Updated By
- [ ] Exports flat CSV file (one row per page)
- [ ] Shows summary statistics (last editor count, stale pages)
- [ ] Runs independently without GLPI connection
- [ ] Reuses existing `parser.py` and `common.config.loader`
