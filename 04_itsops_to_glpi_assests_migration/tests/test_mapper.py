import unittest
import sys
from pathlib import Path

# Add migration dir to path
migration_dir = Path(__file__).resolve().parent.parent
if str(migration_dir) not in sys.path:
    sys.path.insert(0, str(migration_dir))

import mapper

class TestMapper(unittest.TestCase):
    def test_get_glpi_item_type(self):
        # Test exact mappings from PDF specification
        self.assertEqual(mapper.get_glpi_item_type("BEA"), "Peripheral")
        self.assertEqual(mapper.get_glpi_item_type("CRT"), "Monitor")
        self.assertEqual(mapper.get_glpi_item_type("DKS"), "Peripheral")
        self.assertEqual(mapper.get_glpi_item_type("EXT"), "Peripheral")
        self.assertEqual(mapper.get_glpi_item_type("LAN"), "NetworkEquipment")
        self.assertEqual(mapper.get_glpi_item_type("MOB"), "Phone")
        self.assertEqual(mapper.get_glpi_item_type("NB"), "Computer")
        self.assertEqual(mapper.get_glpi_item_type("PC"), "Computer")
        self.assertEqual(mapper.get_glpi_item_type("PHD"), "Peripheral")
        self.assertEqual(mapper.get_glpi_item_type("PRT"), "Printer")
        self.assertEqual(mapper.get_glpi_item_type("SRV"), "Computer")
        self.assertEqual(mapper.get_glpi_item_type("SXT"), "Computer")
        self.assertEqual(mapper.get_glpi_item_type("TAB"), "Phone")
        self.assertEqual(mapper.get_glpi_item_type("TEL"), "Phone")
        self.assertEqual(mapper.get_glpi_item_type("TFT"), "Monitor")
        self.assertEqual(mapper.get_glpi_item_type("WAN"), "NetworkEquipment")
        self.assertEqual(mapper.get_glpi_item_type("WS"), "Computer")
        
        # Test case insensitivity and fallback
        self.assertEqual(mapper.get_glpi_item_type("nb"), "Computer")
        self.assertEqual(mapper.get_glpi_item_type("UNKNOWN_CODE"), "Peripheral")
        self.assertEqual(mapper.get_glpi_item_type(None), "Peripheral")

    def test_get_item_type_label(self):
        self.assertEqual(mapper.get_item_type_label("NB"), "Laptop")
        self.assertEqual(mapper.get_item_type_label("TFT"), "Screen")
        self.assertEqual(mapper.get_item_type_label("TEL"), "Fix Phone")
        self.assertEqual(mapper.get_item_type_label(""), "")

    def test_get_item_used_for_label(self):
        self.assertEqual(mapper.get_item_used_for_label("STK"), "Stock")
        self.assertEqual(mapper.get_item_used_for_label("BRW"), "Loan")
        self.assertEqual(mapper.get_item_used_for_label("SVN"), "Vietnam Workstation")
        self.assertEqual(mapper.get_item_used_for_label("UKN"), "Unknow")
        self.assertEqual(mapper.get_item_used_for_label(""), "")

    def test_map_item_to_glpi(self):
        row = {
            'ITEM_NUMBER': '1000444',
            'ITEM_TYPE': 'NB',
            'ITEM_MODEL': 'Latitude 7420',
            'ITEM_SERIAL_NUMBER': 'SN123456',
            'ITEM_CONSTRUCTOR': 'Dell',
            'ITEM_OS': 'Windows 11',
            'ITEM_OWNER': 'John Doe'
        }
        glpi_type, payload = mapper.map_item_to_glpi(row)
        self.assertEqual(glpi_type, "Computer")
        self.assertEqual(payload["name"], "NB1000444")
        self.assertEqual(payload["otherserial"], "1000444")
        self.assertEqual(payload["serial"], "SN123456")
        self.assertIn("Owner: John Doe", payload["comment"])
        self.assertIn("Constructor: Dell", payload["comment"])

if __name__ == '__main__':
    unittest.main()
