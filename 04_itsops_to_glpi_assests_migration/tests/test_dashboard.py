import unittest
from unittest.mock import MagicMock
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dashboard import extract_recent_activities, extract_inventory_statistics, map_recent_activity, map_inventory_statistic

class TestDashboardMigration(unittest.TestCase):
    
    def setUp(self):
        self.sql_client_mock = MagicMock()
        self.cursor_mock = MagicMock()
        self.sql_client_mock.conn.cursor.return_value = self.cursor_mock

    def test_extract_recent_activities(self):
        self.cursor_mock.description = [('ID',), ('Action_Name',)]
        self.cursor_mock.fetchmany.side_effect = [[(1, 'Create')], []]
        
        results = list(extract_recent_activities(self.sql_client_mock, limit=1))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['Action_Name'], 'Create')
        self.cursor_mock.execute.assert_called_with("SELECT TOP 1 * FROM dbo.ITEM_ACTION_LOGS")

    def test_extract_inventory_statistics(self):
        self.cursor_mock.description = [('Id',), ('Row_Count',), ('KPI_Name',)]
        self.cursor_mock.fetchmany.side_effect = [[(1, 100, 'Total Assets')], []]
        
        results = list(extract_inventory_statistics(self.sql_client_mock, limit=1))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['KPI_Name'], 'Total Assets')
        self.cursor_mock.execute.assert_called_with("SELECT TOP 1 r.*, d.Name as KPI_Name FROM dbo.KPI_Result r JOIN dbo.KPI_Definition d ON r.Def_Id = d.Id")

    def test_map_recent_activity(self):
        row = {
            "Action_Name": "Login",
            "Requestor_Visa": "admin",
            "Launched_On": "2023-01-01 10:00:00",
            "Action_Result": "Success"
        }
        glpi_type, payload = map_recent_activity(row)
        
        self.assertEqual(glpi_type, "Reminder")
        self.assertEqual(payload["name"], "Activity: Login by admin")
        self.assertIn("Action: Login", payload["text"])
        self.assertIn("Result: Success", payload["text"])
        self.assertEqual(payload["state"], 0)

    def test_map_inventory_statistic(self):
        row = {
            'KPI_Name': 'Total Assets',
            'Run_Date': '2023-01-01',
            'Row_Count': 42,
            'Row_Criteria_01': 'Test Criteria'
        }
        item_type, payload = map_inventory_statistic(row)
        self.assertEqual(item_type, 'Stat')
        self.assertEqual(payload['name'], 'Total Assets')
        self.assertEqual(payload['value'], 42)
        self.assertEqual(payload['comment'], 'Test Criteria')

if __name__ == '__main__':
    unittest.main()

