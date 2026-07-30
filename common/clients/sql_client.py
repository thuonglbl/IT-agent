import pyodbc
import logging

logger = logging.getLogger(__name__)

class SQLClient:
    """
    A unified SQL Server client using pyodbc.
    Connects to the database and provides methods to fetch data.
    """
    
    def __init__(self, server, database, username=None, password=None, driver='{ODBC Driver 17 for SQL Server}'):
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.driver = driver
        self.conn = None

    def connect(self):
        try:
            # Fallback to Windows Authentication (Trusted_Connection) if no username provided
            if self.username:
                conn_str = f'DRIVER={self.driver};SERVER={self.server};DATABASE={self.database};UID={self.username};PWD={self.password or ""}'
            else:
                conn_str = f'DRIVER={self.driver};SERVER={self.server};DATABASE={self.database};Trusted_Connection=yes;'
            
            logger.info(f"Connecting to SQL Server: {self.server}, Database: {self.database}")
            self.conn = pyodbc.connect(conn_str)
            logger.info("Successfully connected to the database.")
        except Exception as e:
            logger.error(f"Failed to connect to the database: {e}")
            raise

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")

    def fetch_items(self, limit=None):
        if not self.conn:
            self.connect()
            
        cursor = self.conn.cursor()
        query = "SELECT * FROM dbo._ITEM"
        
        if limit:
            query = f"SELECT TOP {limit} * FROM dbo._ITEM"
            
        logger.info(f"Executing query: {query}")
        cursor.execute(query)
        
        columns = [column[0] for column in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
            
        logger.info(f"Fetched {len(results)} rows from dbo._ITEM")
        return results
