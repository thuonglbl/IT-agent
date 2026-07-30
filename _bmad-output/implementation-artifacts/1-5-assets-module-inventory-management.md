---
baseline_commit: f6db567
---
# Story 1.5: Assets Module - Inventory Management

**Epic:** 1 (ITSOPS inventory to GLPI Assets management migration)
**Status:** done

## Story Requirements

**User Story:**
As a user, I want to migrate the SearchBox, Items, and Oracle Synchronization features from the ITSOPS Assets Inventory module to the GLPI Assets management system, so that I can search and manage inventory items and sync with Oracle within GLPI.

**Acceptance Criteria:**
- Feature: SearchBox from ITSOPS Assets > Inventory is successfully mapped and migrated to GLPI.
- Feature: Items from ITSOPS Assets > Inventory is successfully mapped and migrated to GLPI.
- Feature: Oracle Synchronization from ITSOPS Assets > Inventory is successfully mapped and migrated to GLPI.
- Migration scripts should use the database connection established in story 1.1 to read the data.

## Developer Context

This story handles the core inventory management functionality, moving item tracking and Oracle sync capabilities to GLPI.

### Technical Requirements
- Utilize `pyodbc` to query ITSOPS.
- Use `common/clients/sql_client.py` for database operations.
- Map the SearchBox and Items schemas to GLPI's Computer, Monitor, and NetworkEquipment items, utilizing `04_itsops_to_glpi_assests_migration/mapper.py` (`get_glpi_item_type` function).
- Map Oracle Synchronization records/logic if applicable.

### Database Field Mapping (ITSOPS)
Based on UI and Log analysis, the following `dbo._ITEM` database fields correspond to the ITSOPS Inventory UI:
- **General / Searchbox**:
  - `ITEM_NUMBER`: Inventory number
  - `ITEM_TYPE`: Type (e.g., LAN, NB, SRV, TFT)
  - `ITEM_MODEL`: Model
  - `ITEM_SERIAL_NUMBER`: Serial number
  - `ITEM_USER`: User's visa
  - `ITEM_OWNER`: Item's owner
  - `ITEM_USED_FOR`: Utilisation / Used for
  - `ITEM_LOCATION_OFF`: Site / Office location
  - `ITEM_CONSTRUCTOR`: Constructor
- **Technical specification**:
  - `ITEM_PROCESSOR`: Processor
  - `ITEM_PROCESSOR_MODEL`: Processor model
  - `ITEM_WORK_MEM`: RAM
  - `ITEM_STORAGE_MEM`: Hard drive
  - `ITEM_ORACLE_ASSET_ID`: Oracle Asset ID
  - `ITEM_ORACLE_ASSET_NUMBER`: Oracle Asset Number
- **Buy-Rent Info & Renewing**:
  - `ITEM_VENDOR`: Vendor / Asset's supplier
  - `ITEM_BUY_DATE`: Buy date
  - `ITEM_INVOICE_NUMBER`: Invoice number
  - `ITEM_WARRANTY`: Warranty length
  - `ITEM_PURCHASE_ORDER`: Purchase order
  - `ITEM_PRICE`: Item's price
  - `ITEM_RENTAL_NUMBER`: Rental number
  - `ITEM_WARRANTY_EXPIRATION`: Warranty expiration
  - `ITEM_RENEWAL_YEAR`: Renewal year
  - `ITEM_RENEWAL_STATE`: Renewal state

### GLPI API Mapping (Target Endpoints & Parameters)
The GLPI API endpoints will depend on the asset type (e.g., `/Computer`, `/Monitor`, `/NetworkEquipment`).
Based on the mapping documentation, UI, and Additional Fields plugin configuration, the payload parameters for the GLPI API are:

- **General Information (Main Asset Endpoint)**:
  - `name`: Name of asset = Asset type code (`ITEM_TYPE`, e.g., 'NB') + Inventory number (`ITEM_NUMBER`, e.g., '1000444') -> e.g., `NB1000444`
  - `otherserial`: Inventory/Asset Number (`ITEM_NUMBER`)
  - `serial`: Serial Number (`ITEM_SERIAL_NUMBER`)
  - `users_id`: User (`ITEM_USER` resolved to GLPI User ID)
  - `locations_id`: Location (`ITEM_LOCATION_OFF` resolved to GLPI Location ID, created automatically if missing)
  - `manufacturers_id`: Manufacturer (`ITEM_CONSTRUCTOR` resolved to GLPI Manufacturer ID, created automatically if missing)
  - `states_id`: Status / Used for (`ITEM_USED_FOR` resolved to GLPI State ID by name. Assume predefined; report missing).
  - `*types_id` (e.g., `computertypes_id`): Type (Resolved by name based on `ITEM_TYPE`. Assume predefined; report missing).
  - `*models_id` (e.g., `computermodels_id`): Model (`ITEM_MODEL` resolved to GLPI Model ID, created automatically if missing)
  - `comment`: Comments (e.g., "ITSOPS Import")

- **Additional Fields Plugin (Block: `setmap` - ID: 19 - Associated to `Users`)**:
  - `User office location`: Text field. Note: This updates the User record via `/PluginFieldsUserSetmap`, not the Asset itself!

- **Additional Fields Plugin (Block: `Technical Specification` - ID: 21 - Associated to `INVENTORY`)**:
  - `Processor`: Text field (`ITEM_PROCESSOR`)
  - `RAM`: Text field (`ITEM_WORK_MEM`)
  - `Hard drive`: Text field (`ITEM_STORAGE_MEM`)
  - `Oracle Asset ID`: Text field (`ITEM_ORACLE_ASSET_ID`)
  - `Oracle Asset Number`: Text field (`ITEM_ORACLE_ASSET_NUMBER`)
  *(Note: API endpoint usually `/PluginFieldsComputerTechnicalspecification` depending on the item class).*

- **Additional Fields Plugin (Block: `Renewing` - ID: 23 - Associated to `INVENTORY`)**:
  - `Warranty expiration`: Date field (`ITEM_WARRANTY_EXPIRATION`)
  - `Renewal state`: Text field (`ITEM_RENEWAL_STATE`)

- **Additional Fields Plugin (Block: `ITSOPS Log` - ID: 24 - Associated to `INVENTORY`)**:
  - `ITSOP Log`: Rich Text field. Contains historical logs from ITSOPS.

- **Buy-Rent Info / Financial & Administrative Information (Endpoint: `/Infocom`)**:
  - `suppliers_id`: Supplier / Vendor (`ITEM_VENDOR` resolved to Supplier ID)
  - `date_creation` / `buy_date`: Date of Purchase (`ITEM_BUY_DATE`)
  - `order_number`: Order Number / Purchase order (`ITEM_PURCHASE_ORDER`)
  - `delivery_number` / `invoice_number`: Invoice Number (`ITEM_INVOICE_NUMBER`)
  - `value`: Value / Item's price (`ITEM_PRICE`)
  - `immo_number`: Immobilization Number / Rental number (`ITEM_RENTAL_NUMBER`)
  - `warranty_duration`: Warranty Duration / length (`ITEM_WARRANTY`)

### Architecture Compliance
- Use the two-level configuration structure (`common/config.yaml` and `04_itsops_to_glpi_assests_migration/config.yaml`).
- Maintain modular structure for migration scripts.
- Ensure mapping correctly handles `ITEM_TYPE` from ITSOPS (`LAN`, `NB`, `SRV`, `TFT`) to GLPI structure.

### Library/Framework Requirements
- `pyodbc` for SQL Server connections.
- `requests` if using GLPI API.

### File Structure Requirements
- Update `04_itsops_to_glpi_assests_migration/main.py` or create a specific module (e.g., `04_itsops_to_glpi_assests_migration/inventory.py`) for inventory migration.
- Add tests in `04_itsops_to_glpi_assests_migration/tests/`.

### Testing Requirements
- Unit tests for the data extraction and mapping logic.
- Ensure integration with `SQLClient` doesn't break.
- Must ensure that any tests verify mapping correctly and safely handle missing data.

## Previous Story Intelligence
- **Dev notes and learnings from story 1.2:** 
  - We used Windows Auth fallback for SQLClient. Keep tests robust against explicit vs implicit auth credentials. 
  - `main.py` must handle config dictionary loading safely without NoneType errors. 
  - Use fetchmany/yield to avoid loading massive tables into memory. 
  - Fix NULL handling to avoid inserting literal 'None' string. 
  - Exception handling in `main.py` must not abort the loop on a single failure.

## Git Intelligence Summary
Recent work pattern: The system structure utilizes tests inside the specific module folder (`04_itsops_to_glpi_assests_migration/tests`). Code includes `dashboard.py` and `main.py` utilizing the fetchmany/yield pattern to process data.

## Project Context Reference
- [USER_GUIDE.md](file:///c:/Users/laub/source/repos/IT-agent/04_itsops_to_glpi_assests_migration/USER_GUIDE.md)

Status: in-progress

## Tasks/Subtasks
- [x] Map SearchBox, Items, and Oracle Synchronization schema from ITSOPS to GLPI.
- [x] Implement data extraction logic for these features (using `fetchmany`/`yield`).
- [x] Implement data ingestion logic for GLPI.
- [x] Write unit tests for extraction and ingestion.

### Review Findings
- [x] [Review][Patch] Fix `.capitalize()` string formatting bug in `PluginFields` endpoint for multi-word asset types (e.g. `NetworkEquipment`) [`04_itsops_to_glpi_assests_migration/inventory.py`:240]
- [x] [Review][Patch] Add missing field mappings (`ITEM_OWNER`, `ITEM_PROCESSOR_MODEL`, `ITEM_RENEWAL_YEAR`) [`04_itsops_to_glpi_assests_migration/inventory.py`:76]
- [x] [Review][Patch] Fix unclosed database cursor in `extract_inventory_items` by using try...finally [`04_itsops_to_glpi_assests_migration/inventory.py`:204]
- [x] [Review][Patch] Add input sanitization for SQL schema string in `extract_inventory_items` [`04_itsops_to_glpi_assests_migration/inventory.py`:203]
- [x] [Review][Patch] Avoid inserting empty strings for optional main payload fields (`serial`, `otherserial`) [`04_itsops_to_glpi_assests_migration/inventory.py`:118]
- [x] [Review][Patch] Clean `ITEM_PRICE` and `ITEM_WARRANTY` before inserting into Infocom [`04_itsops_to_glpi_assests_migration/inventory.py`:180]
- [x] [Review][Patch] Expand `safe_str` to strip `'null'`, `'n/a'`, `'-'` placeholders [`04_itsops_to_glpi_assests_migration/inventory.py`:10]
- [x] [Review][Patch] Add unit tests for `NetworkEquipment` multi-word ingestion and missing fields [`04_itsops_to_glpi_assests_migration/tests/test_inventory.py`:45]

## Dev Agent Record
**Completion Notes:**
- Created `inventory.py` to handle extraction, mapping, and ingestion for ITSOPS inventory items, SearchBox features, and Oracle synchronization fields.
- Implemented `safe_str` helper to prevent inserting literal `'None'` or `'none'` strings when processing nullable columns from SQL Server.
- Configured dropdown resolution (`resolve_dropdown`) for Manufacturers, Locations, Models, States, Types, and Suppliers with appropriate auto-creation logic.
- Integrated `inventory.extract_inventory_items` (using `fetchmany(batch_size)` generator pattern), `inventory.map_inventory_item`, and `inventory.ingest_inventory_item` into `main.py`.
- Verified all unit tests pass (18/18 tests in `04_itsops_to_glpi_assests_migration`).

## File List
- `04_itsops_to_glpi_assests_migration/inventory.py`
- `04_itsops_to_glpi_assests_migration/tests/test_inventory.py`
- `04_itsops_to_glpi_assests_migration/main.py`
- `04_itsops_to_glpi_assests_migration/tests/test_main.py`

## Change Log
- **2026-07-27**: Implemented SearchBox, Items, and Oracle Synchronization extraction, mapping, and ingestion in `inventory.py`. Updated `main.py` orchestration and unit tests. All 18 tests passing.

## Status Update
Status: completed
