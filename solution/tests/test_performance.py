import unittest
import tempfile
from pathlib import Path
import sys
import csv

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_layer import Database
from analysis import FundPerformance


class TestFundPerformance(unittest.TestCase):
    def setUp(self):
        """Set up test database with sample data."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.db = Database(self.db_path)
        self.db.connect()
        self.db.create_fund_positions_table()

        self._insert_test_data()
        self.performance = FundPerformance(self.db)

    def tearDown(self):
        """Clean up."""
        self.db.disconnect()
        Path(self.db_path).unlink(missing_ok=True)

    def _insert_test_data(self):
        """Insert test data for performance analysis."""
        # January data
        self.db.execute(
            """INSERT INTO fund_positions
            (fund_name, eom_date, financial_type, symbol, security_name, price, quantity, realised_pl, market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ('FundA', '2023-01-31', 'Equities', 'AAPL', 'Apple', 150.0, 100, 500, 15000)
        )
        self.db.execute(
            """INSERT INTO fund_positions
            (fund_name, eom_date, financial_type, symbol, security_name, price, quantity, realised_pl, market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ('FundA', '2023-01-31', 'Equities', 'MSFT', 'Microsoft', 250.0, 50, 1000, 12500)
        )

        self.db.execute(
            """INSERT INTO fund_positions
            (fund_name, eom_date, financial_type, symbol, security_name, price, quantity, realised_pl, market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ('FundB', '2023-01-31', 'Equities', 'GOOG', 'Google', 100.0, 200, 300, 20000)
        )

        # February data
        self.db.execute(
            """INSERT INTO fund_positions
            (fund_name, eom_date, financial_type, symbol, security_name, price, quantity, realised_pl, market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ('FundA', '2023-02-28', 'Equities', 'AAPL', 'Apple', 160.0, 100, 1000, 16000)
        )
        self.db.execute(
            """INSERT INTO fund_positions
            (fund_name, eom_date, financial_type, symbol, security_name, price, quantity, realised_pl, market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ('FundA', '2023-02-28', 'Equities', 'MSFT', 'Microsoft', 260.0, 50, 1500, 13000)
        )

        self.db.execute(
            """INSERT INTO fund_positions
            (fund_name, eom_date, financial_type, symbol, security_name, price, quantity, realised_pl, market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ('FundB', '2023-02-28', 'Equities', 'GOOG', 'Google', 105.0, 200, 500, 21000)
        )

        self.db.commit()

    def test_generate_performance_report(self):
        """Test generating performance report."""
        output_path = Path(tempfile.gettempdir()) / "test_performance_report.csv"

        result = self.performance.generate_performance_report(str(output_path))

        assert "output_file" in result
        assert "stats" in result
        assert output_path.exists()

        # Verify report structure
        with open(output_path) as f:
            first_line = f.readline()
            assert "eom_date" in first_line
            assert "fund_name" in first_line
            assert "is_best_performer" in first_line
            assert "rate_of_return" in first_line

        # Cleanup
        output_path.unlink()

    def test_best_performer_selection(self):
        """Test that best performer is correctly identified."""
        # FundA February ROR: (29000 - 27500 + 2500) / 27500 = 0.1454
        # FundB February ROR: (21000 - 20000 + 500) / 20000 = 0.075

        output_path = Path(tempfile.gettempdir()) / "test_best_performer.csv"
        self.performance.generate_performance_report(str(output_path))

        # Read and check for best performer (FundA should be 1 for is_best_performer on 2023-02-28)
        best_found = False
        january_found = False
        with open(output_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Check that February has the best performer
                if row['eom_date'] == '2023-02-28' and row['fund_name'] == 'FundA' and row['is_best_performer'] == '1':
                    best_found = True
                # Verify January is NOT in the report (no previous month for comparison)
                if row['eom_date'] == '2023-01-31':
                    january_found = True

        assert best_found, "FundA should be best performer in February"
        assert not january_found, "January should not be in report (no prior month for ROR calculation)"

        # Cleanup
        output_path.unlink()


if __name__ == '__main__':
    unittest.main()
