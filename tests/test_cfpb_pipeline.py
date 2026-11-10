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
from src.generate_report import build_trend_chart_data


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
        self.assertEqual(
            candidates.loc[candidates["issue"] == "Issue A", "baseline_months"].iloc[0],
            "2021-01, 2022-01, 2023-01",
        )
        self.assertTrue(
            candidates["interpretation"].str.contains("not a verified incident").all()
        )

    def test_candidate_baseline_lists_observed_months_without_zero_filling(self):
        rows = [
            {
                "complaint_month": month,
                "issue": "Issue A",
                "complaint_count": count,
                "monthly_denominator": 1_000,
                "complaint_share": count / 1_000,
            }
            for month, count in (
                ("2021-01", 100),
                ("2023-01", 120),
                ("2024-01", 80),
                ("2025-01", 500),
            )
        ]
        candidates = find_emerging_issue_candidates(pd.DataFrame(rows), "2025-01")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates.iloc[0]["baseline_months"], "2021-01, 2023-01, 2024-01")

    def test_report_chart_excludes_later_incomplete_month(self):
        trends = pd.DataFrame(
            [
                {
                    "complaint_month": month,
                    "issue": "Issue A",
                    "complaint_count": count,
                    "monthly_denominator": 100,
                    "complaint_share": count / 100,
                }
                for month, count in (("2026-08", 10), ("2026-09", 20), ("2026-10", 90))
            ]
        )
        _, chart_data = build_trend_chart_data(trends, "2026-09")
        self.assertEqual(chart_data["complaint_month"].astype(str).max(), "2026-09")
        self.assertNotIn("2026-10", chart_data["complaint_month"].astype(str).tolist())


if __name__ == "__main__":
    unittest.main()
