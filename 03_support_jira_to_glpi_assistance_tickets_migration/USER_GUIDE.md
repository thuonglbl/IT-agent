# User Guide: Jira Support to GLPI Assistance Migration

This script automates the migration of Jira Support Issues to GLPI Assistance Tickets via the REST API. It uses the Jira API to fetch issues and the GLPI API to create tickets, preserving history, comments, and actors.

## 1. Directory Structure

Inside the `03_support_jira_to_glpi_assistance_tickets_migration` folder, you will find:
- `config.py`: Configuration file (Important).
- `migrate_support_tickets.py`: Main script to execute the migration.
- `jira_client.py`: Jira API client library.
- `glpi_client_support.py`: GLPI API client library (specifically for Tickets).
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
For the script to correctly map **Reporters (Requesters)** and **Assignees (Technicians)** to the GLPI Ticket, the users must exist in GLPI.

#### Step 0: Import Users from LDAP
Before running this migration, ensure all users are imported into GLPI.
Please refer to the script in `02_project_jira_to_glpi_project_tasks_migration/import_ldap_playwright.py` or import them manually via **Administration > Users > LDAP Directory Link**.

### Jira Configuration (PAT)
For the script to correctly map **Reporters (Requesters)** and **Assignees (Technicians)** to the GLPI Ticket:
1.  **In GLPI**: Users must exist with the **same username (Login)** as in Jira.
2.  **Recursive Search**: The script searches for users across all entities (`is_recursive=True`).
3.  **Fallback**: If a user is not found, the Ticket is created with the API User as the creator, and the original Jira reporter name is mentioned in the Description.

### Jira Configuration (PAT)
You need a **Personal Access Token (PAT)** from Jira (See Milestone 2 guide for steps).

### GLPI Configuration (API & Tokens)
You need an **App-Token** and **User-Token** from GLPI (See Milestone 1 guide for steps).

## 3. Configuration

Open `config_example.py`, update the values, and save it as `config.py`:

*   **JIRA_URL**: URL of your Jira Server.
*   **JIRA_PAT**: Your Personal Access Token.
*   **JIRA_PROJECT_KEY**: Key of the project to migrate.
*   **JIRA_VERIFY_SSL**: Verify SSL (True/False/Path recommend True).
*   **GLPI_URL**: Your GLPI API URL (e.g., `.../api.php/v1`).
*   **GLPI_APP_TOKEN**: Your GLPI App Token.
*   **GLPI_USER_TOKEN**: Your GLPI User Token.
*   **GLPI_VERIFY_SSL**: Verify SSL (True/False/Path recommend Path).
*   **BATCH_SIZE**: Number of tickets per batch.
*   **STATUS_MAPPING**: Status mapping from Jira (flexible) to GLPI (fixed).
*   **TYPE_MAPPING**: Type mapping from Jira (flexible) to GLPI (fixed).
*   **CLASSIFICATION_MAPPING**:
    *   **Step 1: List Classifications**: Run `python list_classifications.py` to see all unique Classification values in your Jira project.
    *   **Step 2: Define Mappings**:
        *   Open `config.py` (or `config_example.py` as reference).
        *   Update `CLASSIFICATION_TO_LOCATION` to map classifications to GLPI Location Names.
        *   Update `CLASSIFICATION_TO_ITEM` to map classifications to GLPI Items (Type + Name).
        *   Supported Item Types: `Business_Service`, `Software`, `Computer`.
    *   **Step 3: Verification in GLPI**:
        *   Log in to GLPI.
        *   Navigate to **Setup > Dropdowns > Common > Locations** to verify Location names match your config.
        *   Navigate to **Assets > Business Services** to verify Business Service names.
        *   Navigate to **Assets > Software** to verify Software names.
        *   *If items are missing in GLPI, the migration will skip linking them (with a warning).*

Navigate to **Administration** > **Users** to ensure all users available before running the script.

Navigate to **Administration** > **Rules** to find relevant rules affect assistance tickets, disable them temporarily to avoid overwriting before running the script.

Navigate to **Setup** > **Plugins** to find relevant plugins affect login, disable them temporarily to avoid authentication issues before running the script.

## 4. Running the Migration

Run the following command:
```bash
python migrate_support_tickets.py
```
After run, check file `missing_users.txt` to see if there are any users that need to be imported into GLPI, then delete all tickets and run the script again.
If run fail, check file `migration_state.json` to see where the script stopped, and run `python migrate_support_tickets.py` again. Delete `migration_state.json` to start the migration from the beginning (remember to delete all tickets first).

## 5. Features & Behavior

### Resume Capability (State Saving)
*   The script creates `migration_state.json`.
*   **If the script stops** (e.g., network error), run it again to **resume** from the last batch.
*   To restart from the beginning, delete `migration_state.json`.

### Ticket Fields Mapping
*   **Title/Summary**: Uses Jira Summary directly (Original Key is in Description).
*   **Description**:
    *   Adds a **Jira Details** table at the top (Type, Priority, Component, Labels, Reporter).
    *   Preserves original description content.
*   **Status Mapping (Dynamic)**:
    *   The script reads all statuses from your Jira Project.
    *   It attempts to match them with GLPI Ticket Statuses (New, Processing, Solved, Closed, etc.).
    *   If a match is found (by name), it maps automatically.
    *   If not found, it defaults to **Processing (Assigned)**.
*   **Type -> Category Sync (Dynamic)**:
    *   Jira **Issue Types** (e.g., Bug, Story, Request) are mapped to **GLPI ITIL Categories**.
    *   **Auto-Create**: If the Category doesn't exist in GLPI, the script **creates it automatically**.
    *   **GLPI Ticket Type**: Defaults to **Request** (2), unless the Jira type contains "Incident", then it sets to **Incident** (1).

### Dates & Actors
*   **Dates**:
    *   **Creation Date**: Preserved.
    *   **Update Date**: Preserved.
    *   **Resolution Date**: Mapped to GLPI `solvedate` (and `closedate` if closed).
*   **Actors**:
    *   **Requester**: Maps Jira Reporter.
    *   **Technician**: Maps Jira Assignee.
    *   **Recursive Search**: Finds users across all GLPI entities.
    *   *Note*: If a user is not found, a Warning is logged, and the field is left empty (or set to API user).

### Comments & History
*   **Comments**: Migrated as **Followups** in GLPI. The header `**Comment by <User> (<Date>)**` is added to preserve context.
*   **History**: Not explicitly migrated as log entries, but the *Update Date* of the ticket is synced.

## 6. Verification
*   Check the console output for "Created Ticket ID: ...".
*   Check **Assistance > Tickets** in GLPI to see the new tickets.
*   Verify that ticket overview and detail are correct.

## 7. Limitations
*   **Ticket ID**: GLPI generates new IDs. The original Jira Key is preserved in the first message for reference.
*   **Users**: cannot create or sync user. If a user is not found, a Warning is logged, and the field is left empty.
*   **Last Update**: GLPI automatically updates this field when changes are made. The script cannot force a specific past date.
*   **Time to Own**: GLPI calculates this based on SLAs and Business Rules. The script attempts to map it but GLPI's internal logic may override it.
