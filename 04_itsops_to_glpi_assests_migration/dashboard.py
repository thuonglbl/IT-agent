import logging

logger = logging.getLogger(__name__)

def extract_recent_activities(sql_client, limit=None, schema="dbo"):
    """Extract Recent Activities from ITEM_ACTION_LOGS"""
    cursor = sql_client.conn.cursor()
    query = f"SELECT * FROM {schema}.ITEM_ACTION_LOGS"
    
    if limit is not None:
        try:
            limit_val = int(limit)
            if limit_val > 0:
                query = f"SELECT TOP {limit_val} * FROM {schema}.ITEM_ACTION_LOGS"
        except (ValueError, TypeError):
            logger.warning(f"Invalid limit: {limit}")
            
    logger.info(f"Executing query: {query}")
    try:
        cursor.execute(query)
        columns = [column[0] for column in cursor.description]
        while True:
            rows = cursor.fetchmany(1000)
            if not rows:
                break
            for row in rows:
                yield dict(zip(columns, row))
    except Exception as e:
        logger.error(f"Error extracting recent activities: {e}")

def extract_inventory_statistics(sql_client, limit=None, schema="dbo"):
    """Extract Inventory Statistic from KPI_Result"""
    cursor = sql_client.conn.cursor()
    query = f"""
        SELECT r.*, d.Name as KPI_Name 
        FROM {schema}.KPI_Result r
        JOIN {schema}.KPI_Definition d ON r.Def_Id = d.Id
    """
    if limit is not None:
        try:
            limit_val = int(limit)
            if limit_val > 0:
                query = f"SELECT TOP {limit_val} r.*, d.Name as KPI_Name FROM {schema}.KPI_Result r JOIN {schema}.KPI_Definition d ON r.Def_Id = d.Id"
        except (ValueError, TypeError):
            logger.warning(f"Invalid limit: {limit}")
            
    logger.info(f"Executing query: {query}")
    try:
        cursor.execute(query)
        columns = [column[0] for column in cursor.description]
        while True:
            rows = cursor.fetchmany(1000)
            if not rows:
                break
            for row in rows:
                yield dict(zip(columns, row))
    except Exception as e:
        logger.error(f"Error extracting inventory statistics: {e}")

def map_recent_activity(row):
    """Map ITSOPS ITEM_ACTION_LOGS to GLPI Reminder"""
    action = row.get('Action_Name') or ''
    user = row.get('Requestor_Visa') or ''
    date = str(row.get('Launched_On') or '')
    result = str(row.get('Action_Result') or '')
    
    payload = {
        "name": f"Activity: {action} by {user}",
        "text": f"Date: {date}\nAction: {action}\nResult: {result}",
        "state": 0  # 0 for info
    }
    return "Reminder", payload

def map_inventory_statistic(row):
    """Map ITSOPS KPI_Result to GLPI Stat"""
    payload = {
        "name": row.get('KPI_Name') or 'Unknown KPI',
        "date": str(row.get('Run_Date') or ''),
        "value": int(row.get('Row_Count') or 0),
        "comment": str(row.get('Row_Criteria_01') or '')
    }
    return "Stat", payload
