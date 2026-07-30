import unittest
from unittest.mock import patch
import sys

from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from common.clients.sql_client import SQLClient

class TestSQLClient(unittest.TestCase):
    @patch('common.clients.sql_client.pyodbc')
    def test_connect_with_credentials(self, mock_pyodbc):
        client = SQLClient(server='test_server', database='test_db', username='test_user', password='test_password')
        client.connect()
        
        expected_conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=test_server;DATABASE=test_db;UID=test_user;PWD=test_password'
        mock_pyodbc.connect.assert_called_once_with(expected_conn_str)
        self.assertIsNotNone(client.conn)

    @patch('common.clients.sql_client.pyodbc')
    def test_connect_windows_auth(self, mock_pyodbc):
        # Empty credentials
        client = SQLClient(server='test_server', database='test_db', username='', password='')
        client.connect()
        
        expected_conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=test_server;DATABASE=test_db;Trusted_Connection=yes;'
        mock_pyodbc.connect.assert_called_once_with(expected_conn_str)
        self.assertIsNotNone(client.conn)
        
    @patch('common.clients.sql_client.pyodbc')
    def test_connect_windows_auth_none(self, mock_pyodbc):
        # None credentials
        client = SQLClient(server='test_server', database='test_db', username=None, password=None)
        client.connect()
        
        expected_conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=test_server;DATABASE=test_db;Trusted_Connection=yes;'
        mock_pyodbc.connect.assert_called_once_with(expected_conn_str)
        self.assertIsNotNone(client.conn)

if __name__ == '__main__':
    unittest.main()
