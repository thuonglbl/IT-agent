import sys
from pathlib import Path
import logging

# Set up logging to show what sql_client is doing
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Add project root to allow importing modules
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from common.config.loader import ConfigLoader
from common.clients.sql_client import SQLClient

def main():
    print("--- TESTING DATABASE CONNECTION ---")
    
    try:
        loader = ConfigLoader()
        config = loader.load()
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        print("Please make sure you have created the 'config.yaml' file in the 04_itsops_to_glpi_assests_migration directory with your real DB credentials.")
        return
        
    db_config = config.get('database') or {}
    if not db_config.get('server'):
        print("❌ Error: The database configuration in config.yaml is missing the 'server' information.")
        return
        
    sql_client = SQLClient(
        server=db_config.get('server'),
        database=db_config.get('database'),
        username=db_config.get('username'),
        password=db_config.get('password'),
        driver=db_config.get('driver', '{ODBC Driver 17 for SQL Server}')
    )
    
    try:
        sql_client.connect()
        print("\n✅ DATABASE CONNECTION SUCCESSFUL!")
        
        print("\n⏳ Fetching 3 sample rows (limit=3)...")
        items = sql_client.fetch_items(limit=3)
        
        print(f"\n✅ Successfully fetched {len(items)} items. Sample data:")
        for i, item in enumerate(items):
            print(f"\n--- Item {i+1} ---")
            # Print the first 5 columns to verify
            for key, value in list(item.items())[:5]: 
                print(f"  {key}: {value}")
                
    except Exception as e:
        print(f"\n❌ ERROR DURING CONNECTION OR DATA FETCH: {e}")
    finally:
        sql_client.close()

if __name__ == "__main__":
    main()
