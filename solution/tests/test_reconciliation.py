import unittest
import pytest
import tempfile
import csv
from datetime import datetime
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
        assert "output_file" in result
        assert output_path.exists()
        assert result['rows'] > 0

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
                assert col in reader.fieldnames, f"Column '{col}' missing from report"

        # Verify data correctness
        aapl_fund1 = next((r for r in rows if r['fund_name'] == 'Fund1' and r['symbol'] == 'AAPL'), None)
        aapl_fund2 = next((r for r in rows if r['fund_name'] == 'Fund2' and r['symbol'] == 'AAPL'), None)
        msft_fund1 = next((r for r in rows if r['fund_name'] == 'Fund1' and r['symbol'] == 'MSFT'), None)

        # Test 1: Price match (Fund1 AAPL: fund_price=150.0, reference_price=150.0)
        assert aapl_fund1 is not None, "Fund1 AAPL position should exist"
        assert float(aapl_fund1['fund_price']) == 150.0
        assert float(aapl_fund1['reference_price']) == 150.0
        assert aapl_fund1['reference_available'] == 'Yes'
        assert float(aapl_fund1['price_difference']) == pytest.approx(0.0, abs=0.0001)

        # Test 2: Price mismatch (Fund2 AAPL: fund_price=152.0, reference_price=150.0)
        assert aapl_fund2 is not None, "Fund2 AAPL position should exist"
        assert float(aapl_fund2['fund_price']) == 152.0
        assert float(aapl_fund2['reference_price']) == 150.0
        assert aapl_fund2['reference_available'] == 'Yes'
        # Price difference: 152.0 - 150.0 = 2.0
        assert float(aapl_fund2['price_difference']) == pytest.approx(2.0, abs=0.0001)

        # Test 3: Price match (Fund1 MSFT: fund_price=250.0, reference_price=250.0)
        assert msft_fund1 is not None, "Fund1 MSFT position should exist"
        assert float(msft_fund1['fund_price']) == 250.0
        assert float(msft_fund1['reference_price']) == 250.0
        assert msft_fund1['reference_available'] == 'Yes'
        assert float(msft_fund1['price_difference']) == pytest.approx(0.0, abs=0.0001)

        # Test 4: Forward-fill (Fund1 GOOG in Feb uses Jan price)
        # Fund position on 2023-02-28 with fund_price=105.0
        # Reference price from 2023-01-31 (forward-filled) = 100.0
        goog_fund1_feb = next((r for r in rows if r['fund_name'] == 'Fund1' and r['symbol'] == 'GOOG' and r['eom_date'] == '2023-02-28'), None)
        assert goog_fund1_feb is not None, "Fund1 GOOG Feb position should exist"
        assert float(goog_fund1_feb['fund_price']) == 105.0
        # Forward-fill should use Jan price (100.0)
        assert float(goog_fund1_feb['reference_price']) == 100.0, "Forward-fill should use previous month's price"
        assert goog_fund1_feb['reference_available'] == 'Yes'
        # Price difference: 105.0 - 100.0 = 5.0
        assert float(goog_fund1_feb['price_difference']) == pytest.approx(5.0, abs=0.0001)

        # Cleanup
        output_path.unlink()


class TestReferencePriceDateFormat(unittest.TestCase):
    """
    Reference price lookup against production date formats.

    equity_prices.DATETIME ships as M/D/YYYY ('8/31/2022') while
    fund_positions.eom_date is YYYY-MM-DD. The lookup compares the two
    columns directly, so SQLite compares them as text rather than as dates.
    bond_prices.DATETIME is already ISO, which is why only equities are hit.
    """

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.db = Database(self.db_path)
        self.db.connect()
        self.db.create_fund_positions_table()

        self.db.execute("""
        CREATE TABLE equity_prices (
            DATETIME TEXT, SYMBOL TEXT, PRICE REAL,
            PRIMARY KEY (DATETIME, SYMBOL)
        )
        """)
        self.db.execute("""
        CREATE TABLE bond_prices (
            DATETIME TEXT, ISIN TEXT, PRICE REAL,
            PRIMARY KEY (DATETIME, ISIN)
        )
        """)

        # Equity prices in production format (M/D/YYYY), spanning the position date
        for datetime_str, price in [
            ('7/29/2022', 162.51),   # before  - prior month
            ('8/31/2022', 156.29),   # ON the position date  <- the correct answer
            ('2/9/2023', 150.23),    # after   - must never be selected
            ('8/31/2023', 183.56),   # after   - must never be selected
        ]:
            self.db.execute(
                "INSERT INTO equity_prices VALUES (?, ?, ?)",
                (datetime_str, 'AAPL', price)
            )

        self.db.execute(
            """INSERT INTO fund_positions
            (fund_name, eom_date, financial_type, symbol, security_name, price, quantity, market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ('Fund1', '2022-08-31', 'Equities', 'AAPL', 'Apple', 150.0, 100, 15000)
        )
        self.db.commit()

        # Mirrors the pipeline: raw dump is loaded, then dates are normalised
        # before any price lookup runs.
        self.db.normalize_reference_dates()

        self.reconciliation = PriceReconciliation(self.db)

    def tearDown(self):
        self.db.disconnect()
        Path(self.db_path).unlink(missing_ok=True)

    def _generate(self):
        output_path = Path(tempfile.gettempdir()) / "test_date_format_report.csv"
        self.reconciliation.generate_reconciliation_report(str(output_path))
        with open(output_path) as f:
            rows = list(csv.DictReader(f))
        output_path.unlink()
        return rows

    @staticmethod
    def _parse(date_str):
        """Parse either ISO or M/D/YYYY."""
        for fmt in ('%Y-%m-%d', '%m/%d/%Y'):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"unrecognised date format: {date_str!r}")

    def test_reference_price_is_never_dated_after_the_position(self):
        """A reference price dated after eom_date cannot exist: the lookup filters on <=."""
        for row in self._generate():
            if not row['reference_price_date']:
                continue
            ref_date = self._parse(row['reference_price_date'])
            eom_date = self._parse(row['eom_date'])
            assert ref_date <= eom_date, (
                f"{row['symbol']} @ {row['eom_date']}: reference price is dated "
                f"{row['reference_price_date']} ({ref_date}), which is AFTER the "
                f"position date. The lookup filters on DATETIME <= eom_date, so this "
                f"is only reachable when the two columns are compared as text "
                f"rather than as dates."
            )

    def test_exact_eom_price_is_preferred_over_forward_fill(self):
        """With a price ON eom_date, that price wins - forward-fill is the fallback."""
        row = self._generate()[0]
        assert float(row['reference_price']) == pytest.approx(156.29, abs=0.01), (
            f"expected the 8/31/2022 price (156.29) for a 2022-08-31 position, "
            f"got {row['reference_price']} dated {row['reference_price_date']}"
        )

    def test_forward_fill_uses_most_recent_prior_price(self):
        """With no price on eom_date, the nearest earlier price is used."""
        # setUp has already normalised, so 8/31/2022 is now stored as ISO.
        # Mutating this fixture is safe: setUp builds a fresh database per test.
        self.db.execute("DELETE FROM equity_prices WHERE DATETIME = '2022-08-31'")
        self.db.commit()

        row = self._generate()[0]
        assert float(row['reference_price']) == pytest.approx(162.51, abs=0.01), (
            f"with 8/31/2022 removed, the 7/29/2022 price (162.51) should be "
            f"forward-filled, got {row['reference_price']} dated "
            f"{row['reference_price_date']}"
        )


if __name__ == '__main__':
    unittest.main()
