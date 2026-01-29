# CSS to mimic Confluence layout in GLPI
# Inject this into every KB article to ensure tables and headers look correct.

CONFLUENCE_CSS = """
<style>
/* Confluence Table Styles */
table.confluenceTable {
    border-collapse: collapse;
    width: 100%;
    margin: 10px 0;
    font-size: 14px;
}

table.confluenceTable th.confluenceTh, 
table.confluenceTable td.confluenceTd {
    border: 1px solid #ddd;
    padding: 8px;
    text-align: left;
    vertical-align: top;
}

table.confluenceTable th.confluenceTh {
    background-color: #f2f2f2;
    font-weight: bold;
    color: #333;
}

/* Row alternate background (optional) */
/* table.confluenceTable tr:nth-child(even) { background-color: #f9f9f9; } */

/* Hover effect */
table.confluenceTable tr:hover {
    background-color: #f5f5f5;
}

/* Highlighted cells */
td.highlight, 
td.confluenceTd.highlight {
    background-color: #fffae6; /* Soft yellow for highlights */
}

/* Metadata / Info blocks */
.confluence-information-macro {
    background-color: #f0f7ff;
    border-left: 3px solid #0078d4;
    padding: 10px;
    margin: 10px 0;
    border-radius: 3px;
}

.confluence-information-macro-tip {
    background-color: #e6ffed;
    border-left-color: #008000;
}

.confluence-information-macro-warning {
    background-color: #fff4ce;
    border-left-color: #ffce00;
}

/* Images */
img.confluence-embedded-image {
    max-width: 100%;
    height: auto;
    border: 0;
}
</style>
"""
