# User Guide: Jira to GLPI Migration Script (API Mode)

This script automates the migration of Jira Issues (Tickets) to GLPI Projects (Tickets) via the REST API. It uses the Jira API to fetch issues and the GLPI API to create tickets, ensuring a robust migration even for large datasets (thousands or millions of tickets) through batch processing and resume capability.

## 1. Directory Structure

Inside the `02_jira_to_glpi_migration` folder, you will find:
- `config.py`: Configuration file (Important).
- `jira_to_glpi.py`: Main script to execute the migration.
- `jira_client.py`: Jira API client library with pagination support.
- `glpi_api.py`: GLPI API client library (enhanced for Tickets).
- `requirements.txt`: Required Python packages.
- `migration_state.json`: Auto-generated file to track progress (Resume capability).

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
For the script to correctly map **Reporters** and **Assignees** to the GLPI Task Team, the users must exist in GLPI with the **same username** as in Jira.
1.  **In GLPI**: Go to **Administration > Users**. Ensure all relevant users are created and their **Login** field is populated correctly.
2.  **In Jira**: Check the user's username in their Profile or User Management.
3.  **Note**: If a user is not found in GLPI (by Login name), the script will log a `[WARN]` and skip adding them to the team, but the task will still be created.

### GLPI Configuration (API & Tokens)
Refer to USER_GUIDE.md in 01_confluence_to_glpi_migration folder for detailed instructions.

### Jira Configuration (PAT)
You need a **Personal Access Token (PAT)** from your Jira Server.
1.  Log in to Jira.
2.  Click on your Profile Picture (top right) > **Profile**.
3.  Click **Personal Access Tokens** in the left menu.
4.  Click **Create token**.
5.  Give it a name and set Expiry date.
6.  **Copy the token** and save in safe place since you won't be able to see it again.

### Jira Settings
*   **JIRA_URL**: Your Jira URL in browser, including  '/jira' at the end.
*   **JIRA_PAT**: Paste your Personal Access Token here.
*   **JIRA_PROJECT_KEY** and **JIRA_JQL**: The Key of the Project you want to migrate (look at the url in browser, it is the part after '/projects/').

## 3. Configuration
Open `config_example.py` in a text editor and update the variables with the values you obtained above then rename to `config.py`:

### Migration Settings
*   **BATCH_SIZE**: Default is `50`. Adjust if you want to fetch more/less tickets per request.
*   **STATE_FILE**: Default is "migration_state.json". This file is used to resume if the script is interrupted (lost internet, server down, etc). To start from the beginning, delete this file.
*   **DEBUG**: `True` to fetch only **one batch** (size = `BATCH_SIZE`) for testing. `False` to run the full migration.
*   **MAPPING_FILE**: Default is "jira_glpi_id_map.json". This file stores the mapping between Jira Keys (e.g., PROJ-123) and GLPI IDs. **Do not delete this file** if you plan to resume migration or run it in batches, as it is crucial for linking Sub-tasks to their Parent tickets correctly.

### Jira Custom Fields
*   **JIRA_CUSTOM_FIELDS**: A dictionary mapping Jira field names to their custom field IDs.
*   **How to find IDs**: Go to your Jira Project Settings > Fields > select your current schema > on the Screens column, hover on the link "X screens". This will show you the custom field IDs for the fields in that screen.

Navigate to **Administration** > **Users** to ensure all users available before running the script.

Navigate to **Administration** > **Rules** to find relevant rules affect project tasks, disable them temporarily to avoid overwriting before running the script.

Navigate to **Setup** > **Plugins** to find relevant plugins affect login, disable them temporarily to avoid authentication issues before running the script.

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
