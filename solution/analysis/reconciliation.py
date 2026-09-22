import csv
from pathlib import Path
from typing import Dict

class PriceReconciliation:
    def __init__(self, db_instance):
        self.db = db_instance

    @staticmethod
    def _get_reference_prices_cte() -> str:
        """
        Returns the CTE for reference price lookup with forward-fill logic.
        Used by both reconciliation and stats queries.
        """
        return """
        WITH ref_prices AS (
            SELECT
                fp.id,
                fp.symbol,
                fp.eom_date,
                COALESCE(
                    (SELECT ep.PRICE
                     FROM equity_prices ep
                     WHERE ep.SYMBOL = fp.symbol
                     AND ep.DATETIME <= fp.eom_date
                     ORDER BY ep.DATETIME DESC LIMIT 1),
                    (SELECT bp.PRICE
                     FROM bond_prices bp
                     WHERE bp.ISIN = fp.symbol
                     AND bp.DATETIME <= fp.eom_date
                     ORDER BY bp.DATETIME DESC LIMIT 1)
                ) as reference_price
            FROM fund_positions fp
        )
        """

    def generate_reconciliation_report(self, output_file: str = "output/price_reconciliation_report.csv") -> Dict:
        """
        Generate price reconciliation analysis using pure SQL.
        Compares fund prices vs reference prices with forward-fill logic for missing dates.
        """
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        cte = self._get_reference_prices_cte()

        # Get reconciliation data
        reconciliation_query = cte + """
        SELECT
            fp.fund_name,
            fp.eom_date,
            fp.financial_type as instrument_type,
            fp.symbol,
            fp.security_name,
            fp.price as fund_price,
            rp.reference_price,
            ROUND(fp.price - rp.reference_price, 4) as price_difference,
            ROUND((fp.price - rp.reference_price) / rp.reference_price * 100, 4) as price_difference_pct,
            fp.quantity,
            fp.market_value,
            CASE WHEN rp.reference_price IS NOT NULL THEN 'Yes' ELSE 'No' END as reference_available
        FROM fund_positions fp
        LEFT JOIN ref_prices rp ON fp.id = rp.id
        WHERE fp.symbol IS NOT NULL
        ORDER BY fp.eom_date, fp.fund_name, fp.symbol
        """

        results = self.db.fetch_all(reconciliation_query)

        # Write directly to CSV (convert sqlite3.Row to dict)
        if results:
            # Convert sqlite3.Row objects to regular dicts
            rows_as_dicts = [dict(row) for row in results]
            fieldnames = list(rows_as_dicts[0].keys())
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows_as_dicts)

        return {
            "output_file": output_file,
            "rows": len(results)
        }
