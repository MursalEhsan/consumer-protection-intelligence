import unittest

import pandas as pd

from src.cfpb_source_assessment import summarize_source


class CFPBSourceAssessmentTests(unittest.TestCase):
    def test_summary_handles_missing_narratives(self):
        df = pd.DataFrame(
            {
                "Date received": ["2024-01-01", "2024-01-02"],
                "Product": ["Credit card", "Mortgage"],
                "Issue": ["Fees", "Late payment"],
                "Company": ["Bank A", "Bank B"],
            }
        )
        report = summarize_source(df)
        self.assertFalse(report["narrative_availability"]["public_bulk_export_has_narrative_text"])
        self.assertIsNone(report["dataset_summary"]["latest_usable_narrative_date"])
        self.assertEqual(report["dataset_summary"]["latest_complaint_date"], "2024-01-02")
        self.assertIn("Empirical modeling is incomplete", report["modeling_status"])
        self.assertFalse(report["structured_issue_classifier"]["trained"])

    def test_summary_reports_full_archive_missingness_when_provided(self):
        df = pd.DataFrame(
            {
                "Date received": [None, "2024-01-05", "2024-01-06"],
                "Product": ["Auto loan", "Auto loan", None],
                "Issue": ["Fraud", None, "Late fee"],
                "Company": ["Lender 1", "Lender 2", "Lender 3"],
            }
        )
        report = summarize_source(
            df,
            {
                "source_rows_scanned": 10,
                "missing_values_by_field": {
                    "Date received": 1,
                    "Product": 2,
                    "Issue": 3,
                    "Company": 0,
                },
            },
        )
        summary = report["dataset_summary"]
        self.assertEqual(summary["row_count"], 10)
        self.assertEqual(summary["sample_row_count"], 3)
        self.assertEqual(summary["missingness_rate_by_field"]["Product"], 0.2)


if __name__ == "__main__":
    unittest.main()
