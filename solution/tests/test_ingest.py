import unittest
import tempfile
from pathlib import Path
import sys
import csv

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_layer import Database, DataIngestion


class TestDataIngestion(unittest.TestCase):
    def setUp(self):
        """Set up test database and ingestion object."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.db = Database(self.db_path)
        self.db.connect()
        self.db.create_fund_positions_table()

        self.ingest = DataIngestion(self.db)

    def tearDown(self):
        """Clean up."""
        self.db.disconnect()
        Path(self.db_path).unlink(missing_ok=True)

    def test_parse_date_from_filename_dash_separator(self):
        """Test date parsing with dash separator."""
        filename = "Applebead.31-08-2022 breakdown.csv"
        date = self.ingest.parse_date_from_filename(filename)
        self.assertEqual(date, "2022-08-31")

    def test_parse_date_from_filename_underscore_separator(self):
        """Test date parsing with underscore separator."""
        filename = "Belaware.31_01_2023.csv"
        date = self.ingest.parse_date_from_filename(filename)
        self.assertEqual(date, "2023-01-31")

    def test_parse_date_from_filename_yyyymmdd(self):
        """Test date parsing with YYYYMMDD format."""
        filename = "TT_monthly_Trustmind.20220831.csv"
        date = self.ingest.parse_date_from_filename(filename)
        self.assertEqual(date, "2022-08-31")

    def test_parse_date_from_filename_yyyy_mm_dd(self):
        """Test date parsing with YYYY-MM-DD format."""
        filename = "rpt-Catalysm.2022-08-31.csv"
        date = self.ingest.parse_date_from_filename(filename)
        self.assertEqual(date, "2022-08-31")

    def test_parse_date_from_filename_mm_dd_yyyy(self):
        """Test date parsing with MM-DD-YYYY format."""
        filename = "Report-of-Gohen.01-31-2023.csv"
        date = self.ingest.parse_date_from_filename(filename)
        self.assertEqual(date, "2023-01-31")

    def test_parse_fund_name(self):
        """Test fund name extraction."""
        filename = "Applebead.31-08-2022 breakdown.csv"
        fund_name = self.ingest.parse_fund_name(filename)
        self.assertEqual(fund_name, "Applebead")

    def test_parse_fund_name_with_prefix(self):
        """Test fund name extraction with Report-of- prefix."""
        filename = "Report-of-Gohen.01-31-2023.csv"
        fund_name = self.ingest.parse_fund_name(filename)
        self.assertEqual(fund_name, "Gohen")

    def test_parse_fund_name_with_rpt_prefix(self):
        """Test fund name extraction with rpt- prefix."""
        filename = "rpt-Catalysm.2022-08-31.csv"
        fund_name = self.ingest.parse_fund_name(filename)
        self.assertEqual(fund_name, "Catalysm")

    def test_parse_fund_name_with_tt_prefix(self):
        """Test fund name extraction with TT_monthly_ prefix."""
        filename = "TT_monthly_Trustmind.20220831.csv"
        fund_name = self.ingest.parse_fund_name(filename)
        self.assertEqual(fund_name, "Trustmind")

    def test_parse_fund_name_with_fund_prefix(self):
        """Test fund name extraction with Fund prefix."""
        filename = "Fund Whitestone.30-06-2023 - details.csv"
        fund_name = self.ingest.parse_fund_name(filename)
        self.assertEqual(fund_name, "Whitestone")

    def test_parse_fund_name_with_mend_report_prefix(self):
        """Test fund name extraction with mend-report prefix."""
        filename = "mend-report Wallington.30_06_2023.csv"
        fund_name = self.ingest.parse_fund_name(filename)
        self.assertEqual(fund_name, "Wallington")

    def test_parse_float_valid(self):
        """Test float parsing with valid value."""
        result = DataIngestion._parse_float("123.45")
        self.assertEqual(result, 123.45)

    def test_parse_float_empty(self):
        """Test float parsing with empty value."""
        result = DataIngestion._parse_float("")
        self.assertIsNone(result)

    def test_parse_float_invalid(self):
        """Test float parsing with invalid value."""
        result = DataIngestion._parse_float("abc")
        self.assertIsNone(result)

    def test_ingest_csv_file(self):
        """Test ingesting a single CSV file."""
        # Create a temporary CSV file
        temp_csv = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        temp_csv_path = temp_csv.name

        # Write test data
        writer = csv.DictWriter(
            temp_csv,
            fieldnames=['FINANCIAL TYPE', 'SYMBOL', 'SECURITY NAME', 'SEDOL', 'PRICE', 'QUANTITY', 'REALISED P/L', 'MARKET VALUE']
        )
        writer.writeheader()
        writer.writerow({
            'FINANCIAL TYPE': 'Equities',
            'SYMBOL': 'AAPL',
            'SECURITY NAME': 'Apple Inc',
            'SEDOL': '',
            'PRICE': '150.0',
            'QUANTITY': '100',
            'REALISED P/L': '500',
            'MARKET VALUE': '15000'
        })
        temp_csv.close()

        # Rename to match format
        renamed_path = Path(temp_csv_path).parent / "TestFund.31-01-2023.csv"
        Path(temp_csv_path).rename(renamed_path)

        # Ingest
        fund_name, eom_date, positions = self.ingest.ingest_csv_file(renamed_path)

        self.assertEqual(fund_name, "TestFund")
        self.assertEqual(eom_date, "2023-01-31")
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]['SYMBOL'], 'AAPL')

        # Cleanup
        renamed_path.unlink()

    def test_insert_positions(self):
        """Test inserting positions into database."""
        positions = [
            {
                'FINANCIAL TYPE': 'Equities',
                'SYMBOL': 'AAPL',
                'SECURITY NAME': 'Apple',
                'SEDOL': '',
                'PRICE': '150.0',
                'QUANTITY': '100',
                'REALISED P/L': '500',
                'MARKET VALUE': '15000'
            },
            {
                'FINANCIAL TYPE': 'Equities',
                'SYMBOL': 'MSFT',
                'SECURITY NAME': 'Microsoft',
                'SEDOL': '',
                'PRICE': '300.0',
                'QUANTITY': '50',
                'REALISED P/L': '1000',
                'MARKET VALUE': '15000'
            }
        ]

        self.ingest.insert_positions('TestFund', '2023-01-31', positions)

        # Verify
        count = self.db.get_table_count('fund_positions')
        self.assertEqual(count, 2)

        result = self.db.fetch_one(
            "SELECT * FROM fund_positions WHERE symbol = ?",
            ('AAPL',)
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['price'], 150.0)
        self.assertEqual(result['quantity'], 100.0)

    def test_handle_null_sedol(self):
        """Test handling of null SEDOL values."""
        positions = [
            {
                'FINANCIAL TYPE': 'Equities',
                'SYMBOL': 'AAPL',
                'SECURITY NAME': 'Apple',
                'SEDOL': '',
                'PRICE': '150.0',
                'QUANTITY': '100',
                'REALISED P/L': '500',
                'MARKET VALUE': '15000'
            }
        ]

        self.ingest.insert_positions('TestFund', '2023-01-31', positions)

        result = self.db.fetch_one(
            "SELECT sedol FROM fund_positions WHERE symbol = ?",
            ('AAPL',)
        )
        self.assertIsNone(result[0])


if __name__ == '__main__':
    unittest.main()
