import unittest
from unittest.mock import MagicMock, call, patch
import sys
from pathlib import Path

# Add project root and migration dir to path
project_root = Path(__file__).resolve().parent.parent.parent
migration_dir = Path(__file__).resolve().parent.parent

if str(migration_dir) not in sys.path:
    sys.path.insert(0, str(migration_dir))
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

import inventory

class TestInventoryMigration(unittest.TestCase):
    def setUp(self):
        self.sql_client_mock = MagicMock()
        self.cursor_mock = MagicMock()
        self.sql_client_mock.conn.cursor.return_value = self.cursor_mock
        
        self.glpi_client_mock = MagicMock()
        # Setup default mock return values for ID lookups
        self.glpi_client_mock.get_user_id_by_email.return_value = 101
        self.glpi_client_mock.get_location_id.return_value = 201
        def mock_get_item_id(item_type, name):
            print(f"MOCK CALLED: {repr(item_type)}, {repr(name)}")
            return {
                ("Manufacturer", "Dell"): 301,
                ("State", "In Use"): 401,
                ("Glpi\\CustomAsset\\INVENTORYAssetType", "Laptop"): 501,
                ("Glpi\\CustomAsset\\INVENTORYAssetModel", "Latitude 7420"): 601,
                ("Supplier", "TechSupply"): 701,
                ("Glpi\\CustomDropdown\\InventoryOwnerDropdown", "John Doe"): 101,
            }.get((item_type, name), None)
            
        self.glpi_client_mock.get_item_id.side_effect = mock_get_item_id
        self.glpi_client_mock.create_item.return_value = 999

    def test_safe_str(self):
        self.assertEqual(inventory.safe_str("Hello"), "Hello")
        self.assertEqual(inventory.safe_str(None), "")
        self.assertEqual(inventory.safe_str("None"), "")
        self.assertEqual(inventory.safe_str("none"), "")
        self.assertEqual(inventory.safe_str("null"), "")
        self.assertEqual(inventory.safe_str("N/A"), "")
        self.assertEqual(inventory.safe_str("-"), "")
        self.assertEqual(inventory.safe_str(" 1000444 "), "1000444")
        self.assertEqual(inventory.safe_str(None, default="Unknown"), "Unknown")

    def test_map_inventory_item_computer(self):
        row = {
            'ITEM_NUMBER': '1000444',
            'ITEM_TYPE': 'NB',
            'ITEM_MODEL': 'Latitude 7420',
            'ITEM_SERIAL_NUMBER': 'SN123456',
            'ITEM_USER': 'john.doe@example.com',
            'ITEM_OWNER': 'John Doe',
            'ITEM_USED_FOR': 'In Use',
            'ITEM_LOCATION_OFF': 'Paris Office',
            'ITEM_LOCATION_BAT': 'Building A',
            'ITEM_CONSTRUCTOR': 'Dell',
            'ITEM_PROCESSOR': 'i7-1185G7',
            'ITEM_PROCESSOR_MODEL': 'Core i7',
            'ITEM_WORK_MEM': '16GB',
            'ITEM_STORAGE_MEM': '512GB SSD',
            'ORC_AssetId': 'ORC-101',
            'ORC_AssetNumber': 'ORC-NUM-202',
            'ITEM_VENDOR': 'TechSupply',
            'ITEM_BUY_DATE': '2022-01-15',
            'ITEM_INVOICE': 'INV-2022-001',
            'ITEM_WARRANTY': '36 months',
            'ITEM_PURCHASE_ORDER': 'PO-555',
            'ITEM_PRICE': '$1,200.50',
            'ITEM_RENTAL_NUMBER': 'RNT-100',
            'ITEM_WARRANTY_EXPIRY_DATE': '2025-01-15',
            'ITEM_RENEWAL_YEAR': '2025',
            'ITEM_RENEWAL': 'Active',
            'ITEM_LOG': 'Initial setup completed in 2022.'
        }
        
        glpi_type, main_payload, aux_payloads = inventory.map_inventory_item(row, glpi_client=self.glpi_client_mock)
        
        self.assertEqual(glpi_type, 'Glpi\\CustomAsset\\INVENTORYAsset')
        self.assertEqual(main_payload['name'], 'NB1000444')
        self.assertEqual(main_payload['otherserial'], '1000444')
        self.assertEqual(main_payload['serial'], 'SN123456')
        self.assertEqual(main_payload['users_id'], 101)
        self.assertEqual(main_payload['locations_id'], 201)
        self.assertEqual(main_payload['manufacturers_id'], 301)
        self.assertEqual(main_payload['states_id'], 401)
        self.assertEqual(main_payload['assets_assettypes_id'], 501)
        self.assertEqual(main_payload['assets_assetmodels_id'], 601)
        self.assertEqual(main_payload['comment'], 'ITSOPS-Import')
        
        # Verify aux payloads
        self.assertEqual(aux_payloads['technical_spec']['processorfield'], 'i7-1185G7 - Core i7')
        self.assertEqual(aux_payloads['technical_spec']['ramfield'], '16GB')
        self.assertEqual(aux_payloads['technical_spec']['harddrivefield'], '512GB SSD')
        self.assertEqual(aux_payloads['technical_spec']['oracleassetidfield'], 'ORC-101')
        self.assertEqual(aux_payloads['technical_spec']['oracleassetnumberfield'], 'ORC-NUM-202')
        
        self.assertEqual(aux_payloads['renewing']['warrantyexpirationfield'], '2025-01-15')
        self.assertEqual(aux_payloads['renewing']['renewalstatefield'], 'Active')
        
        self.assertEqual(aux_payloads['itsops_log']['itsoplogfield'], 'Initial setup completed in 2022.')
        
        self.assertEqual(aux_payloads['infocom']['suppliers_id'], 701)
        self.assertEqual(aux_payloads['infocom']['buy_date'], '2022-01-15')
        self.assertEqual(aux_payloads['infocom']['order_number'], 'PO-555')
        self.assertEqual(aux_payloads['infocom']['bill'], 'INV-2022-001')
        self.assertEqual(aux_payloads['infocom']['value'], '1200.50')
        self.assertEqual(aux_payloads['infocom']['immo_number'], 'RNT-100')
        self.assertEqual(aux_payloads['infocom']['warranty_duration'], '36 months')

    def test_map_inventory_item_nulls(self):
        row = {
            'ITEM_NUMBER': '2000111',
            'ITEM_TYPE': 'LAN',
            'ITEM_MODEL': 'None',
            'ITEM_SERIAL_NUMBER': None,
            'ITEM_USER': None,
            'ITEM_LOCATION_OFF': None,
            'ITEM_CONSTRUCTOR': 'None',
            'ITEM_PROCESSOR': None,
            'ITEM_ORACLE_ASSET_ID': None
        }
        
        glpi_type, main_payload, aux_payloads = inventory.map_inventory_item(row, glpi_client=None)
        self.assertEqual(glpi_type, 'Glpi\\CustomAsset\\INVENTORYAsset')
        self.assertEqual(main_payload['name'], 'LAN2000111')
        self.assertNotIn('serial', main_payload)
        self.assertEqual(main_payload['otherserial'], '2000111')
        
        # Ensure no 'None' literal string in technical_spec or comment
        self.assertNotIn('None', str(aux_payloads.get('technical_spec', {})))

    def test_extract_inventory_items(self):
        self.cursor_mock.description = [('ITEM_NUMBER',), ('ITEM_TYPE',)]
        self.cursor_mock.fetchmany.side_effect = [[('1000444', 'NB'), ('2000111', 'LAN')], []]
        
        results = list(inventory.extract_inventory_items(self.sql_client_mock, limit=2, batch_size=10, shared_erp_db="MOCK_SHARED_ERP_DB"))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['ITEM_NUMBER'], '1000444')
        self.assertEqual(results[1]['ITEM_TYPE'], 'LAN')
        expected_query = """
        SELECT TOP 2 
            i.*,
            CASE 
                WHEN i.ITEM_USED_FOR = 'PWS' THEN ldap.physicalDeliveryOfficeName
                ELSE i.ITEM_LOCATION_OFF
            END AS EMPLOYEE_LOCATION,
            e.Visa AS EMPLOYEE_VISA,
            e.Email AS EMPLOYEE_EMAIL,
            (SELECT MODITEM_USER, MODITEM_DATE, MODITEM_FIELD, MODITEM_OLDVALUE, MODITEM_NEWVALUE, MODITEM_REASON 
             FROM [dbo].[MODITEM] m 
             WHERE m.ITEM_ID = i.ITEM_ID 
             ORDER BY MODITEM_DATE DESC 
             FOR JSON AUTO) as MODITEM_JSON
        FROM [dbo].[_ITEM] i
        OUTER APPLY (
            SELECT TOP 1 Visa, Email
            FROM [dbo].[Employee_View] ev
            WHERE ev.Id = i.ITEM_USER_ID
        ) e
        OUTER APPLY (
            SELECT TOP 1 physicalDeliveryOfficeName
            FROM [MOCK_SHARED_ERP_DB].[dbo].[LDAP_Users] lu
            WHERE lu.sAMAccountName = e.Visa
            ORDER BY lu.whenChanged DESC
        ) ldap
    
        ORDER BY i.ID
    """
        self.cursor_mock.execute.assert_called_with(expected_query)
        self.cursor_mock.fetchmany.assert_called_with(10)
        self.cursor_mock.close.assert_called_once()

    def test_extract_inventory_items_with_start_after_id(self):
        self.cursor_mock.description = [('ITEM_NUMBER',), ('ITEM_TYPE',)]
        self.cursor_mock.fetchmany.side_effect = [[('3000555', 'SRV')], []]
        
        results = list(inventory.extract_inventory_items(self.sql_client_mock, limit=1, start_after_id=5000, batch_size=10, shared_erp_db="MOCK_SHARED_ERP_DB"))
        self.assertEqual(len(results), 1)
        
        expected_query = """
        SELECT TOP 1 
            i.*,
            CASE 
                WHEN i.ITEM_USED_FOR = 'PWS' THEN ldap.physicalDeliveryOfficeName
                ELSE i.ITEM_LOCATION_OFF
            END AS EMPLOYEE_LOCATION,
            e.Visa AS EMPLOYEE_VISA,
            e.Email AS EMPLOYEE_EMAIL,
            (SELECT MODITEM_USER, MODITEM_DATE, MODITEM_FIELD, MODITEM_OLDVALUE, MODITEM_NEWVALUE, MODITEM_REASON 
             FROM [dbo].[MODITEM] m 
             WHERE m.ITEM_ID = i.ITEM_ID 
             ORDER BY MODITEM_DATE DESC 
             FOR JSON AUTO) as MODITEM_JSON
        FROM [dbo].[_ITEM] i
        OUTER APPLY (
            SELECT TOP 1 Visa, Email
            FROM [dbo].[Employee_View] ev
            WHERE ev.Id = i.ITEM_USER_ID
        ) e
        OUTER APPLY (
            SELECT TOP 1 physicalDeliveryOfficeName
            FROM [MOCK_SHARED_ERP_DB].[dbo].[LDAP_Users] lu
            WHERE lu.sAMAccountName = e.Visa
            ORDER BY lu.whenChanged DESC
        ) ldap
     WHERE i.ID > 5000
        ORDER BY i.ID
    """
        self.cursor_mock.execute.assert_called_with(expected_query)
        self.cursor_mock.fetchmany.assert_called_with(10)
        self.cursor_mock.close.assert_called_once()

    def test_ingest_inventory_item_network_equipment_endpoint_formatting(self):
        glpi_type = 'NetworkEquipment'
        main_payload = {'name': 'LAN2000111'}
        aux_payloads = {
            'technical_spec': {'oracle_asset_id': 'ORCL-100'},
            'renewing': {'renewal_state': 'Active'}
        }
        self.glpi_client_mock.create_item.side_effect = [888, 889, 890]
        
        asset_id = inventory.ingest_inventory_item(self.glpi_client_mock, glpi_type, main_payload, aux_payloads)
        self.assertEqual(asset_id, 888)
        
        # Verify exact PascalCase endpoint formatting for multi-word asset type
        self.glpi_client_mock.create_item.assert_any_call(
            'PluginFieldsNetworkEquipmentTechnicalspecification',
            {'items_id': 888, 'itemtype': 'NetworkEquipment', 'oracle_asset_id': 'ORCL-100'}
        )
        self.glpi_client_mock.create_item.assert_any_call(
            'PluginFieldsNetworkEquipmentRenewing',
            {'items_id': 888, 'itemtype': 'NetworkEquipment', 'renewal_state': 'Active'}
        )

    def test_ingest_inventory_item_failure(self):
        glpi_type = 'Computer'
        main_payload = {'name': 'NB1000444'}
        aux_payloads = {'infocom': {'value': '1000'}}
        
        # Mock main asset creation failure (returning None)
        self.glpi_client_mock.create_item.return_value = None
        
        asset_id = inventory.ingest_inventory_item(self.glpi_client_mock, glpi_type, main_payload, aux_payloads)
        self.assertIsNone(asset_id)
        # Verify that only 1 call was made (to create main asset), and aux items were NOT created
        self.assertEqual(self.glpi_client_mock.create_item.call_count, 1)

if __name__ == '__main__':
    unittest.main()
