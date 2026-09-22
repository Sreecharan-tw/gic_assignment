import csv
from pathlib import Path
from datetime import datetime
from typing import List, Tuple
import re

class DataIngestion:
    def __init__(self, db_instance):
        self.db = db_instance
        # Look for external-funds in parent directory first, then current directory
        parent_dir = Path("..") / "external-funds"
        current_dir = Path("external-funds")
        self.funds_directory = parent_dir if parent_dir.exists() else current_dir

    def parse_date_from_filename(self, filename: str) -> str:
        """
        Extract and parse date from fund CSV filename.
        Handles formats like:
        - "Applebead.31-08-2022 breakdown.csv" (DD-MM-YYYY)
        - "Belaware.31_01_2023.csv" (DD_MM_YYYY)
        - "Leeder.01_31_2023.csv" (MM_DD_YYYY)
        - "Report-of-Gohen.01-31-2023.csv" (MM-DD-YYYY)
        - "TT_monthly_Trustmind.20220831.csv" (YYYYMMDD)
        - "rpt-Catalysm.2022-08-31.csv" (YYYY-MM-DD)
        - "Virtous.01-31-2023 - securities.csv" (MM-DD-YYYY)
        """
        base_name = filename.replace(" breakdown", "").replace(" - securities", "").replace(".csv", "")

        # Try YYYY-MM-DD format first
        date_match = re.search(r'(\d{4})[_-](\d{2})[_-](\d{2})', base_name)
        if date_match:
            year, month, day = date_match.groups()
            try:
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                pass

        # Try YYYYMMDD format
        date_match = re.search(r'(\d{4})(\d{2})(\d{2})', base_name)
        if date_match:
            year, month, day = date_match.groups()
            try:
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                pass

        # Try DD-MM-YYYY or MM-DD-YYYY format
        # This is ambiguous, so try both interpretations
        date_match = re.search(r'(\d{1,2})[_-](\d{1,2})[_-](\d{4})', base_name)
        if date_match:
            first_num, second_num, year = date_match.groups()
            first_num, second_num = int(first_num), int(second_num)

            # Try DD-MM-YYYY first
            try:
                if first_num <= 31 and second_num <= 12:
                    date_obj = datetime(int(year), second_num, first_num)
                    return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                pass

            # Try MM-DD-YYYY
            try:
                if first_num <= 12 and second_num <= 31:
                    date_obj = datetime(int(year), first_num, second_num)
                    return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                pass

        return None

    def parse_fund_name(self, filename: str) -> str:
        """Extract fund name from filename."""
        # Remove common report prefixes and suffixes
        base_name = filename
        base_name = base_name.replace("Report-of-", "")
        base_name = base_name.replace("rpt-", "")
        base_name = base_name.replace("TT_monthly_", "")
        base_name = base_name.replace("mend-report ", "")
        base_name = base_name.replace("Fund ", "")
        base_name = base_name.replace(" breakdown", "")
        base_name = base_name.replace(" - details", "")
        base_name = base_name.replace(" - securities", "")
        base_name = base_name.replace(".csv", "")

        # Get the part before the first date pattern
        # Remove everything after the fund name (dates, etc.)
        fund_name = re.sub(r'[\.\s_-][\d\-_\.]+.*', '', base_name)
        return fund_name.strip()

    def ingest_csv_file(self, file_path: Path) -> Tuple[str, str, List[dict]]:
        """
        Parse a single fund CSV file.
        Returns: (fund_name, eom_date, list of position records)
        """
        fund_name = self.parse_fund_name(file_path.name)
        eom_date = self.parse_date_from_filename(file_path.name)

        if not eom_date:
            print(f"Warning: Could not parse date from {file_path.name}")
            return None, None, []

        positions = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    positions.append(row)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return None, None, []

        return fund_name, eom_date, positions

    def insert_positions(self, fund_name: str, eom_date: str, positions: List[dict]):
        """Insert fund positions into database."""
        query = """
        INSERT OR REPLACE INTO fund_positions
        (fund_name, eom_date, financial_type, symbol, security_name, sedol, price, quantity, realised_pl, market_value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        for pos in positions:
            try:
                params = (
                    fund_name,
                    eom_date,
                    pos.get('FINANCIAL TYPE', '').strip(),
                    pos.get('SYMBOL', '').strip() or None,
                    pos.get('SECURITY NAME', '').strip(),
                    pos.get('SEDOL', '').strip() or None,
                    self._parse_float(pos.get('PRICE')),
                    self._parse_float(pos.get('QUANTITY')),
                    self._parse_float(pos.get('REALISED P/L')),
                    self._parse_float(pos.get('MARKET VALUE'))
                )
                self.db.execute(query, params)
            except Exception as e:
                print(f"Error inserting position for {fund_name} on {eom_date}: {e}")
                self.db.rollback()
                raise

        self.db.commit()

    def load_all_funds(self) -> dict:
        """Load all fund CSV files into database."""
        if not self.funds_directory.exists():
            raise FileNotFoundError(f"Directory not found: {self.funds_directory}")

        csv_files = sorted(self.funds_directory.glob("*.csv"))
        stats = {"total": len(csv_files), "loaded": 0, "errors": 0}

        for csv_file in csv_files:
            fund_name, eom_date, positions = self.ingest_csv_file(csv_file)

            if fund_name and eom_date and positions:
                try:
                    self.insert_positions(fund_name, eom_date, positions)
                    stats["loaded"] += 1
                except Exception as e:
                    print(f"Failed to load {csv_file.name}: {e}")
                    stats["errors"] += 1
            else:
                stats["errors"] += 1

        return stats

    @staticmethod
    def _parse_float(value: str) -> float:
        """Safely parse string to float."""
        if not value or value.strip() == '':
            return None
        try:
            return float(value)
        except ValueError:
            return None
