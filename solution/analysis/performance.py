import csv
from pathlib import Path
from typing import Dict

class FundPerformance:
    def __init__(self, db_instance):
        self.db = db_instance

    def generate_performance_report(self, output_file: str = "output/fund_performance_report.csv") -> Dict:
        """
        Generate fund performance analysis using pure SQL.
        Shows best performing fund per month with rate of return calculations.
        """
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        # Pure SQL query using LAG for month-over-month comparison
        query = """
        WITH monthly_metrics AS (
            SELECT
                fund_name,
                eom_date,
                SUM(market_value) as total_market_value,
                SUM(realised_pl) as total_realised_pl,
                LAG(SUM(market_value)) OVER (PARTITION BY fund_name ORDER BY eom_date) as prev_month_market_value
            FROM fund_positions
            GROUP BY fund_name, eom_date
        ),
        performance_metrics AS (
            SELECT
                eom_date,
                fund_name,
                prev_month_market_value as start_market_value,
                total_market_value as end_market_value,
                total_realised_pl as realised_pl,
                CASE
                    WHEN prev_month_market_value IS NOT NULL AND prev_month_market_value != 0
                    THEN (total_market_value - prev_month_market_value + total_realised_pl) / prev_month_market_value
                    ELSE NULL
                END as rate_of_return
            FROM monthly_metrics
        ),
        performance_ranking AS (
            SELECT *, 
                RANK() OVER (PARTITION BY eom_date ORDER BY rate_of_return DESC) as performance_rank
            FROM performance_metrics
            )
        SELECT
            eom_date,
            fund_name,
            ROUND(start_market_value, 2) as start_market_value,
            ROUND(end_market_value, 2) as end_market_value,
            ROUND(realised_pl, 2) as realised_pl,
            ROUND(rate_of_return, 6) as rate_of_return,
            ROUND(rate_of_return * 100, 2) as rate_of_return_pct,
            CASE WHEN performance_rank = 1 THEN 1 ELSE 0 END as is_best_performer
        FROM performance_ranking
        WHERE rate_of_return IS NOT NULL
        ORDER BY eom_date, performance_rank
        """

        results = self.db.fetch_all(query)

        # Calculate stats from results
        stats = {
            "total_months": len(set(row["eom_date"] for row in results)),
            "best_performers": sum(1 for row in results if row["is_best_performer"])
        }

        # Convert sqlite3.Row to dict and write directly to CSV
        if results:
            rows_as_dicts = [dict(row) for row in results]
            fieldnames = list(rows_as_dicts[0].keys())
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows_as_dicts)

        return {
            "output_file": output_file,
            "stats": stats,
            "rows": len(results)
        }
