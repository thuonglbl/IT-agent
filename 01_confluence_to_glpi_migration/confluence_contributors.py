"""
Confluence Contributor Report
Scans Confluence HTML export files and generates a report grouped by Last Updated By.
See: _bmad-output/planning-artifacts/PRD-confluence-contributor-report.md
"""
import os
import sys

# Fix path: add project root, remove script dir to avoid common/logging shadowing stdlib
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_script_dir, '..'))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import re
import csv
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from bs4 import BeautifulSoup

from common.config.loader import load_config
from parser import ConfluenceParser

# Regex: extract date after "on" in metadata text
DATE_REGEX = re.compile(r'on\s+(\w+\s+\d{1,2},\s+\d{4})')
# Regex: extract Confluence page ID from filename
PAGE_ID_REGEX = re.compile(r'_?(\d+)\.html$')


def extract_metadata(file_path):
    """Extract structured metadata (author, editor, date) from raw HTML."""
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    meta_div = soup.find('div', class_='page-metadata')
    if not meta_div:
        return 'Unknown', 'Unknown', None

    author_span = meta_div.find('span', class_='author')
    editor_span = meta_div.find('span', class_='editor')

    created_by = author_span.get_text(strip=True) if author_span else 'Unknown'
    last_updated_by = editor_span.get_text(strip=True) if editor_span else created_by

    # Extract date
    meta_text = meta_div.get_text(separator=' ', strip=True)
    date_match = DATE_REGEX.search(meta_text)
    last_updated = None
    if date_match:
        try:
            last_updated = datetime.strptime(date_match.group(1), "%b %d, %Y")
        except ValueError:
            pass

    return created_by, last_updated_by, last_updated


def extract_page_id(filename):
    """Extract Confluence page ID from filename."""
    match = PAGE_ID_REGEX.search(filename)
    return match.group(1) if match else ''


def scan_pages(export_dir):
    """Walk export dir, parse each HTML file, return list of page dicts."""
    pages = []
    for root, _, files in os.walk(export_dir):
        for filename in files:
            if not filename.endswith('.html'):
                continue

            file_path = os.path.join(root, filename)

            # Reuse existing parser for title + breadcrumbs
            parser = ConfluenceParser(file_path)
            try:
                parser.parse()
            except Exception as e:
                print(f"  Warning: Could not parse {filename}: {e}")
                continue

            title = parser.title or 'Untitled'
            breadcrumbs = parser.breadcrumbs or []
            # Skip first breadcrumb (space name) for display
            breadcrumb_str = ' > '.join(breadcrumbs[1:]) if len(breadcrumbs) > 1 else ''

            # Extract structured metadata
            created_by, last_updated_by, last_updated = extract_metadata(file_path)

            pages.append({
                'title': title,
                'breadcrumbs': breadcrumb_str,
                'created_by': created_by,
                'last_updated_by': last_updated_by,
                'last_updated': last_updated,
                'last_updated_str': last_updated.strftime("%b %d, %Y") if last_updated else 'N/A',
                'confluence_id': extract_page_id(filename),
                'filename': filename,
            })

    return pages


def group_by_editor(pages):
    """Group pages by last_updated_by, sorted by page count desc."""
    groups = defaultdict(list)
    for page in pages:
        groups[page['last_updated_by']].append(page)

    # Sort pages within each group by date (newest first), N/A last
    for editor in groups:
        groups[editor].sort(
            key=lambda p: p['last_updated'] or datetime.min,
            reverse=True
        )

    # Sort groups by page count descending
    sorted_groups = dict(
        sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)
    )
    return sorted_groups


def print_report(groups, total_pages, stale_months):
    """Print formatted console report."""
    stale_cutoff = datetime.now() - timedelta(days=stale_months * 30)
    stale_count = 0
    no_metadata_count = 0

    print("=" * 80)
    print("CONFLUENCE CONTRIBUTOR REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"Total pages: {total_pages} | Last editors: {len(groups)}")
    print("=" * 80)

    for editor, pages in groups.items():
        print(f"\n## {editor} ({len(pages)} pages)")
        print(f"{'#':>3} | {'Page Title':<45} | {'Breadcrumbs':<40} | {'Created By':<25} | {'Last Updated':<12}")
        print(f"{'---':>3}-+-{'-'*45}-+-{'-'*40}-+-{'-'*25}-+-{'-'*12}")

        for i, page in enumerate(pages, 1):
            title = page['title'][:45]
            bc = page['breadcrumbs'][:40]
            cb = page['created_by'][:25]
            lu = page['last_updated_str']

            print(f"{i:>3} | {title:<45} | {bc:<40} | {cb:<25} | {lu:<12}")

            if page['last_updated'] and page['last_updated'] < stale_cutoff:
                stale_count += 1
            if editor == 'Unknown':
                no_metadata_count += 1

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nTOP LAST EDITORS (by page count):")
    for i, (editor, pages) in enumerate(groups.items(), 1):
        if i > 10:
            break
        print(f"  {i:>2}. {editor:<30} - {len(pages)} pages")

    print(f"\nPAGES WITHOUT METADATA: {no_metadata_count}")
    print(f"PAGES LAST UPDATED > {stale_months} MONTHS AGO: {stale_count} (potential stale content)")


def export_csv(pages, output_path):
    """Export flat CSV file, one row per page."""
    fieldnames = ['last_updated_by', 'page_title', 'breadcrumbs', 'created_by',
                  'last_updated', 'confluence_id', 'filename']

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for page in sorted(pages, key=lambda p: p['last_updated_by']):
            writer.writerow({
                'last_updated_by': page['last_updated_by'],
                'page_title': page['title'],
                'breadcrumbs': page['breadcrumbs'],
                'created_by': page['created_by'],
                'last_updated': page['last_updated_str'],
                'confluence_id': page['confluence_id'],
                'filename': page['filename'],
            })

    print(f"\nCSV exported: {output_path}")


def main():
    arg_parser = argparse.ArgumentParser(description='Confluence Contributor Report')
    arg_parser.add_argument('--stale-months', type=int, default=6,
                            help='Months threshold for stale content (default: 6)')
    arg_parser.add_argument('--export-dir', type=str, default=None,
                            help='Path to Confluence HTML export directory')
    args = arg_parser.parse_args()

    # Resolve export dir: CLI arg > config file
    export_dir = args.export_dir
    if not export_dir:
        try:
            config = load_config(validate=False)
            export_dir = config.get('confluence', {}).get('export_dir', '')
        except Exception as e:
            print(f"Warning: Could not load config.yaml: {e}")
            print("Use --export-dir to specify the Confluence export directory.")
            return

    if not export_dir or not os.path.exists(export_dir):
        print(f"Error: Export directory not found: {export_dir}")
        print("Set confluence.export_dir in config.yaml")
        return

    print(f"Scanning: {export_dir}\n")

    # Scan and parse
    pages = scan_pages(export_dir)
    if not pages:
        print("No HTML files found.")
        return

    # Group and report
    groups = group_by_editor(pages)
    print_report(groups, len(pages), args.stale_months)

    # Export CSV
    csv_path = os.path.join(os.path.dirname(__file__), 'confluence_contributors.csv')
    export_csv(pages, csv_path)


if __name__ == '__main__':
    main()
