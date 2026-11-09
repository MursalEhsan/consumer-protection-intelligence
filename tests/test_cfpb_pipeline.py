import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.cfpb_pipeline import (
    SAMPLE_LIMIT,
    build_sqlite_warehouse,
    find_emerging_issue_candidates,
    latest_mature_month,
    load_source_sample,
)


class CFPBSourcePipelineTests(unittest.TestCase):
    def test_sample_limit_rejects_values_above_cap(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            load_source_sample(max_sample_rows=SAMPLE_LIMIT + 1)

    def test_latest_mature_month_excludes_unmatured_month(self):
        month, cutoff = latest_mature_month(
            {
                "latest_complaint_date": "2026-11-08",
                "retrieval_timestamp_utc": "2026-11-09T02:00:00+00:00",
            }
        )
        self.assertEqual(str(month), "2026-09")
        self.assertEqual(cutoff.strftime("%Y-%m-%d"), "2026-10-25")

    def test_sql_trend_view_uses_full_source_denominators(self):
        sample = pd.DataFrame(
            {
                "Date received": pd.to_datetime(["2024-01-03", "2024-01-04"]),
                "Product": ["Credit card", "Mortgage"],
                "Sub-product": ["Card", "Home loan"],
                "Issue": ["Fees", "Late payment"],
                "Submitted via": ["Web", "Phone"],
            }
        )
        metadata = {
            "monthly_issue_counts": [
                {"month": "2024-01", "issue": "Fees", "count": 25},
                {"month": "2024-01", "issue": "Late payment", "count": 75},
            ],
            "monthly_row_counts": {"2024-01": 100},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            connection = build_sqlite_warehouse(
                sample,
                metadata,
                database_path=Path(temp_dir) / "test.db",
            )
            result = connection.execute(
                """
                SELECT issue, complaint_count, monthly_denominator, complaint_share
                FROM vw_monthly_issue_trends
                WHERE issue = 'Fees'
                """
            ).fetchone()
            connection.close()
        self.assertEqual(result[:3], ("Fees", 25, 100))
        self.assertAlmostEqual(result[3], 0.25)

    def test_anomaly_candidates_compare_same_calendar_month(self):
        rows = []
        for year in (2021, 2022, 2023):
            rows.extend(
                {
                    "complaint_month": f"{year}-01",
                    "issue": issue,
                    "complaint_count": count,
                    "monthly_denominator": 100,
                    "complaint_share": count / 100,
                }
                for issue, count in (("Issue A", 10), ("Other", 90))
            )
        rows.extend(
            {
                "complaint_month": f"2024-01",
                "issue": issue,
                "complaint_count": count,
                "monthly_denominator": 100,
                "complaint_share": count / 100,
            }
            for issue, count in (("Issue A", 60), ("Other", 40))
        )
        candidates = find_emerging_issue_candidates(pd.DataFrame(rows), "2024-01")
        self.assertIn("Issue A", candidates["issue"].tolist())
        self.assertTrue(
            candidates["interpretation"].str.contains("not a verified incident").all()
        )


if __name__ == "__main__":
    unittest.main()
