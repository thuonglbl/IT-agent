# User Guide: Confluence to GLPI Migration Script

This script automates the migration of HTML export files from Confluence to the GLPI Knowledge Base via the GLPI API.

## 1. Preparation: Export Data from Confluence

1.  **Log in to Confluence** and go to the space you want to export.
2.  **Go to Space Settings**: Click on "Space tools" > "Content Tools" in the sidebar.
3.  **Content Tools**: Select the **Export** tab. (if you don't see it, you don't have permission to export, please contact your Confluence administrator to give you permission or ask him/her to do it for you)
4.  **Select Format**: Choose **HTML** and click on **Next**.
5.  **Export Scheme**: Select **Normal Export** if you want to export all pages, or **Custom Export** if you want to export specific pages.
    *   *Note: Ensure "Include comments" is checked if you want them.*
6.  **Export**: Click **Export**.
7.  **Download**: Once processing is complete, download the zip file.
8.  **Extract**: Extract the zip file to a folder on your computer (e.g., `C:\Confluence-export`). This path will be used in `config.yaml`.
    *   *Note: Export folder name has .html at the end, which is confusing, remove it.*

## 2. Directory Structure

Inside the `01_confluence_to_glpi_migration` folder, you will find:

```
01_confluence_to_glpi_migration/
├── cleanup_category.py         # Delete imported KB items (for rollback)
├── config.yaml                 # Your configuration (create from example)
├── config.yaml.example         # Template configuration (copy to config.yaml)
├── css_styles.py               # Mimic Confluence CSS styles
├── main.py                     # Main migration script
├── parser.py                   # HTML parsing utilities
├── requirements.txt            # Python dependencies
└── test_curl.cmd               # Test GLPI API connection
```

**Configuration Files**:
- `common/config.yaml`: Shared credentials (GLPI tokens, Jira PAT, logging settings)
- `01_confluence_to_glpi_migration/config.yaml`: Folder-specific settings (export path, category names)

## 3. Prerequisites

### Install Python
Ensure Python 3.x is installed on your system.
```bash
python --version
```

If not install, Install Python Silently (Without GUI)
```bash
python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
```

### Install Dependencies
Open a Command Prompt or Terminal in the project folder and run:
```bash
pip install -r requirements.txt
```

### GLPI Configuration (API & Tokens)
You need an **App-Token** and a **User-Token** from GLPI.

> **Note**: You must have **Super-Admin** permissions (or equivalent) to configure the API. If you do not have these permissions, please ask your GLPI Administrator to provide the **App-Token** and generate a **User-Token** for you.

1.  **Log in to GLPI**: Log in to your GLPI instance with your credentials.
2.  **Enable API**: Go to **Setup > General > API**. In Legacy API part, enable **Enable Legacy REST API** and **Enable login with external token**.
3.  **Determine API URL**: The script uses the **Legacy REST API** endpoint: `https://your-glpi-server/api.php/v1`.
    *   **Why Legacy v1?**: I explicitly choose the Legacy API (`v1`) instead of the newer `v2+` because `v1` proved to be more stable with **User Tokens** in environments using **OAuth/SSO plugins**. The newer API versions often conflict with these plugins (returning 400/401 errors), whereas the Legacy API bypasses these specific strict checks.
4.  **App-Token**: In the API clients (Legacy API) part, click **Add API Client** (or open an existing one).
    *   **Active**: Set to **Yes**.
    *   **Log Connections**: Set to **Logs**.
    *   **IPv4 address range**: Remove all values (leave empty) to bypass IP restrictions.
    *   **App-Token**: Locate the **Application Token(app_token)** field. Click the **Regenerate** button if needed, and copy the token value.
5.  **User-Token**: Go to **User Preference** (top right user icon) > **My Settings**. In Main tab, Passwords and access keys part, tick **Regenerate** and click **Save** to get your personal User-Token.

### Configuration Setup

This project uses **two-level configuration inheritance**:
1. **Common config** (`common/config.yaml`): Shared GLPI/Jira credentials, logging settings
2. **Folder config** (`01_confluence_to_glpi_migration/config.yaml`): Confluence-specific settings

#### Step 1: Configure Common Settings

Copy and edit the common configuration:
```bash
cd common
cp config.yaml.example config.yaml
```

Open `common/config.yaml` and update

**SSL Certificate**:
- Set `verify_ssl: true` to use default system CAs
- Set `verify_ssl: "common/glpi.pem"` for custom certificate (contact GLPI admin for cert file)
- Set `verify_ssl: false` to disable (insecure, not recommended)

#### Step 2: Configure Folder-Specific Settings

Copy and edit the folder configuration:
```bash
cd 01_confluence_to_glpi_migration
cp config.yaml.example config.yaml
```

Open `config.yaml` and update:
```yaml
confluence:
  export_dir: "C:\\Confluence-export"  # Path to extracted Confluence export (from Step 8)

cleanup:
  default_category: "Confluence KB"    # Root category name in GLPI
```

**Environment Variables** (Optional):
Override sensitive credentials without editing files:
```cmd
set GLPI_USER_TOKEN=your_token_here
set GLPI_APP_TOKEN=your_app_token_here
python main.py
```

Navigate to **Setup** > **Plugins** to find relevant plugins affect login, disable them temporarily to avoid authentication issues before running the script.

## 4. Running the Migration

### Test Connection (Recommended)
Before running the main migration, ensure your configuration is correct:
1.  Run the script: `python test_curl.py`.
2.  If successful, you should see a session token or a 200 OK response.

### Run Migration
Run the following command:
```bash
python main.py
```

## 5. Verifying Results

The script will output logs to the console:
- `Processing: Page-Name.html`: Processing file.
- `Uploading image: image.png`: Uploading images to GLPI Documents.
- `Resolving Category Path`: Creating categories based on breadcrumbs.
- `Success! KB Item ID: 123`: Article created successfully.

After completion, verify the new articles in GLPI under **Tools > Knowledge Base**.

## Notes
- **Images**: Images are uploaded to **Management > Documents** and embedded in the articles.
- **Categories**: Categories are automatically created in GLPI mirroring the Confluence folder structure (breadcrumbs).
- **Duplicates**: The script does not currently check for existing articles. Running it twice will create duplicate entries.

## 6. Cleanup (Optional)

If you need to delete the imported data (e.g., to re-run the migration), you can use the cleanup script.

1.  Open `cleanup_category.py`.
2.  Modify the `category_name` variable if you want to delete a specific category (recommended root category).
3.  Run the command:
    ```bash
    python cleanup_category.py
    ```
    *   **Warning**: This script will permanently delete all items belonging to the specified category ID. Use with caution.

### Manual Cleanup (UI Method)
If the script fails or you prefer a visual method:
1.  Go to **Tools > Knowledge Base**.
2.  In the left sidebar, click on the **Category** you want to clean.
3.  In the list view, click the **Check All** checkbox (top left of the list).
4.  Click the **Actions** button at the top.
5.  Select **Delete permanently**.
6.  Click **Submit**.
7. Go to **Management > Documents** and delete the documents, then delete in Trash also.

## 7. Limitations

*   **One-Way Migration**: This script performs a one-time import from Confluence to GLPI. It does **not** maintain a sync link.
*   **Manual Updates Required**: If the content is updated in Confluence after the migration, those changes will **not** automatically appear in GLPI. You must manually update the article in GLPI to reflect the changes.
