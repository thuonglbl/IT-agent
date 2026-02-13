# User Guide: Jira Projects to GLPI Project Tasks Migration (API Mode)

This script automates the migration of Jira Issues to GLPI Project Tasks via the REST API. It uses the Jira API to fetch issues and the GLPI API to create project tasks, ensuring a robust migration even for large datasets through batch processing and resume capability.

## 1. Directory Structure

Inside the `02_project_jira_to_glpi_project_tasks_migration` folder, you will find:

```
02_project_jira_to_glpi_project_tasks_migration/
├── config.yaml.example         # Template configuration (copy to config.yaml)
├── config.yaml                 # Your configuration (create from example)
├── jira_to_glpi.py             # Main migration script
├── import_ldap_playwright.py   # Helper: import LDAP users to GLPI
├── requirements.txt            # Python dependencies
├── migration_state.json        # Auto-generated progress tracker
└── jira_glpi_id_map.json       # Auto-generated ID mapping (DO NOT DELETE)
```

**Configuration Files**:
- `common/config.yaml`: Shared credentials (GLPI tokens, Jira PAT, logging, batch settings)
- `02_project_jira_to_glpi_project_tasks_migration/config.yaml`: Project-specific settings (project key, JQL, custom fields, color map)

## 2. Prerequisites

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

### User Mapping (Crucial)
For the script to correctly map **Reporters** and **Assignees** to the GLPI Task Team, the users must exist in GLPI.

#### Step 0: Import Users from LDAP
Before running the migration, you must import all users from LDAP into GLPI.
We have provided a script `import_ldap_playwright.py` to automate this process (since manual import is slow).

**How to run it:**
1.  **Install Browser Binaries** (Run once):
    ```bash
    # Note: 'playwright' library is installed via requirements.txt
    playwright install chromium
    ```

2.  **Configuration (Recommended):**
    Open `config.py` and ensure `GLPI_URL` is set to `http` if your server is NOT support SSL to avoid SSL redirect loops, if supported keep it as `https`.
    
    To automate login (optional), add your credentials to `config.py`:
    ```python
    # Add to config.py
    GLPI_USERNAME = "your_username"
    GLPI_PASSWORD = "your_password"
    ```

3.  **Run the script:**
    Change MAX_BATCHES in import_ldap_playwright.py to 1 to debug, or set to 1000 for full run
    ```bash
    python import_ldap_playwright.py
    ```
    
4.  **Process:**
    The script will launch a browser, login automatically (if credentials provided), and import users in batches. It includes auto-retry logic for network glitches and redirects.

### Jira Configuration (PAT)
You need a **Personal Access Token (PAT)** from your Jira Server.
1.  Log in to Jira.
2.  Click on your Profile Picture (top right) > **Profile**.
3.  Click **Personal Access Tokens** in the left menu.
4.  Click **Create token**.
5.  Give it a name and set Expiry date.
6.  **Copy the token** and save in safe place since you won't be able to see it again.

### GLPI Configuration (API & Tokens)
Refer to [USER_GUIDE.md](../01_confluence_to_glpi_migration/USER_GUIDE.md) in folder 01 for detailed GLPI API setup instructions.

## 3. Configuration Setup

This project uses **two-level configuration inheritance**:
1. **Common config** (`common/config.yaml`): Shared GLPI/Jira credentials, batch size, logging
2. **Folder config** (`02_project_jira_to_glpi_project_tasks_migration/config.yaml`): Project-specific settings

### Step 1: Configure Common Settings

Copy and edit the common configuration:
```bash
cd common
cp config.yaml.example config.yaml
```

Open `common/config.yaml` and update

**Debug Mode**:
- `debug: false` → Process all tasks (full migration)
- `debug: true` → Process only 1 batch (batch_size tasks) for testing

### Step 2: Configure Project-Specific Settings

Copy and edit the folder configuration:
```bash
cd 02_project_jira_to_glpi_project_tasks_migration
cp config.yaml.example config.yaml
```

Open `config.yaml` and update:

**Jira Settings**:
```yaml
jira:
  project_key: "MYPROJECT"                 # Your Jira project key (from browser URL)
  jql: "project = MYPROJECT ORDER BY key ASC"

  custom_fields:
    story_points: customfield_10010
    acceptance_criteria: customfield_10020
    # ... (Add your project specific fields)
```

**GLPI Settings**:
```yaml
glpi:
  project_name: "My GLPI Project Name"     # Must match exactly in GLPI
```

**Migration Settings**:
```yaml
migration:
  state_file: "migration_state.json"
  mapping_file: "jira_glpi_id_map.json"    # DO NOT DELETE - crucial for sub-task linkage
```

**Color Mapping** (Jira → GLPI):
```yaml
jira:
  color_map:
    success: "#00875A"      # Green
    inprogress: "#0052CC"   # Blue
    default: "#42526E"      # Gray
```

### Finding Jira Custom Field IDs

To find custom field IDs:
1. Go to Jira Project Settings > Fields
2. Select your current schema
3. Hover over "X screens" link in the Screens column
4. Note the `customfield_XXXXX` ID from the URL

**Pre-Migration Checklist**:
- [ ] Navigate to **Administration** > **Users** to ensure all users are imported
- [ ] Navigate to **Administration** > **Rules** to find rules affecting project tasks - disable temporarily to avoid auto-actions
- [ ] Navigate to **Setup** > **Plugins** to find authentication plugins - disable temporarily if they interfere with API login

**Environment Variables** (Optional):
Override sensitive credentials without editing files:
```cmd
set JIRA_PAT=your_token_here
set GLPI_USER_TOKEN=your_token_here
python jira_to_glpi.py
```

## 4. Running the Migration

Run the following command:
```bash
python jira_to_glpi.py
```

## 5. Features & Behavior

### Resume Capability (State Saving)
*   The script creates a file named `migration_state.json`.
*   It saves the progress (how many tickets processed) after every batch.
*   **If the script stops** (internet lost, computer restart, Ctrl+C), just run `python jira_to_glpi.py` again. It will automatically **resume** from where it left off.
*   To restart from the beginning, delete `migration_state.json`.

### Attachments
*   The script automatically downloads attachments from Jira and uploads them to GLPI.
*   Links to these files are embedded in the Ticket Description.

### Comments
*   Jira Comments are migrated as **Followups** in GLPI.
*   The original author and timestamp are preserved in the text body (e.g., `[2023-01-01] John Doe wrote:`).

## 6. Verification
*   Check the console output for "Success! Ticket ID: ...".
*   Check your GLPI Project/Ticket list to see the incoming data.

## 7. Limitations
*   **Ticket ID**: GLPI generates new IDs. The original Jira Key is preserved in the *Title* and *Description* for reference.
*   **Users**: The script uses a single API User to create tickets. The original reporter's name is added to the Description text, but the GLPI "Requester" field will be the API User (unless mapped explicitly).
