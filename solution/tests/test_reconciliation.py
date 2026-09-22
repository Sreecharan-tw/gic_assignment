import unittest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_layer import Database
from analysis import PriceReconciliation


class TestPriceReconciliation(unittest.TestCase):
    def setUp(self):
        """Set up test database with sample data."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.db = Database(self.db_path)
        self.db.connect()
        self.db.create_fund_positions_table()

        # Create reference tables
        self._create_reference_tables()
        self._insert_test_data()

        self.reconciliation = PriceReconciliation(self.db)

    def tearDown(self):
        """Clean up."""
        self.db.disconnect()
        Path(self.db_path).unlink(missing_ok=True)

    def _create_reference_tables(self):
        """Create reference data tables."""
        # Equity tables
        self.db.execute("""
        CREATE TABLE equity_reference (
            SYMBOL TEXT PRIMARY KEY,
            COUNTRY TEXT,
            SECURITY_NAME TEXT,
            SECTOR TEXT,
            INDUSTRY TEXT,
            CURRENCY TEXT
        )
        """)

        self.db.execute("""
        CREATE TABLE equity_prices (
            DATETIME TEXT,
            SYMBOL TEXT,
            PRICE REAL,
            PRIMARY KEY (DATETIME, SYMBOL)
        )
        """)

        # Bond tables
        self.db.execute("""
        CREATE TABLE bond_reference (
            SECURITY_NAME TEXT,
            ISIN TEXT PRIMARY KEY,
            SEDOL TEXT,
            COUNTRY TEXT,
            COUPON REAL,
            MATURITY_DATE TEXT,
            COUPON_FREQUENCY TEXT,
            SECTOR TEXT,
            CURRENCY TEXT
        )
        """)

        self.db.execute("""
        CREATE TABLE bond_prices (
            DATETIME TEXT,
            ISIN TEXT,
            PRICE REAL,
            PRIMARY KEY (DATETIME, ISIN)
        )
        """)

        self.db.commit()

    def _insert_test_data(self):
        """Insert test data."""
        # Insert equity prices for January
        self.db.execute(
            "INSERT INTO equity_prices VALUES (?, ?, ?)",
            ('2023-01-31', 'AAPL', 150.0)
        )
        self.db.execute(
            "INSERT INTO equity_prices VALUES (?, ?, ?)",
            ('2023-01-31', 'MSFT', 250.0)
        )
        # Insert price for GOOG in January (for forward-fill test)
        self.db.execute(
            "INSERT INTO equity_prices VALUES (?, ?, ?)",
            ('2023-01-31', 'GOOG', 100.0)
        )

        # Insert fund positions for January
        self.db.execute(
            """INSERT INTO fund_positions
            (fund_name, eom_date, financial_type, symbol, security_name, price, quantity, market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ('Fund1', '2023-01-31', 'Equities', 'AAPL', 'Apple', 150.0, 100, 15000)
        )

        self.db.execute(
            """INSERT INTO fund_positions
            (fund_name, eom_date, financial_type, symbol, security_name, price, quantity, market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ('Fund1', '2023-01-31', 'Equities', 'MSFT', 'Microsoft', 250.0, 50, 12500)
        )

        # Price mismatch case in January
        self.db.execute(
            """INSERT INTO fund_positions
            (fund_name, eom_date, financial_type, symbol, security_name, price, quantity, market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ('Fund2', '2023-01-31', 'Equities', 'AAPL', 'Apple', 152.0, 100, 15200)
        )

        # Forward-fill test: Fund position in February but price data only in January
        self.db.execute(
            """INSERT INTO fund_positions
            (fund_name, eom_date, financial_type, symbol, security_name, price, quantity, market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ('Fund1', '2023-02-28', 'Equities', 'GOOG', 'Google', 105.0, 200, 21000)
        )

        self.db.commit()

    def test_generate_reconciliation_report(self):
        """Test generating reconciliation report with actual reconciliation logic verification."""
        import csv
        output_path = Path(tempfile.gettempdir()) / "test_reconciliation_report.csv"

        result = self.reconciliation.generate_reconciliation_report(str(output_path))

        # Verify return value
        self.assertIn("output_file", result)
        self.assertTrue(output_path.exists())
        self.assertGreater(result['rows'], 0)

        # Verify report contains expected columns and read data rows
        with open(output_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            # Verify expected columns exist
            expected_columns = [
                "fund_name", "eom_date", "instrument_type", "symbol",
                "security_name", "fund_price", "reference_price",
                "price_difference", "price_difference_pct", "quantity",
                "market_value", "reference_available"
            ]
            for col in expected_columns:
                self.assertIn(col, reader.fieldnames, f"Column '{col}' missing from report")

        # Verify data correctness
        aapl_fund1 = next((r for r in rows if r['fund_name'] == 'Fund1' and r['symbol'] == 'AAPL'), None)
        aapl_fund2 = next((r for r in rows if r['fund_name'] == 'Fund2' and r['symbol'] == 'AAPL'), None)
        msft_fund1 = next((r for r in rows if r['fund_name'] == 'Fund1' and r['symbol'] == 'MSFT'), None)

        # Test 1: Price match (Fund1 AAPL: fund_price=150.0, reference_price=150.0)
        self.assertIsNotNone(aapl_fund1, "Fund1 AAPL position should exist")
        self.assertEqual(float(aapl_fund1['fund_price']), 150.0)
        self.assertEqual(float(aapl_fund1['reference_price']), 150.0)
        self.assertEqual(aapl_fund1['reference_available'], 'Yes')
        self.assertAlmostEqual(float(aapl_fund1['price_difference']), 0.0, places=4)

        # Test 2: Price mismatch (Fund2 AAPL: fund_price=152.0, reference_price=150.0)
        self.assertIsNotNone(aapl_fund2, "Fund2 AAPL position should exist")
        self.assertEqual(float(aapl_fund2['fund_price']), 152.0)
        self.assertEqual(float(aapl_fund2['reference_price']), 150.0)
        self.assertEqual(aapl_fund2['reference_available'], 'Yes')
        # Price difference: 152.0 - 150.0 = 2.0
        self.assertAlmostEqual(float(aapl_fund2['price_difference']), 2.0, places=4)

        # Test 3: Price match (Fund1 MSFT: fund_price=250.0, reference_price=250.0)
        self.assertIsNotNone(msft_fund1, "Fund1 MSFT position should exist")
        self.assertEqual(float(msft_fund1['fund_price']), 250.0)
        self.assertEqual(float(msft_fund1['reference_price']), 250.0)
        self.assertEqual(msft_fund1['reference_available'], 'Yes')
        self.assertAlmostEqual(float(msft_fund1['price_difference']), 0.0, places=4)

        # Test 4: Forward-fill (Fund1 GOOG in Feb uses Jan price)
        # Fund position on 2023-02-28 with fund_price=105.0
        # Reference price from 2023-01-31 (forward-filled) = 100.0
        goog_fund1_feb = next((r for r in rows if r['fund_name'] == 'Fund1' and r['symbol'] == 'GOOG' and r['eom_date'] == '2023-02-28'), None)
        self.assertIsNotNone(goog_fund1_feb, "Fund1 GOOG Feb position should exist")
        self.assertEqual(float(goog_fund1_feb['fund_price']), 105.0)
        # Forward-fill should use Jan price (100.0)
        self.assertEqual(float(goog_fund1_feb['reference_price']), 100.0, "Forward-fill should use previous month's price")
        self.assertEqual(goog_fund1_feb['reference_available'], 'Yes')
        # Price difference: 105.0 - 100.0 = 5.0
        self.assertAlmostEqual(float(goog_fund1_feb['price_difference']), 5.0, places=4)

        # Cleanup
        output_path.unlink()


if __name__ == '__main__':
    unittest.main()
