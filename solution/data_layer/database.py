import sqlite3
from pathlib import Path
from typing import Optional

class Database:
    def __init__(self, db_path: str = "funds_analysis.db"):
        self.db_path = Path(db_path)
        self.connection = None

    def connect(self):
        """Connect to SQLite database."""
        self.connection = sqlite3.connect(str(self.db_path))
        self.connection.row_factory = sqlite3.Row
        return self.connection

    def disconnect(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()

    def execute(self, query: str, params: tuple = None):
        """Execute a query and return cursor."""
        cursor = self.connection.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor

    def fetch_all(self, query: str, params: tuple = None) -> list:
        """Execute query and fetch all results."""
        cursor = self.execute(query, params)
        return cursor.fetchall()

    def fetch_one(self, query: str, params: tuple = None) -> Optional[dict]:
        """Execute query and fetch one result."""
        cursor = self.execute(query, params)
        return cursor.fetchone()

    def commit(self):
        """Commit transaction."""
        if self.connection:
            self.connection.commit()

    def rollback(self):
        """Rollback transaction."""
        if self.connection:
            self.connection.rollback()

    def setup_from_sql(self, sql_file: str):
        """Load and execute SQL file to setup reference data."""
        with open(sql_file, 'r') as f:
            sql_script = f.read()

        cursor = self.connection.cursor()
        cursor.executescript(sql_script)
        self.commit()

    def create_fund_positions_table(self):
        """Create table to store fund position data."""
        query = """
        CREATE TABLE IF NOT EXISTS fund_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_name TEXT NOT NULL,
            eom_date TEXT NOT NULL,
            financial_type TEXT,
            symbol TEXT,
            security_name TEXT,
            sedol TEXT,
            price REAL,
            quantity REAL,
            realised_pl REAL,
            market_value REAL,
            UNIQUE(fund_name, eom_date, symbol)
        );
        """
        self.execute(query)
        self.commit()

    def create_indexes(self):
        """Create indexes for performance optimization on reference price lookups."""
        indexes = [
            """CREATE INDEX IF NOT EXISTS idx_equity_prices_symbol_date
               ON equity_prices(SYMBOL, DATETIME DESC)""",
            """CREATE INDEX IF NOT EXISTS idx_bond_prices_isin_date
               ON bond_prices(ISIN, DATETIME DESC)"""
        ]
        for index_query in indexes:
            self.execute(index_query)
        self.commit()

    def table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        result = self.fetch_one(query, (table_name,))
        return result is not None

    def get_table_count(self, table_name: str) -> int:
        """Get row count for a table."""
        query = f"SELECT COUNT(*) FROM {table_name}"
        result = self.fetch_one(query)
        return result[0] if result else 0
