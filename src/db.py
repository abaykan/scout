import mysql.connector
from mysql.connector import Error
import json
import logging

class Database:
    def __init__(self, config_path='config.json'):
        self.config = self._load_config(config_path)
        self.connection = None
        self.logger = logging.getLogger(__name__)
        
    def _load_config(self, config_path):
        """Load database configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config['database']
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            raise Exception(f"Error loading database config: {e}")
    
    def connect(self):
        """Establish database connection"""
        try:
            self.connection = mysql.connector.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                port=self.config.get('port', 3306)
            )
            self.logger.info("Database connection established")
            return True
        except Error as e:
            self.logger.error(f"Database connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            self.logger.info("Database connection closed")
    
    def execute_query(self, query, params=None):
        """Execute a SQL query and return results"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            
            if query.strip().lower().startswith('select'):
                result = cursor.fetchall()
            else:
                self.connection.commit()
                result = cursor.rowcount
            
            cursor.close()
            return result
        except Error as e:
            self.logger.error(f"Query execution failed: {e}")
            return None
    
    def initialize_database(self):
        """Create database tables if they don't exist"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS programs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                platform VARCHAR(50) NOT NULL,
                program_name VARCHAR(255) NOT NULL,
                program_url VARCHAR(500) NOT NULL,
                scope TEXT,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_program (platform, program_name)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS subdomains (
                id INT AUTO_INCREMENT PRIMARY KEY,
                subdomain VARCHAR(255) NOT NULL UNIQUE,
                source VARCHAR(100),
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                is_new BOOLEAN DEFAULT TRUE
            )
            """
        ]
        
        for table_sql in tables:
            self.execute_query(table_sql)
        
        self.logger.info("Database tables initialized")
