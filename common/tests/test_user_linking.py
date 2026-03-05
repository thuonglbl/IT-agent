"""
Unit tests for user linking: fullname cache, mention resolution, metadata resolution.
"""
import pytest
from bs4 import BeautifulSoup

# Import the normalize helper and GlpiClient
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from common.clients.glpi_client import _normalize_name


# ===== Normalization Tests =====

def test_normalize_name_basic():
    assert _normalize_name("Jean DUPONT") == "jean dupont"


def test_normalize_name_accents():
    assert _normalize_name("André Müller") == "andre muller"


def test_normalize_name_extra_whitespace():
    assert _normalize_name("  First   LAST  ") == "first last"


def test_normalize_name_empty():
    assert _normalize_name("") == ""
    assert _normalize_name(None) == ""


# ===== Fullname Cache Tests =====

def test_fullname_cache_skips_empty():
    """Users with empty firstname AND realname should not be in fullname_cache."""
    from common.clients.glpi_client import GlpiClient
    client = GlpiClient(url="http://fake", app_token="fake")
    # Simulate what load_user_cache does internally
    client.fullname_cache = {}

    # User with both names
    fullname = f"{'John'} {'Doe'}".strip()
    normalized = _normalize_name(fullname)
    if normalized:
        client.fullname_cache[normalized] = 1

    # User with empty names
    fullname_empty = f"{''} {''}".strip()
    normalized_empty = _normalize_name(fullname_empty)
    if normalized_empty:
        client.fullname_cache[normalized_empty] = 2

    assert "john doe" in client.fullname_cache
    assert client.fullname_cache["john doe"] == 1
    assert len(client.fullname_cache) == 1  # Empty name not added


def test_get_user_id_by_fullname():
    from common.clients.glpi_client import GlpiClient
    client = GlpiClient(url="http://fake", app_token="fake")
    client.fullname_cache = {"jean dupont": 42, "andre muller": 99}

    assert client.get_user_id_by_fullname("Jean DUPONT") == 42
    assert client.get_user_id_by_fullname("André Müller") == 99
    assert client.get_user_id_by_fullname("Unknown Person") is None
    assert client.get_user_id_by_fullname(None) is None
    assert client.get_user_id_by_fullname("") is None


# ===== Mention Resolution Tests =====

def _make_parser_with_content(html_content):
    """Helper to create a parser-like object with content_div set."""
    from bs4 import BeautifulSoup
    # We need to import the actual parser
    # But to avoid file dependency, we'll create a minimal mock
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '01_confluence_to_glpi_migration'))
    from parser import ConfluenceParser

    # Create a temp HTML file for the parser
    import tempfile
    full_html = f"""<!DOCTYPE html><html><head><title>Test</title></head>
    <body><div id="main-content">{html_content}</div></body></html>"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(full_html)
        temp_path = f.name

    try:
        p = ConfluenceParser(temp_path)
        p.parse()
        return p
    finally:
        os.unlink(temp_path)


def test_resolve_mentions_found():
    parser = _make_parser_with_content(
        '<a class="confluence-userlink" data-username="jlo">Firstname LASTNAME</a>'
    )
    login_cache = {"jlo": 123}
    unresolved = parser.resolve_user_mentions(login_cache)

    assert unresolved == []
    html = parser.get_content_html()
    assert '/front/user.form.php?id=123' in html


def test_resolve_mentions_not_found():
    parser = _make_parser_with_content(
        '<a class="confluence-userlink" data-username="xyz" href="/old">Unknown User</a>'
    )
    login_cache = {}
    unresolved = parser.resolve_user_mentions(login_cache)

    assert unresolved == ["xyz"]
    html = parser.get_content_html()
    assert 'href' not in html
    assert 'Unknown User' in html


def test_resolve_mentions_missing_data_username():
    parser = _make_parser_with_content(
        '<a class="confluence-userlink">No Username Attr</a>'
    )
    login_cache = {"jlo": 123}
    unresolved = parser.resolve_user_mentions(login_cache)

    assert unresolved == []
    html = parser.get_content_html()
    assert 'No Username Attr' in html


def test_resolve_mentions_no_content():
    """Parser with no content_div should return empty list."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '01_confluence_to_glpi_migration'))
    from parser import ConfluenceParser

    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write("<html><head><title>Empty</title></head><body></body></html>")
        temp_path = f.name

    try:
        p = ConfluenceParser(temp_path)
        p.parse()
        result = p.resolve_user_mentions({"jlo": 1})
        assert result == []
    finally:
        os.unlink(temp_path)


# ===== Metadata Resolution Tests =====

def _make_parser_with_metadata(metadata_html, content_html="<p>Content</p>"):
    """Helper to create a parser with metadata div."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '01_confluence_to_glpi_migration'))
    from parser import ConfluenceParser

    import tempfile
    full_html = f"""<!DOCTYPE html><html><head><title>Test</title></head>
    <body>
    <div id="content" class="view">
        <div class="page-metadata">{metadata_html}</div>
        <div id="main-content">{content_html}</div>
    </div>
    </body></html>"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(full_html)
        temp_path = f.name

    try:
        p = ConfluenceParser(temp_path)
        p.parse()
        return p
    finally:
        os.unlink(temp_path)


def test_resolve_metadata_author_found():
    parser = _make_parser_with_metadata(
        "Created by <span class='author'> Jean DUPONT</span>, last updated on Jan 01, 2025"
    )
    lookup = lambda name: 42 if _normalize_name(name) == "jean dupont" else None
    unresolved = parser.resolve_metadata_users(lookup)

    assert unresolved == []
    assert '/front/user.form.php?id=42' in parser.metadata_html
    assert 'Jean DUPONT' in parser.metadata_html


def test_resolve_metadata_not_found():
    parser = _make_parser_with_metadata(
        "Created by <span class='author'> Unknown Person</span>, last updated on Jan 01, 2025"
    )
    lookup = lambda name: None
    unresolved = parser.resolve_metadata_users(lookup)

    assert unresolved == ["Unknown Person"]
    assert 'Unknown Person' in parser.metadata_html


def test_resolve_metadata_no_metadata_div():
    """Page without metadata div should return empty list."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '01_confluence_to_glpi_migration'))
    from parser import ConfluenceParser

    import tempfile
    full_html = """<!DOCTYPE html><html><head><title>Test</title></head>
    <body><div id="main-content"><p>No metadata</p></div></body></html>"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(full_html)
        temp_path = f.name

    try:
        p = ConfluenceParser(temp_path)
        p.parse()
        result = p.resolve_metadata_users(lambda name: 1)
        assert result == []
    finally:
        os.unlink(temp_path)
