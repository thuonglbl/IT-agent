import os
import sys
import logging
import time

# Add parent directory to path to import common
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.clients.sql_client import SQLClient
from common.clients.glpi_client import GlpiClient
import inventory

from common.config.loader import ConfigLoader

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    loader = ConfigLoader(config_path=config_path)
    return loader.load()

def main():
    start_time = time.time()
    config = load_config()
    
    # Init SQL Client
    db_config = config.get('database') or {}
    sql_client = SQLClient(
        server=db_config.get('server'),
        database=db_config.get('database'),
        username=db_config.get('username'),
        password=db_config.get('password'),
        driver=db_config.get('driver', '{ODBC Driver 17 for SQL Server}')
    )
    
    # Init GLPI Client
    glpi_config = config.get('glpi') or {}
    glpi_client = GlpiClient(
        url=glpi_config.get('url'),
        app_token=glpi_config.get('app_token'),
        user_token=glpi_config.get('user_token'),
        username=glpi_config.get('username'),
        password=glpi_config.get('password'),
        verify_ssl=glpi_config.get('verify_ssl', False)
    )
    
    try:
        sql_client.connect()
        glpi_client.init_session()
        if hasattr(glpi_client, 'load_location_cache'):
            glpi_client.load_location_cache()
        
        # Fetch items from DB
        migration_config = config.get('migration') or {}
        is_debug = migration_config.get('debug', False)
        limit = migration_config.get('batch_size', 10) if is_debug else None
        item_id = migration_config.get('debug_item_id') if is_debug else None
        schema = db_config.get('schema', 'dbo')
        shared_erp_db = db_config.get('shared_erp_database')
        
        batch_size = migration_config.get('batch_size', 1000) if not is_debug else (limit or 10)
        
        start_after_id = None
        state_file = os.path.join(os.path.dirname(__file__), 'resume_state.json')
        if not is_debug and os.path.exists(state_file):
            import json
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    start_after_id = state.get('last_id')
                    if start_after_id:
                        logger.info(f"Resuming from ID > {start_after_id}")
            except Exception as e:
                logger.warning(f"Could not read state file: {e}")
                
        items = inventory.extract_inventory_items(sql_client, limit=limit, item_id=item_id, start_after_id=start_after_id, schema=schema, batch_size=batch_size, shared_erp_db=shared_erp_db)
        
        last_processed_id = start_after_id
        
        try:
            import json
            for idx, row in enumerate(items):
                current_id = row.get('ID')
                try:
                    logger.info(f"Processing item {idx + 1}: {row.get('ITEM_NUMBER')}")
                    
                    glpi_type, main_payload, aux_payloads = inventory.map_inventory_item(row, glpi_client=glpi_client)
                    logger.info(f"Mapped to GLPI Type: {glpi_type} with payload: {main_payload}")
                    
                    # Create in GLPI
                    asset_id = inventory.ingest_inventory_item(glpi_client, glpi_type, main_payload, aux_payloads)
                    if asset_id:
                        logger.info(f"Successfully migrated item {row.get('ITEM_NUMBER')} -> {glpi_type} ID: {asset_id}")
                    else:
                        logger.error(f"Failed to migrate item {row.get('ITEM_NUMBER')}")
                except Exception as e:
                    logger.error(f"Failed to process item {row.get('ITEM_NUMBER')}: {e}")
                
                # Update last processed ID
                if current_id:
                    last_processed_id = current_id
                    
                # Save state periodically
                if not is_debug and (idx + 1) % 50 == 0 and last_processed_id:
                    with open(state_file, 'w') as f:
                        json.dump({"last_id": last_processed_id}, f)
                        
        except KeyboardInterrupt:
            logger.info("Migration interrupted by user.")
        finally:
            if not is_debug and last_processed_id:
                import json
                with open(state_file, 'w') as f:
                    json.dump({"last_id": last_processed_id}, f)
                logger.info(f"Saved resume state. Last ID processed: {last_processed_id}")
                
    except Exception as e:
        logger.error(f"Migration setup or general failure: {e}")
    finally:
        sql_client.close()
        glpi_client.kill_session()
        
        end_time = time.time()
        duration = end_time - start_time
        
        days, rem = divmod(duration, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{int(days)}d")
        if hours > 0:
            parts.append(f"{int(hours)}h")
        if minutes > 0:
            parts.append(f"{int(minutes)}m")
        parts.append(f"{seconds:.2f}s")
        
        formatted_time = " ".join(parts)
        logger.info(f"Script finished in {formatted_time}.")

if __name__ == "__main__":
    main()
