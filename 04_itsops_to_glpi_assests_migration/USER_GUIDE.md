# User Guide: ITSOPS to GLPI Assets Migration Script

This script automates the migration of IT assets from the legacy ITSOPS SQL Server database to the GLPI Assets Management system via the GLPI API.

## 1. Directory Structure

Inside the `04_itsops_to_glpi_assests_migration` folder, you will find:

```
04_itsops_to_glpi_assests_migration/
├── main.py                     # Main migration script
├── mapper.py                   # Data transformation and mapping logic (ITSOPS -> GLPI)
└── requirements.txt            # Python dependencies (including pyodbc)
```

**Common Library** (shared across all migrations):
```
common/
├── clients/
│   ├── glpi_client.py          # GLPI API client (Asset creation operations)
│   └── sql_client.py           # SQL Server database client
└── config.yaml                 # Shared configurations (GLPI tokens, Logging)
```

**Configuration Files**:
- `common/config.yaml`: Centralized configuration for GLPI tokens, migration defaults, and Logging.
- `04_itsops_to_glpi_assests_migration/config.yaml`: Folder-specific configuration for the ITSOPS SQL Database.

## 2. Prerequisites

### Install Python
Ensure Python 3.x is installed on your system.
```bash
python --version
```

### Install OBDC Driver
Since this script connects directly to SQL Server, ensure that you have **ODBC Driver 17 for SQL Server** installed on your Windows machine. If you use SQL Server Management Studio (SSMS) on the same machine, you likely already have it.

You can verify if the driver is installed by running the following command in PowerShell:
```powershell
Get-OdbcDriver -Name "ODBC Driver 17 for SQL Server"
```
If it returns a result, the driver is installed. If not, you need to download and install it from Microsoft's website.

### Install Dependencies
Open a Command Prompt or Terminal in the project folder and run:
```bash
pip install -r .\04_itsops_to_glpi_assests_migration\requirements.txt
```

### GLPI Configuration (API & Tokens)
Refer to the instructions in `01_confluence_to_glpi_migration` to acquire your **App-Token** and **User-Token** for GLPI.

## 3. Configuration Setup

This script uses a two-level configuration structure. You need to configure both the shared settings and the project-specific settings.

### Step 1: Configure GLPI Settings (Shared)
Open `common/config.yaml` and ensure the `glpi` block is filled with your GLPI URL, App-Token, and User-Token:

```yaml
glpi:
  url: "YourGlpiApiUrl"
  app_token: "YourAppToken"
  user_token: "YourUserToken"
```

### Step 2: Configure Database Settings (Project-Specific)
Copy `04_itsops_to_glpi_assests_migration/config.yaml.example` to `04_itsops_to_glpi_assests_migration/config.yaml`.
Open the new `config.yaml` file and fill in the `database` section with your target SQL server details. 

If you are using **SSO (Windows Authentication)**, leave the `username` and `password` blank:

```yaml
database:
  server: "server-name"
  database: "database-name"
  username: "user-name"  # Leave blank for Windows Authentication
  password: "password"
  driver: "{ODBC Driver 17 for SQL Server}"
```

### Step 3: Migration Debug Settings
In the `common/config.yaml` file, it's recommended to test with a small batch first using the `migration` section:

```yaml
migration:
  batch_size: 10
  debug: true
```
When `debug` is set to `true`, the script will only pull up to `batch_size` items from the database. Set `debug: false` to migrate the entire database.

## 4. Testing the Database Connection

Because connecting to the database correctly is critical, a dedicated script is provided to test your configuration without running the full migration process (which would push data to GLPI).

1. Ensure your `config.yaml` is fully configured with your database credentials.
2. Run the test script from your project root directory:
   ```bash
   python .\04_itsops_to_glpi_assests_migration\test_db_connection.py
   ```
3. The script will attempt to connect to your SQL Server and fetch the first 3 rows of data. It will print out a sample of the data or clearly display any connection errors that need to be addressed.

## 5. Running the Migration

Run the main migration script from your project root directory:

```bash
python .\04_itsops_to_glpi_assests_migration\main.py
```

Check your console output and the `logs/migration_*.log` files to monitor the progress and identify any records that failed to migrate.

## 6. Inventory Data Mapping

This section details the extraction and mapping of inventory items, SearchBox features, and Oracle Synchronization from ITSOPS to GLPI.

* **ITSOPS Screen:** Assets > Inventory
* **ITSOPS Source (SQL):** `dbo._ITEM` table
* **GLPI Target Endpoints:**
  * **Main Asset Endpoints:** `Computer`, `Monitor`, `NetworkEquipment`, `Peripheral`, `Printer`, `Phone` (mapped dynamically via `ITEM_TYPE` short codes in `mapper.py`)
  * **Financial & Purchase Endpoint:** `/Infocom`
  * **Plugin Fields Endpoints:** `PluginFields<AssetType>Technicalspecification`, `PluginFields<AssetType>Renewing`, `PluginFields<AssetType>Itsopslog`, `PluginFieldsUserSetmap`

### Mapping Details:

1. **General Information (Main Asset Endpoint)**
   * `ITEM_TYPE` + `ITEM_NUMBER` -> `name` (Asset type code + Inventory number)
   * `ITEM_NUMBER` -> `otherserial` (Internal Inventory Number)
   * `ITEM_SERIAL_NUMBER` -> `serial`
   * `ITEM_USER` -> `users_id` (Resolved to GLPI User ID)
   * `ITEM_LOCATION_OFF` -> `locations_id` (Resolved/auto-created Location ID)
   * `ITEM_CONSTRUCTOR` -> `manufacturers_id` (Resolved/auto-created Manufacturer ID)
   * `ITEM_USED_FOR` -> `states_id` (Resolved GLPI State ID)
   * `ITEM_TYPE` -> `*types_id` (e.g., `computertypes_id`)
   * `ITEM_MODEL` -> `*models_id` (e.g., `computermodels_id`, auto-created)
   * `ITEM_OWNER`, `ITEM_CONSTRUCTOR`, `ITEM_OS` -> `comment`

2. **Technical Specification Plugin (`PluginFields<AssetType>Technicalspecification`)**
   * `ITEM_PROCESSOR` -> `processor`
   * `ITEM_PROCESSOR_MODEL` -> `processor_model`
   * `ITEM_WORK_MEM` -> `ram`
   * `ITEM_STORAGE_MEM` -> `hard_drive`
   * `ITEM_ORACLE_ASSET_ID` -> `oracle_asset_id`
   * `ITEM_ORACLE_ASSET_NUMBER` -> `oracle_asset_number`

3. **Renewing Plugin (`PluginFields<AssetType>Renewing`)**
   * `ITEM_WARRANTY_EXPIRATION` -> `warranty_expiration`
   * `ITEM_RENEWAL_YEAR` -> `renewal_year`
   * `ITEM_RENEWAL_STATE` -> `renewal_state`

4. **Buy-Rent & Financial Info (`/Infocom`)**
   * `ITEM_VENDOR` -> `suppliers_id` (Resolved/auto-created Supplier ID)
   * `ITEM_BUY_DATE` -> `buy_date`
   * `ITEM_PURCHASE_ORDER` -> `order_number`
   * `ITEM_INVOICE` -> `invoice_number`
   * `ITEM_PRICE` -> `value` (Cleaned numeric value)
   * `ITEM_RENTAL_NUMBER` -> `immo_number`
   * `ITEM_WARRANTY` -> `warranty_duration`

5. **User Office Location Plugin (`PluginFieldsUserSetmap`)**
   * `ITEM_LOCATION_OFF` + `ITEM_USER` -> `user_office_location` mapped to `users_id`

6. **ITSOPS Logs Plugin (`PluginFields<AssetType>Itsopslog`)**
   * `ITEM_LOG` / `ITSOP_LOG` -> `itsop_log`