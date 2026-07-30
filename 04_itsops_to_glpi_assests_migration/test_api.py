import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config.loader import ConfigLoader
from common.clients.glpi_client import GlpiClient

config = ConfigLoader().load()
glpi_config = config.get('glpi', {})

client = GlpiClient(
    url=glpi_config.get('url'),
    app_token=glpi_config.get('app_token'),
    user_token=glpi_config.get('user_token'),
    username=glpi_config.get('username'),
    password=glpi_config.get('password'),
    verify_ssl=glpi_config.get('verify_ssl', False)
)

client.init_session()
print("Session init successful")

try:
    reminder_payload = {
        "name": "Test Reminder",
        "text": "This is a test reminder",
        "state": 0
    }
    reminder_id = client.create_item("Reminder", reminder_payload)
    print(f"Created Reminder ID: {reminder_id}")
except Exception as e:
    print(f"Error creating Reminder: {e}")

try:
    stat_payload = {
        "name": "Test Stat",
        "value": 100
    }
    stat_id = client.create_item("Stat", stat_payload)
    print(f"Created Stat ID: {stat_id}")
except Exception as e:
    print(f"Error creating Stat: {e}")
    
client.kill_session()
