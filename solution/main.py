"""
Main execution script for fund analysis pipeline.
Orchestrates database setup, data ingestion, and report generation.
"""

import sys
import traceback
from pathlib import Path
from data_layer import Database, DataIngestion
from analysis import PriceReconciliation, FundPerformance


class FundAnalysisPipeline:
    def __init__(self, db_path: str = "funds_analysis.db"):
        self.db_path = db_path
        self.db = None
        self.ingest_stats = None
        self.recon_result = None
        self.perf_result = None

    def _setup_database(self) -> bool:
        print("\n[1/5] Initializing database...")
        self.db = Database(self.db_path)
        self.db.connect()

        try:
            print("[2/5] Loading reference data from master-reference-sql.sql...")
            sql_file = Path("../master-reference-sql.sql")
            if not sql_file.exists():
                sql_file = Path("master-reference-sql.sql")

            if not sql_file.exists():
                print(f"Error: SQL file not found at {sql_file}")
                return False

            self.db.setup_from_sql(str(sql_file))
            print("Reference data loaded successfully")

            # Must run before create_indexes() so the index is built once,
            # over final values, rather than churning on every rewrite.
            normalized = self.db.normalize_reference_dates()
            print(f"Normalized {normalized} equity price dates to ISO format")

            print("[3/5] Creating fund positions table and indexes...")
            self.db.create_fund_positions_table()
            self.db.create_indexes()
            print("Fund positions table and indexes created")

            return True
        except Exception as e:
            print(f"Error setting up database: {e}")
            return False

    def _ingest_data(self) -> bool:
        print("[4/5] Ingesting fund position data...")
        try:
            ingest = DataIngestion(self.db)
            self.ingest_stats = ingest.load_all_funds()

            print(f"  Total files: {self.ingest_stats['total']}")
            print(f"  Successfully loaded: {self.ingest_stats['loaded']}")
            print(f"  Errors: {self.ingest_stats['errors']}")

            if self.ingest_stats['loaded'] == 0:
                print("No fund data loaded")
                return False

            print("Fund data ingestion complete")
            return True
        except Exception as e:
            print(f"Error ingesting data: {e}")
            return False

    def _generate_reports(self) -> bool:
        print("[5/5] Generating analysis reports...")
        try:
            Path("output").mkdir(exist_ok=True)

            print("Generating price reconciliation report...")
            reconciliation = PriceReconciliation(self.db)
            self.recon_result = reconciliation.generate_reconciliation_report()
            print(f"    - {self.recon_result['rows']} positions analyzed")
            print(f"    - Output: {self.recon_result['output_file']}")

            print("Generating fund performance report...")
            performance = FundPerformance(self.db)
            self.perf_result = performance.generate_performance_report()
            print(f"    - {self.perf_result['stats']['total_months']} months analyzed")
            print(f"    - {self.perf_result['stats']['best_performers']} best performers identified")
            print(f"    - Output: {self.perf_result['output_file']}")

            return True
        except Exception as e:
            print(f"Error generating reports: {e}")
            return False

    def _print_summary(self) -> None:
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        print(f"\nGenerated reports:")
        print(f"  1. Price Reconciliation: {self.recon_result['output_file']}")
        print(f"  2. Fund Performance: {self.perf_result['output_file']}")
        print("\n")

    def run(self) -> bool:
        try:
            if not self._setup_database():
                return False

            if not self._ingest_data():
                return False

            if not self._generate_reports():
                return False

            self._print_summary()
            return True

        except Exception as e:
            print(f"\nPipeline failed: {e}")
            traceback.print_exc()
            return False

        finally:
            if self.db:
                self.db.disconnect()


if __name__ == "__main__":
    pipeline = FundAnalysisPipeline()
    success = pipeline.run()
    sys.exit(0 if success else 1)
