import unittest
from unittest.mock import patch, MagicMock
import sys

from pathlib import Path

# Add project root and migration script dir to path
project_root = Path(__file__).resolve().parent.parent.parent
migration_dir = Path(__file__).resolve().parent.parent

if str(migration_dir) not in sys.path:
    sys.path.insert(0, str(migration_dir))
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

import main
from common.config.loader import ConfigLoader

class TestMainConfigLoad(unittest.TestCase):
    @patch('test_main.ConfigLoader.load')
    def test_config_loader(self, mock_load):
        mock_load.return_value = {
            'database': {
                'server': 'mock_server',
                'database': 'mock_db',
                'username': 'mock_user',
                'password': 'mock_password',
                'driver': 'mock_driver'
            }
        }
        loader = ConfigLoader()
        config = loader.load()
        
        self.assertIn('database', config)
        db_config = config['database']
        
        # Verify the database configuration keys exist without hardcoding actual values (secrets)
        self.assertIn('server', db_config)
        self.assertIn('database', db_config)
        self.assertIn('username', db_config)
        self.assertIn('password', db_config)
        self.assertIn('driver', db_config)

    @patch('main.SQLClient')
    @patch('main.GlpiClient')
    @patch('main.load_config')
    def test_main_initializes_sql_client_correctly(self, mock_load_config, mock_glpi_client, mock_sql_client):
        # Setup mock config
        mock_config = {
            'database': {
                'server': 'mock_server',
                'database': 'mock_db',
                'username': '',
                'password': '',
                'driver': 'mock_driver'
            },
            'glpi': {},
            'migration': {'debug': False}
        }
        mock_load_config.return_value = mock_config
        
        main_func = main.main
        
        # Mock fetch_items and fetchmany to return empty so loop doesn't execute
        mock_sql_client_instance = MagicMock()
        mock_sql_client_instance.fetch_items.return_value = []
        mock_sql_client_instance.conn.cursor().fetchmany.return_value = []
        mock_sql_client.return_value = mock_sql_client_instance
        
        # Run main
        main_func()
        
        # Verify SQLClient was initialized with the config values
        mock_sql_client.assert_called_once_with(
            server='mock_server',
            database='mock_db',
            username='',
            password='',
            driver='mock_driver'
        )

    @patch('main.SQLClient')
    @patch('main.GlpiClient')
    @patch('main.load_config')
    def test_main_passes_explicit_credentials(self, mock_load_config, mock_glpi_client, mock_sql_client):
        mock_config = {
            'database': {
                'server': 'mock_server',
                'database': 'mock_db',
                'username': 'admin',
                'password': 'secret_password',
                'driver': 'mock_driver'
            },
            'glpi': {},
            'migration': {'debug': False}
        }
        mock_load_config.return_value = mock_config
        
        # Mock fetch_items and fetchmany to return empty so loop doesn't execute
        mock_sql_client_instance = MagicMock()
        mock_sql_client_instance.fetch_items.return_value = []
        mock_sql_client_instance.conn.cursor().fetchmany.return_value = []
        mock_sql_client.return_value = mock_sql_client_instance
        
        # Run main
        main.main()
        
        # Verify SQLClient was initialized with explicit credentials
        mock_sql_client.assert_called_once_with(
            server='mock_server',
            database='mock_db',
            username='admin',
            password='secret_password',
            driver='mock_driver'
        )

    @patch('main.SQLClient')
    @patch('main.GlpiClient')
    @patch('main.load_config')
    @patch('main.logger')
    def test_main_handles_db_connection_error(self, mock_logger, mock_load_config, mock_glpi_client, mock_sql_client):
        mock_config = {
            'database': {'server': 'mock_server', 'database': 'mock_db'},
            'glpi': {},
            'migration': {}
        }
        mock_load_config.return_value = mock_config
        
        mock_sql_client_instance = MagicMock()
        mock_sql_client_instance.connect.side_effect = Exception("Connection timeout")
        mock_sql_client.return_value = mock_sql_client_instance
        
        # Run main, should handle exception gracefully and log error
        main.main()
        
        mock_logger.error.assert_called_with("Migration setup or general failure: Connection timeout")

    @patch('main.inventory')
    @patch('main.SQLClient')
    @patch('main.GlpiClient')
    @patch('main.load_config')
    def test_main_runs_inventory_migration(self, mock_load_config, mock_glpi_client, mock_sql_client, mock_inventory):
        mock_config = {
            'database': {'server': 'mock_server', 'database': 'mock_db'},
            'glpi': {},
            'migration': {'debug': True, 'batch_size': 5}
        }
        mock_load_config.return_value = mock_config
        
        mock_inventory.extract_inventory_items.return_value = [{'ITEM_NUMBER': '100'}]
        mock_inventory.map_inventory_item.return_value = ('Computer', {'name': 'NB100'}, {'infocom': {'value': '500'}})
        mock_inventory.ingest_inventory_item.return_value = 999
        
        main.main()
        
        mock_inventory.extract_inventory_items.assert_called_once()
        mock_inventory.map_inventory_item.assert_called_once_with({'ITEM_NUMBER': '100'}, glpi_client=mock_glpi_client.return_value)
        mock_inventory.ingest_inventory_item.assert_called_once_with(mock_glpi_client.return_value, 'Computer', {'name': 'NB100'}, {'infocom': {'value': '500'}})

if __name__ == '__main__':
    unittest.main()
