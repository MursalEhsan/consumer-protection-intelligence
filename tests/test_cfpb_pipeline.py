import sqlite3
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
    screen_issue_month,
)
from src.generate_report import (
    build_featured_issue_series,
    build_trend_chart_data,
    query_year_over_year_comparison,
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

    def test_featured_issue_series_keeps_missing_months_as_gaps_and_excludes_incomplete(self):
        trends = pd.DataFrame(
            [
                {"complaint_month": month, "issue": "Issue A", "complaint_share": share}
                for month, share in (
                    ("2025-08", 0.4),
                    ("2025-10", 0.5),
                    ("2026-09", 0.6),
                    ("2026-10", 0.9),
                )
            ]
        )
        series = build_featured_issue_series(trends, "Issue A", "2026-09")
        observed = series.set_index(series["complaint_month"].astype(str))
        self.assertTrue(pd.isna(observed.loc["2025-09", "complaint_share"]))
        self.assertEqual(series["complaint_month"].astype(str).max(), "2026-09")
        self.assertNotIn("2026-10", series["complaint_month"].astype(str).tolist())

    def test_year_over_year_comparison_calculates_shares_and_percentage_points(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "comparison.db"
            with sqlite3.connect(database_path) as connection:
                connection.executescript(
                    """
                    CREATE TABLE source_monthly_issue_counts (
                        month TEXT, issue TEXT, count INTEGER
                    );
                    CREATE TABLE source_monthly_totals (
                        month TEXT, complaint_count INTEGER
                    );
                    INSERT INTO source_monthly_issue_counts VALUES
                        ('2026-09', 'Issue A', 371428),
                        ('2025-09', 'Issue A', 267731);
                    INSERT INTO source_monthly_totals VALUES
                        ('2026-09', 660839),
                        ('2025-09', 503847);
                    """
                )
            result = query_year_over_year_comparison(
                database_path, "Issue A", "2026-09"
            )
        self.assertEqual(result["current_issue_count"], 371428)
        self.assertEqual(result["prior_year_issue_count"], 267731)
        self.assertAlmostEqual(result["current_issue_share"], 371428 / 660839)
        self.assertAlmostEqual(result["prior_year_issue_share"], 267731 / 503847)
        self.assertAlmostEqual(
            result["share_change_percentage_points"],
            100 * ((371428 / 660839) - (267731 / 503847)),
        )

    def test_year_over_year_comparison_surfaces_missing_prior_month(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "comparison.db"
            with sqlite3.connect(database_path) as connection:
                connection.executescript(
                    """
                    CREATE TABLE source_monthly_issue_counts (
                        month TEXT, issue TEXT, count INTEGER
                    );
                    CREATE TABLE source_monthly_totals (
                        month TEXT, complaint_count INTEGER
                    );
                    INSERT INTO source_monthly_issue_counts VALUES
                        ('2024-07', 'Issue A', 10);
                    INSERT INTO source_monthly_totals VALUES ('2024-07', 100);
                    """
                )
            result = query_year_over_year_comparison(
                database_path, "Issue A", "2024-07"
            )
        self.assertEqual(result["prior_year_month"], "2023-07")
        self.assertIsNone(result["prior_year_issue_count"])
        self.assertIsNone(result["prior_year_total_complaints"])
        self.assertIsNone(result["prior_year_issue_share"])
        self.assertIsNone(result["share_change_percentage_points"])

    def test_screen_reports_observed_eligible_and_flagged_issue_counts(self):
        rows = []
        for issue, historical_counts, current_count in (
            ("Eligible", (100, 120, 80), 600),
            ("Below minimum", (100, 100, 100), 49),
            ("Insufficient history", (100, 100), 80),
        ):
            historical_years = (2021, 2022, 2023)[-len(historical_counts):]
            rows.extend(
                {
                    "complaint_month": f"{year}-01",
                    "issue": issue,
                    "complaint_count": count,
                    "monthly_denominator": 1_000,
                    "complaint_share": count / 1_000,
                }
                for year, count in zip(historical_years, historical_counts)
            )
            rows.append(
                {
                    "complaint_month": "2024-01",
                    "issue": issue,
                    "complaint_count": current_count,
                    "monthly_denominator": 1_000,
                    "complaint_share": current_count / 1_000,
                }
            )
        rows.append(
            {
                "complaint_month": "2024-02",
                "issue": "Later incomplete month",
                "complaint_count": 900,
                "monthly_denominator": 1_000,
                "complaint_share": 0.9,
            }
        )
        candidates, counts = screen_issue_month(pd.DataFrame(rows), "2024-01")
        self.assertEqual(
            counts,
            {
                "observed_issue_labels": 3,
                "eligible_issue_labels": 1,
                "flagged_issue_labels": 1,
            },
        )
        self.assertEqual(candidates["issue"].tolist(), ["Eligible"])


if __name__ == "__main__":
    unittest.main()
