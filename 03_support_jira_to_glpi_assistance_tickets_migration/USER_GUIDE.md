# User Guide: Jira Support to GLPI Assistance Migration v2.0

This script automates the migration of Jira Support Issues to GLPI Assistance Tickets via the REST API. It uses the Jira API to fetch issues and the GLPI API to create tickets, preserving history, comments, and actors.

## What's New in v2.0

- ✅ **Common Library**: Shared API clients, utilities, and configuration across all migrations
- ✅ **Configuration Inheritance**: Two-level config (common + folder-specific) with environment variable override
- ✅ **YAML Configuration**: Secure, environment-friendly configuration management
- ✅ **Modular Architecture**: Clean, maintainable code structure with reusable components
- ✅ **Enhanced Logging**: Structured logging with DEBUG/INFO/WARNING/ERROR levels
- ✅ **Better Error Handling**: Detailed error messages and troubleshooting

---

## 1. Directory Structure

Inside the `03_support_jira_to_glpi_assistance_tickets_migration` folder, you will find:

```
03_support_jira_to_glpi_assistance_tickets_migration/
├── config.yaml.example         # Template configuration (copy to config.yaml)
├── config.yaml                 # Your configuration (create from example)
├── migrate_support_tickets.py  # Main migration script
├── list_classifications.py     # Helper: discover Jira classifications
├── list_security_levels.py     # Helper: discover Jira security levels
├── requirements.txt            # Python dependencies
├── migration_state.json        # Auto-generated progress tracker
├── missing_users.txt           # Auto-generated missing users report
└── logs/                       # Auto-created log directory
    └── migration_*.log         # Timestamped log files
```

**Configuration Files**:
- `common/config.yaml`: Shared credentials (GLPI tokens, Jira PAT, batch size, logging)
- `common/glpi.pem`: SSL certificate for GLPI (if using self-signed certificates)
- `03_support_jira_to_glpi_assistance_tickets_migration/config.yaml`: Ticket-specific settings (project key, status/type/priority mappings, classification mappings, custom field IDs)

---

## 2. Prerequisites

### 2.1. Install Python

Ensure Python 3.8+ is installed on your system:
```bash
python --version
```

If not installed, install Python silently (without GUI):
```bash
python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
```

### 2.2. Install Dependencies

Open a Command Prompt or Terminal in the project folder and run:
```bash
pip install -r requirements.txt
```

This installs:
- `requests`: HTTP client for API calls
- `pyyaml`: YAML configuration parsing
- `paramiko`: SSH/SFTP library (for advanced features)
- `playwright`: Browser automation (for future UI features)

### 2.3. User Mapping (Crucial)

For the script to correctly map **Reporters (Requesters)** and **Assignees (Technicians)** to GLPI Tickets, users must exist in GLPI.

#### Import Users from LDAP

**Before running this migration**, ensure all users are imported into GLPI:
1. Go to **Administration > Users > LDAP Directory Link** in GLPI
2. Or use automated import: `02_project_jira_to_glpi_project_tasks_migration/import_ldap_playwright.py`

**Important**: Users must have the **same username (Login)** in GLPI as in Jira.

**Fallback**: If a user is not found, the ticket is created with the API User as the creator, and the original Jira reporter name is mentioned in the description.

### 2.4. Jira Configuration (PAT)

You need a **Personal Access Token (PAT)** from Jira:
1. Log in to Jira
2. Go to **Profile > Personal Access Tokens**
3. Click **Create Token**
4. Save the token securely (you'll need it for configuration)

### 2.5. GLPI Configuration (API & Tokens)

You need an **App-Token** and **User-Token** from GLPI:

**App-Token**:
1. Go to **Setup > General > API**
2. Click **Add API client**
3. Enable **API Client** and save the generated **App-Token**

**User-Token**:
1. Go to your user profile: **My Settings > Remote access keys**
2. Generate a new **API token**
3. Save the **User-Token**

---

## 3. Configuration Setup

This project uses **two-level configuration inheritance**:
1. **Common config** (`common/config.yaml`): Shared GLPI/Jira credentials, batch size, logging
2. **Folder config** (`03_support_jira_to_glpi_assistance_tickets_migration/config.yaml`): Ticket-specific mappings and settings

### 3.1. Configure Common Settings

Copy and edit the common configuration:
```bash
cd common
cp config.yaml.example config.yaml
```

Open `common/config.yaml` and update

**Debug Mode**:
- `debug: false` → Process all tickets (full migration)
- `debug: true` → Process only 1 batch (batch_size tickets) for testing

**SSL Certificate**:
- Place your `glpi.pem` certificate in the `common/` folder
- Or set `verify_ssl: true` to use system certificates
- Or set `verify_ssl: false` to disable verification (not recommended)

### 3.2. Configure Ticket-Specific Settings

Copy and edit the folder configuration:
```bash
cd 03_support_jira_to_glpi_assistance_tickets_migration
cp config.yaml.example config.yaml
```

Open `config.yaml` and update the following sections:

#### 3.2.1. Jira Settings

```yaml
jira:
  project_key: "SUPPORT"     # Your Jira project key
```

> **Note**: Jira URL and PAT are configured in `common/config.yaml`

#### 3.2.2. Migration Settings

```yaml
migration:
  state_file: "migration_state.json"   # Progress tracker
  missing_users_file: "missing_users.txt"
  jira_debug_ticket_key: null          # Optional: Target specific ticket (e.g., "SUPPORT-123")
```

**Debug Modes**:
1. **Process One Batch**: Set `migration.debug: true` in `common/config.yaml` to process only 1 batch (50 tickets)
2. **Target Specific Ticket**: Set `jira_debug_ticket_key: "SUPPORT-123"` in this config to migrate only that ticket

#### 3.2.3. Field Mappings

The configuration includes mappings for:
- **Status**: Jira status → GLPI status ID
- **Type**: Jira issue type → GLPI ticket type (1=Incident, 2=Request)
- **Priority**: Jira priority → [Urgency, Impact] scale

Example:
```yaml
mappings:
  status:
    assigned: 2           # GLPI: Processing (Assigned)
    in progress: 3        # GLPI: Processing (Planned)
    resolved: 5           # GLPI: Solved
    closed: 6             # GLPI: Closed
  status_default: 3       # Default if not found

  type:
    incident: 1           # GLPI: Incident
    change: 2             # GLPI: Request
  type_default: 2

  priority:
    next hour: [5, 5]           # Very high urgency and impact
    next business day: [3, 3]   # Medium urgency and impact
  priority_default: [3, 3]
```

#### 3.2.4. Classification Mapping

Map Jira **Classification** custom field values to GLPI **Locations** and **Items** (Business Services, Software):

```yaml
mappings:
  classification_to_location:
    Location_A: "Building A"
    Location_B: "Building B"
    Remote: "Remote"

  classification_to_item:
    Intranet: ["Business_Service", "Intranet"]
    Network: ["Business_Service", "Network Configuration"]
    VPN: ["Software", "VPN Client"]
    Teams: ["Software", "Microsoft Teams"]
```

**How to discover classifications**:
```bash
python list_classifications.py
```

This will scan your Jira project and list all unique classification values.

#### 3.2.5. Custom Field IDs

Jira custom field IDs (use browser **Inspect** tool to find these in Jira HTML):

```yaml
custom_fields:
  classification: "customfield_10010"
  reporter_details: "customfield_10020"
  request_participants: "customfield_10030"
  customer_request_type: "customfield_10040"
  approvers: "customfield_10050"
  approvals: "customfield_10060"

  sla_fields:
    - "customfield_10100"  # Time to assign
    - "customfield_10101"  # In Progress
    - "customfield_10102"  # In progress To Fixed
```

---

## 4. Environment Variables (Optional)

You can override sensitive credentials using environment variables instead of editing `config.yaml`.

### 4.1. Supported Environment Variables

- `JIRA_PAT`: Jira Personal Access Token
- `JIRA_URL`: Jira server URL
- `GLPI_APP_TOKEN`: GLPI application token
- `GLPI_USER_TOKEN`: GLPI user token
- `GLPI_PASSWORD`: GLPI password
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### 4.2. Example Usage

**Windows (CMD)**:
```cmd
set JIRA_PAT=your_token_here
set GLPI_USER_TOKEN=your_token_here
python migrate_support_tickets.py
```

**Windows (PowerShell)**:
```powershell
$env:JIRA_PAT="your_token_here"
$env:GLPI_USER_TOKEN="your_token_here"
python migrate_support_tickets.py
```

**Linux/Mac**:
```bash
export JIRA_PAT=your_token_here
export GLPI_USER_TOKEN=your_token_here
python migrate_support_tickets.py
```

---

## 5. Running the Migration

### 5.1. Initial Run

Execute the migration script:
```bash
python migrate_support_tickets.py
```

**What happens**:
1. Loads configuration from `config.yaml`
2. Initializes Jira and GLPI clients
3. Loads GLPI caches (users, groups, categories, locations)
4. Builds dynamic status mapping
5. Fetches tickets from Jira in batches
6. Creates corresponding tickets in GLPI
7. Saves progress after each batch

**Console output**:
```
2026-02-13 14:30:45 [INFO] migration: === Jira Support to GLPI Assistance Migration v2.0 ===
2026-02-13 14:30:45 [INFO] migration: Initializing Jira client...
2026-02-13 14:30:46 [INFO] migration: Initializing GLPI client...
2026-02-13 14:30:47 [INFO] migration: Loading GLPI user cache...
2026-02-13 14:30:50 [INFO] migration: Fetching issues (offset: 0, limit: 50)...
2026-02-13 14:30:52 [INFO] migration: Processing ITSAMPLE-123: Unable to access VPN
2026-02-13 14:30:55 [INFO] migration:   -> Created Ticket ID: 4567
```

### 5.2. Debug Mode

#### Debug Mode 1: Process One Batch

Edit `common/config.yaml`:
```yaml
migration:
  debug: true
```

Run migration:
```bash
python migrate_support_tickets.py
```

This will process **1 batch** (50 tickets by default) and exit.

#### Debug Mode 2: Target Specific Ticket

Edit `03_support_jira_to_glpi_assistance_tickets_migration/config.yaml`:
```yaml
migration:
  jira_debug_ticket_key: "SUPPORT-123"
```

Run migration:
```bash
python migrate_support_tickets.py
```

This will migrate **only** `SUPPORT-123`.

### 5.3. Resume After Interruption

If the migration is interrupted (network failure, system sleep, etc.), the script automatically resumes from where it left off.

**How it works**:
- Progress is saved in `migration_state.json` after each batch
- Contains: `start_at` (pagination offset) and `total_processed` (count)

**To resume**:
Simply run the script again:
```bash
python migrate_support_tickets.py
```

**To restart from beginning**:
Delete the state file:
```bash
rm migration_state.json
python migrate_support_tickets.py
```

### 5.4. Check Log Files

Logs are saved to `logs/migration_YYYYMMDD_HHMMSS.log`.

**View log in real-time**:
```bash
tail -f logs/migration_*.log
```

**Search for errors**:
```bash
grep ERROR logs/migration_*.log
```

---

## 6. Features & Behavior

### 6.1. Resume Capability

- State is saved after every batch (default: 50 tickets)
- Survives network failures, VPN disconnects, system sleep
- Delete `migration_state.json` to restart from scratch

### 6.2. Field Mapping

**Jira → GLPI Mapping**:
- **Status**: Jira status → GLPI status (1-6, 10)
- **Type**: Jira issue type → GLPI ticket type (1=Incident, 2=Request)
- **Priority**: Jira priority → GLPI Urgency + Impact (1-5 scale)
- **Classification**: Jira classification → GLPI Location + Items

### 6.3. Actors

- **Reporter (Jira)** → **Requester (GLPI)**
- **Assignee (Jira)** → **Assigned Technician (GLPI)**
- **Participants (Jira)** → **Observers (GLPI)**

**Missing Users**: If a user is not found in GLPI:
- Tracked in `missing_users.txt`
- Ticket created with API user as fallback
- Original name preserved in description

### 6.4. Dates

- **Created Date**: Preserved from Jira
- **Updated Date**: Preserved from Jira
- **Resolved Date**: Mapped to GLPI Solve Date + Close Date
- **Timezone**: Converted to UTC+7 (Vietnam)

### 6.5. Attachments

- Downloaded from Jira
- Uploaded to GLPI Documents
- Linked to tickets
- Embedded images in description

### 6.6. Comments

- Migrated as GLPI Followups
- Author preserved (if user exists in GLPI)
- Original date preserved
- Jira markup converted to HTML

### 6.7. History

- Changelog extracted from Jira
- Formatted as HTML table in description
- Includes: User, Date, Field, Original Value, New Value

### 6.8. SLA Information

- Extracted from Jira SLA fields
- Preserved in description table
- Status: Met, Breached, In Progress

---

## 7. Troubleshooting

### 7.1. Authentication Errors

**Problem**: `Failed to load configuration: Missing 'jira.pat' in config`

**Solution**:
1. Check `config.yaml` has `pat` field filled
2. Or set environment variable: `export JIRA_PAT=your_token_here`
3. Verify token is valid in Jira

---

**Problem**: `GLPI session initialization failed: Authentication error`

**Solution**:
1. Check App-Token and User-Token in `config.yaml`
2. Verify tokens are active in GLPI
3. Try fallback Basic Auth: provide `username` and `password`
4. Check GLPI API is enabled: **Setup > General > API**

---

### 7.2. SSL Certificate Issues

**Problem**: `SSL verification failed` or `certificate verify failed`

**Solution**:
1. For Jira: Set `jira.verify_ssl: false` in `config.yaml`
2. For GLPI: Provide certificate path: `glpi.verify_ssl: "glpi.pem"`
3. Or disable: `glpi.verify_ssl: false` (not recommended for production)

---

### 7.3. Missing Users

**Problem**: Many users not found in GLPI, tickets created with wrong requester

**Solution**:
1. Import all users from LDAP to GLPI first
2. Check username consistency between Jira and GLPI
3. Review `missing_users.txt` after migration
4. Import missing users manually or via LDAP sync
5. Re-run migration (delete migrated tickets first or update them)

**Check missing users**:
```bash
cat missing_users.txt
```

Format:
```
Login Name      Full Name
john.doe        John Doe
jane.smith      Jane Smith
```

---

### 7.4. Failed Attachments

**Problem**: Attachments not uploaded or linked

**Solution**:
1. Check Jira permissions: API user must access attachments
2. Verify GLPI upload limits: **Setup > General > Upload**
3. Check network bandwidth: large files may timeout
4. Review logs: `grep "attachment" logs/migration_*.log`

---

### 7.5. Status/Type Mapping Issues

**Problem**: Tickets created with wrong status or type

**Solution**:
1. Review `mappings.status` in `config.yaml`
2. Check dynamic mapping in logs: `grep "Dynamic mapping" logs/migration_*.log`
3. Add missing status mappings manually
4. Verify GLPI status IDs: **Setup > Dropdowns > Assistance > Status**

---

### 7.6. Performance Issues

**Problem**: Migration is very slow

**Solution**:
1. Reduce `batch_size` in `config.yaml` (try 10 or 20)
2. Check network latency to Jira and GLPI servers
3. Review GLPI server load and database performance
4. Disable unnecessary GLPI plugins temporarily
5. Run migration during off-peak hours

---

### 7.7. Classification Mapping Not Working

**Problem**: Location or Items not linked to tickets

**Solution**:
1. Verify classification values exist in Jira: `python list_classifications.py`
2. Check mapping in `config.yaml` matches exactly (case-sensitive)
3. Verify Location names exist in GLPI: **Setup > Dropdowns > Locations**
4. Check Item names (Business Services, Software) in GLPI: **Assets**
5. Review logs: `grep "classification" logs/migration_*.log`

---

## 8. Verification

After migration, verify the results:

### 8.1. Check Console Output

```bash
Migration complete. Total processed: 250
```

### 8.2. Check GLPI

1. Go to **Assistance > Tickets**
2. Verify ticket count matches Jira
3. Spot-check random tickets:
   - Title and description correct
   - Status, type, priority mapped correctly
   - Requester and assignee correct
   - Dates preserved (Created, Resolved)
   - Attachments linked
   - Comments migrated

### 8.3. Check Missing Users Report

```bash
cat missing_users.txt
```

If there are missing users, import them and consider re-running migration for affected tickets.

### 8.4. Check Logs

```bash
grep ERROR logs/migration_*.log
grep WARNING logs/migration_*.log
```

---

## 9. Limitations

1. **GLPI generates new IDs**: Jira ticket keys (e.g., `ITSAMPLE-123`) are preserved in the description, but GLPI assigns new ticket IDs
2. **Cannot create/sync users automatically**: Users must be imported manually or via LDAP before migration
3. **Last Update field auto-updates**: GLPI updates this field automatically, so original Jira update date is only in description
4. **Time to Own calculated by GLPI SLAs**: Cannot set historical values

---

## 10. Best Practices

### 10.1. Pre-Migration Checklist

- [ ] Import all LDAP users to GLPI
- [ ] Verify username consistency (Jira login = GLPI login)
- [ ] Disable GLPI rules temporarily (to avoid auto-actions)
- [ ] Disable GLPI authentication plugins (SSO, LDAP) if they interfere
- [ ] Backup GLPI database
- [ ] Test with debug mode first (`target_ticket_key: "ITSAMPLE-123"`)
- [ ] Run `list_classifications.py` to discover Jira classifications
- [ ] Update `config.yaml` with correct classification mappings

### 10.2. During Migration

- [ ] Monitor log file in real-time: `tail -f logs/migration_*.log`
- [ ] Don't interrupt during batch processing (wait for "State saved" message)
- [ ] Check `missing_users.txt` periodically
- [ ] Monitor GLPI server load and database performance

### 10.3. Post-Migration

- [ ] Verify ticket counts (Jira total vs GLPI created)
- [ ] Spot-check random tickets (5-10 samples)
- [ ] Review missing users report and import them
- [ ] Re-enable GLPI rules
- [ ] Update ticket assignments if needed (due to missing users)
- [ ] Communicate migration completion to team

---

## 11. Advanced Configuration

### 11.1. Custom Log Formats

Edit `common/config.yaml`:
```yaml
logging:
  format: "%(asctime)s [%(levelname)-8s] %(name)-20s: %(message)s"
  level: "DEBUG"  # For detailed field extraction and mapping logic
```

**Log Levels**:
- **DEBUG**: Detailed field extraction, mapping logic, API request/response
- **INFO**: Ticket processing progress, batch status (default)
- **WARNING**: Missing users, fallback mappings
- **ERROR**: API failures, validation errors
- **CRITICAL**: Fatal errors that stop migration

### 11.2. Multiple Environment Setups

Create separate common config files:
- `common/config.dev.yaml` (Development)
- `common/config.staging.yaml` (Staging)
- `common/config.prod.yaml` (Production)

Then create symbolic link or copy the desired config:
```bash
cp common/config.prod.yaml common/config.yaml
```

### 11.3. Parallel Migrations (Multiple Projects)

Not currently supported. Run sequentially with different folder configs:
```bash
# Edit 03_support_jira_to_glpi_assistance_tickets_migration/config.yaml
# Set project_key: "SUPPORT"
python migrate_support_tickets.py

# Edit config.yaml again
# Set project_key: "HELPDESK"
python migrate_support_tickets.py
```

---

## 12. Support & Feedback

**Issues**: Report bugs at my GitHub repository

**Questions**: Email me at thuong.lambale@gmail.com

**Logs**: Always attach log files when reporting issues
