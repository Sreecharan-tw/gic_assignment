import unittest
import sqlite3
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_layer import Database


class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Create temporary database for testing."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        self.db = Database(self.db_path)
        self.db.connect()

    def tearDown(self):
        """Clean up temporary database."""
        self.db.disconnect()
        Path(self.db_path).unlink(missing_ok=True)

    def test_database_connection(self):
        """Test database connection."""
        self.assertIsNotNone(self.db.connection)
        self.assertIsInstance(self.db.connection, sqlite3.Connection)

    def test_create_fund_positions_table(self):
        """Test fund_positions table creation."""
        self.db.create_fund_positions_table()
        self.assertTrue(self.db.table_exists('fund_positions'))

    def test_table_count(self):
        """Test row counting in tables."""
        self.db.create_fund_positions_table()
        count = self.db.get_table_count('fund_positions')
        self.assertEqual(count, 0)

    def test_execute_and_fetch(self):
        """Test execute and fetch operations."""
        self.db.create_fund_positions_table()

        # Insert test data
        query = """
        INSERT INTO fund_positions
        (fund_name, eom_date, financial_type, symbol, price, quantity, realised_pl, market_value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = ('TestFund', '2023-01-31', 'Equities', 'AAPL', 150.0, 100.0, 500.0, 15000.0)
        self.db.execute(query, params)
        self.db.commit()

        # Fetch and verify
        result = self.db.fetch_one("SELECT * FROM fund_positions WHERE fund_name = ?", ('TestFund',))
        self.assertIsNotNone(result)
        self.assertEqual(result['fund_name'], 'TestFund')
        self.assertEqual(result['symbol'], 'AAPL')
        self.assertEqual(result['price'], 150.0)

    def test_fetch_all(self):
        """Test fetching multiple rows."""
        self.db.create_fund_positions_table()

        # Insert multiple records
        for i in range(3):
            query = """
            INSERT INTO fund_positions
            (fund_name, eom_date, financial_type, symbol, price)
            VALUES (?, ?, ?, ?, ?)
            """
            params = (f'Fund{i}', '2023-01-31', 'Equities', f'SYM{i}', 100.0 + i)
            self.db.execute(query, params)

        self.db.commit()

        # Fetch all
        results = self.db.fetch_all("SELECT * FROM fund_positions WHERE eom_date = ?", ('2023-01-31',))
        self.assertEqual(len(results), 3)

    def test_unique_constraint(self):
        """Test unique constraint on fund_positions."""
        self.db.create_fund_positions_table()

        # Insert first record
        query = """
        INSERT OR REPLACE INTO fund_positions
        (fund_name, eom_date, symbol, price)
        VALUES (?, ?, ?, ?)
        """
        params = ('Fund1', '2023-01-31', 'AAPL', 150.0)
        self.db.execute(query, params)
        self.db.commit()

        # Insert duplicate (should replace)
        params2 = ('Fund1', '2023-01-31', 'AAPL', 155.0)
        self.db.execute(query, params2)
        self.db.commit()

        # Verify only one record exists
        count = self.db.get_table_count('fund_positions')
        self.assertEqual(count, 1)

        # Verify it has the updated price
        result = self.db.fetch_one(
            "SELECT price FROM fund_positions WHERE fund_name = ? AND symbol = ?",
            ('Fund1', 'AAPL')
        )
        self.assertEqual(result[0], 155.0)


if __name__ == '__main__':
    unittest.main()
